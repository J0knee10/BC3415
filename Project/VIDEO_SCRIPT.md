# Smishing Triage: video script

Audience: the CFO and CTO together. Target: under 5:00. That's about 4:20 of speech (650 words at 150 a minute), plus pasting and the Gemini replies. Cut the Gemini waits in editing.

Coverage over depth: each section makes one point with one number, and the detail goes in "If someone asks" at the bottom. Model and evaluation numbers come from `reports/` and the writeup. The token and latency figures were measured on 24 Oct and are not in the reports (see the notes at the bottom).

---

## Before you hit record

- [ ] Start the bot from `Indiv/`: `..\..\.venv\Scripts\python.exe -m app.bot`. Check the log says "scam-type enrichment on".
- [ ] Open Telegram Desktop on the chat with @bc3415_smishing_bot (https://t.me/bc3415_smishing_bot). Clear old messages.
- [ ] Have the four test messages (below) in a notepad, and `Indiv/reports/mock_screenshot.png` ready to drag in.
- [ ] Open `Smishing_Triage_Slides.pptx` (in `Indiv/` and `Smishing_Triage/`). Its speaker notes hold every line below. Slide 6 is blank on purpose: the Telegram recording goes over it. To rebuild the deck, run `node build.js` in `Project/slides_src/` (needs `pptxgenjs`).
- [ ] **Never open `Indiv/.env` on screen.** It holds the real keys.
- [ ] Don't re-run `main.py` just before recording. If you do, check that `Indiv/reports` still matches `Smishing_Triage/reports`.

```
Your DBS account is suspended. Verify at http://dbs-secure.co/login
WIN a FREE iPhone! Txt WIN to 85233 now. T and Cs apply
Eh you reaching already? I order first ah
Hi mum this is my new number, my phone broke. Can you PayNow me $500 urgently
```

---

## 1. The problem (0:00–0:55)

**(next)** in the lines below means: click to the next slide at that point. Start recording on slide 1.

**Screen:** slides 1–5 (cover, scam costs, why a bank would pay, three classes, the brief's pattern). Move to slide 3 on "Why would a bank pay".

> "Hi, I'm Jonathan. This is Smishing Triage, a scam checker for a Singapore bank's customers. **(next)** Scams cost Singapore 913 million dollars last year, about 24,500 dollars a case, and over 9,000 cases began on WhatsApp or Telegram.
>
> **(next)** Why would a bank pay for this? Since December 2024, under MAS's Shared Responsibility Framework, a phishing loss falls on the bank if it breached one of its anti-phishing duties, then on the telco for SMS scams, and otherwise on the customer. The checker doesn't move that liability, but fewer customers phished means less exposure and fewer disputes.
>
> **(next)** A spam filter lumps marketing in with phishing, but one wastes three seconds and the other can empty an account. So there are three classes: legitimate, marketing spam, and smishing, which is phishing by text. The model is judged on scams caught, not accuracy. **(next)** It follows the brief's pattern: a text verdict, an image channel, and a second stage that names the problem."

## 2. Live demo (0:55–2:10)

**(next)** **Screen:** slide 6 (blank), with your Telegram recording placed over it (https://t.me/bc3415_smishing_bot). Paste each message below in order, wait, point at the reply. Expected replies were checked against the rebuilt model on 25 Oct.

1. **DBS:** paste
   ```
   Your DBS account is suspended. Verify at http://dbs-secure.co/login
   ```
   Expect: ⚠️ Likely scam (98%), flagged on the link, "account", "suspended", "Verify", then the Gemini scam type.
   > "A fake DBS link. It's called a likely scam at 98%, and it shows the words that triggered that, so the customer learns what to look for next time. Below that, an LLM names the scam type: bank impersonation."
2. **iPhone:** paste
   ```
   WIN a FREE iPhone! Txt WIN to 85233 now. T and Cs apply
   ```
   Expect: 📣 Marketing / spam (99%).
   > "Marketing spam. Annoying, but not an alarm."
3. **Eh you reaching:** paste
   ```
   Eh you reaching already? I order first ah
   ```
   Expect: ✅ No scam signals found (96%), with the "not a guarantee" line.
   > "A normal message. It never says 'safe', only 'no scam signals found'. A false all-clear is worse than no answer."
4. **Hi mum:** paste
   ```
   Hi mum this is my new number, my phone broke. Can you PayNow me $500 urgently
   ```
   Expect: ❔ No scam signals found (95%), with the 🔎 "a person should check it" line.
   > "The hard case: a scam with no link. The model thinks it's legitimate, but there's a question mark. A person should check it. More on that in a moment."
5. **Screenshot:** drag in `Indiv/reports/mock_screenshot.png`. It reads: "Your parcel 9G8841 is held at customs. Pay the S$3.20 clearance fee at http://sgpost-clear.co/pay within 12 hours."
   Expect: ⚠️ Likely scam (88%), flagged on the link, "customs", "Pay".
   > "Screenshots work too. OCR reads the text, and then the same model judges it."

The links in messages 1 and 5 are made up for the demo. Don't open them.

## 3. Where the human is, and why there (2:10–2:50)

**Screen:** slide 7 (review line set by cost), then slide 8 ("Hi mum" and the review table) from "'Hi mum' had a 4% scam chance".

> "**(next)** So where's the human? Not at a flat 'below 60% confidence' rule, because mistakes don't cost the same. A two-minute analyst review costs about S$1.67. A missed scam costs about S$67 in expected loss.
>
> So when the bot would say 'no scam signals', a scam chance above 2.5% sends it to a person. **(next)** 'Hi mum' had a 4% scam chance, so it goes to review.
>
> On the test set that's 10% of messages, including every scam the model missed. The S$67 is my least certain number, so the table shows every alternative."

## 4. Why a trained model first, then the LLM (2:50–3:30)

**Screen:** slide 9 (the two steps and the token bill), then slide 10 (the real savings) from "The real savings are elsewhere".

> "**(next)** Why a trained model first, and the LLM second? It saves tokens: only about a quarter of checks reach the LLM, so the bill drops from about 12 US dollars a year to 3. Trivial either way.
>
> **(next)** The real savings are elsewhere. Speed: a fifth of a second, not 6 to 8. Privacy: unflagged messages never go to an AI provider. And a probability I can price for the review rule, which an LLM doesn't give me.
>
> It isn't a funding question. If an LLM beats this model on local data, it can sit behind the same predict()."

## 5. Why the numbers are honest (3:30–4:10)

**Screen:** slide 11 (first version claimed 95%), then slide 12 (the honest result) from "The honest result is 76%".

> "**(next)** How do I know these numbers are honest? My first version claimed 95%. But scam campaigns send near-identical copies, and my test set had copies of the training data. Now near-copies are grouped and kept on one side of the split.
>
> **(next)** The honest result is 76% of scams caught. The interval is wide, 56 to 89%, because there are only 43 distinct campaigns. 0.2% of Singaporeans' personal chats are wrongly flagged. The model and its test figures rebuild from one config file and one command. 19 tests check it, including that the LLM gate holds."

## 6. Recommendation (4:10–4:50)

**Screen:** slide 13 (not ready for customers), slide 14 (the pilot ask) from "So the ask is", and slide 15 on "Thank you".

> "**(next)** My recommendation is that it's not ready for customers. It catches 60% of real local scams. It also flagged all 5 genuine bank and SingPost notices it saw, and that alone is a no-go. Both problems come from foreign training data.
>
> **(next)** So the ask is a three-month pilot, about S$9,000: 5,000 to label local messages, and 4,000 of staff time to run the trial. It passes only if it catches 80% of local scams and flags at most 1% of the bank's real alerts. The running cost is people, not tokens: about S$10,000 to 14,000 a year of review time. **(next)** Thank you."

---

## If someone asks (not in the video)

**Bank liability (Shared Responsibility Framework)**
- **The order:** since 16 Dec 2024, the bank bears a phishing loss if it breached one of its specified anti-phishing duties; for scams sent by SMS, the telco bears it if the bank complied and the telco did not; otherwise the customer does (MAS–IMDA Guidelines, paras 6.2–6.7; writeup reference [3]).
- **What the checker does not do:** it is voluntary, so it discharges none of those duties and moves no liability. Most losses would still fall on customers, so for the bank the gain is fewer disputed claims, less exposure when one of its own controls slips, and customer trust.

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
