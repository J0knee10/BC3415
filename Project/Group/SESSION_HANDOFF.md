# Session handoff: BC3415 group project

Last session: 25 Oct 2026. Pick up from "Next steps" below.

## Latest (25 Oct): group switched to the Carousell dispute agent

The user confirmed the switch. The new brief is a Claude Doc: https://claude.ai/artifact/GT6FV41MgCYXh5QeQWnTmQ. It covers the problem, evidence, workflow diagram, data, evaluation, business case, risks, the 6-person work split (C1 to C4 coders, B1 and B2 business) and a timeline to an assumed 15 Nov deadline. `Project Brief.docx` is untouched (still PolicyPatch). Next steps:

- Assign names to the six roles.
- Run the professor check.
- Confirm the deadline.
- Copy the Carousell policy pages in by hand.
- Check the Mercari licence.

## Exploring a Carousell dispute agent (option B)

The user says the group is open to changing direction a lot, since little work has been done. The idea under exploration is an agent that helps Carousell Singapore settle "significantly not as described" disputes on second-hand items sold between individuals.

**Carousell SG rules** (from help-centre search snippets; the pages return 403 to automated fetching, so someone must copy the policy text in by hand):
- Buyer Protection covers only orders paid with the 'Buy' button using in-app payment; cash and bank transfers are excluded.
- Dispute reasons: not received; "significantly not as described" (different size, colour, model or version, missing parts, undisclosed defects). Not covered: "materially similar with subjective and non-significant variations", e.g. "light pink vs rose pink".
- The buyer raises the dispute within the earliest of three windows; one is 2 days after the item shows as delivered.
- The seller has 24h to accept or counter-propose, then the buyer has 24h to accept; otherwise it escalates to Carousell, which emails both sides within 24h. Missing an evidence deadline loses the dispute. Payment is held throughout.
- 'Buy' button sellers need a rating of at least 4.0 and a low cancellation rate.

**Evidence:**
- SPF: Carousell had 29.0% of e-commerce scam cases in 2025 (6,703 cases and S$16.7M lost across all e-commerce scams). In 1H 2026, Carousell cases rose 17.1% to 1,555.
- MHA: 2,476 Carousell scam reports in 2023.
- Caveat: most scams happen outside Buyer Protection (bank transfers, pre-orders), so these figures show a trust problem, not a dispute problem. No dispute volume or outcome data found, only anecdotes.
- eBay forums show the same "not as described" abuse pattern on second-hand items.

**Carousell's existing AI:** "List with AI" (Gemini), an AI car finder (May 2026), phone diagnostics (Laku6) and fraud ML. No AI for disputes found.

**Data idea:** the Mercari Price Suggestion dataset on Kaggle (about 1.4M real second-hand listings with a condition grade of 1–5 and free-text descriptions), with synthetic disputes generated on top. Check the Kaggle competition-data licence first.

## Update (25 Oct, later): group narrowed to two Shopee proposals

