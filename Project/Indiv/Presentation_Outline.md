# Individual Project: Presentation Outline

> **Status (2026-09-23): changing direction, not decided yet.** The Agentic AI Swing Trader outline is kept at the bottom as an archive. The two options still being considered are below.

## Direction Change

### Why change

- The brief asks for a **trained text classification model** (e.g. Naive Bayes, BERT) built with Python (Scikit-learn, PyTorch, HuggingFace). In the swing trader, the LLM agents do the classification, so no classifier is actually built or trained.
- **"Accuracy and performance of models"** is graded, so the project needs a **public labelled dataset** to report precision, recall, F1 and a confusion matrix. Without one, most of the time goes into labelling data.
- **Image classification is optional,** but the brief's retail case is built on combining text and images. Doing it counts towards "creativity in combining text insights".
- **To check with the lecturer:** the brief's retail case is "applicable to both options". Confirm we're allowed to choose our own business case. If not, Option 1 is closest to the brief.

### How the demo works (applies to both options)

The model is just a function: text or an image goes in, and a label with a confidence score comes out. No live connection to WhatsApp or a company database is needed. The training dataset is used offline to train and evaluate the model. At demo time, the input comes from the user through a thin interface.

```
[Input channel] → [Preprocess] → [Model] → [Decision rule] → [Output channel]
 web form / bot    clean, OCR     label+conf   flag / approve    screen / reply / dashboard
```

The grade is mostly about the middle three boxes. The input and output channels are only there to make the demo convincing.

### Option 1: Returns and Refund Triage (e-commerce sellers)

- **Problem:** sellers read every return or refund request by hand. The product decides whether to auto-approve, ask for more information, or escalate.
- **Text model:** complaint message → wrong item / damaged / not as described / changed mind.
- **Image model (optional):** uploaded photo → damaged vs. intact, or whether it matches the listing.
- **Combined decision:** text and image agree it's damaged → auto-refund. They disagree → flag for a person to review.
- **Customer journey:** a return request form (message plus photo) → an instant status shown to the customer → a **seller triage dashboard** listing requests with labels and flags. SQLite or a CSV file is enough to link the two screens.
- **Datasets:** Amazon Reviews 2023 (McAuley Lab; some reviews include photos) for text, MVTec AD for defect images. The defect images are only a stand-in for customer product photos.
- **Strengths:** it's closest to the brief's retail case, uses both text and images, trains the text model on real data, and ends with a clear business action.
- **Weaknesses:** the demo has less "wow" than Option 2, and the image data only approximates the real use case.

### Option 2: Scam Message Checker (consumers, Singapore)

