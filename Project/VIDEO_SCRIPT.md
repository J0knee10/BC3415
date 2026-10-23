# Smishing Triage: video script

Audience: the CFO and CTO together. Target: under 5:00. That's about 4:00 of speech (595 words at 150 a minute), plus pasting and the Gemini replies. Cut the Gemini waits in editing.

Coverage over depth: each section makes one point with one number, and the detail goes in "If someone asks" at the bottom. Model and evaluation numbers come from `reports/` and the writeup. The token and latency figures were measured on 24 Oct and are not in the reports (see the notes at the bottom).

---

## Before you hit record

- [ ] Start the bot from `Indiv/`: `..\..\.venv\Scripts\python.exe -m app.bot`. Check the log says "scam-type enrichment on".
- [ ] Open Telegram Desktop on the chat with @bc3415_smishing_bot. Clear old messages.
- [ ] Have the four test messages (below) in a notepad, and `Indiv/reports/mock_screenshot.png` ready to drag in.
- [ ] Open these tabs: the writeup PDF (§1 opening paragraph, §1 pilot table, §9 review table), `config.yaml` (`cost_matrix`), `src/scam_type.py` (`enrich()`), and a terminal in `Indiv/` showing the end of an earlier `main.py` run.
- [ ] **Never open `Indiv/.env` on screen.** It holds the real keys.
- [ ] Don't re-run `main.py` just before recording. If you do, check that `Indiv/reports` still matches `Smishing_Triage/reports`.

```
Your DBS account is suspended. Verify at http://dbs-secure.co/login
WIN a FREE iPhone! Txt WIN to 85233 now. T and Cs apply
Eh you reaching already? I order first ah
Hi mum this is my new number, my phone broke. Can you PayNow me $500 urgently
```

---

## 1. The problem (0:00–0:35)

**Screen:** writeup §1, opening paragraph with reference [1].

> "Hi, I'm Jonathan. This is Smishing Triage, a scam checker for a Singapore bank's customers. Scams cost Singapore 913 million dollars last year, about 24,500 dollars a case, and over 9,000 cases began on WhatsApp or Telegram.
>
> A spam filter lumps marketing in with phishing, but one wastes three seconds and the other can empty an account. So there are three classes, and the model is judged on scams caught, not on accuracy. It follows the brief's pattern: a text verdict, an image channel, and a second stage that names the problem."

## 2. Live demo (0:35–1:50)

**Screen:** Telegram. Paste, wait, point at the reply.

- **DBS:** "A fake DBS link. It's called a likely scam at 98%, and it shows the words that triggered that, so the customer learns what to look for next time. Below that, an LLM names the scam type: bank impersonation."
- **iPhone:** "Marketing spam. Annoying, but not an alarm."
- **Eh you reaching:** "A normal message. It never says 'safe', only 'no scam signals found'. A false all-clear is worse than no answer."
- **Hi mum:** "The hard case: a scam with no link. The model thinks it's legitimate, but there's a question mark. A person should check it. More on that in a moment."
- **Drag in the screenshot:** "Screenshots work too. OCR reads the text, and then the same model judges it."

## 3. Where the human is, and why there (1:50–2:30)

**Screen:** `config.yaml` at `cost_matrix`, then the §9 table.

> "So where's the human? Not at a flat 'below 60% confidence' rule, because mistakes don't cost the same. A two-minute analyst review costs about S$1.67. A missed scam costs about S$67 in expected loss.
>
> So when the bot would say 'no scam signals', a scam chance above 2.5% sends it to a person. Spam and scam verdicts get their own lines from the same costs. 'Hi mum' had a 4% scam chance, so it goes to review.
>
> On the test set that's 10% of messages, including every scam the model missed. The S$67 is my least certain number, so the writeup shows every alternative."

## 4. Why a trained model first, then the LLM (2:30–3:10)

**Screen:** `src/scam_type.py`, at the line in `enrich()` that returns early unless the verdict is smishing.

> "Why a trained model first, and the LLM second? It does save tokens. Only about a quarter of checks reach the LLM, so the bill drops from at most about 12 US dollars a year to 3. That's trivial either way.
>
> The real savings are elsewhere. Speed: a fifth of a second, not 6 to 8. Privacy: unflagged messages never go to an AI provider. And a probability I can price for the review rule, which an LLM doesn't give me.
>
> It isn't a funding question. If an LLM beats this model on local data, it can sit behind the same predict()."