Base idea: return and refund policy changes in e-commerce, for Shopee only. Two versions on the table (Ronak's summary):

- **Akshaya's:** Shopee return/refund rules + PolicyPatch-style automation (auto-update the system when a rule changes). Risk: "rule changes are slow to implement" is the generic problem the professor rejected.
- **Ronak's (SPayLater):** help Shopee's internal SPayLater (BNPL) ops team see the consequences of a proposed refund-policy change *before* approving it. Chatbot + RAG over policy + simulator on synthetic transactions; no code patching.

Claude drafted a plain-English business problem for the SPayLater version, grounded in the real rules on help.shopee.sg (article 76479: full vs partial refund, before/after order completion, partial refunds offset the last instalment first, interest not reduced or refunded, excess goes to ShopeePay). Example policy change used: "refund interest on the returned part of an order".

Evidence check on "Shopee refunds are exploited and cost Shopee a lot" (25 Oct):
- **No public Shopee loss figure exists.** The evidence is anecdotes plus Shopee's own countermeasures: a channel for sellers to report fraudulent buyers (Jul 2024), restrictions on accounts that abuse returns, and refund-only decisions based on refund history.
- **The cost mostly falls on sellers, not Shopee.** When the buyer wins, the seller pays shipping and loses the item. Shopee's costs are indirect: customer-service workload, sellers leaving, trust.
- **No evidence found of refund abuse through SPayLater.** SPayLater fraud stories are scams on buyers. Sea's credit-loss provision was about US$1.37B in 2025, but that comes from loan defaults, not refunds.
- **Strongest stories are refund-policy changes that backfired:** China's "refund only" (Pinduoduo 2021, abused, all major platforms rolled it back in Apr 2025 after regulator pressure); Shopee Vietnam's 15-day change-of-mind return window (Mar 2024, seller backlash). These support the "test the change before approving" framing.
- **Industry figures** (Riskified, Appriss) are global, not SEA, and Riskified sells anti-fraud tools, so treat them as vendor claims.
- **Assignment fit (checked the brief):** it grades the LLM/agent and RAG, not the simulator. Plan discussed: make a LangGraph agent the core, and the replay a tool it calls. The LLM's essential job is reading the free-text refund cases (buyer reasons, chats, evidence descriptions) to decide whether each case meets the new rule, which plain code can't do. The brief names LangChain, not LangGraph specifically.
- **User's preference (25 Oct):** the user now leans towards option 5, a return-dispute agent that helps Shopee's dispute staff settle buyer–seller disputes using Shopee's policy. The group has not agreed yet.
- **Dispute-agent evidence check (25 Oct). Key finding: Shopee already built this.** On the Q4 2024 earnings call (4 Mar 2025, Motley Fool transcript), CFO Tony Hou said: "we're using AI model to better -- to make better judgment on the return refund decision ... when there's escalation or disagreement between the buyer and seller, they will come to us. We built an AI engine to be able to make a lot better judgment on this and make it a lot faster." CEO Forrest Li called the return-refund process "a key e-commerce pain-point". This proves the problem is real but hurts originality, so the pitch needs a different angle (explainable decisions with policy citations and fairness to sellers, or a seller-side assistant).
- **Other evidence:**
  - CASE logged 4,641 e-commerce complaints in 2024, up 25% and the highest since 2020, about a third of all complaints. This covers all e-commerce, not just Shopee.
  - In the 2023 CASE–Shopee MOU, Shopee committed to an average of 2.5 working days to resolve return/refund requests.
  - Taobao set up a crowdsourced public jury for disputes (340k cases in its first year).
  - Seller complaints: Stomp, MS News.
- **Other platforms (25 Oct):**
  - Lazada, Amazon and TikTok Shop: no public statements about AI deciding disputes, but that is not proof they lack it. Amazon sellers complain about "automated" A-to-z decisions.
  - Many vendors already sell AI refund/dispute automation (Fini, etc.), so switching company alone doesn't fix originality.
  - Carousell (Singapore, consumer-to-consumer, second-hand goods) is the most distinct alternative. Carousell Protection was replaced by "Buyer Protection" in Jul 2023, and refunds hinge on "significantly not as described". Details come from secondary sources; verify on Carousell's own pages.
- **Open point:** a plain marketplace-refund version (buyer, seller, platform) may already pass the professor's test without SPayLater.

## The professor's feedback (24 Oct)

> Define industry is okay as well, but need to uniquely address a problem, for eg. Our solution for fintech cant be used for banks or hedge funds etc. Basically the problem needs to be unique to a particular industry/company.

**Our read: PolicyPatch, as written, fails this test.**

- The brief pitches it for two industries at once ("marketplace or fintech policy change") and cites MAS guidelines meant for banks.
- Its core problem, "rule changes get lost between ops and engineering", exists at any company with business rules in code. Rename ShopLite to BankLite and the same pipeline works. Everything marketplace-specific sits in the fake codebase, not in the problem.
- The test to apply to any idea: **could a bank or a hedge fund use it unchanged?** If yes, it is too generic.

### What "unique" looks like in the past model projects

This module is **BC3415 AI in Accounting & Finance**. The model group projects are in `../BC 3415 3409 AI - Past Assignments and Group Project References v003/Project-Ref-v002/Model Group Projects/`. The clearest example is UpSkill Lens, written for Udemy, with a section titled "Financial Impact for Udemy". The model projects name one company or industry, describe its specific pain, and quantify the value for it. They also carry business sections: market analysis, competitors, business model, financials and risks.

### Options discussed (none agreed yet)

| | Idea | For | Why only they have this problem | Data | Change from PolicyPatch |
|---|---|---|---|---|---|
| 1 | **Campaign rule agent** (PolicyPatch, narrowed) | Shopee | Double-day sales (11.11, 12.12): temporary voucher, shipping and refund rules that must switch back afterwards; vouchers stacking on one order | Synthetic orders | Small |
| 2 | **GST input-tax claim checker** | Singapore bookkeeping and accounting firms | IRAS rules on input tax that cannot be claimed (e.g. club fees, medical costs, private cars) apply only to GST-registered businesses | SROIE (public scanned receipts) + IRAS guides | Full restart |
| 3 | **HS code classifier for customs** | Freight forwarders and customs brokers | Only importers and brokers classify goods into tariff codes; a wrong code means wrong duty, a missed permit or a lost FTA rate | US CBP CROSS rulings (public, labelled) + tariff schedule | Full restart |
| 4 | **Travel insurance claim triage** | One Singapore insurer | Policy wordings, exclusions and evidence (e.g. flight-delay letters) exist only in insurance | Public policy wordings + synthetic claims | Full restart |
| 5 | **Buyer–seller return disputes** | Shopee | Three-sided disputes (buyer, seller, platform) with photo evidence | Shopee policies + synthetic cases | Full restart |

How each would work:

1. **Campaign rule agent.** Keeps the PolicyPatch pipeline and Codex; ShopLite's services become campaign, voucher and shipping-subsidy services. The impact step replays last year's 11.11 orders under the new rules and reports platform subsidy cost, seller cost and orders affected. Risk: it is still a developer tool, so the professor may still see it as generic.
2. **GST checker.** OCR on receipts (Week 8 material), RAG over IRAS rules, flags input tax that cannot be claimed with a citation, fills in the GST F5 boxes, and escalates unclear items to an accountant. Best fit for an Accounting & Finance module.
3. **HS code classifier.** Reads a product description, searches the tariff notes, asks clarifying questions (material, use), proposes a code with reasons. Best evaluation story: accuracy at 2, 4 and 6 digits against the CROSS rulings.
4. **Insurance claim triage.** Checks a claim against the policy wording and evidence, then approves, asks for documents or escalates. Closest to the Shopify customer-support case in the assignment.
5. **Return disputes.** Weighs buyer photos and seller replies against Shopee's return policy and recommends an outcome. Drops Codex and the PolicyPatch work.

Also possible: bring back **VeriAssist** (DBS card disputes), narrowed to choosing the card-network dispute reason code. Only card issuers do this.

**Claude's recommendation:**

- If the group wants to keep PolicyPatch: option 1, but check the framing with the professor before building.
- If the group is open to switching: option 2 (best fit for the module) or option 3 (clearest accuracy numbers). Both have real public data and a problem only one industry has, and they are easy to measure.

**Not yet verified** (check before anything goes into the pitch): the exact IRAS input-tax rules, the CROSS dataset's licence and access, specific insurer policy wordings, and any Shopee campaign-incident examples. Do not use statistics until they are sourced.

## Background: how we got here

- **VeriAssist** (13 Oct): a DBS card-support agent that checks its own answers. Replaced after a group meeting the user did not attend.
- **PolicyPatch** (16 Oct): a tool for internal staff at a platform like Shopee. An ops person types a rule change in plain English. The system:
  1. turns it into exact rules;
  2. has Codex change the code of a fake marketplace ("ShopLite");
  3. tests the change and replays past cases to show the impact;
  4. produces a pull-request-style summary for a human to approve.
- A "version 3" reframing ("change control for rules in code") was **rejected** by the group.
- **Rule: any change to the project must be agreed by the group first.** Do not edit `Project Brief.docx` until the group has chosen a direction.
- **Sea x OpenAI Codex Hackathon:** the PolicyPatch pitch targeted its "AI-Native Products & Operations" track. Its rules (Vietnam edition) ban pre-built code and require teams of 3 to 4. If the group drops PolicyPatch, this link probably goes too.

## Files in this folder

| File | What it is |
| --- | --- |
| `Project Brief.docx` | PolicyPatch brief (version 2), written 16 Oct. Most details are Claude's proposals, not yet agreed by the group |
| `Project Brief (VeriAssist, superseded).docx` | The old VeriAssist brief |
| `Project Idea (original backup).docx` | The five original ideas: wealth-platform support agent, annual-report narrative vs numbers, accounts-payable three-way match, regulatory change tracker, card disputes |
| `Group_Assignment_Extended_AI_LLM_RAG(1).docx` | The assignment brief (40%; Option A coding + 3–5 min video, or Option B 15 slides) |

Feasibility research doc (version 3 ideas, plus real Shopee/Lazada/Stripe rules, MAS TRM, competitors, Codex pricing): https://claude.ai/code/artifact/2243a3da-bed5-49cb-baeb-118482e6d661. Still undecided whether to keep or delete it.

## Next steps

1. **Share the professor's feedback and the options above with the group.** Get them to pick a direction. Claude offered to turn the options into a one-page note for the group; not done yet.
2. **Confirm the real deadline.** The PolicyPatch timeline ended 15 Nov, about three weeks away. A full restart is tight but doable; options 2 and 3 are the smallest builds.
3. **Ask the professor a one-line check** on the chosen idea, e.g. "Would a GST input-tax checker for Singapore bookkeeping firms count as unique to one industry?"
4. Once agreed, rewrite `Project Brief.docx` for the chosen idea, keeping the old one as a backup like before.
5. Still open from before: who pays for any paid AI usage, whether a written report is needed besides the video, and whether to keep the feasibility doc.

## Housekeeping (individual project, same repo)

On 24 Oct the BC3415 repo was pulled to `be83a46` on the desktop. The old untracked copies were moved aside to `D:\Jon\Uni\BC3415\Smishing_Triage_old_backup\` and `D:\Jon\Uni\BC3415\writeup_draft_old_backup.pdf`. They hold nothing that `Project/Indiv/` lacks and can be deleted. `Indiv/artifacts/` and `Indiv/reports/` were built by older code and need rebuilding before re-syncing `Smishing_Triage/` (see `Project/SESSION_HANDOFF.md`).

## To resume with Claude

Open Claude Code in the BC3415 folder (`D:\Jon\Uni\BC3415` on the desktop, `C:\Users\user.MYLNB2402\Work\BC3415` on the other machine) and say: "Continue the BC3415 group project; read `Project/Group/SESSION_HANDOFF.md` first."
