# Smishing Triage

A three-class message classifier that separates **legitimate messages (`ham`)**,
**commercial spam (`spam`)**, and **smishing (`smishing`)** — phishing delivered
by SMS — served as a *forward-it-to-check* Telegram bot, pitched in the
writeup as a checker for a Singapore bank's customers.

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
| Accuracy | 0.9434 |
| Macro F1 | 0.8131 |
| **Smishing recall** | **0.7615**  (95% CI 0.563 – 0.893, resampled by cluster) |
| Smishing precision | 0.7830 |
| Smishing passed as legitimate | 7 of 109 (all 7 sent to human review) |
| Brier score (calibration) | 0.0789 |
| False alarms on Singapore ham | 0.21%  (18 / 8,547) |
| Real Singapore scams caught | 60%  (36 / 60; 68% warned as spam or smishing) |
| Sent to human review (test) | 10.0%, including all 26 scams the bot missed |

Validation macro F1: Naive Bayes 0.790 · word LogReg 0.807 · word+char LogReg
0.832 · **char SVM 0.806**. The four are within noise of each other; the char
SVM is the only one that flags under 1% of Singaporean ham (0.21%, against
1.2–2.6% for the others), which is the selection rule.

Validation recall (0.619) is lower than test (0.761). Over six repeated cluster
splits of the non-test data, real-only recall ranges from 0.75 to 0.90 and
averages 0.80 (`reports/ablation_repeated.csv`), so the single validation
split, whose 63 scams sit in only 27 clusters, is unusually hard. The wide
test interval is the honest summary: 109 test scams in 43 clusters.

Most remaining error is the spam↔smishing boundary; 7 test scams passed as
legitimate, and the review rule sends all 7 to a person.

These numbers come from a split with no template and no near-copy shared
between training, validation and test, made without deleting any real message
(see *Design decisions*).

---

## Setup

Python 3.11 or later, in a virtual environment:

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt        # or requirements-lock.txt for exact versions
```

`artifacts/model.joblib` is a pickled scikit-learn pipeline; load it with the
scikit-learn version in `requirements-lock.txt` (1.9.0).

### Credentials (both optional)

| Variable | Enables | Without it |
|---|---|---|
| `GEMINI_API_KEY` | Scam-type enrichment ([AI Studio](https://aistudio.google.com/apikey), free tier) | Enrichment is skipped; the classifier still answers |
| `TELEGRAM_BOT_TOKEN` | The bot front end (from @BotFather) | `app.bot` refuses to start and explains how to get one |

Put them in a `.env` file at the project root, which is gitignored and loaded
automatically by every entry point:

```bash
cp .env.example .env            # then fill in the values
```

A variable already set in the shell takes precedence over the file.

The OCR path additionally needs the Tesseract **binary** on the system
(Windows: `winget install UB-Mannheim.TesseractOCR`); the English language
data is fetched into `tessdata/` by `src.download`.

---

## Quickstart

The trained model (`artifacts/model.joblib`), the processed splits
(`data/processed/`) and the raw corpora (`data/raw/`) ship with the submission
(they are gitignored in the repository), so these run straight away:

```bash
python -m src.predict "Your DBS account is locked. Verify at http://bit.ly/x9"
python -m src.train        # retrain from data/processed and regenerate reports/
python -m pytest tests
```

To rebuild everything from the raw corpora:

```bash
python main.py             # every stage in order: download → preprocess → train
                           # → ablation → splits → robustness → review → demo
