# Agentic AI Swing Trader: Presentation Outline

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
