"""The model ladder.

Run with::

    python -m src.train

Four rungs, each a complete pipeline from text to label. Every rung is scored
on the validation split; the test split is touched **once**, at the end, by the
selected model only. Selection is on macro F1 with smishing recall as the
tiebreak — the project's stated priority, applied mechanically rather than by
eye.

The ladder is the deliverable as much as the final model is. A single model
with a good number says nothing about whether a simpler one would have done;
the ladder answers that, and the error analysis after each rung says what the
next rung has to fix.
"""

from __future__ import annotations

import json
import sys

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from . import evaluate as ev
from . import features as ft
from .config import CFG

FEATURE_COLUMNS = [ft.TEXT_RAW, ft.TEXT_CLEAN]


def load_splits() -> dict[str, pd.DataFrame]:
    """Read the splits written by ``src.preprocess``."""
    splits = {}
    for name in ["train", "val", "test", "shift_sg"]:
        path = CFG.processed_dir / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing — run `python -m src.preprocess` first."
            )
        splits[name] = pd.read_csv(path).fillna({ft.TEXT_CLEAN: "", ft.TEXT_RAW: ""})

    # Optional: the hand-collected Singapore scam set, evaluation only.
    sg_scams = CFG.processed_dir / "sg_scams.csv"
    if sg_scams.exists():
        splits["sg_scams"] = pd.read_csv(sg_scams).fillna({ft.TEXT_CLEAN: ""})
    return splits


def build_ladder() -> dict[str, Pipeline]:
    """The four rungs, cheapest first.

    ``class_weight="balanced"`` throughout: smishing is the smallest class and
    the one that matters, so the loss has to say so. Naive Bayes has no such
    parameter, which is part of why it is the floor.
    """
    return {
        # Rung 1 — the floor. Named directly in the assignment brief.
        "nb_word_counts": Pipeline(
            [("features", ft.count_features()), ("clf", MultinomialNB())]
        ),
        # Rung 2 — linear baseline with readable coefficients.
        "logreg_word_tfidf": Pipeline(
            [
                ("features", ft.word_features()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=3000, class_weight="balanced", solver="lbfgs"
                    ),
                ),
            ]
        ),
        # Rung 3 — the obfuscation handler. Expected to lead the classical set.
        # LinearSVC has no predict_proba, so it is wrapped in a calibrator;
        # the bot needs a confidence score to show the user.
        "svm_char_tfidf": Pipeline(
            [
                ("features", ft.char_features()),
                (
                    "clf",
                    CalibratedClassifierCV(
                        LinearSVC(class_weight="balanced"), cv=5, method="sigmoid"
                    ),
                ),
            ]
        ),
        # Rung 4 — both representations at once.
        "logreg_word_char": Pipeline(
            [
                ("features", ft.word_char_features()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=3000, class_weight="balanced", solver="lbfgs"
                    ),
                ),
            ]
        ),
    }


def _predict(model: Pipeline, df: pd.DataFrame, rule: str = "argmax"):
    """Predict labels and, where the estimator supports it, probabilities.

    ``rule`` is the operating point: ``argmax`` (the most probable class) or
    ``min_cost`` (the cheapest class under the cost matrix).
    """
    X = df[FEATURE_COLUMNS]
    proba = model.predict_proba(X) if hasattr(model, "predict_proba") else None
    if rule == "min_cost" and proba is not None:
        y_pred = ev.min_cost_predict(proba, list(model.classes_))
    else:
        y_pred = model.predict(X)
    return y_pred, proba


