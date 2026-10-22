"""Smishing Triage — the whole pipeline in one place.

This is the orchestrator. It contains no logic of its own: every step below is
a call into ``src/``, in the order the project actually runs. Read it top to
bottom to see how the system fits together, then open the module a step names
to see how that step works.

    python main.py                      run every stage in order
    python main.py --stage train        run one stage
    python main.py --demo "message"     classify a single message
    python main.py --skip-download      reuse data already on disk

Two pipelines live here. Stages 1-7 are the **training pipeline** and its
checks: they run offline and end with a model file. Stage 8 is the **serving
path**: it loads
that file and answers messages. The Telegram bot (``python -m app.bot``) is
the serving path with a chat interface in front of it.
"""

from __future__ import annotations

import argparse
import sys


def banner(n: int | str, title: str, why: str = "") -> None:
    """Print a stage header. The 'why' line is the point of this file."""
    print(f"\n{'=' * 72}")
    print(f"  STAGE {n} — {title}")
    if why:
        print(f"  {why}")
    print("=" * 72)


# --- Stage 1 ------------------------------------------------------------
def stage_download() -> None:
    """Get the four corpora onto disk.

    UCI and NUS download automatically. Both Mendeley sets sit behind a bot
    check, so they are fetched by hand once; this step reports which are
    missing rather than failing; preprocessing then stops unless a two-class
    model is asked for explicitly.
    """
    banner(1, "DOWNLOAD", "four corpora + Tesseract language data → data/raw/")

    from src.download import check_manual, fetch_auto, fetch_tessdata

    fetch_auto()
    fetch_tessdata()
    if not check_manual():
        print(
            "\n  Note: without the Mendeley sets there is no smishing class; "
            "preprocessing will\n  stop rather than overwrite the three-class "
            "model (use --allow-two-class to override)."
        )


# --- Stage 2 ------------------------------------------------------------
def stage_preprocess() -> None:
    """Unify, deduplicate, normalise, split.

    The three decisions that matter are all here: deduplicate *before*
    splitting (the corpora overlap heavily), keep two text representations
    (word features want clean text, character features want the raw digits and
    punctuation), and bar LLM-generated rows from validation and test.
    """
    banner(2, "PREPROCESS", "data/raw/ → data/processed/{train,val,test,shift_sg}.csv")

    from src.preprocess import build

    build(allow_missing_target="--allow-two-class" in sys.argv[1:])


# --- Stage 3 ------------------------------------------------------------
def stage_train() -> None:
    """Fit the model ladder, pick a winner, spend the test set once.

    Four rungs, cheapest first. Each is scored on validation and its smishing
    misses are printed, because what one rung misses is what the next rung has
    to fix. Only the selected model touches the test set, and only once.
    """
    banner(3, "TRAIN", "4-rung ladder → artifacts/model.joblib")

    from src.train import run

    run()


# --- Stage 4 ------------------------------------------------------------
def stage_ablation() -> None:
    """Does the LLM-generated corpus help, or should it stay excluded?

    The served model trains on real messages only (``train.use_synthetic`` in
    config.yaml). This fits the champion pipeline with and without the
    generated rows and compares them on real validation messages, which is the
    evidence for that setting.
    """
    banner(4, "ABLATION", "real-only training vs. adding the LLM-generated corpus")

    from src.ablation import repeated, run

    run()
    repeated()


# --- Stage 5 ------------------------------------------------------------
def stage_splits() -> None:
    """Does the way the data is split change what the test score means?

    The same real messages split three ways (each message at random, by
    template with near-copies deleted, by near-copy cluster), the champion
    design trained on each, for three seeds. Evidence for the method in
    ``preprocess.split``. It informed that choice of method; it does not
    choose or tune the served model.
    """
    banner(5, "SPLIT STUDY", "random vs. delete vs. cluster splits")

    from src.split_study import run

    run()


# --- Stage 6 ------------------------------------------------------------
def stage_robustness() -> None:
    """Does the verdict survive the perturbations scammers actually use?

    Constructed variants of a few messages: leetspeak spellings, a link with
    and without ``http://``, harmless links, chat-style scams. Reported as
    behaviour, not accuracy, in ``reports/robustness_probes.csv``.
    """
    banner(6, "ROBUSTNESS", "obfuscation, link form, harmless links")

    from src.robustness import run

    run()


# --- Stage 7 ------------------------------------------------------------
def stage_review() -> None:
    """When should a person look instead of the bot answering alone?

    A message goes to human review when the expected cost of the bot's verdict
    standing alone, under the cost matrix, exceeds the cost of a review.
    Reported for several review costs in ``reports/human_review.csv``.
    """
    banner(7, "HUMAN REVIEW", "which verdicts a person should check")

    from src.review import run

    run()


# --- Stage 8 ------------------------------------------------------------
def stage_demo(message: str | None = None) -> None:
    """The serving path — what happens to one message at run time.

    ``predict()`` is the entry point everything downstream uses: this script,
    the OCR path, the Telegram bot. The LLM second stage is gated inside
    ``scam_type.enrich()``, so it runs only on a smishing verdict and
    legitimate messages never leave the machine.
    """
    banner(8, "SERVE", "predict() → verdict, confidence, red flags → optional enrichment")

    from src import scam_type
    from src.predict import predict

    samples = (
        [message]
        if message
        else [
            # One per class, so the demo shows the distinction the project exists for.
            "Eh you reaching already? I order first ah",
            "WIN a FREE iPhone! Txt WIN to 85233 now. T and Cs apply",
            "Your DBS account is suspended. Verify at http://dbs-secure.co/login",
        ]
    )

    for text in samples:
        print(f"\n  > {text}")
        prediction = predict(text)
        # enrich() re-checks the verdict itself; passing it in avoids a second
        # call to the model.
        _, scam = scam_type.enrich(text, prediction)
        for line in scam_type.describe(prediction, scam).splitlines():
            print(f"    {line}")

    if not scam_type.available():
        print(
            "\n  (scam-type enrichment off — set GEMINI_API_KEY to enable it; "
            "the classifier runs either way)"
        )


STAGES = {
    "download": stage_download,
    "preprocess": stage_preprocess,
    "train": stage_train,
    "ablation": stage_ablation,
    "splits": stage_splits,
    "robustness": stage_robustness,
    "review": stage_review,
    "demo": stage_demo,
}


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(
        description="Smishing Triage — run the pipeline end to end.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--stage", choices=list(STAGES), help="run one stage only")
    parser.add_argument("--demo", metavar="MESSAGE", help="classify one message and exit")
    parser.add_argument(
        "--skip-download", action="store_true", help="reuse data already on disk"
    )
    parser.add_argument(
        "--allow-two-class",
        action="store_true",
        help="build a ham/spam-only model if the Mendeley smishing data is missing",
    )
    args = parser.parse_args(argv[1:])

    if args.demo:
        stage_demo(args.demo)
        return 0

    if args.stage:
        STAGES[args.stage]()
        return 0

    # The full run, in order.
    if not args.skip_download:
        stage_download()
    stage_preprocess()
    stage_train()
    stage_ablation()
    stage_splits()
    stage_robustness()
    stage_review()
    stage_demo()

    print(f"\n{'=' * 72}\n  done — `python -m app.bot` to run the Telegram front end\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
