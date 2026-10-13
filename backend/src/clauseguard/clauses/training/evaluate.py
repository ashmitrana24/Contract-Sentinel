"""Evaluation harness for clause classification.

Computes precision, recall, F1, support, and Wilson score 95% confidence intervals
per label and across micro/macro averages.
Designed for honest benchmarking against CUAD expert labels.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from clauseguard.clauses.taxonomy import CORE_CUAD_LABELS


def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calculate the Wilson score confidence interval for a proportion k/n."""
    if n <= 0:
        return (0.0, 0.0)

    # z=1.96 for 95% CI
    z = 1.959963984540054
    p_hat = k / n

    denom = 1.0 + (z**2) / n
    center = (p_hat + (z**2) / (2 * n)) / denom
    variance_term = (p_hat * (1 - p_hat) / n) + ((z**2) / (4 * (n**2)))
    spread = (z * math.sqrt(max(0.0, variance_term))) / denom

    low = max(0.0, center - spread)
    high = min(1.0, center + spread)
    return (round(low, 4), round(high, 4))


@dataclass
class LabelMetrics:
    """Metrics for a single clause label."""

    label: str
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
    f1: float
    support: int  # tp + fn
    predicted_count: int  # tp + fp
    precision_ci_95: tuple[float, float]
    recall_ci_95: tuple[float, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    """Full evaluation report across multiple labels."""

    split_name: str
    num_samples: int
    labels: dict[str, LabelMetrics]
    macro_precision: float
    macro_recall: float
    macro_f1: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    total_tp: int
    total_fp: int
    total_fn: int

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["labels"] = {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in self.labels.items()}
        return d


def evaluate_predictions(
    y_true: list[set[str]],
    y_pred: list[set[str]],
    eval_labels: tuple[str, ...] | list[str] = CORE_CUAD_LABELS,
    split_name: str = "val",
) -> EvaluationReport:
    """Evaluate predictions against ground truth labels."""
    assert len(y_true) == len(y_pred), f"Mismatched lengths: {len(y_true)} vs {len(y_pred)}"
    n_samples = len(y_true)

    label_metrics_map: dict[str, LabelMetrics] = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0

    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []

    for label in eval_labels:
        tp = 0
        fp = 0
        fn = 0
        tn = 0

        for true_set, pred_set in zip(y_true, y_pred, strict=False):
            is_true = label in true_set
            is_pred = label in pred_set

            if is_true and is_pred:
                tp += 1
            elif not is_true and is_pred:
                fp += 1
            elif is_true and not is_pred:
                fn += 1
            else:
                tn += 1

        total_tp += tp
        total_fp += fp
        total_fn += fn

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        p_ci = wilson_score_interval(tp, tp + fp)
        r_ci = wilson_score_interval(tp, tp + fn)

        metrics = LabelMetrics(
            label=label,
            tp=tp,
            fp=fp,
            fn=fn,
            tn=tn,
            precision=round(prec, 4),
            recall=round(rec, 4),
            f1=round(f1, 4),
            support=tp + fn,
            predicted_count=tp + fp,
            precision_ci_95=p_ci,
            recall_ci_95=r_ci,
        )
        label_metrics_map[label] = metrics

        # For macro averaging, only include labels that have support > 0
        if (tp + fn) > 0:
            precisions.append(prec)
            recalls.append(rec)
            f1s.append(f1)

    macro_p = (sum(precisions) / len(precisions)) if precisions else 0.0
    macro_r = (sum(recalls) / len(recalls)) if recalls else 0.0
    macro_f = (sum(f1s) / len(f1s)) if f1s else 0.0

    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f = (2 * micro_p * micro_r / (micro_p + micro_r)) if (micro_p + micro_r) > 0 else 0.0

    return EvaluationReport(
        split_name=split_name,
        num_samples=n_samples,
        labels=label_metrics_map,
        macro_precision=round(macro_p, 4),
        macro_recall=round(macro_r, 4),
        macro_f1=round(macro_f, 4),
        micro_precision=round(micro_p, 4),
        micro_recall=round(micro_r, 4),
        micro_f1=round(micro_f, 4),
        total_tp=total_tp,
        total_fp=total_fp,
        total_fn=total_fn,
    )
