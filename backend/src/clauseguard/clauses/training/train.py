"""Train TF-IDF + LogisticRegression models for clause classification.

Builds multi-label classification pipeline for the 36 CUAD contractual labels:
- Word n-grams (1-2) and character n-grams (3-5) via FeatureUnion.
- Balanced LogisticRegression per label.
- Decision threshold tuning strictly on the VAL split.
- Exports production artifacts to backend/models/clauses/v1/.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion

from clauseguard.clauses.rules import classify_clause_rules
from clauseguard.clauses.taxonomy import ALL_LABELS, CORE_CUAD_LABELS, EXTRA_RULE_LABELS, LABEL_MAP
from clauseguard.clauses.training.cuad_data import (
    LabeledClause,
    load_cuad_raw,
    load_dataset_by_split,
)
from clauseguard.clauses.training.evaluate import evaluate_predictions
from clauseguard.clauses.training.split import partition_contracts

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "backend" / "models" / "clauses" / "v1"


def build_feature_extractor() -> FeatureUnion:
    """Build union of word (1-2) and char (3-5) TF-IDF vectorizers."""
    return FeatureUnion([
        (
            "word",
            TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=25000,
                min_df=2,
                sublinear_tf=True,
                token_pattern=r"(?u)\b\w+\b",
            ),
        ),
        (
            "char",
            TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                max_features=25000,
                min_df=3,
                sublinear_tf=True,
            ),
        ),
    ])


class MultiLabelClauseModel:
    """Multi-label classifier holding vectorizer, binary classifiers, and thresholds."""

    def __init__(
        self,
        vectorizer: FeatureUnion,
        classifiers: dict[str, LogisticRegression],
        thresholds: dict[str, float],
    ) -> None:
        self.vectorizer = vectorizer
        self.classifiers = classifiers
        self.thresholds = thresholds

    def predict_proba(self, texts: list[str]) -> dict[str, np.ndarray]:
        """Predict probabilities for each label given a list of raw text clauses."""
        X = self.vectorizer.transform(texts)
        probs: dict[str, np.ndarray] = {}
        for label, clf in self.classifiers.items():
            if hasattr(clf, "predict_proba"):
                probs[label] = clf.predict_proba(X)[:, 1]
            else:
                probs[label] = np.zeros(len(texts), dtype=float)
        return probs

    def predict_labels(
        self,
        texts: list[str],
        hybrid_with_rules: bool = True,
        headings: list[str] | None = None,
    ) -> list[set[str]]:
        """Predict sets of positive labels per text."""
        probs = self.predict_proba(texts)
        num_samples = len(texts)
        results: list[set[str]] = [set() for _ in range(num_samples)]

        # Model predictions
        for label, p_arr in probs.items():
            thresh = self.thresholds.get(label, 0.50)
            for i in range(num_samples):
                if p_arr[i] >= thresh:
                    results[i].add(label)

        # Rules hybrid
        if hybrid_with_rules:
            for i in range(num_samples):
                heading = headings[i] if headings else ""
                r_matches = classify_clause_rules(texts[i], heading=heading)
                for rm in r_matches:
                    results[i].add(rm["label"])

        return results


def find_best_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    candidates: list[float] | None = None,
    target_min_precision: float = 0.50,
) -> tuple[float, float, float, float]:
    """Find threshold that maximizes F1 while respecting minimum precision if feasible."""
    if candidates is None:
        candidates = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]

    best_thresh = 0.50
    best_f1 = -1.0
    best_p = 0.0
    best_r = 0.0

    n_pos = np.sum(y_true)
    if n_pos == 0:
        return (0.50, 0.0, 0.0, 0.0)

    for t in candidates:
        pred = (y_prob >= t).astype(int)
        tp = int(np.sum((y_true == 1) & (pred == 1)))
        fp = int(np.sum((y_true == 0) & (pred == 1)))
        fn = int(np.sum((y_true == 1) & (pred == 0)))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        # Prioritize thresholds with acceptable precision
        if prec >= target_min_precision and f1 > best_f1:
            best_f1 = f1
            best_thresh = t
            best_p = prec
            best_r = rec

    # If no threshold met min precision, pick threshold maximizing F1 overall
    if best_f1 < 0:
        for t in candidates:
            pred = (y_prob >= t).astype(int)
            tp = int(np.sum((y_true == 1) & (pred == 1)))
            fp = int(np.sum((y_true == 0) & (pred == 1)))
            fn = int(np.sum((y_true == 1) & (pred == 0)))

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

            if f1 > best_f1:
                best_f1 = f1
                best_thresh = t
                best_p = prec
                best_r = rec

    return (best_thresh, best_p, best_r, max(0.0, best_f1))


def train_and_tune_model(
    train_clauses: list[LabeledClause],
    val_clauses: list[LabeledClause],
) -> tuple[MultiLabelClauseModel, dict[str, Any]]:
    """Train vectorizer, logistic regression classifiers, and tune thresholds on VAL only."""
    logger.info("Extracting features on %d training clauses...", len(train_clauses))
    train_texts = [f"{c.heading}\n{c.text}" if c.heading else c.text for c in train_clauses]
    val_texts = [f"{c.heading}\n{c.text}" if c.heading else c.text for c in val_clauses]

    vectorizer = build_feature_extractor()
    X_train = vectorizer.fit_transform(train_texts)
    X_val = vectorizer.transform(val_texts)

    classifiers: dict[str, LogisticRegression] = {}
    thresholds: dict[str, float] = {}
    tuning_stats: dict[str, dict[str, float]] = {}

    for label in CORE_CUAD_LABELS:
        y_train = np.array([1 if label in c.labels else 0 for c in train_clauses], dtype=int)
        y_val = np.array([1 if label in c.labels else 0 for c in val_clauses], dtype=int)

        n_pos_train = int(np.sum(y_train))
        n_pos_val = int(np.sum(y_val))

        if n_pos_train < 3:
            logger.warning("Label %s has only %d positive samples in train; skipping ML training.", label, n_pos_train)
            thresholds[label] = 0.50
            continue

        clf = LogisticRegression(
            class_weight="balanced",
            C=1.0,
            max_iter=1000,
            solver="lbfgs",
            random_state=42,
        )
        clf.fit(X_train, y_train)
        classifiers[label] = clf

        val_probs = clf.predict_proba(X_val)[:, 1]
        best_t, p, r, f1 = find_best_threshold(y_val, val_probs)
        thresholds[label] = best_t
        tuning_stats[label] = {
            "threshold": best_t,
            "train_pos": n_pos_train,
            "val_pos": n_pos_val,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
        }

    model = MultiLabelClauseModel(
        vectorizer=vectorizer,
        classifiers=classifiers,
        thresholds=thresholds,
    )

    return model, tuning_stats


def save_artifacts(
    model: MultiLabelClauseModel,
    tuning_stats: dict[str, Any],
    val_report: dict[str, Any],
    train_count: int,
    val_count: int,
    output_dir: Path = ARTIFACTS_DIR,
) -> None:
    """Save all model artifacts to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. model.joblib
    model_bundle = {
        "vectorizer": model.vectorizer,
        "classifiers": model.classifiers,
        "thresholds": model.thresholds,
        "scikit_learn_version": "1.8.0",
    }
    joblib.dump(model_bundle, output_dir / "model.joblib", compress=3)
    logger.info("Saved model bundle to %s", output_dir / "model.joblib")

    # 2. taxonomy.json
    taxonomy_data = {
        "version": "1.0",
        "total_labels": len(ALL_LABELS),
        "core_cuad_labels": list(CORE_CUAD_LABELS),
        "extra_rule_labels": list(EXTRA_RULE_LABELS),
        "labels": {k: v.to_dict() for k, v in LABEL_MAP.items()},
    }
    with open(output_dir / "taxonomy.json", "w", encoding="utf-8") as f:
        json.dump(taxonomy_data, f, indent=2)

    # 3. thresholds.json
    with open(output_dir / "thresholds.json", "w", encoding="utf-8") as f:
        json.dump(model.thresholds, f, indent=2)

    # 4. metrics.json (Val metrics)
    with open(output_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(val_report, f, indent=2)

    # 5. training_config.json
    config_data = {
        "created_at": datetime.now(UTC).isoformat(),
        "train_clauses_count": train_count,
        "val_clauses_count": val_count,
        "ngram_words": [1, 2],
        "ngram_chars": [3, 5],
        "classifier": "LogisticRegression(class_weight='balanced', C=1.0)",
        "tuning_stats": tuning_stats,
    }
    with open(output_dir / "training_config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    logger.info("Saved all training artifacts to %s", output_dir)


def run_pipeline() -> None:
    """Execute end-to-end training and evaluation pipeline on Train and Val."""
    raw_contracts = load_cuad_raw()
    titles = [c["title"] for c in raw_contracts]
    split = partition_contracts(titles, seed=42)

    # Load Train and Val (Test split is strictly ignored during development)
    train_clauses, val_clauses, _ = load_dataset_by_split(split)

    model, tuning_stats = train_and_tune_model(train_clauses, val_clauses)

    # Evaluate Hybrid (Model + Rules) on VAL
    val_texts = [c.text for c in val_clauses]
    val_headings = [c.heading for c in val_clauses]
    val_y_true = [c.labels for c in val_clauses]

    val_y_pred = model.predict_labels(
        val_texts,
        hybrid_with_rules=True,
        headings=val_headings,
    )

    report = evaluate_predictions(val_y_true, val_y_pred, split_name="val_hybrid")

    logger.info("=== VAL HYBRID EVALUATION RESULTS ===")
    logger.info("Micro P: %.4f, Micro R: %.4f, Micro F1: %.4f", report.micro_precision, report.micro_recall, report.micro_f1)
    logger.info("Macro P: %.4f, Macro R: %.4f, Macro F1: %.4f", report.macro_precision, report.macro_recall, report.macro_f1)

    save_artifacts(
        model=model,
        tuning_stats=tuning_stats,
        val_report=report.to_dict(),
        train_count=len(train_clauses),
        val_count=len(val_clauses),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_pipeline()
