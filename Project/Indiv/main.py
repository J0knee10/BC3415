"""Smishing Triage — the whole pipeline in one place.

This is the orchestrator. It contains no logic of its own: every step below is
a call into ``src/``, in the order the project actually runs. Read it top to
bottom to see how the system fits together, then open the module a step names
to see how that step works.

    python main.py                      run every stage in order
    python main.py --stage train        run one stage
    python main.py --demo "message"     classify a single message
    python main.py --skip-download      reuse data already on disk

Two pipelines live here. Stages 1-4 are the **training pipeline**: they run
offline and end with a model file. Stage 5 is the **serving path**: it loads
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
    missing rather than failing, and the pipeline runs on whatever is present.
    """
    banner(1, "DOWNLOAD", "four corpora + Tesseract language data → data/raw/")

    from src.download import check_manual, fetch_auto, fetch_tessdata

    fetch_auto()
    fetch_tessdata()
    if not check_manual():
        print(
            "\n  Note: without the Mendeley sets there is no smishing class, "
            "so the pipeline\n  degrades to a two-class spam filter."
        )


# --- Stage 2 ------------------------------------------------------------
def stage_preprocess() -> None:
    """Unify, normalise, deduplicate, split.

    The three decisions that matter are all here: deduplicate *before*
    splitting (the corpora overlap heavily), keep two text representations
    (word features want clean text, character features want the raw digits and
    punctuation), and bar LLM-generated rows from validation and test.
    """
    banner(2, "PREPROCESS", "data/raw/ → data/processed/{train,val,test,shift_sg}.csv")

    from src.preprocess import build

    build()


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
    """Does the LLM-generated augmentation actually help?

    Most of the training smishing examples are synthetic, which raises a
    question the headline metric cannot answer: is the model learning smishing,
    or the generator's style? This fits the same pipeline with and without
    them and compares on real messages only.
    """
    banner(4, "ABLATION", "is the synthetic augmentation earning its place?")

    from src.ablation import run

    run()


# --- Stage 5 ------------------------------------------------------------
def stage_demo(message: str | None = None) -> None:
    """The serving path — what happens to one message at run time.

    ``predict()`` is the entry point everything downstream uses: this script,
    the OCR path, the Telegram bot. The LLM second stage is gated inside
    ``scam_type.enrich()``, so it runs only on a smishing verdict and
    legitimate messages never leave the machine.
    """
    banner(5, "SERVE", "predict() → verdict, confidence, red flags → optional enrichment")

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
    stage_demo()

    print(f"\n{'=' * 72}\n  done — `python -m app.bot` to run the Telegram front end\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
