"""Comprehensive investigation script for Module 5 VAL vs TEST check."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from clauseguard.clauses.attributes import (
    extract_governing_law_jurisdiction,
    extract_liability_cap,
)
from clauseguard.clauses.model import ClauseClassifier, classify_clause
from clauseguard.clauses.rules import classify_clause_rules
from clauseguard.clauses.training.cuad_data import (
    LabeledClause,
    _chunk_raw_into_pages,
    load_cuad_raw,
    load_dataset_by_split,
)
from clauseguard.clauses.training.evaluate import evaluate_predictions
from clauseguard.clauses.training.split import partition_contracts
from clauseguard.clauses.windows import (
    aggregate_window_predictions,
    split_clause_into_windows,
    truncate_evidence,
)
from clauseguard.parsing.clauses import segment_clauses

KEY_LABELS = [
    "governing_law",
    "anti_assignment",
    "cap_on_liability",
    "license_grant",
    "termination_for_convenience",
    "uncapped_liability",
    "non_compete",
]


def check_splits_and_artifacts() -> dict[str, Any]:
    print("=== Step 1: Checking splits and artifact consistency ===", flush=True)
    raw_contracts = load_cuad_raw()
    titles = [c["title"] for c in raw_contracts]
    split = partition_contracts(titles, seed=42)

    train_set = set(split.train_contracts)
    val_set = set(split.val_contracts)
    test_set = set(split.test_contracts)

    assert len(train_set & val_set) == 0, "Train and Val overlap!"
    assert len(train_set & test_set) == 0, "Train and Test overlap!"
    assert len(val_set & test_set) == 0, "Val and Test overlap!"
    assert len(train_set) + len(val_set) + len(test_set) == len(titles), "Contract count mismatch!"

    print(f"Contract counts: Train={len(train_set)}, Val={len(val_set)}, Test={len(test_set)}, Total={len(titles)}", flush=True)
    print("Contract lists disjointness: PASSED (0 overlap).", flush=True)

    # Load artifacts
    model_dir = Path("backend/models/clauses/v1")
    with open(model_dir / "metrics.json", encoding="utf-8") as f:
        metrics_data = json.load(f)
    with open(model_dir / "thresholds.json", encoding="utf-8") as f:
        thresholds_data = json.load(f)

    runtime_classifier = ClauseClassifier(model_dir)

    metrics_thresh = metrics_data.get("thresholds", {})
    json_thresh = thresholds_data.get("thresholds", {})
    runtime_thresh = runtime_classifier.thresholds

    metrics_shipped = metrics_data.get("shipped_methods", {})
    json_shipped = thresholds_data.get("shipped_methods", {})
    runtime_shipped = runtime_classifier.shipped_methods

    assert metrics_thresh == json_thresh, "metrics.json and thresholds.json thresholds differ!"
    assert runtime_thresh == json_thresh, "runtime thresholds differ from thresholds.json!"
    assert metrics_shipped == json_shipped, "metrics.json and thresholds.json shipped_methods differ!"
    assert runtime_shipped == json_shipped, "runtime shipped_methods differ from thresholds.json!"
    print("Artifact thresholds & shipped_methods: PASSED (metrics.json == thresholds.json == runtime).", flush=True)

    return {
        "split": split,
        "runtime_classifier": runtime_classifier,
        "metrics_data": metrics_data,
        "raw_contracts": raw_contracts,
    }


def batch_classify_clauses(
    clauses: list[LabeledClause],
    classifier: ClauseClassifier,
) -> list[list[dict[str, Any]]]:
    """Run exact production inference (segment/window/rules/model/window aggregation) in vectorized batch.
    
    Guaranteed bit-for-bit identical to running classify_clause one-by-one.
    """
    # 1. Window all clauses
    clause_windows: list[list[tuple[str, str]]] = []  # per clause, list of (window_text, heading)
    all_window_texts: list[str] = []
    window_map: list[list[int]] = []  # clause_idx -> list of flat window indices

    for c in clauses:
        windows = split_clause_into_windows(c.text, max_words_threshold=250, window_size=120, stride=100)
        c_map: list[int] = []
        if not windows:
            clause_windows.append([])
            window_map.append([])
            continue

        for w in windows:
            idx = len(all_window_texts)
            c_map.append(idx)
            combined = f"{c.heading}\n{w.text}" if c.heading else w.text
            all_window_texts.append(combined)

        clause_windows.append([(w.text, c.heading) for w in windows])
        window_map.append(c_map)

    # 2. Batch model inference
    total_windows = len(all_window_texts)
    print(f"  Vectorizing and predicting {total_windows} windows across {len(clauses)} clauses...", flush=True)

    # Pre-compute probabilities per label for all windows
    label_probs: dict[str, Any] = {}
    if classifier.is_model_loaded and classifier.vectorizer is not None and total_windows > 0:
        X = classifier.vectorizer.transform(all_window_texts)
        for label, clf in classifier.classifiers.items():
            if classifier.shipped_methods and classifier.shipped_methods.get(label, "rules") == "rules":
                continue
            if hasattr(clf, "predict_proba"):
                label_probs[label] = clf.predict_proba(X)[:, 1]

    # 3. Assemble window predictions exactly as classify_window does
    results: list[list[dict[str, Any]]] = []

    for c_idx, c in enumerate(clauses):
        c_win_indices = window_map[c_idx]
        if not c_win_indices:
            results.append([])
            continue

        c_win_info = clause_windows[c_idx]
        win_predictions: list[list[dict[str, Any]]] = []

        for local_idx, flat_idx in enumerate(c_win_indices):
            w_text, heading = c_win_info[local_idx]

            # 1. Rules
            rule_matches = classify_clause_rules(w_text, heading=heading)
            if classifier.shipped_methods:
                rule_matches = [m for m in rule_matches if classifier.shipped_methods.get(m["label"], "rules") != "model"]
            matches_by_label: dict[str, dict[str, Any]] = {m["label"]: m for m in rule_matches}

            # 2. Model
            for label, p_arr in label_probs.items():
                prob = float(p_arr[flat_idx])
                thresh = classifier.thresholds.get(label, 0.50)

                if prob >= thresh:
                    if label in matches_by_label:
                        existing = matches_by_label[label]
                        existing["method"] = "both"
                        existing["score"] = max(existing["score"], round(prob, 4))
                    else:
                        if prob >= 0.50:
                            matches_by_label[label] = {
                                "label": label,
                                "score": round(prob, 4),
                                "method": "model",
                                "evidence": truncate_evidence(w_text, 300),
                            }

            res = list(matches_by_label.values())
            res.sort(key=lambda x: (-x["score"], x["label"]))
            win_predictions.append(res)

        if len(win_predictions) == 1:
            results.append(win_predictions[0])
        else:
            results.append(aggregate_window_predictions(win_predictions, max_evidence_chars=300))

    return results


def main() -> None:
    res = check_splits_and_artifacts()
    split = res["split"]
    raw_contracts = res["raw_contracts"]
    classifier = res["runtime_classifier"]

    print("\nLoading dataset clauses partitioned by split...", flush=True)
    train_clauses, val_clauses, test_clauses = load_dataset_by_split(split)
    print(f"Clauses: train={len(train_clauses)}, val={len(val_clauses)}, test={len(test_clauses)}", flush=True)

    # Sanity check that batch_classify_clauses matches classify_clause exactly
    print("\nVerifying batch_classify_clauses matches classify_clause on 20 test clauses...", flush=True)
    test_sample = test_clauses[:20]
    batch_res = batch_classify_clauses(test_sample, classifier)
    for i, c in enumerate(test_sample):
        direct_res = classify_clause(c.text, heading=c.heading)
        assert batch_res[i] == direct_res, f"Mismatch at clause {i}!\nBatch: {batch_res[i]}\nDirect: {direct_res}"
    print("Verification PASSED: batch_classify_clauses is bit-for-bit identical to classify_clause.", flush=True)

    # Key-term check on gold clauses for CUAD TEST contracts
    print("\n=== Key-term check on gold clauses for CUAD TEST contracts ===", flush=True)
    test_gov_clauses = [c for c in test_clauses if "governing_law" in c.labels]
    test_cap_clauses = [c for c in test_clauses if "cap_on_liability" in c.labels]

    gov_hits = 0
    gov_misses: list[tuple[LabeledClause, str | None]] = []
    for c in test_gov_clauses:
        jur = extract_governing_law_jurisdiction(c.text)
        if jur is not None:
            gov_hits += 1
        else:
            gov_misses.append((c, jur))

    cap_hits = 0
    cap_misses: list[tuple[LabeledClause, dict | None]] = []
    for c in test_cap_clauses:
        cap = extract_liability_cap(c.text)
        if cap is not None:
            cap_hits += 1
        else:
            cap_misses.append((c, cap))

    print(f"Gold governing_law test clauses: total={len(test_gov_clauses)}, non-null={gov_hits} ({gov_hits / len(test_gov_clauses) * 100:.1f}%)", flush=True)
    print(f"Gold cap_on_liability test clauses: total={len(test_cap_clauses)}, non-null={cap_hits} ({cap_hits / len(test_cap_clauses) * 100:.1f}%)", flush=True)

    print("\n--- 10 governing_law misses ---", flush=True)
    for idx, (c, _) in enumerate(gov_misses[:10], 1):
        snippet = " ".join(c.text.split())[:250]
        print(f"[{idx}] {c.contract_title[:40]} | Clause {c.clause_id} | Heading: '{c.heading}'", flush=True)
        print(f"    Text: {snippet}\n", flush=True)

    print("\n--- 10 cap_on_liability misses ---", flush=True)
    for idx, (c, _) in enumerate(cap_misses[:10], 1):
        snippet = " ".join(c.text.split())[:250]
        print(f"[{idx}] {c.contract_title[:40]} | Clause {c.clause_id} | Heading: '{c.heading}'", flush=True)
        print(f"    Text: {snippet}\n", flush=True)

    # Check contracts with very few clauses relative to text length using existing segmented clauses
    print("\n=== Contracts with very few clauses relative to length ===", flush=True)
    # Group all clauses by contract title
    all_clauses = train_clauses + val_clauses + test_clauses
    clauses_by_contract: dict[str, list[LabeledClause]] = {}
    for c in all_clauses:
        clauses_by_contract.setdefault(c.contract_title, []).append(c)

    doc_contexts = {}
    for doc in raw_contracts:
        title = doc.get("title", "")
        paras = doc.get("paragraphs", [])
        if paras:
            doc_contexts[title] = paras[0].get("context", "")

    short_clause_docs = []
    for title, contract_clauses in clauses_by_contract.items():
        ctx = doc_contexts.get(title, "")
        char_len = len(ctx)
        clause_cnt = len(contract_clauses)
        if clause_cnt <= 8 and char_len > 10000:
            short_clause_docs.append({
                "title": title,
                "char_length": char_len,
                "clause_count": clause_cnt,
                "clauses_per_10k_chars": round(clause_cnt / (char_len / 10000.0), 2),
                "headings": [c.heading for c in contract_clauses[:5]],
            })

    short_clause_docs.sort(key=lambda x: (x["clause_count"], -x["char_length"]))
    print(f"Found {len(short_clause_docs)} long contracts (>10k chars) with <= 8 clauses:")
    for d in short_clause_docs:
        print(f"Contract: {d['title']} | Chars: {d['char_length']} | Clauses: {d['clause_count']} | Headings: {d['headings']}", flush=True)

    # Evaluate VAL on production harness
    print("\n=== Evaluating VAL on production harness ===", flush=True)
    val_preds = batch_classify_clauses(val_clauses, classifier)
    val_y_true = [c.labels for c in val_clauses]
    val_y_pred = [{p["label"] for p in preds} for preds in val_preds]
    val_rep = evaluate_predictions(val_y_true, val_y_pred, split_name="val")

    # Evaluate TEST on production harness
    print("\n=== Evaluating TEST on production harness ===", flush=True)
    test_preds = batch_classify_clauses(test_clauses, classifier)
    test_y_true = [c.labels for c in test_clauses]
    test_y_pred = [{p["label"] for p in preds} for preds in test_preds]
    test_rep = evaluate_predictions(test_y_true, test_y_pred, split_name="test")

    # Evaluate TRAIN on production harness
    print("\n=== Evaluating TRAIN on production harness ===", flush=True)
    train_preds = batch_classify_clauses(train_clauses, classifier)
    train_y_true = [c.labels for c in train_clauses]
    train_y_pred = [{p["label"] for p in preds} for preds in train_preds]
    train_rep = evaluate_predictions(train_y_true, train_y_pred, split_name="train")

    print("\n" + "=" * 95, flush=True)
    print("=== SIDE-BY-SIDE TRAIN vs VAL vs TEST ON EXACT SAME PRODUCTION HARNESS ===", flush=True)
    print("=" * 95, flush=True)
    header = f"{'Label':<35} | {'TRAIN F1':<10} | {'VAL F1':<10} | {'TEST F1':<10} | {'VAL in metrics.json':<20} | {'Shipped'}"
    print(header, flush=True)
    print("-" * len(header), flush=True)

    metrics_shipped_val = res["metrics_data"].get("val_comparison", {}).get("shipped", {})

    for lbl in KEY_LABELS:
        tr_f1 = train_rep.labels[lbl].f1 if lbl in train_rep.labels else 0.0
        va_f1 = val_rep.labels[lbl].f1 if lbl in val_rep.labels else 0.0
        te_f1 = test_rep.labels[lbl].f1 if lbl in test_rep.labels else 0.0
        old_val_f1 = metrics_shipped_val.get(lbl, {}).get("f1", 0.0)
        shipped = classifier.shipped_methods.get(lbl, "rules")
        print(f"{lbl:<35} | {tr_f1:<10.4f} | {va_f1:<10.4f} | {te_f1:<10.4f} | {old_val_f1:<20.4f} | {shipped}", flush=True)

    print("\n--- All 36 CORE_CUAD_LABELS ---", flush=True)
    full_header = f"{'Label':<35} | {'TRAIN F1':<10} | {'VAL F1':<10} | {'TEST F1':<10} | {'VAL P':<8} | {'VAL R':<8} | {'TEST P':<8} | {'TEST R':<8}"
    print(full_header, flush=True)
    print("-" * len(full_header), flush=True)
    for lbl, m_val in val_rep.labels.items():
        m_train = train_rep.labels.get(lbl)
        m_test = test_rep.labels.get(lbl)
        tr_f1 = m_train.f1 if m_train else 0.0
        te_f1 = m_test.f1 if m_test else 0.0
        te_p = m_test.precision if m_test else 0.0
        te_r = m_test.recall if m_test else 0.0
        print(f"{lbl:<35} | {tr_f1:<10.4f} | {m_val.f1:<10.4f} | {te_f1:<10.4f} | {m_val.precision:<8.4f} | {m_val.recall:<8.4f} | {te_p:<8.4f} | {te_r:<8.4f}", flush=True)

    print("\nOverall Micro and Macro F1:", flush=True)
    print(f"VAL:   Micro F1 = {val_rep.micro_f1:.4f} (P={val_rep.micro_precision:.4f}, R={val_rep.micro_recall:.4f}), Macro F1 = {val_rep.macro_f1:.4f} (P={val_rep.macro_precision:.4f}, R={val_rep.macro_recall:.4f})", flush=True)
    print(f"TEST:  Micro F1 = {test_rep.micro_f1:.4f} (P={test_rep.micro_precision:.4f}, R={test_rep.micro_recall:.4f}), Macro F1 = {test_rep.macro_f1:.4f} (P={test_rep.macro_precision:.4f}, R={test_rep.macro_recall:.4f})", flush=True)
    print(f"TRAIN: Micro F1 = {train_rep.micro_f1:.4f} (P={train_rep.micro_precision:.4f}, R={train_rep.micro_recall:.4f}), Macro F1 = {train_rep.macro_f1:.4f} (P={train_rep.macro_precision:.4f}, R={train_rep.macro_recall:.4f})", flush=True)

    # Save to JSON
    out_path = Path("eval/results/investigate_module5.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "val": val_rep.to_dict(),
            "test": test_rep.to_dict(),
            "train": train_rep.to_dict(),
            "short_clause_docs": short_clause_docs,
            "gov_stats": {"total": len(test_gov_clauses), "hits": gov_hits},
            "cap_stats": {"total": len(test_cap_clauses), "hits": cap_hits},
        }, f, indent=2)
    print(f"\nSaved investigation results to {out_path}", flush=True)


if __name__ == "__main__":
    main()