- **Problem:** SMS and WhatsApp scams (job, investment, impersonation, phishing) are a major problem in Singapore, and users can't easily tell whether a message is a scam.
- **Text model:** message → ham / spam / smishing, possibly extended to scam type.
- **Image part:** screenshot → OCR → text model, so users can just send a screenshot. This is OCR rather than true image classification. A possible extension is an image classifier that detects fake bank or login pages in screenshots.
- **Customer journey: "forward to check"** (this is how Singapore's CheckMate WhatsApp bot works). WhatsApp chats can't be read directly because they are end-to-end encrypted and there's no API for them. Instead:
  1. The user gets a suspicious message.
  2. They forward the message, or a screenshot of it, to the bot.
  3. The bot replies, e.g. *"⚠️ Likely scam: job scam (92%). Red flags: 'easy money', 'Telegram', 'deposit'."* The red flags come from LIME or SHAP.
- **Ways to deliver it:**

| Option | Effort | Notes |
|---|---|---|
| Gradio / Streamlit web page (paste text or upload a screenshot) | Very low | Enough for the grade |
| **Telegram bot** (`python-telegram-bot`) | Low, about 50–80 lines | Free, no approval process, runs on a laptop. Best demo: forward a scam on the phone and show the reply live |
| WhatsApp bot (Meta WhatsApp Cloud API) | Medium to high | Needs a Meta Business account and a registered number. Too much hassle for this project |
| Automatic SMS filtering (native Android app or iOS SMS filter extension) | High | Out of scope |

- **Optional:** log each check to SQLite and show a "scam trends" chart.
- **Datasets:** UCI SMS Spam Collection (5,574 messages, ham/spam), Mendeley SMS Phishing Dataset (2022; ham / spam / smishing).
- **Strengths:** the most natural end-user experience, the strongest demo, real text data, and relevant to Singapore.
- **Weaknesses:** it doesn't match the brief's retail case (lecturer approval needed), the image part is OCR rather than image classification, and the datasets are not Singapore-specific.

### Options considered and dropped

- **#5 Car insurance claim triage** (claim text plus car damage photos, CarDD dataset). Dropped because there's no public dataset of claim *texts*. The descriptions would have to be synthetic, which weakens the text classifier, and that is the part the brief grades most.
- Others looked at: fake job posting detector (EMSCAD), fake review detector, content moderation (Jigsaw Toxic), support ticket router (Banking77), bank complaint routing (CFPB), SME expense categorisation (SROIE), and financial news sentiment with a trained model (FinancialPhraseBank).

### Project shape (either option)

1. **Preprocessing pipeline:** cleaning, deduplication, a stratified split, and handling class imbalance. This is graded on its own.
2. **Model ladder:** start with TF-IDF plus Naive Bayes or Logistic Regression as a baseline, then fine-tune DistilBERT or RoBERTa. Optionally compare against a zero-shot LLM from the old swing trader work. Report metrics for every model.
3. **Explainability:** LIME or SHAP to show which words drove each prediction.
4. **Image model (optional):** fine-tune ResNet or EfficientNet, or use CLIP zero-shot. Add a rule or scoring layer that merges text and image outputs into a decision.
5. **Usability:** a reusable `predict()` module, a config file for labels and paths, and a Gradio, Streamlit or Telegram front end for the demo video.

### Next steps

- [ ] Confirm with the lecturer that we can choose our own business case (this affects Option 2)
- [ ] Check the datasets for each option: size, labels, class balance, how recent they are, licence
- [ ] Choose Option 1 or Option 2
- [ ] Rewrite this outline for the chosen option

---

# Archive: Agentic AI Swing Trader (previous direction)

**Format:** Option A (Coding-Based), framed as a pitch to the CTO
**Length:** ~5 minute screen-recorded video

## Deliverables

| # | Deliverable | Notes |
|---|---|---|
| 1 | Python code / project | Comment the code clearly. "Explainability and commentary in code" and "usability and reusability" are both graded. |
| 2 | Text classification model | Covered by the **Sentiment Agent**, which classifies market text. |
| 3 | Screen-recorded video, 3–5 minutes | Demo plus a few framing slides at the start and end. |

> **Key framing:** the sentiment agent *is* the text classifier. OpenClaw runs it, but it still reads market text and labels it (bullish / bearish / neutral). Keep this front and centre, because it is what the module grades.

---

## 1. Hook and Problem (0:00–0:30)

- Swing traders have to follow too many instruments, news items and sentiment shifts to do it by hand.
- Good setups are missed or spotted late, and emotion leaks into entries and exits.
- **The question for the CTO:** *"Can a team of AI agents do the first pass of research and trade selection, running locally for close to zero per-call cost?"*

## 2. Solution Overview (0:30–1:00)

- An agentic swing-trading system: 4 specialised agents on local Qwen models, orchestrated by **n8n** and connected through **OpenClaw**.
- Paper trades on **OANDA** (FX/CFDs) and **moomoo** (equities).
- Why it's worth funding:
  - **Private:** strategies and account data never leave your hardware.
  - **Cheap:** no API bills.
  - **Auditable:** every agent's reasoning is logged.
  - **Modular:** agents can be swapped or upgraded independently.

## 3. Architecture (1:00–2:00): Key Slide

```
[Scraper / Opportunity Finder]  Qwen 3.5 4B, wide funnel
            ↓
[Account telemetry checks]  balance, open positions, exposure
            ↓
   ┌────────┴────────┐
[Sentiment Agent]  [Financial Data Agent]     ← run in parallel
 TEXT CLASSIFICATION   price / technicals / fundamentals
 bullish / bearish / neutral
   └────────┬────────┘
[Final Decision Maker]  → TRADE (entry, SL, TP) or REJECT
            ↓
[Guardrails]  e.g. reward:risk must be at least 1:1
            ↓
[OANDA / moomoo paper-trading APIs]
```

- **n8n** is the orchestrator: scheduling, routing and retries.
- **OpenClaw** connects the agents and their tools.
- **Why separate agents:** each job gets its own prompt, the risk of one model hallucinating an entire trade on its own is smaller, and each agent's output can be checked separately.

## 4. Where Text Classification Fits (2:00–2:45): What the Module Grades

- **Input:** headlines, news and social text the scraper picked up for a ticker.
- **Classification:** the sentiment agent labels it (e.g. bullish / bearish / neutral, with confidence and a reason).
- **Use:** that label is one of the two inputs to the decision maker, so text classification is directly turned into a trade decision. This is the "creativity in combining text insights" point.
- **Why an LLM rather than Naive Bayes or FinBERT:**
  - Reads context and sarcasm, and handles text it hasn't seen before
  - Needs no labelled training set
  - Explains its label
  - Trade-off: slower and less consistent

## 5. Demo (2:45–3:45)

Record at home. Suggested sequence:

1. The **n8n workflow canvas**, to show the 4 agents and the flow.
2. Trigger one run, or replay a logged run: scraper candidates → sentiment output → data analysis output.
3. **Decision maker output:** one **accepted** trade with SL/TP and one **rejected** trade, ideally one blocked by the 1:1 R:R guardrail. Showing the system saying no builds a lot of trust.
4. The trade appearing in the **OANDA or moomoo paper account**.

## 6. Results So Far (3:45–4:15)

- Paper-trading period, number of trades, win rate, average R:R and P&L, taken from the OANDA and moomoo dashboards.
- Be upfront: *"Early testing phase, small sample, not statistically meaningful yet."* CTOs trust candour more than inflated numbers.

## 7. Limitations and Risks (4:15–4:35)

- **Missed signals.** In classification terms this is low **recall** at the funnel stage: the small 4B scraper drops good opportunities.
- **No backtesting yet**, so there's no historical validation.
- **The local models are small,** so their judgement is limited and output can vary between runs.
- **Hallucination risk.** Mitigations: guardrails, paper trading only, and a separate check at the decision stage.

## 8. Roadmap and Funding Request (4:35–5:00)

| Phase | Timeline | What |
|---|---|---|
| **Now** | Done | 4-agent pipeline running live on paper accounts |
| **Phase 1** | 1–2 months | Backtesting harness; log and score sentiment accuracy |
| **Phase 2** | 2–3 months | Cloud or larger models for the scraper and decision maker to fix missed signals; custom performance dashboard |
| **Phase 3** | 3–6 months | Small real-capital pilot with hard drawdown limits; more data sources |

- **With funding:** cloud models (or a GPU to run larger Qwen models) for better recall and judgement, plus a backtesting engine and a dashboard.
- **Close:** *"The architecture is proven end to end. Funding goes into model quality and validation, not building from scratch."*

---

## To Collect Before Recording (Home PC)

- [ ] Screenshots or a screen recording of the **n8n workflow**
- [ ] **Model details:** Qwen model and size for each of the other 3 agents, and what runs them (Ollama, LM Studio, etc.)
- [ ] The sentiment agent's **labels** and a sample output
- [ ] **Paper-trading stats** from the OANDA and moomoo dashboards, plus start dates
- [ ] One **accepted** and one **rejected** decision log for the demo
- [ ] **Strongly recommended, about 30 minutes:** hand-label 30–50 past sentiment outputs and compute accuracy. This gives a number for the "accuracy and performance of models" criterion (e.g. *"the sentiment agent agreed with my labels 78% of the time"*).