def compare_operating_points(
    model: Pipeline, val: pd.DataFrame, shift: pd.DataFrame
) -> pd.DataFrame:
    """Score both decision rules on validation and the Singapore shift set.

    Argmax treats every error alike; the cost matrix does not. The rule served
    is set in ``config.yaml`` rather than picked here, because the cost matrix
    leaves out what the shift set measures: how often a real local message is
    called a scam. This table is the evidence for that setting.
    """
    rows = []
    for rule in ["argmax", "min_cost"]:
        y_pred, _ = _predict(model, val, rule)
        row = ev.summarise(val["label"], y_pred, name=rule)
        if len(shift):
            y_shift, _ = _predict(model, shift, rule)
            row["sg_false_alarm_rate"] = float((y_shift != "ham").mean())
        rows.append(row)
    table = pd.DataFrame(rows).rename(columns={"model": "rule"})

    target = CFG.target_label
    cols = [
        c
        for c in [
            "rule",
            "macro_f1",
            f"{target}_recall",
            f"{target}_precision",
            "expected_cost",
            "sg_false_alarm_rate",
        ]
        if c in table
    ]
    print(f"\n{'=' * 60}\nOPERATING POINT — validation (and SG shift set)")
    print(table[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nserving: {CFG.operating_point}  (set in config.yaml)")
    table[cols].to_csv(CFG.reports_dir / "operating_point_val.csv", index=False)
    return table


def _evaluate_sg_scams(model: Pipeline, sg: pd.DataFrame, rule: str) -> dict:
    """Score the hand-collected Singapore set; write every verdict to reports.

    Two rates for the scams: *caught* (called smishing) and *flagged* (called
    anything but ham). A scam called spam still gets a warning in front of the
    user, so the gap between the two is the spam↔smishing boundary again.
    """
    target = CFG.target_label
    y_pred, proba = _predict(model, sg, rule)
    p_target = proba[:, list(model.classes_).index(target)]
    scams = (sg["label"] == target).to_numpy()

    print(f"\n{'=' * 60}\nSINGAPORE SCAM SET (hand-collected, n={len(sg)})")
    result: dict = {}
    if scams.any():
        caught = float((y_pred[scams] == target).mean())
        flagged = float((y_pred[scams] != "ham").mean())
        print(f"scams caught as {target}: {caught:.3f}  ({(y_pred[scams] == target).sum()}/{scams.sum()})")
        print(f"scams flagged (spam or {target}): {flagged:.3f}")
        result.update(sg_scam_recall=caught, sg_scam_flagged=flagged)

        if "scam_type" in sg:
            by_type = (
                pd.DataFrame({"type": sg.loc[scams, "scam_type"], "caught": y_pred[scams] == target})
                .groupby("type")["caught"]
                .agg(["sum", "count"])
            )
            print("\ncaught by scam type:")
            print(by_type.to_string())

    if (~scams).any():
        ham_alarm = float((y_pred[~scams] != "ham").mean())
        print(f"\nfalse alarms on the legitimate local messages: {(y_pred[~scams] != 'ham').sum()}/{(~scams).sum()}")
        result["sg_legit_false_alarm_rate"] = ham_alarm

    cols = [c for c in ["text", "label", "scam_type", "source_url"] if c in sg]
    sg[cols].assign(predicted=y_pred, **{f"p_{target}": p_target}).to_csv(
        CFG.reports_dir / "sg_scams_predictions.csv", index=False
    )
    return result


def run() -> pd.DataFrame:
    splits = load_splits()
    train, val, test = splits["train"], splits["val"], splits["test"]

    print(f"train {len(train):,}  val {len(val):,}  test {len(test):,}")
    print(f"train class balance: {train['label'].value_counts().to_dict()}\n")

    leaderboard = []
    fitted = {}

    for name, model in build_ladder().items():
        print(f"\n{'=' * 60}\nfitting {name}")
        model.fit(train[FEATURE_COLUMNS], train["label"])
        fitted[name] = model

        y_pred, proba = _predict(model, val)
        row = ev.report(val["label"], y_pred, name=f"{name} [val]")
        row["model"] = name  # the leaderboard keys on the bare name
        leaderboard.append(row)

        # What this rung missed, to motivate the next one.
        misses = ev.error_analysis(
            val, val["label"], y_pred, proba, classes=list(model.classes_)
        )
        if len(misses):
            print(f"\ntop {CFG.target_label} misses:")
            for _, r in misses.head(5).iterrows():
                print(f"  [{r['predicted']}] {str(r['text'])[:100]}")

    board = pd.DataFrame(leaderboard)

    # --- selection ------------------------------------------------------
    # Macro F1, with recall on the target class breaking ties. Done on
    # validation only; the test split has not been touched yet.
    target_recall = f"{CFG.target_label}_recall"
    sort_keys = ["macro_f1"] + ([target_recall] if target_recall in board else [])
    board = board.sort_values(sort_keys, ascending=False).reset_index(drop=True)

    print(f"\n{'=' * 60}\nVALIDATION LEADERBOARD")
    cols = [c for c in ["model", "accuracy", "macro_f1", "expected_cost", target_recall] if c in board]
    print(board[cols].to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    champion_name = board.iloc[0]["model"]
    champion = fitted[champion_name]
    print(f"\nselected: {champion_name}")

    # --- operating point ------------------------------------------------
    # Compared before the test set is touched. The configured rule is stored
    # on the model so that predict() serves the rule the test number describes.
    compare_operating_points(champion, val, splits["shift_sg"])
    rule = CFG.operating_point
    champion.decision_rule_ = rule

    # --- the one test evaluation ----------------------------------------
    print(f"\n{'=' * 60}\nTEST — evaluated once, by the selected model only")
    y_pred, proba = _predict(champion, test, rule)
    test_row = ev.report(test["label"], y_pred, name=f"{champion_name} [test]")
    test_row["operating_point"] = rule

    # --- Singapore shift set --------------------------------------------
    # NUS is ham-only, so the question it answers is narrow but sharp: how
    # often does the model cry wolf on ordinary Singaporean messages?
    shift = splits["shift_sg"]
    if len(shift):
        print(f"\n{'=' * 60}\nSINGAPORE SHIFT SET (NUS, ham only, n={len(shift):,})")
        y_shift, _ = _predict(champion, shift, rule)
        false_alarm = (y_shift != "ham").mean()
        print(f"false alarm rate on local ham: {false_alarm:.4f}")
        print(pd.Series(y_shift).value_counts().to_string())
        test_row["sg_false_alarm_rate"] = float(false_alarm)

    # --- Singapore scam set ---------------------------------------------
    # The other half of the local picture: how many real local scams does it
    # catch? Hand-collected and small, so it is reported per scam type and
    # message by message, not as a single headline number.
    if "sg_scams" in splits and len(splits["sg_scams"]):
        test_row.update(_evaluate_sg_scams(champion, splits["sg_scams"], rule))

    # --- persist --------------------------------------------------------
    joblib.dump(champion, CFG.artifacts_dir / "model.joblib")
    board.to_csv(CFG.reports_dir / "leaderboard_val.csv", index=False)
    with open(CFG.reports_dir / "test_result.json", "w", encoding="utf-8") as fh:
        json.dump({"champion": champion_name, **test_row}, fh, indent=2, default=str)
    ev.confusion(test["label"], y_pred).to_csv(CFG.reports_dir / "confusion_test.csv")

    print(f"\nsaved model to {CFG.artifacts_dir / 'model.joblib'}")
    return board


if __name__ == "__main__":
    run()
    sys.exit(0)
