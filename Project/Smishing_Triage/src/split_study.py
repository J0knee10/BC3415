"""Does the way the data is split change what the test score means?

Run with::

    python -m src.split_study

The same real messages are split into train / validation / test three ways,
and the champion model design is trained on each, for three seeds:

* ``random``: each message is assigned on its own, the textbook split.
* ``delete``: split by template, then training rows that nearly copy a
  validation or test message are deleted (the project's previous method).
* ``cluster``: whole near-copy clusters are assigned at random (the method
  ``preprocess.split`` uses).

For each, it reports the test smishing recall, split into test scams with a
near-twin in training and test scams without one, how many real scams the
model trained on, and how many of the real Singapore scams it catches. Those
never enter any training set, so they are the common yardstick.

This is evidence about the split method, and it informed the choice of the
method in ``preprocess.split``. It does not choose or tune the served model.
Written to ``reports/split_study.csv``.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from .config import CFG
from .datasets import SYNTHETIC_SOURCES, load_all
from .preprocess import (
    CLUSTER,
    GROUP,
    cluster_split,
    deduplicate,
    near_copies,
    near_copy_clusters,
    normalise_text,
)
from .train import FEATURE_COLUMNS, build_ladder


def _random(pool: pd.DataFrame, size: float, seed: int):
    return train_test_split(pool, test_size=size, stratify=pool["label"], random_state=seed)


def _by_template(pool: pd.DataFrame, size: float, seed: int):
    templates = pool.groupby(GROUP)["label"].first()
    keep, hold = train_test_split(
        templates.index.to_numpy(), test_size=size, random_state=seed, stratify=templates.to_numpy()
    )
    return pool[pool[GROUP].isin(set(keep))], pool[pool[GROUP].isin(set(hold))]


def _splits(method: str, pool: pd.DataFrame, corpus: pd.DataFrame, seed: int):
    """Train and test frames for one method and seed (validation set aside)."""
    cfg = CFG.split
    if method == "random":
        train, test = _random(pool, cfg["test_size"], seed)
        train, val = _random(train, cfg["val_size"], seed)
    elif method == "delete":
        train, test = _by_template(pool, cfg["test_size"], seed)
        train, val = _by_template(train, cfg["val_size"], seed)
        held = pd.concat([val, test])
        train = train[~near_copies(train, held, corpus=corpus)]
    else:
        train, test = cluster_split(pool, cfg["test_size"], cfg["stratify"], seed)
        train, val = cluster_split(train, cfg["val_size"], cfg["stratify"], seed)
    return train, test


def run(model_name: str = "svm_char_tfidf", seeds: tuple[int, ...] | None = None) -> pd.DataFrame:
    seeds = seeds or (CFG.split["random_state"], 1, 2)
    target = CFG.target_label

    df, _ = deduplicate(load_all())
    df["text_clean"] = df["text"].map(normalise_text)
    df = df[df["text_clean"].str.len() > 0].reset_index(drop=True)
    pool = df[(df["source"] != "nus") & ~df["source"].isin(SYNTHETIC_SOURCES)].copy()
    pool[CLUSTER] = near_copy_clusters(pool, corpus=df)

    sg = pd.read_csv(CFG.processed_dir / "sg_scams.csv").fillna({GROUP: ""})
    sg_scam = (sg["label"] == target).to_numpy()

    rows = []
    for method in ["random", "delete", "cluster"]:
        for seed in seeds:
            train, test = _splits(method, pool, df, seed)
            model = build_ladder()[model_name]
            model.fit(train[FEATURE_COLUMNS], train["label"])

            y_pred = model.predict(test[FEATURE_COLUMNS])
            scam = (test["label"] == target).to_numpy()
            caught = y_pred == target
            twin = test[GROUP].isin(set(train[GROUP])).to_numpy() | near_copies(test, train, corpus=df)
            sg_pred = model.predict(sg[FEATURE_COLUMNS])

            def recall(mask):
                return float(caught[mask].mean()) if mask.any() else np.nan

            rows.append(
                {
                    "method": method,
                    "seed": seed,
                    "train_scams": int((train["label"] == target).sum()),
                    "test_scams": int(scam.sum()),
                    "test_recall": recall(scam),
                    "twin_scams": int((scam & twin).sum()),
                    "twin_recall": recall(scam & twin),
                    "new_scams": int((scam & ~twin).sum()),
                    "new_recall": recall(scam & ~twin),
                    "sg_caught": int((sg_pred[sg_scam] == target).sum()),
                    "sg_scams": int(sg_scam.sum()),
                }
            )

    table = pd.DataFrame(rows)
    print(f"\n{'=' * 60}\nSPLIT STUDY — {model_name}, real messages only")
    print("twin = a test scam with a near-copy (or the same template) in training\n")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    table.to_csv(CFG.reports_dir / "split_study.csv", index=False)
    return table


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    run()
    sys.exit(0)
