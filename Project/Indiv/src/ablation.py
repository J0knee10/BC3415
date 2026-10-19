"""Augmentation ablation.

Run with::

    python -m src.ablation

The Mendeley balanced corpus is published as LLM-generated, but most of it is
reworded copies of the other corpora. The served model excludes it
(``train.use_synthetic: false``); this module is the evidence for that setting.

It fits the champion pipeline with and without the generated rows and compares
them twice:

* on the validation split and the Singapore shift set (``run``), and
* over repeated template splits of the non-test data (``repeated``), because
  a single split of ~80 smishing messages swings recall by tens of points and
  one split cannot tell a real effect from luck.

Both comparisons avoid the test split entirely. The test set is spent once, by
``src.train``, on the selected model; re-using it here to pick an augmentation
setting would be exactly the leak the project's evaluation design exists to
prevent.
"""

from __future__ import annotations

import sys

import pandas as pd
from sklearn.model_selection import train_test_split

from . import evaluate as ev
from .config import CFG
from .datasets import SYNTHETIC_SOURCES
from .preprocess import GROUP, near_copies
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


def repeated(model_name: str = "svm_char_tfidf", seeds: int = 6) -> pd.DataFrame:
    """Real-only vs. with generated rows, over repeated template splits.

    The real training and validation messages are pooled and re-split by
    template (80/20) once per seed; the test split is never used. Generated
    rows and training rows that nearly copy a fold's held-out messages are
    removed, exactly as ``preprocess.split`` does.
    """
    splits = load_splits()
    train, val, test = splits["train"], splits["val"], splits["test"]
    is_gen = train["source"].isin(SYNTHETIC_SOURCES)
    generated = train[is_gen]
    pool = pd.concat([train[~is_gen], val], ignore_index=True)
    corpus = pd.concat([pool, generated, test], ignore_index=True)  # fixed TF-IDF weights
    target_recall = f"{CFG.target_label}_recall"

    rows = []
    for seed in range(seeds):
        templates = pool.groupby(GROUP)["label"].first()
        keep, hold = train_test_split(
            templates.index.to_numpy(), test_size=0.2, random_state=seed,
            stratify=templates.to_numpy(),
        )
        fold_train = pool[pool[GROUP].isin(set(keep))]
        fold_val = pool[pool[GROUP].isin(set(hold))]
        fold_train = fold_train[~near_copies(fold_train, fold_val, corpus=corpus)]
        gen_ok = generated[~near_copies(generated, fold_val, corpus=corpus)]

        for condition, data in [("real_only", fold_train), ("with_generated", pd.concat([fold_train, gen_ok]))]:
            model = build_ladder()[model_name]
            model.fit(data[FEATURE_COLUMNS], data["label"])
            r = ev.summarise(fold_val["label"], model.predict(fold_val[FEATURE_COLUMNS]))
            rows.append({"seed": seed, "condition": condition, "macro_f1": r["macro_f1"],
                         target_recall: r.get(target_recall)})

    table = pd.DataFrame(rows)
    wide = table.pivot(index="seed", columns="condition", values=[target_recall, "macro_f1"])
    print(f"\n{'=' * 60}\nREPEATED SPLITS — {model_name}, {seeds} template splits, test unused")
    print(wide.to_string(float_format=lambda v: f"{v:.3f}"))
    gain = (wide[target_recall]["with_generated"] - wide[target_recall]["real_only"])
    f1_gain = (wide["macro_f1"]["with_generated"] - wide["macro_f1"]["real_only"])
    print(
        f"\ngenerated rows: {CFG.target_label} recall {gain.mean():+.3f} on average "
        f"(better in {(gain > 0).sum()} of {seeds}), macro F1 {f1_gain.mean():+.3f}"
    )
    real = wide[target_recall]["real_only"]
    print(f"real-only {CFG.target_label} recall ranges {real.min():.2f}–{real.max():.2f} across splits")
    table.to_csv(CFG.reports_dir / "ablation_repeated.csv", index=False)
    return table


if __name__ == "__main__":
    run()
    repeated()
    sys.exit(0)
