"""Augmentation ablation.

Run with::

    python -m src.ablation

The Mendeley balanced corpus is LLM-generated and contributes the large
majority of the smishing messages in the training split. That raises a
question the headline metric cannot answer: is the model learning smishing, or
is it learning the generator's style?

This module answers it by fitting the same pipeline twice — once on the real
messages alone, once with the synthetic rows added — and comparing both on the
validation split and on the Singapore shift set.

Both comparisons avoid the test split entirely. The test set is spent once, by
``src.train``, on the selected model; re-using it here to pick an augmentation
setting would be exactly the leak the project's evaluation design exists to
prevent.
"""

from __future__ import annotations

import sys

import pandas as pd

from . import evaluate as ev
from .config import CFG
from .datasets import SYNTHETIC_SOURCES
from .train import FEATURE_COLUMNS, build_ladder, load_splits


def run(model_name: str = "svm_char_tfidf") -> pd.DataFrame:
    splits = load_splits()
    train, val, shift = splits["train"], splits["val"], splits["shift_sg"]

    real_only = train[~train["source"].isin(SYNTHETIC_SOURCES)].reset_index(drop=True)

    conditions = {
        "real_only": real_only,
        "real_plus_synthetic": train,
    }

    rows = []
    for condition, data in conditions.items():
        counts = data["label"].value_counts().to_dict()
        print(f"\n{'=' * 60}\n{condition}: {len(data):,} rows  {counts}")

        # A fresh pipeline per condition — refitting the same object would
        # carry state across conditions.
        model = build_ladder()[model_name]
        model.fit(data[FEATURE_COLUMNS], data["label"])

        y_pred = model.predict(val[FEATURE_COLUMNS])
        row = ev.report(val["label"], y_pred, name=f"{model_name} / {condition} [val]")
        row["condition"] = condition
        row["train_rows"] = len(data)

        # Does the augmentation make the model noisier on real local messages?
        # The shift set is ham-only, so any non-ham prediction is a false alarm.
        y_shift = model.predict(shift[FEATURE_COLUMNS])
        row["sg_false_alarm_rate"] = float((y_shift != "ham").mean())
        print(f"SG false alarm rate: {row['sg_false_alarm_rate']:.4f}")

        rows.append(row)

    board = pd.DataFrame(rows)
    target_recall = f"{CFG.target_label}_recall"
    cols = [
        c
        for c in [
            "condition",
            "train_rows",
            "accuracy",
            "macro_f1",
            target_recall,
            "expected_cost",
            "sg_false_alarm_rate",
        ]
        if c in board
    ]

    print(f"\n{'=' * 60}\nABLATION — {model_name}, validation split")
    print(board[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    # The verdict, stated rather than left for the reader to infer.
    if target_recall in board:
        delta = board.loc[1, target_recall] - board.loc[0, target_recall]
        direction = "helps" if delta > 0 else "hurts" if delta < 0 else "makes no difference"
        print(
            f"\nsynthetic augmentation {direction}: "
            f"{CFG.target_label} recall {delta:+.4f} on validation"
        )

    board.to_csv(CFG.reports_dir / "ablation_augmentation.csv", index=False)
    return board


if __name__ == "__main__":
    run()
    sys.exit(0)
