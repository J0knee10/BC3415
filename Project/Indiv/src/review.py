"""Human in the loop — when the bot should hand a message to a person.

Run with::

    python -m src.review

The rule is a cost-sensitive form of Chow's reject option (Chow, 1970),
using this project's cost matrix. For each message the model gives three probabilities. The expected
cost of the bot answering on its own is the cost of its verdict averaged over
what the message might really be:

    answer cost = sum over true classes  P(true class) x cost(true class, verdict)

If that exceeds the cost of a human review, a person should look at it.

Why not a flat confidence cut-off such as "review below 60%": the errors are
not equally expensive. A message the model calls legitimate with only a 3%
chance of being a scam already carries an expected cost of 20 x 0.03 = 0.6,
because a missed scam costs 20. A message split 55/45 between legitimate and
marketing spam carries at most 0.45, because that mistake costs 1. The first
deserves a human; the second does not, though its confidence is far lower.

The review cost is in the cost matrix's units (``review.cost`` in
config.yaml; the derivation is in the writeup's human-in-the-loop section).
It was chosen with validation and test figures both in view, so the test
figures at the chosen cost are not an untouched estimate. ``run`` reports
every value in ``review.grid`` on every evaluation set, so a reader can see
how the figures move with the choice.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from .config import CFG


def answer_cost(proba, classes: list[str], labels) -> np.ndarray:
    """Expected cost of answering each message with its given verdict.

    ``proba`` columns follow ``classes`` (the estimator's ``classes_``);
    ``labels`` are the verdicts actually served.
    """
    order = [CFG.labels.index(c) for c in classes]
    costs = np.array(CFG.cost_matrix())[np.ix_(order, order)]
    # expected[n, j] = sum_i P(class i) * cost(i, j): the cost of answering j.
    expected = np.asarray(proba) @ costs
    col = [list(classes).index(str(lab)) for lab in labels]
    return expected[np.arange(len(col)), col]


def needs_review(proba, classes: list[str], labels, cost: float | None = None) -> np.ndarray:
    """True where a human review is cheaper than letting the verdict stand."""
    cost = CFG.raw["review"]["cost"] if cost is None else cost
    return answer_cost(proba, classes, labels) > cost


def run() -> pd.DataFrame:
    """Review load and errors caught, for every review cost, on every set."""
    from .predict import load_model
    from .train import FEATURE_COLUMNS, _predict, load_splits

    model = load_model()
    classes = list(model.classes_)
    rule = getattr(model, "decision_rule_", "argmax")
    target = CFG.target_label
    splits = load_splits()
    sets = [s for s in ["val", "test", "shift_sg", "sg_scams"] if s in splits]

    rows = []
    for name in sets:
        df = splits[name]
        y_pred, proba = _predict(model, df, rule)
        y = df["label"].to_numpy()
        wrong = y_pred != y
        missed = (y == target) & (y_pred != target)  # a scam not called a scam
        false_alarm = (y == "ham") & (y_pred != "ham")  # a real message flagged
        for cost in CFG.raw["review"]["grid"]:
            r = needs_review(proba, classes, y_pred, cost)
            rows.append(
                {
                    "set": name,
                    "review_cost": cost,
                    "messages": len(df),
                    "reviewed": int(r.sum()),
                    "review_share": float(r.mean()),
                    "errors": int(wrong.sum()),
                    "errors_reviewed": int((wrong & r).sum()),
                    "missed_scams": int(missed.sum()),
                    "missed_scams_reviewed": int((missed & r).sum()),
                    "false_alarms": int(false_alarm.sum()),
                    "false_alarms_reviewed": int((false_alarm & r).sum()),
                    "reviewed_by_verdict": {
                        c: int((r & (y_pred == c)).sum()) for c in classes
                    },
                }
            )

    table = pd.DataFrame(rows)
    served = CFG.raw["review"]["cost"]
    print("HUMAN REVIEW — a message goes to a person when the expected cost of")
    print(f"the bot's answer exceeds the review cost (served: {served})\n")
    cols = [
        "set",
        "review_cost",
        "review_share",
        "errors_reviewed",
        "errors",
        "missed_scams_reviewed",
        "missed_scams",
        "false_alarms_reviewed",
        "false_alarms",
    ]
    print(table[cols].to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    table.to_csv(CFG.reports_dir / "human_review.csv", index=False)
    return table


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    run()
    sys.exit(0)
