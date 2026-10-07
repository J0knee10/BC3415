"""Evaluation.

The headline number for this project is **recall on the smishing class**, not
accuracy. On a corpus that is ~85% ham, a model that predicts ham for
everything scores 85% accuracy and is worthless. Every function here is built
around that.

Also provided:

* bootstrap confidence intervals, because the smishing test set is small
  (~128 messages) and a point estimate alone would overstate precision;
* expected cost under the matrix in ``config.yaml``, which is how an operating
  point gets chosen;
* error analysis that surfaces the misses the next model has to fix.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn import metrics

from .config import CFG


def _present_labels(y_true, y_pred) -> list[str]:
    """Configured labels, restricted to those actually present in the data.

    Lets the whole pipeline run on two classes before the Mendeley smishing
    set is in place, and switch to three without a code change.
    """
    seen = set(map(str, y_true)) | set(map(str, y_pred))
    return [lab for lab in CFG.labels if lab in seen]


def confusion(y_true, y_pred) -> pd.DataFrame:
    """Confusion matrix as a labelled frame — true rows, predicted columns."""
    labels = _present_labels(y_true, y_pred)
    cm = metrics.confusion_matrix(y_true, y_pred, labels=labels)
    return pd.DataFrame(
        cm,
        index=pd.Index(labels, name="true"),
        columns=pd.Index(labels, name="predicted"),
    )


def expected_cost(y_true, y_pred) -> float:
    """Mean cost per message under the configured cost matrix.

    This is the number to minimise when choosing an operating point. Accuracy
    treats every error as equal; this does not.
    """
    labels = CFG.labels
    costs = np.array(CFG.cost_matrix())
    index = {lab: i for i, lab in enumerate(labels)}

    total = 0.0
    for t, p in zip(y_true, y_pred):
        if t in index and p in index:
            total += costs[index[t]][index[p]]
    return total / max(len(y_true), 1)


def bootstrap_ci(y_true, y_pred, label: str, metric: str = "recall") -> tuple[float, float]:
    """Percentile bootstrap interval for a per-class metric.

    Resamples message indices with replacement. Reported alongside the point
    estimate so the small smishing class is not quoted with false confidence.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    n = len(y_true)
    rng = np.random.default_rng(CFG.split["random_state"])

    scorer = {
        "recall": metrics.recall_score,
        "precision": metrics.precision_score,
        "f1": metrics.f1_score,
    }[metric]

    draws = []
    for _ in range(CFG.evaluate["bootstrap_n"]):
        idx = rng.integers(0, n, n)
        draws.append(
            scorer(y_true[idx], y_pred[idx], labels=[label], average="macro", zero_division=0)
        )

    alpha = CFG.evaluate["bootstrap_alpha"]
    lo, hi = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def summarise(y_true, y_pred, name: str = "") -> dict:
    """One row of the leaderboard: the metrics that decide model selection."""
    labels = _present_labels(y_true, y_pred)
    report = metrics.classification_report(
        y_true, y_pred, labels=labels, output_dict=True, zero_division=0
    )

    row = {
        "model": name,
        "accuracy": metrics.accuracy_score(y_true, y_pred),
        "macro_f1": report["macro avg"]["f1-score"],
        "expected_cost": expected_cost(y_true, y_pred),
    }

    # Per-class detail, with the target class first because it is the point.
    target = CFG.target_label
    ordered = [target] + [lab for lab in labels if lab != target]
    for lab in ordered:
        if lab in report:
            row[f"{lab}_precision"] = report[lab]["precision"]
            row[f"{lab}_recall"] = report[lab]["recall"]
            row[f"{lab}_f1"] = report[lab]["f1-score"]

    return row


def report(y_true, y_pred, name: str = "", show_ci: bool = True) -> dict:
    """Print a full evaluation and return the leaderboard row."""
    row = summarise(y_true, y_pred, name)
    target = CFG.target_label

    print(f"\n--- {name} ---")
    print(f"accuracy      {row['accuracy']:.4f}")
    print(f"macro F1      {row['macro_f1']:.4f}")
    print(f"expected cost {row['expected_cost']:.4f}  (lower is better)")

    if f"{target}_recall" in row:
        line = f"{target} recall {row[f'{target}_recall']:.4f}"
        if show_ci:
            lo, hi = bootstrap_ci(y_true, y_pred, target, "recall")
            line += f"   95% CI [{lo:.3f}, {hi:.3f}]"
            row[f"{target}_recall_ci"] = (lo, hi)
        print(line)

    print("\nconfusion matrix")
    print(confusion(y_true, y_pred).to_string())
    return row


def error_analysis(
    X: pd.DataFrame,
    y_true,
    y_pred,
    proba=None,
    classes: list[str] | None = None,
    label: str | None = None,
    top: int = 15,
) -> pd.DataFrame:
    """The misses on the class that matters, worst first.

    When probabilities are available the rows are sorted by how confidently the
    model got it wrong — those are the cases that tell you what the next rung
    of the ladder needs to do differently.
    """
    label = label or CFG.target_label
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    missed = (y_true == label) & (y_pred != label)
    if not missed.any():
        return pd.DataFrame(columns=["text", "true", "predicted"])

    out = pd.DataFrame(
        {
            "text": X.loc[missed, "text"].values,
            "true": y_true[missed],
            "predicted": y_pred[missed],
        }
    )

    # Column order follows the estimator's own classes_, which is not
    # necessarily the configured label order.
    if proba is not None and classes is not None and label in classes:
        col = list(classes).index(label)
        out["p_target"] = np.asarray(proba)[missed, col]
        out = out.sort_values("p_target")

    return out.head(top)