## 5. Why the numbers are honest (3:10–3:50)

**Screen:** terminal with the end of the earlier `main.py` run, then `config.yaml`.

> "How do I know these numbers are honest? My first version claimed 95%. But scam campaigns send near-identical copies, and my test set had copies of the training data. Now near-copies are grouped and kept on one side of the split.
>
> The honest result is 76% of scams caught. The interval is wide, 56 to 89%, because there are only 43 distinct campaigns. 0.2% of Singaporeans' personal chats are wrongly flagged. The model and its test figures rebuild from one config file and one command. 19 tests check it, including that the LLM gate holds."

## 6. Recommendation (3:50–4:30)

**Screen:** writeup §1 pilot table and go/no-go list.

> "My recommendation is that it's not ready for customers. It catches 60% of real local scams. It also flagged all 5 genuine bank and SingPost notices it saw, and that alone is a no-go. Both problems come from foreign training data.
>
> So the ask is a three-month pilot, about S$9,000, mostly to label local messages. It passes only if it catches 80% of local scams and flags at most 1% of the bank's real alerts. The running cost is people, not tokens: about S$10,000 to 14,000 a year of review time. Thank you."

---

## If someone asks (not in the video)

**Human review**
- **Where the S$67 comes from:** S$24,500 average loss × about 0.27% (about 1 in 370) of missed scams turning into a loss. 1.67 / 67 ≈ 2.5%. The 0.27% was fixed under the previous split with test results in view and not revisited. The 1% used in the benefit case would put the review cost at 0.14 and send about 43% of test messages to review. §9 shows every candidate (0.14 to 2.0).
- **The other verdicts:** a "spam" verdict stands alone only if the model is about 95% sure it isn't a scam. A "likely scam" verdict needs it to be about 75% sure the message isn't legitimate.
- **Why 20 for a missed scam?** It's a judgement call. The review line depends on the ratio of review cost to missed-scam cost (0.5 / 20 = 1/40), and the S$ figures pin that ratio down.
- **Singapore result with review:** the model catches 36 of 60 local scams. With review, 54 of 60 are caught or seen by a person.
- **The other human points (designed, not built):** reviewed messages would become labelled training data, a person signs off a retrained model, and the customer makes the final call.

**Two steps**
- **Token basis:** measured at 123 input + 78 output tokens per call (24 Oct). Priced at US$0.30 / US$2.50 per million tokens, the highest Flash-Lite rate found on Google's pricing page. The code calls the `gemini-flash-lite-latest` alias, so the real rate may be lower. 50,000 checks a year all through the LLM ≈ US$11.60. Gated, about 24% of checks reach the LLM, so about US$3.
- **Why Flash-Lite:** naming a scam type from a short message is a simple task, so the smallest, fastest model is enough. It also fits the free tier. A bank deployment would use a paid or self-hosted model, so customer messages aren't used for training; the pilot budget includes this.
- **Is a 2.5% line too low if reviews cost money?** No. Each review costs S$1.67 against S$67 for a missed scam, so 2.5% is the break-even point. The S$10,000–14,000 a year is large only next to the token bill, not next to the estimated S$2.9m of losses avoided. If review capacity were capped, you would raise the review cost and the line would move up.
- **Privacy, precisely:** in the demo every message passes through Telegram. In a deployment it would be the bank's own channel. Either way, only flagged messages are sent to Google.
- **Why not an LLM-only classifier:** it isn't measured on this task, its answers vary between runs, and it would send every personal message to a provider.
- **Why use an LLM at all:** there's no public labelled data for scam types. Spot check: 30 of 36 caught local scams matched the hand labels.

**Technical**
- **Preprocessing:** cross-corpus dedup, URLs, phone numbers and amounts turned into placeholders, and character n-grams on the raw text, so "DB5" and "acc0unt" are still caught.
- **predict()** is the single entry point. The bot, OCR, notebook and demo all go through it.
- **"One command":** the model and evaluation results rebuild from `python main.py --skip-download`. The Gemini spot check and the background figures are the exceptions (writeup §11).