python main.py --skip-download   # the same, reusing data already on disk
```

or stage by stage:

```bash
python -m src.download     # fetch datasets + Tesseract language data
python -m src.preprocess   # unify, deduplicate, normalise, split
python -m src.train        # fit the ladder, select on validation, test once
python -m src.predict "Your DBS account is locked. Verify at http://bit.ly/x9"
```

Two of the four datasets (both Mendeley sets) sit behind a bot check and cannot
be scripted; they are included in `data/raw/`. To fetch them yourself,
`src.download` prints the page URL and destination folder for each. Without
both Mendeley sets there is no smishing class, so `src.preprocess` stops
before writing anything rather than replace the three-class model;
`--allow-two-class` builds a ham/spam-only model on purpose.

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
| `python main.py` | Runs every stage below in order (`--stage <name>` for one, `--demo "<message>"` to classify one) |
| `python -m src.download` | Fetches UCI, NUS and Tesseract data; reports what must be downloaded by hand |
| `python -m src.preprocess` | Builds `train/val/test/shift_sg/sg_scams.csv` and `label_conflicts.csv` in `data/processed/` |
| `python -m src.train` | Fits all four rungs, selects on validation, evaluates test once, writes `artifacts/model.joblib` |
| `python -m src.ablation` | Does the LLM-generated corpus help? Validation and six repeated cluster splits (test unused) |
| `python -m src.split_study` | Random vs. delete vs. cluster splits on the same messages: what the test score means under each |
| `python -m src.robustness` | Constructed probes: leetspeak, link form, harmless links, chat-style scams |
| `python -m src.review` | The human-review rule at several review costs, on every evaluation set |
| `python -m src.predict "<message>"` | One verdict on the command line |
| `python -m src.ocr <image>` | Extracts text from a screenshot, then classifies it |
| `python -m src.scam_type --evaluate` | Compares the Gemini scam-type label with the hand labels on the Singapore scams the model caught (needs `GEMINI_API_KEY`) |
| `python -m app.bot` | Runs the Telegram bot |
| `python -m pytest tests` | Checks the guarantees the evaluation depends on (no template or near-copy shared across training, validation and test, the LLM gate holds) |
| `python build_notebook.py` | Regenerates and executes `notebooks/walkthrough.ipynb` from the modules (`--no-execute` to only write it) |

**The programmatic entry point is `predict()`:**

```python
from src.predict import predict

result = predict("Your parcel is held at customs. Pay at http://sgpost-clear.co/pay")
result.label        # 'smishing'
result.confidence   # 0.96
result.scores       # {'ham': 0.014, 'smishing': 0.956, 'spam': 0.031}
result.red_flags    # ['http://sgpost-clear.co/pay', 'customs']  (LIME)
result.is_threat    # True
result.needs_review # False  (True when a person should check it)
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
| `ablation.py` | The LLM-generated-corpus experiment, single and repeated splits |
| `split_study.py` | The split-method experiment: random, delete and cluster splits compared |
| `robustness.py` | Constructed perturbation probes (behaviour, not accuracy) |
| `review.py` | Human in the loop: which verdicts a person should check |
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
cost matrix, the near-duplicate threshold, whether synthetic data is used, the
selection guardrail, the human-review cost, and bootstrap settings. No module hardcodes a top-level path;
label names come from the config, except that `ham` is treated as the
"no warning" class.

Changing `labels.names` changes every confusion-matrix axis and the cost
matrix together. (The model itself keeps string labels; its `classes_` are
alphabetical.) The pipeline derives the classes actually
present from the data, which is why `--allow-two-class` can build a two-class
filter when the Mendeley sets are absent without any code change.

---

## Design decisions worth knowing

**Smishing recall is the headline metric, not accuracy.** The test set is ~83%
ham, so a model predicting ham for everything scores 83% accuracy and is
useless. `config.yaml` carries a cost matrix (a missed smishing message costs
20, a false scam alarm on a legitimate message costs 2) and `evaluate.expected_cost` reports against
it.

**The operating point is a stated choice, made with the evidence in view.**
`src.train` scores two decision rules on validation before touching test —
argmax, and the minimum-expected-cost rule under the matrix — and writes
`reports/operating_point_val.csv`. The matrix prefers min-cost (smishing
recall 0.62 → 0.90), but precision falls from 0.83 to 0.63 and false alarms on
Singaporean ham triple (0.21% → 0.64%). The matrix prices a false scam alarm
at 2 and has no term for user trust, so `config.yaml` serves argmax. All 18
scams min-cost would add on validation are sent to human review instead.

**Deduplication happens before splitting.** The corpora are built on each
other — Mendeley's smishing set is UCI plus re-labelling, and UCI absorbed part
of the NUS corpus. Deduplication removes 13,595 of 31,852 rows. Skip it and the
same messages land in train and test.

