# Smishing Triage — Project Brief

**Module:** BC3415 AI in Accounting & Finance
**Assignment:** Individual Assignment — Real-World Applications of Text Classification (45% of module grade)
**Submission route:** Option A (coding-based). Code plus a 3–5 minute screen-recorded walkthrough. No slide deck required.

---

## 1. What the project is

A three-class message classifier that separates **legitimate messages, commercial spam, and smishing** (phishing delivered by SMS), delivered as a *forward-it-to-check* bot for Singapore users. The model explains which words drove its decision, and the evaluation measures how performance degrades on local Singaporean text.

The distinction between spam and smishing is the point of the project. A binary ham-vs-spam classifier puts a marketing blast and a credential-harvesting message in the same class. For a user, one wastes three seconds and the other costs them thousands of dollars. Separating them changes what the system is for: not an inbox tidier, a fraud control.

### Why this, in business terms

Scams cost people in Singapore about S$913.1 million across 37,308 cases in 2025, down from about S$1.11 billion in 2024 ([SPF Annual Scam and Cybercrime Brief 2025](https://www.police.gov.sg/-/media/SPF/Advisories/Scams/Annual-Scam-and-Cybercrime-Brief-2025.pdf)), and S$410.6 million in the first half of 2026 alone ([SPF Mid-Year Brief 2026](https://www.police.gov.sg/-/media/SPF/Media-Room/Statistics/Mid-Year-Scam-and-Cybercrime-Brief-2026/Mid-Year-Scam-and-Cybercrime-Brief-2026.pdf)). Messaging is a primary delivery channel. Telcos and banks filter at the network layer, but messages still get through, and a user has no quick way to check a specific one. The product is a second opinion on demand: forward a suspicious message, get a verdict with a confidence score and the specific red flags that triggered it, in seconds.

---

## 2. Scope

### In scope

- **Three-class text classifier:** `ham` / `spam` / `smishing`
- **Model ladder** with metrics reported at every rung (§4)
- **Smishing recall as the headline metric**, not overall accuracy — a missed smishing message is the expensive error, a false alarm on a marketing text costs nothing
- **Explainability:** LIME or SHAP token attributions, surfaced to the user as plain-language red flags
- **Singapore domain-shift evaluation** using the NUS SMS Corpus as local ham
- **Screenshot → OCR → classifier**, so a user can forward an image rather than retyping
- **LLM second stage** for scam-type enrichment on messages already flagged as smishing (§6)
- **Telegram bot** front end for the demo

### Out of scope

State these explicitly in the writeup — a drawn boundary reads as judgment, an undrawn one reads as an omission.

- Email phishing — different feature space (headers, SPF/DKIM/DMARC alignment, attachments)
- Phishing *website* detection from URL or page content
- Voice call and in-person scams
- Live WhatsApp interception. WhatsApp is end-to-end encrypted with no read API; forward-to-check is the standard workaround and is how Singapore's CheckMate bot operates
- Automatic on-device SMS filtering (native Android app or iOS SMS filter extension)

---

## 3. Data

| Dataset | Rows | Role | Access |
|---|---|---|---|
| Mendeley SMS Phishing (`f45bkkt8pr`) | 5,971 — 4,844 ham / 489 spam / 638 smishing | **Core 3-class training set.** The only public corpus that separates spam from smishing | Direct download |
| UCI SMS Spam Collection | 5,574 — 4,827 ham / 747 spam | Additional ham and spam; the standard benchmark to report against | Direct; `pip install ucimlrepo` |
| NUS SMS Corpus | 55,835 English messages from Singaporeans | **Singapore ham** — the local-shift test set | GitHub `WING-NUS/nus-sms-corpus` |
| Mendeley Balanced Spam/Smishing (`vmg875v4xs`) | 10,191 | LLM-generated. **Train-side augmentation only — never in the test set** | Direct download |
| DIFrauD (HF `difraud/difraud`) | 95,854 across 7 domains; Phishing 15,272, SMS 6,574 | Optional transfer/pretraining source; MIT licence | Direct |

### The binding constraint

**638 smishing messages.** This is the bottleneck class, and the brief names it rather than letting a marker discover it. After deduplication and a template-aware split, the test set holds 101 smishing examples, so a single misclassification moves recall by a full point. Mitigations, each of which earns marks in its own right:

- Stratified splits and class weighting, documented as part of the preprocessing pipeline
- **Character n-grams**, which handle the obfuscation smishing relies on (`DB5`, `acc0unt`, shortened-link skeletons) better than word features
- LLM-balanced augmentation on the training side only, reported as an **ablation** — whether it helped is itself a result
- Confidence intervals on the smishing metrics, not a bare point estimate

### Deduplication

UCI and the Mendeley sets overlap. Deduplicate across all sources **before** splitting, or the same message lands in both train and test and inflates every number. Then split by *template* (normalised text), not by row: scam campaigns reuse one template with a different number or amount each time, and a row-level split put 27% of test smishing beside a sibling in training.

---

## 4. Method

### Preprocessing pipeline

Load and unify label schemes across sources → normalise text → deduplicate → stratified train/validation/test split. Keep two text representations: a cleaned one for word features, and the **raw** text for character features, since digits and punctuation carry signal for obfuscated messages.

Normalisation replaces URLs, phone numbers and currency amounts with placeholder tokens rather than deleting them — their *presence* is predictive even when the specific value is not.

### Model ladder

Report accuracy, per-class precision/recall/F1, macro F1, and a confusion matrix at every rung.

1. **TF-IDF + Multinomial Naive Bayes** — the floor. Fast, and named directly in the assignment brief.
2. **TF-IDF + Logistic Regression** — linear baseline with interpretable coefficients.
3. **Character n-gram TF-IDF + Linear SVM** — the obfuscation handler. Expect this to be the strongest classical model.
4. **Word + character TF-IDF + Logistic Regression** — both representations at once.
5. **Fine-tuned DistilBERT** — contextual model, top of the ladder. *Specified, not built* (§12).

Select on **validation** macro F1, with smishing recall as the tiebreak. Any threshold or ensemble weight is learned on validation and locked before the test set is touched, **once**.

### Error analysis

After each rung, inspect the smishing false negatives with the lowest predicted probability. What the model misses should drive what the next rung does differently. This is what "accuracy and performance of models" looks like when done properly.

### Evaluation framing

Build a small cost matrix: a missed smishing message is expensive, spam-flagged-as-ham is free, ham-flagged-as-smishing is a minor annoyance. Choose the operating point against that matrix and say so. Reporting accuracy alone on a class-imbalanced fraud problem is the mistake this framing exists to avoid.

What happened when this was done: `src.train` scores argmax and the minimum-expected-cost rule on validation and on the Singapore shift set (`reports/operating_point_val.csv`). The matrix prefers min-cost: smishing recall rises from 0.95 to 0.99. But precision falls from 0.91 to 0.78, and false alarms on Singaporean ham rise from 0.26% to 1.77%. The matrix has no term for that, so the served rule is argmax, set in `config.yaml`. This is a reportable finding: a cost matrix is only as good as the costs it leaves out.

---

## 5. Explainability

LIME or SHAP token attributions on the selected model, rendered for the user as red flags in plain language:

> ⚠️ **Likely smishing (92%)** — flagged on: *"verify"*, *"account suspended"*, *"bit.ly"*

Two purposes: it satisfies the explainability criterion, and it makes the product genuinely more useful than a bare verdict, because a user who sees *why* learns to spot the next one unaided.

---

## 6. LLM second stage (scam-type enrichment)

Scam *type* labels — job, investment, delivery, banking impersonation, love scam — **do not exist as public labelled message data**. Those taxonomies live in analysis papers, not in a downloadable label column. Training a scam-type classifier would require self-labelled or synthetic data, undermining the one component the rubric weighs most.

Instead, a **zero-shot LLM classifier runs only on messages the trained model has already flagged as smishing**, and names a likely scam type in the user-facing reply. It is an enrichment layer, explicitly unevaluated, sitting strictly downstream of the graded model.

It runs on the **Gemini API via Google AI Studio**, whose free tier (~1,500 requests/day on the Flash models) is far more than this project consumes, so the whole project costs nothing to run. NTU provides students with Google AI Studio and Vertex AI access under its Google partnership; a personal free-tier key works identically. Set `GEMINI_API_KEY`.

The gate is enforced in `scam_type.enrich()` rather than left to the caller, so legitimate messages never reach the network at all.

State it plainly in the writeup and the video: *"The trained classifier makes the decision. The LLM only labels what kind of scam it looks like, and that label is not part of the evaluation."* The architecture — a cheap, measurable model gating an expensive, unmeasurable one — is a defensible engineering choice and worth a sentence of justification.

---

## 7. Deliverables

| # | Deliverable | Notes |
|---|---|---|
| 1 | Python codebase | Commented throughout. A reusable `predict()` entry point, a config file for labels and paths, no hardcoded paths. Usability and reusability are graded |
| 2 | Trained 3-class classifier | With saved artifacts, so the demo loads rather than retrains |
| 3 | Technical writeup | Option A does not require slides, but both strong reference submissions shipped a written document alongside the code |
| 4 | Screen-recorded video, 3–5 min | See §8 |

---

## 8. Demo

Record the Telegram bot on a phone, screen-mirrored:

1. Forward a real marketing SMS → **spam**, low concern
2. Forward a real smishing SMS → **smishing**, with confidence and red flags
3. Forward a **screenshot** of one → OCR path, same verdict
4. Show an ordinary personal message correctly passing as **ham** — the system does not just flag everything. **Do not use a bank OTP or SingPost notice here:** all 5 genuine ones in the Singapore test set were flagged (§12). Name that limitation in the video instead of hiding it

Pre-test every demo message with `python -m src.predict` before recording. Parcel and government-impersonation scams with a link are the reliable smishing examples (caught 16 of 16 in the Singapore set).

Bookend with a short framing of the problem and a closing view of the metrics table and confusion matrix.

---

## 9. Risks and limitations

To state in the writeup rather than have a marker raise them:

- **Small smishing class** (638 messages) limits confidence in the headline metric
- **Datasets are not Singapore-specific.** The NUS corpus supplies local ham, but no public *local smishing* corpus exists, so smishing examples skew US/UK/India in phrasing and brand references
- **Concept drift.** Scam phrasing changes faster than any static training set; deployment would need periodic retraining and drift monitoring
- **Adversarial evasion.** Attackers obfuscate deliberately; character n-grams help but do not solve it
- **OCR quality** varies with screenshot resolution and dark mode, introducing errors upstream of the classifier
- **Privacy.** Forwarded messages contain personal content. The bot logs only a label, a confidence and a length — never the message body. Two residual issues worth naming rather than hiding: the classifier itself runs locally, but the scam-type enrichment sends flagged messages to Google, and on the **free tier Google may use prompts and outputs to improve its models**. Only messages already classified as scams are sent, never legitimate ones. A billed account or a locally hosted model (Ollama) would close the gap, and that trade-off is worth a sentence in the writeup: a scam-checking product that ships users' messages to a third party has a tension in it

---

## 10. Repository layout

```
Indiv/
├── PROJECT_BRIEF.md                      this file
├── Text_Classification_Assignment.docx   the assignment brief as issued
├── config.yaml                           labels, paths, splits, cost matrix
├── requirements.txt
├── data/
│   ├── raw/                              downloaded datasets (gitignored)
│   └── processed/                        unified, deduplicated splits (gitignored)
├── src/
│   ├── config.py                         loads config.yaml; single source of paths
│   ├── download.py                       fetches UCI + NUS + tessdata; checks the manual sets
│   ├── datasets.py                       per-source loaders → unified schema
│   ├── preprocess.py                     normalise, deduplicate, split
│   ├── features.py                       word / character / combined vectorisers
│   ├── evaluate.py                       metrics, cost, bootstrap CIs, error analysis
│   ├── train.py                          the model ladder and selection
│   ├── ablation.py                       synthetic-augmentation ablation
│   ├── predict.py                        reusable predict() entry point
│   ├── scam_type.py                      LLM second stage, gated on a smishing verdict
│   └── ocr.py                            screenshot → text
├── app/
│   └── bot.py                            Telegram front end (the application)
├── notebooks/                            exploration and figures for the writeup
├── artifacts/                            trained model (gitignored)
├── tessdata/                             Tesseract language data (gitignored)
└── reports/                              leaderboard, confusion matrix, results (gitignored)
```

### Running it

```bash
python -m src.download                    # UCI, NUS and Tesseract data; instructions for Mendeley
python -m src.preprocess                  # normalise, deduplicate, split
python -m src.train                       # fit the ladder, select on validation, test once
python -m src.ablation                    # does synthetic augmentation help?
python -m src.predict "message text"      # single verdict
python -m src.ocr screenshot.png          # OCR then classify
python -m app.bot                         # the demo front end
```

Everything runs from `../../.venv`. Two optional capabilities degrade rather than
fail when their credentials are absent: without `GEMINI_API_KEY` the scam-type
enrichment is skipped and the classifier still answers; without
`TELEGRAM_BOT_TOKEN` the bot refuses to start and says how to get one.

The two Mendeley sets sit behind a bot check and cannot be scripted. `src.download`
prints the page URL and the destination folder for each; the pipeline runs on
whatever is present, so it degrades to a two-class spam filter if they are missing.

---

## 11. Assignment criteria mapping

| Criterion | Where it is met |
|---|---|
| Accuracy and performance of models | §4 model ladder, per-class metrics, validation-locked selection, error analysis |
| Data preprocessing pipeline | §4 preprocessing; §3 deduplication and class imbalance handling |
| Explainability and commentary in code | §5 LIME/SHAP; commented codebase |
| Creativity in combining text insights | §6 LLM second stage; §4 word plus character feature combination; OCR input path |
| Usability and reusability of code | §7 `predict()` entry point, config-driven, Telegram bot front end |

---

## 12. Open items

- [ ] Add the DistilBERT rung — needs `transformers` and `torch` (~2.5 GB install)
- [x] Swap the leave-one-out explainer for LIME or SHAP. The current probe returns
      nothing on saturated predictions, because dropping one word from a 99%-confident
      message does not move the score
- [ ] Get a `TELEGRAM_BOT_TOKEN` from @BotFather and run the bot end to end on a phone
- [ ] Get a `GEMINI_API_KEY` (NTU Google account or https://aistudio.google.com/apikey),
      confirm the model id in `scam_type.MODEL` is current, and check the enrichment
      against real messages
- [ ] Tune the spam↔smishing boundary — it is where almost all remaining error sits
      (the cost-matrix operating point was tried; see §4 Evaluation framing)
- [x] Collect a small Singapore smishing set (30–50 real messages, evaluation only).
      The shift set measures false alarms on local ham but nothing measures misses on
      local scams, and a typical SingPost parcel scam is currently classified as ham
- [x] Install the Tesseract binary (not on this machine) or drop the screenshot step
      from the demo
- [x] Replace the placeholder scam-loss figure in §1 with a cited number from the
      SPF annual scams statistics
- [x] Technical writeup (Claude Docs; exported to `Smishing_Triage_Writeup.pdf`)
- [ ] Version 2 (future work, not pursued): local *training* data — genuine
      transactional SMS from banks and SingPost as ham, conversation-stage scams as
      smishing. Not pursued because public data for these message types is very small
      compared with the rest (mostly screenshots, often Chinese, bank notifications
      rarely published). Collected separately; the Singapore scam set must stay unseen
- [ ] Record the demo video
