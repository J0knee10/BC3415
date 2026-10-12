# Smishing Triage

A three-class message classifier that separates **legitimate messages (`ham`)**,
**commercial spam (`spam`)**, and **smishing (`smishing`)** — phishing delivered
by SMS — served as a *forward-it-to-check* Telegram bot for Singapore users.

A binary ham-vs-spam filter puts a marketing blast and a credential-harvesting
message in the same class. For a user, one wastes three seconds and the other
costs them thousands of dollars. Separating them is what this project is for.

For the problem framing, results and limitations, see the technical writeup,
`Smishing_Triage_Writeup.pdf`. This file is the developer's guide.

---

## Results

Champion model: **character n-gram TF-IDF + calibrated LinearSVC**.

| Metric | Test |
|---|---|
| Accuracy | 0.9731 |
| Macro F1 | 0.9040 |
| **Smishing recall** | **0.8911**  (95% CI 0.826 – 0.947) |
| Smishing precision | 0.8571 |
| False alarms on Singapore ham | 0.26%  (23 / 8,942) |
| Real Singapore scams caught | 63%  (38 / 60; 72% warned as spam or smishing) |

Validation ladder: Naive Bayes 0.9004 → word LogReg 0.9258 → word+char LogReg
0.9279 → **char SVM 0.9453** (macro F1).

Almost all remaining error is the spam↔smishing boundary. Ham is near-perfect.

These numbers come from a template-aware split (see *Design decisions*). An
earlier row-level split reported smishing recall of 0.954; about a quarter of
its test smishing messages had a near-identical template variant in training.

---

## Setup

Python 3.11 or later, in a virtual environment:

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### Credentials (both optional)