**The split is made over near-copy clusters, not messages.** Scam campaigns
reuse one template with a different phone number or prize amount each time, or
reword a phrase ("it has been resent" → "it ingest been resent"), and exact
deduplication keeps every variant. In an earlier version of the pipeline,
splitting by message put 27% of the test smishing messages next to a training
message with the same template (about two-thirds counting near-copies). `preprocess.near_copy_clusters()` links two messages when they
share a template or their character n-gram cosine similarity is 0.7 or more on
the raw *or* the number-blanked text (TF-IDF weights fitted once on the whole
corpus; most pairs inspected at that level were the same message with a word or
number changed). `preprocess.cluster_split()` then assigns whole clusters at
random, stratified by label (scikit-learn's `StratifiedGroupKFold`): still a
random split, with the campaign as the unit. Near-copies always land on the
same side, so nothing real is deleted and validation and test are kept apart
too. The 6,007 real messages form 4,956 clusters (largest 40).
`src.split_study` shows why: a message-level random split trains on as many
scams but tests two-thirds of its scams on near-twins of training messages,
and the previous method (split by template, then delete near-copies from
training) left only 199 real training scams instead of 374. On real
Singapore scams the three methods are within seed noise of each other, so the
cluster split is chosen on principle, not on that number. Generated rows,
which only ever join training, are still dropped if they nearly copy a
held-out message, and the same check keeps the Singapore shift and scam sets
clear of training messages. A test re-checks the real splits with independent
weights.

**Every corpus is read as UTF-8.** Reading them as latin-1 turned each "£" into
"Â£" in over two thousand corpus messages — a
character-model cue that no real incoming message carries.

**303 messages carry conflicting labels**, almost all `uci=spam` vs
`mendeley=smishing` on identical text — UCI's spam class conflates marketing
with scams and Mendeley separates them. `SOURCE_PRIORITY` in `preprocess.py`
resolves conflicts by source, and Mendeley ranks above UCI, so the finer label
wins. 52 conflicts also sit inside a single corpus; there the row that sorts
first is kept, which leaves 16 messages that one source called smishing
labelled spam (12 train, 2 validation, 2 test). They are all written to
`data/processed/label_conflicts.csv` because they are the interesting cases.

**Two text columns, deliberately.** `text_clean` (normalised, lowercased,
placeholder tokens) feeds word features; raw `text` feeds character features,
because digits, case and punctuation are exactly what obfuscated smishing
abuses. Each rung's `ColumnTransformer` picks the column it needs: word rungs
read `text_clean`, the char SVM reads only `text`, and the combined rung reads
both. The character vectoriser keeps case (`lowercase=False`) for shouted
calls to action and brand spellings.

**The LLM-generated corpus is excluded from training.** The Mendeley
"balanced" set is mostly reworded copies of the other corpora. On the single
validation split it adds +9.5 points of smishing recall, but over six repeated
cluster splits of the non-test data it shows no reliable benefit (−1.7 points
on average: better in 1, tied in 1, worse in 4; +2.1 under the previous split;
`src.ablation`), so the served model trains on real messages only
(`train.use_synthetic: false`); the rows stay in `train.csv` so the ablation
can measure them.

**Selection has a false-alarm guardrail.** The four rungs are within about 0.04
macro F1 of each other (63 validation smishing messages; one message moves
recall by 1.6 points) but differ up to twelvefold on how often they flag
ordinary Singaporean messages. `src.train` picks the best validation macro F1
among rungs flagging at most 1% of the shift set
(`selection.max_sg_false_alarm`). The cap was set under an earlier split with
that split's validation results in view; because the shift set informs
selection, its false-alarm rate is a guardrail, not an untouched estimate.

**Confidences are calibrated on in-distribution text.** The SVM is wrapped in
sigmoid calibration. On test, the Brier score is 0.079, and messages given
~0.94 smishing probability are smishing 90% of the time; the middle bins are
small (20–31 messages) and noisier (`reports/calibration_test.csv`). On
out-of-distribution text, such as real local scams, a confident "no scam
signals" is not reliable.

**What the model relies on.** `reports/top_features.csv` lists the strongest
n-grams per class. For smishing they are digit fragments of UK premium-rate
numbers (`08…`, `09…`, `00`) and `http`: the model learned what a scam SMS in these
corpora looks like, which is why it transfers poorly to Singapore scams.

**The NUS corpus is held out as a separate shift set**, not mixed in. It is
ham-only, so it answers one sharp question: how often does the model cry wolf
on ordinary Singaporean messages? It is less of a shift than it looks: UCI's
ham was partly drawn from the NUS corpus, so the training ham already includes
Singaporean student chat. The test that matters for local generalisation is
the Singapore scam set.

**The selected model is evaluated on test once**, at the end of
`train.run()`, and no model choice depends on the test set. The split study and
the review analysis also report test figures, as evidence about method, and
the review cost was fixed with an earlier split's test figures in view (below).
The ablation evaluates on validation only.

**A person checks what the bot should not answer alone.** `src/review.py`
applies a cost-sensitive form of Chow's reject option: a message goes to human
review when the expected cost of its verdict standing alone exceeds the cost of
a review (`review.cost: 0.5` in `config.yaml`, 1/40 of a missed scam). Not a
flat confidence cut-off, because the mistakes are not equally expensive: a
"no scam signals" verdict with a 3% scam chance costs 20 × 0.03 = 0.6 and
goes to a person, while a 55/45 legitimate-vs-spam split costs at most 0.45 and
does not. On test it sends 10.0% of messages to review, including all 26
missed scams. Every review cost in `review.grid` is reported on every set
(`reports/human_review.csv`). The cost was fixed under the previous split with
that split's validation and test figures both in view, and not revisited; the
table shows how the figures move with the choice.

**The LLM never makes the decision.** `scam_type.enrich()` gates on the trained
model's verdict, so the enrichment runs only on messages already flagged as
smishing — which also keeps legitimate messages off the network. No metric
depends on the scam-type label; as a spot check, it matches the hand label on
30 of the 36 Singapore scams the model caught, with one call timing out
(`reports/scam_type_eval.csv`).

---

## Known limitations

- Red flags come from LIME, which is sampling-based. Function words ("your",
  "our") and bare numbers are filtered out, but a flag list can still include
  a weak word that co-occurs with the real cue, and flags explain the model's
  behaviour, not ground truth about the message.
- **Small smishing class.** After deduplication, 546 real smishing messages
  remain: 374 to train on, 63 for validation, 109 for test. The 95% confidence
  interval on test recall is 0.56–0.89. It resamples near-copy clusters rather
  than messages, because the 109 test scams come from only 43 clusters and
  copies of one campaign are not independent evidence.
- **Local scams are the weak spot.** On 60 real scams sent to people in
  Singapore (`data/raw/sg_scams/`, evaluation only, 51 transcribed with AI
  assistance from SPF and news screenshots), the model catches 60% and warns on
  68%. Scams with a link (one the URL pattern recognises) are caught 26 times
  in 32; chat-style scams without one (Carousell buyers, job recruiters) 10
  times in 28. All 5 genuine local SingPost and bank OTP messages in that set
  were flagged, because the
  training ham is personal chat with almost no transactional SMS. Per-message
  verdicts are in
  `reports/sg_scams_predictions.csv`. Fixing this needs local training data
  of both kinds, left for a version 2: the public data for these message types
  is very small compared with the corpora used here.
- **False reassurance.** About a third of real local scams (19 of 60) get "no
  scam signals found", often with high confidence. The bot says this is not a
  guarantee, and the review rule sends 13 of those 19 to a person, but a user
  may still read it as an all-clear.
- **Robustness is partial** (`reports/robustness_probes.csv`, 7 of 12 probes
  pass). Leetspeak spellings (`DB5`, `acc0unt`) are still caught. Three
  failures are link-related (a scam link without `http://` passes as
  legitimate, so does the same lure asking for a card number with no link, and
  a harmless news link is called a scam) and two are chat-style scams with no
  link at all.
- Selection rests on one validation split of 63 smishing messages with no
  hyperparameter search; the differences between the rungs are within noise.
- OCR errors land *upstream* of the classifier, so a misread character becomes
  a feature the model never saw in training.
- A transformer model was not attempted; the ladder stops at linear models
  on TF-IDF features.
- On the Gemini free tier, Google may use prompts and outputs to improve its
  models. Only messages already flagged as scams are sent.
