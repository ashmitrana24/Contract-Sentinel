"""Runtime inference model for clause classification.

Loads trained TF-IDF + LogisticRegression bundle with fallback to rules-only mode
if model artifacts are absent or incompatible. Handles long clause windowing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib

from clauseguard.clauses.rules import classify_clause_rules
from clauseguard.clauses.windows import (
    aggregate_window_predictions,
    split_clause_into_windows,
    truncate_evidence,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models" / "clauses" / "v1"


class ClauseClassifier:
    """Runtime clause classifier supporting hybrid (model + rules) or rules-only inference."""

    def __init__(self, model_dir: Path | str | None = None) -> None:
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        self.vectorizer = None
        self.classifiers: dict[str, Any] = {}
        self.thresholds: dict[str, float] = {}
        self.high_precision_thresholds: dict[str, float] = {}
        self.shipped_methods: dict[str, str] = {}
        self.is_model_loaded = False

        self._load_model_artifacts()

    def _load_model_artifacts(self) -> None:
        """Attempt to load trained artifacts from disk."""
        model_path = self.model_dir / "model.joblib"
        thresh_path = self.model_dir / "thresholds.json"

        if not model_path.exists():
            logger.warning(
                "Clause classification model not found at %s. Running in rules-only fallback mode.",
                model_path,
            )
            return

        try:
            bundle = joblib.load(model_path)
            self.vectorizer = bundle.get("vectorizer")
            self.classifiers = bundle.get("classifiers", {})
            self.thresholds = bundle.get("thresholds", {})

            if thresh_path.exists():
                with open(thresh_path, encoding="utf-8") as f:
                    t_data = json.load(f)
                    if isinstance(t_data, dict) and "thresholds" in t_data:
                        self.thresholds = t_data["thresholds"]
                        self.high_precision_thresholds = t_data.get("high_precision_thresholds", {})
                        self.shipped_methods = t_data.get("shipped_methods", {})
                    else:
                        self.thresholds = t_data
                        self.high_precision_thresholds = {}
                        self.shipped_methods = {}
            else:
                self.shipped_methods = {}

            if self.vectorizer is not None and self.classifiers:
                self.is_model_loaded = True
                logger.info("Successfully loaded ML clause classifier with %d labels.", len(self.classifiers))
            else:
                logger.warning("Invalid model bundle format. Falling back to rules-only mode.")
        except Exception as e:
            logger.warning("Failed to load ML clause model (%s). Falling back to rules-only mode.", e)
            self.is_model_loaded = False
            self.shipped_methods = {}

    def classify_window(self, text: str, heading: str = "") -> list[dict[str, Any]]:
        """Classify a single text window using hybrid rules + model."""
        combined_text = f"{heading}\n{text}" if heading else text

        # 1. Deterministic rules
        rule_matches = classify_clause_rules(text, heading=heading)
        if self.shipped_methods:
            rule_matches = [m for m in rule_matches if self.shipped_methods.get(m["label"], "rules") != "model"]
        matches_by_label: dict[str, dict[str, Any]] = {m["label"]: m for m in rule_matches}

        # 2. ML model predictions if loaded
        if self.is_model_loaded and self.vectorizer is not None:
            try:
                X = self.vectorizer.transform([combined_text])
                for label, clf in self.classifiers.items():
                    # If label is shipped as rules-only, skip model prediction
                    if self.shipped_methods and self.shipped_methods.get(label, "rules") == "rules":
                        continue

                    thresh = self.thresholds.get(label, 0.50)
                    if hasattr(clf, "predict_proba"):
                        prob = float(clf.predict_proba(X)[0, 1])
                    else:
                        continue

                    if prob >= thresh:
                        if label in matches_by_label:
                            existing = matches_by_label[label]
                            existing["method"] = "both"
                            existing["score"] = max(existing["score"], round(prob, 4))
                        else:
                            # Model-only label: enforce minimum output score of 0.50
                            if prob >= 0.50:
                                matches_by_label[label] = {
                                    "label": label,
                                    "score": round(prob, 4),
                                    "method": "model",
                                    "evidence": truncate_evidence(text, 300),
                                }
            except Exception as e:
                logger.warning("Error running ML prediction on clause window: %s", e)

        results = list(matches_by_label.values())
        results.sort(key=lambda x: (-x["score"], x["label"]))
        return results

    def classify_clause(self, text: str, heading: str = "") -> list[dict[str, Any]]:
        """Classify a clause with automatic windowing for long texts (>250 words)."""
        # Fall back to heading if body text is empty/whitespace
        effective_text = text if text and text.strip() else heading
        effective_heading = heading if text and text.strip() else ""
        windows = split_clause_into_windows(effective_text, max_words_threshold=250, window_size=120, stride=100)
        if not windows:
            return []

        if len(windows) == 1:
            return self.classify_window(windows[0].text, heading=effective_heading)

        window_predictions: list[list[dict[str, Any]]] = []
        for w in windows:
            w_preds = self.classify_window(w.text, heading=effective_heading)
            window_predictions.append(w_preds)

        return aggregate_window_predictions(window_predictions, max_evidence_chars=300)


# Global singleton instance
_GLOBAL_CLASSIFIER: ClauseClassifier | None = None


def get_clause_classifier() -> ClauseClassifier:
    """Retrieve global ClauseClassifier instance."""
    global _GLOBAL_CLASSIFIER
    if _GLOBAL_CLASSIFIER is None:
        _GLOBAL_CLASSIFIER = ClauseClassifier()
    return _GLOBAL_CLASSIFIER


def classify_clause(text: str, heading: str = "") -> list[dict[str, Any]]:
    """Convenience helper to classify a clause with default global classifier."""
    return get_clause_classifier().classify_clause(text, heading=heading)
