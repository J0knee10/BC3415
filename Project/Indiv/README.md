# Smishing Triage

A three-class message classifier that separates **legitimate messages (`ham`)**,
**commercial spam (`spam`)**, and **smishing (`smishing`)** — phishing delivered
by SMS — served as a *forward-it-to-check* Telegram bot for Singapore users.

A binary ham-vs-spam filter puts a marketing blast and a credential-harvesting
message in the same class. For a user, one wastes three seconds and the other
costs them thousands of dollars. Separating them is what this project is for.

For the assignment framing, scope boundaries and rationale, see
[`PROJECT_BRIEF.md`](PROJECT_BRIEF.md). This file is the developer's guide.

---

## Results

Champion model: **character n-gram TF-IDF + calibrated LinearSVC**.

| Metric | Test |
|---|---|
| Accuracy | 0.9784 |
| Macro F1 | 0.9234 |
| **Smishing recall** | **0.9541**  (95% CI 0.911 – 0.990) |
| False alarms on Singapore ham | 0.22%  (20 / 8,948) |

Validation ladder: Naive Bayes 0.8740 → word LogReg 0.9019 → word+char LogReg
0.9125 → **char SVM 0.9298** (macro F1).

Almost all remaining error is the spam↔smishing boundary. Ham is near-perfect.

---

## Setup

Everything runs from the shared virtual environment at `../../.venv`; nothing
is installed to the global interpreter.

```bash
# From the Indiv/ directory. On Windows use ../../.venv/Scripts/python.exe
../../.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### Credentials (both optional)

| Variable | Enables | Without it |
|---|---|---|
| `GEMINI_API_KEY` | Scam-type enrichment ([AI Studio](https://aistudio.google.com/apikey), free tier) | Enrichment is skipped; the classifier still answers |
| `TELEGRAM_BOT_TOKEN` | The bot front end (from @BotFather) | `app.bot` refuses to start and explains how to get one |

The OCR path additionally needs the Tesseract **binary** on the system; the
English language data is fetched into `tessdata/` by `src.download`.

---

## Quickstart

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

**The programmatic entry point is `predict()`:**

```python
from src.predict import predict

result = predict("Your parcel is held at customs. Pay at http://sgpost-clear.co/pay")
result.label        # 'smishing'
result.confidence   # 0.96
result.scores       # {'ham': 0.027, 'smishing': 0.962, 'spam': 0.011}
result.red_flags    # ['http://sgpost-clear.co/pay', 'Your', 'customs.']
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

**Deduplication happens before splitting.** The corpora are built on each
other — Mendeley's smishing set is UCI plus re-labelling, and UCI absorbed part
of the NUS corpus. Deduplication removes 13,595 of 31,852 rows. Skip it and the
same messages land in train and test.

**303 messages carry conflicting labels across corpora**, almost all
`uci=spam` vs `mendeley=smishing` on identical text — UCI's spam class
conflates marketing with scams and Mendeley separates them. `SOURCE_PRIORITY`
in `preprocess.py` resolves them to the finer label. They are written to
`data/processed/label_conflicts.csv` because they are the interesting cases.

**Two text columns, deliberately.** `text_clean` (normalised, lowercased,
placeholder tokens) feeds word features; raw `text` feeds character features,
because digits, case and punctuation are exactly what obfuscated smishing
abuses. Every pipeline is a `ColumnTransformer` over both.

**Synthetic data is structurally barred from evaluation.** The LLM-generated
Mendeley set is forced into the training split by `preprocess.split()`; it
cannot reach validation or test. The ablation shows it lifts smishing recall
+9.1pp without raising false alarms on real Singapore ham.

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

- The leave-one-out explainer in `predict.explain_tokens` returns nothing on
  saturated predictions — dropping one word from a 99%-confident message does
  not move the score. LIME or SHAP is the fix.
- OCR errors land *upstream* of the classifier, so a misread character becomes
  a feature the model never saw in training.
- The DistilBERT rung is specified but not built; it needs `transformers` and
  `torch` (~2.5 GB).
- On the Gemini free tier, Google may use prompts and outputs to improve its
  models. Only messages already flagged as scams are sent. See §9 of the brief.
