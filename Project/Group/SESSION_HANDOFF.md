# Session handoff: BC3415 group project (PolicyPatch)

Last session: 16 Oct 2026. Pick up from "Next steps" below.

## Where things stand

- **The project changed after a group meeting** (which you did not attend). The old idea, **VeriAssist**, was a DBS card-support chatbot that checks its own answers. The new idea is **PolicyPatch**.
- **PolicyPatch, in one paragraph:** a tool for internal staff at a platform like Shopee. An ops person types a rule change in plain English, e.g. "Refund claims above $100 require photo evidence unless the seller is trusted; repeat refund claimants should be routed to manual review." The system then:
  1. turns it into exact rules and asks about anything ambiguous;
  2. has Codex (OpenAI's coding AI) change the code of a small fake marketplace we build;
  3. tests the change;
  4. replays past cases to show the impact;
  5. produces a pull-request-style summary for a human to approve.

  It never puts a change live by itself.
- **Possible link to the Sea x OpenAI Codex Hackathon:** the pitch mentions its "AI-Native Products & Operations" track. Its rules (Vietnam edition page) ban pre-built code and require teams of 3 to 4. Confirm with the group whether we are entering at all.

## Files in this folder

| File | What it is |
| --- | --- |
| `Project Brief.docx` | **Current brief (PolicyPatch, version 2)**, written 16 Oct from the meeting's pitch text. Same structure and styling as the old brief |
| `Project Brief (VeriAssist, superseded).docx` | The old VeriAssist brief, kept as a backup |
| `Project Idea (original backup).docx` | The five original project ideas, from before VeriAssist was chosen |
| `Group_Assignment_Extended_AI_LLM_RAG(1).docx` | The assignment brief from the lecturer (40%, Option A coding or B slides) |

## Important: what the group has NOT agreed yet

The meeting's pitch was one paragraph. Most details in `Project Brief.docx` are my proposals for expanding it, so the group still needs to confirm them:

- the fake marketplace's name ("ShopLite") and its 6 services;
- the 24 test scenarios and the evaluation plan;
- roles (4 coders + 2 business);
- the 4-week timeline (19 Oct to 15 Nov);
- the tech choices (Codex CLI, Streamlit, etc.).

A "version 3" reframing (pitching the project as "change control for rules in code") was **rejected**. Any change to the project must be agreed by the group first.

## Separate research doc (pending your decision)

- **Feasibility doc:** https://claude.ai/code/artifact/2243a3da-bed5-49cb-baeb-118482e6d661
- It contains the version 3 suggestions, plus research that may still be useful:
  - real Shopee, Lazada, Amazon and Stripe rules to base test scenarios on;
  - MAS Technology Risk Management Guidelines (change management is section 7.5);
  - competitors (Stripe Radar, FICO, coding agents);
  - Codex pricing: the student offer is US/Canada only, so it likely doesn't apply to us.
- **Open question:** delete the doc, or keep it as reference material for the group?

## Next steps

1. Decide: delete or keep the feasibility doc.
2. Read `Project Brief.docx`, especially the "Start here" overview and Section 19 (open decisions).
3. With the group, confirm the details listed above, plus:
   - the real deadline;
   - who pays for Codex usage;
   - whether we enter the hackathon.
4. Ask the lecturer:
   - Is an internal-operations use case OK, given the assignment's customer-support case study?
   - Is Codex acceptable as the core AI agent?
   - Is a written report needed besides the video?
5. Update the brief only with what the group agrees.

## To resume with Claude

Open Claude Code in `C:\Users\user.MYLNB2402\Work` and say something like: "Continue the BC3415 group project; read `BC3415/Project/Group/SESSION_HANDOFF.md` first."