| Variable | Enables | Without it |
|---|---|---|
| `GEMINI_API_KEY` | Scam-type enrichment ([AI Studio](https://aistudio.google.com/apikey), free tier) | Enrichment is skipped; the classifier still answers |
| `TELEGRAM_BOT_TOKEN` | The bot front end (from @BotFather) | `app.bot` refuses to start and explains how to get one |

The OCR path additionally needs the Tesseract **binary** on the system
(Windows: `winget install UB-Mannheim.TesseractOCR`); the English language
data is fetched into `tessdata/` by `src.download`.

---

## Quickstart

The trained model (`artifacts/model.joblib`) and the processed splits
(`data/processed/`) ship with the project, so these run straight away:

```bash
python -m src.predict "Your DBS account is locked. Verify at http://bit.ly/x9"
python -m src.train        # retrain from data/processed and regenerate reports/
python -m pytest tests
```

To rebuild everything from the raw corpora:

```bash
python -m src.download     # fetch datasets + Tesseract language data
python -m src.preprocess   # unify, normalise, deduplicate, split
python -m src.train        # fit the ladder, select on validation, test once
python -m src.predict "Your DBS account is locked. Verify at http://bit.ly/x9"
```

Two of the four datasets (both Mendeley sets) sit behind a bot check and cannot
be scripted. `src.download` prints the page URL and destination folder for each.
**The pipeline runs on whatever is present** — without them it degrades to a
two-class spam filter rather than failing.

---

## How it works

Two pipelines share one set of modules: a **training pipeline** that runs
offline and produces a model file, and a **serving path** that loads it.

### Training (offline, run once)

```
  download.py          datasets.py           preprocess.py            train.py
┌──────────────┐   ┌─────────────────┐   ┌──────────────────┐   ┌───────────────┐
│ UCI      zip │   │ one loader per  │   │ normalise        │   │ 4-rung ladder │
│ NUS      xml │──▶│ source, all     │──▶│ deduplicate      │──▶│ select on val │
│ Mendeley csv │   │ emitting        │   │ split            │   │ test ONCE     │
│ (by hand)    │   │ text/label/src  │   │                  │   │               │
└──────────────┘   └─────────────────┘   └──────────────────┘   └───────┬───────┘
     data/raw/                             data/processed/              │
                                           train/val/test/shift_sg      ▼
                                                              artifacts/model.joblib
```

### Serving (every message)

```
    text ──────────────────────┐
                               ▼
  image ──▶ ocr.py ──▶ text ──▶ predict.py ──▶ Prediction(label, confidence, red_flags)
                                   │
                                   └── label == "smishing"? ──▶ scam_type.py ──▶ Gemini
                                                                 (enrichment only)
```

`app/bot.py` is the only thing that touches Telegram. It calls `scam_type.enrich()`,
which calls `predict()` and then gates the LLM call on the verdict.

---

## Entry points

| Command | What it does |
|---|---|
| `python -m src.download` | Fetches UCI, NUS and Tesseract data; reports what must be downloaded by hand |
| `python -m src.preprocess` | Builds `train/val/test/shift_sg.csv` in `data/processed/` |
| `python -m src.train` | Fits all four rungs, selects on validation, evaluates test once, writes `artifacts/model.joblib` |
| `python -m src.ablation` | Does LLM-generated augmentation actually help? (validation only) |
| `python -m src.predict "<message>"` | One verdict on the command line |
| `python -m src.ocr <image>` | Extracts text from a screenshot, then classifies it |
| `python -m app.bot` | Runs the Telegram bot |
| `python -m pytest tests` | Checks the guarantees the evaluation depends on (no template crosses a split, the LLM gate holds) |
| `python build_notebook.py` | Regenerates `notebooks/walkthrough.ipynb` from the modules |

**The programmatic entry point is `predict()`:**

```python
from src.predict import predict

result = predict("Your parcel is held at customs. Pay at http://sgpost-clear.co/pay")
result.label        # 'smishing'
result.confidence   # 0.96
result.scores       # {'ham': 0.027, 'smishing': 0.962, 'spam': 0.011}
result.red_flags    # ['http://sgpost-clear.co/pay', 'customs']  (LIME)
result.is_threat    # True
print(result.describe())
```

Nothing downstream needs to know how the model was built or which rung won.

---

## Module map

| Module | Responsibility |
|---|---|
| `config.py` | Loads `config.yaml`; the single source of paths, labels and the cost matrix |
| `download.py` | Dataset acquisition; distinguishes scriptable from manual sources |
| `datasets.py` | One loader per corpus, all emitting `text` / `label` / `source` |
| `preprocess.py` | Normalisation, deduplication, splitting |
| `features.py` | Word, character and combined vectorisers |
| `evaluate.py` | Metrics, cost, bootstrap CIs, error analysis |
| `train.py` | The model ladder, selection, and the single test evaluation |
| `ablation.py` | The synthetic-augmentation experiment |
| `predict.py` | The reusable serving entry point |
| `scam_type.py` | LLM second stage, gated on a smishing verdict |
| `ocr.py` | Screenshot → text |

`app/` is the application layer, kept separate from the ML library:

| Module | Responsibility |
|---|---|
| `app/bot.py` | Telegram front end — the only module that talks to Telegram |

`app/` imports `src.predict` and never reaches past it into the model.

---

## Configuration

Everything tunable lives in [`config.yaml`](config.yaml) — label names and
order, all paths, split ratios and seed, normalisation placeholder tokens, the
cost matrix, and bootstrap settings. No module hardcodes a path or a label.

Changing `labels.names` changes the integer encoding, every confusion-matrix
axis, and the cost matrix together. The pipeline derives the classes actually
present from the data, which is why it runs as a two-class filter when the
Mendeley sets are absent without any code change.

---

## Design decisions worth knowing

**Smishing recall is the headline metric, not accuracy.** The corpus is ~83%
ham, so a model predicting ham for everything scores 83% accuracy and is
useless. `config.yaml` carries a cost matrix (a missed smishing message costs
20, a false alarm on ham costs 2) and `evaluate.expected_cost` reports against
it.

**The operating point is a stated choice, made with the evidence in view.**
`src.train` scores two decision rules on validation before touching test —
argmax, and the minimum-expected-cost rule under the matrix — and writes
`reports/operating_point_val.csv`. The matrix prefers min-cost (smishing
recall 0.95 → 0.99), but precision falls from 0.91 to 0.78 and false alarms on
Singaporean ham rise from 0.26% to 1.77%. The matrix prices a false scam alarm
at 2 and has no term for user trust, so `config.yaml` serves argmax.

**Deduplication happens before splitting.** The corpora are built on each
other — Mendeley's smishing set is UCI plus re-labelling, and UCI absorbed part
of the NUS corpus. Deduplication removes 13,595 of 31,852 rows. Skip it and the
same messages land in train and test.

**The split is made over templates, not rows.** Scam campaigns reuse one
template with a different phone number or prize amount each time, and exact
deduplication keeps every variant. Splitting by row put 27% of the test
smishing messages next to a sibling in training. `preprocess.split()` groups
messages by their normalised text, so every variant of a template lands in one
split, and drops synthetic and shift-set rows that share a template across the
boundary.

**Every corpus is read as UTF-8.** Reading them as latin-1 turned each "£" into
"Â£" in over a thousand training messages — a character-model cue that no real
incoming message carries.

**303 messages carry conflicting labels across corpora**, almost all
`uci=spam` vs `mendeley=smishing` on identical text — UCI's spam class
conflates marketing with scams and Mendeley separates them. `SOURCE_PRIORITY`
in `preprocess.py` resolves them to the finer label. They are written to
`data/processed/label_conflicts.csv` because they are the interesting cases.

**Two text columns, deliberately.** `text_clean` (normalised, lowercased,
placeholder tokens) feeds word features; raw `text` feeds character features,
because digits, case and punctuation are exactly what obfuscated smishing
abuses. Every pipeline is a `ColumnTransformer` over both. The character
vectoriser sets `lowercase=False` to keep case; on validation that lifted
macro F1 from 0.936 to 0.945.

**Synthetic data is structurally barred from evaluation.** The LLM-generated
Mendeley set is forced into the training split by `preprocess.split()`; it
cannot reach validation or test. (Its ham rows all duplicate real Mendeley ham
and are removed by deduplication, so what survives is generated spam and
smishing — 84% of the training smishing class.) The ablation shows it lifts
validation smishing recall from 0.911 to 0.949 (+3.8pp), at the cost of five
more false alarms in 8,942 Singaporean messages.

**The NUS corpus is held out as a separate shift set**, not mixed in. It is
ham-only, so it answers one sharp question: how often does the model cry wolf
on ordinary Singaporean messages?

**The test set is touched once**, by the selected model only, at the end of
`train.run()`. The ablation deliberately evaluates on validation for the same
reason.

**The LLM never makes the decision.** `scam_type.enrich()` gates on the trained
model's verdict, so the enrichment runs only on messages already flagged as
smishing — which also keeps legitimate messages off the network. The scam-type
label is unevaluated and no metric depends on it.

---

## Known limitations

- Red flags come from LIME, which is sampling-based: a flag list can include a
  common word ("Your", "now") when it co-occurs with the real cue, and flags
  explain the model's behaviour, not ground truth about the message.
- **Local scams are the weak spot.** On 60 real scams sent to people in
  Singapore (`data/raw/sg_scams/`, evaluation only, 51 transcribed by hand from
  SPF and news screenshots), the model catches 63%. Scams with a link are caught
  29 times in 32; chat-style scams without one (Carousell buyers, job
  recruiters) 9 times in 28. All 5 genuine local SingPost and bank OTP messages
  in that set were flagged, because the training ham is personal chat with
  almost no transactional SMS. Per-message verdicts are in
  `reports/sg_scams_predictions.csv`. Fixing this needs local training data
  of both kinds, left for a version 2: the public data for these message types
  is very small compared with the corpora used here.
- OCR errors land *upstream* of the classifier, so a misread character becomes
  a feature the model never saw in training.
- The DistilBERT rung is specified but not built; it needs `transformers` and
  `torch` (~2.5 GB).
- On the Gemini free tier, Google may use prompts and outputs to improve its
  models. Only messages already flagged as scams are sent.
