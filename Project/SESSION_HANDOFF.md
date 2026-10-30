# Smishing Triage — session handoff

Last session: 20 October 2026. Latest independent grader estimate: **84–86% (A-)**, assuming the video is delivered.

## Where things are

| Path | What it is |
|---|---|
| `Indiv/` | **Working copy.** Make every change here. Contains `.env` (real keys) and `PROJECT_BRIEF.md` (private notes). |
| `Smishing_Triage/` | **Submission folder, not zipped.** The user adds the video and zips it themselves. Identical to `Indiv/` minus `.env`, `PROJECT_BRIEF.md` and the .docx (SHA-256 verified, 56 files, 20 Oct). |
| `writeup_src/writeup.html` | Source of `Smishing_Triage_Writeup.pdf`. The Claude Docs version is out of date; don't export from it. |
| `writeup_src/make_figures.py` | Redraws `fig/sg_scams.png` from `Indiv/reports/sg_scams_predictions.csv`. |
| `Smishing_Triage_Submission.zip` | **Old Oct 12 version. Do not submit.** |

Python: `D:\Jon\Uni\BC3415\.venv\Scripts\python.exe` (run from inside `Indiv/`).

## Current results (do not change unless the model changes)

- Test: smishing recall **0.733** (95% CI 0.628–0.829, resampled by template: 101 scams, 86 templates), precision 0.804, macro F1 0.825, accuracy 0.953, Brier 0.066. No test scam marked legitimate (the other 27 called spam).
- False alarms on Singapore ham (NUS): 0.24% (21 / 8,616).
- Real Singapore scams: 29/60 caught (48%), 39/60 warned (65%); with link 19/32, without 10/28; 4 of 5 genuine local notices flagged.
- Gemini scam type agrees with hand labels on 25 of 29 caught SG scams (re-run 20 Oct on the laptop; was 24 on the other machine; LLM output varies).
- Repeated splits: real-only recall ranges 0.54–0.91, averages 0.71.

## Decisions already made (don't reopen)

- Train on **real messages only** (`train.use_synthetic: false`): the LLM-generated corpus makes no reliable difference over 6 repeated splits. Writeup gives it one line.
- Selection: best validation macro F1 among models flagging ≤1% of Singapore ham → char SVM. Disclosed as set with validation results in view.
- Operating point: argmax.
- Near-copy removal on raw **and** number-blanked text at 0.7, TF-IDF weights fitted on the whole corpus.
- Ship the raw data in the submission.
- F1 falling across versions is expected: each drop was a leak being closed (0.904 → 0.842 → 0.825).
- Not doing: hyperparameter tuning, transformer baseline, the within-Mendeley label-conflict tie-break, the bare-domain TLD list.

## Session of 20 Oct (laptop, `C:\Users\user.MYLNB2402\Work\BC3415\Project`)

Done (items 1 and 2 below are complete):
- Re-ran the whole pipeline here; every number reproduced exactly. 18 tests pass (new test for the template bootstrap). Notebook rebuilt, PDF reprinted, `Smishing_Triage/` rebuilt (55 files, hashes match `Indiv/`).
- CI now resamples templates (`evaluate.bootstrap_ci(groups=...)`): **0.628–0.829**. Updated in writeup summary, section 3, section 5 table, section 8, and the README.
- Source check: the SPF 2025 brief (p. 8 and Annex E) shows SMS was the contact method in only **450** of 37,308 cases, against 9,355 for messaging platforms. Section 1 now cites that and says the checker accepts any forwarded text. The SRF paragraph was checked against Guidelines 6.2–6.7 and the MAS URL was added to reference [3].
- Section 1 additions: staff-time row (S$4,000; total about S$9,000), a no-go blocker paragraph, and an illustrative benefit table (S$2.4m/yr today, S$3.9m at target). The handoff's formula had no "share that would otherwise have lost money" term, so one was added (1%); without it the formula assumes every scam message caught is a S$24,500 loss.
- Paths on this machine: Python `C:\Users\user.MYLNB2402\Work\BC3415\.venv\Scripts\python.exe`; Edge `file:///C:/Users/user.MYLNB2402/Work/BC3415/Project/writeup_src/writeup.html`.
- Grader agent: `C:\Users\user.MYLNB2402\Work\.claude\agents\bc3415-grader.md`.

- Grader run (20 Oct): **78–85%, most likely about 82 (A−)** if a competent video is delivered; 60–70% if there is no video. Criteria: performance 14, preprocessing 18, explainability 18, creativity 16, usability 17 (out of 20 each). Its quick fixes have been applied (0.71 → 0.70, the reproducibility wording, the red-flag claim, the transcription note, the lock file's Python version, a notebook rebuild warning, and the OCR mapping to the brief).
- Not done (the grader's optional fixes): grouped CV inside CalibratedClassifierCV; a hyperparameter search or transformer rung; the brief mapping in the Summary.

- Later on 20 Oct: the user added `Indiv/.env` on the laptop. Both keys work (Telegram getMe OK, the bot starts, Gemini answers). `scam_type_eval.csv` was regenerated: **25 of 29**, docs updated.
- A context-free consistency reviewer found 15 doc/code mismatches; all were fixed. None changed a model number (see README and writeup §2/§5/§7/§8/§9 wording). The `smishing_templates` column was renamed, and the ablation CI now resamples by template.
- Fresh-venv test (a copy without `.env`, `pip install -r requirements.txt`, Python 3.13): 18 tests pass, predict/demo/OCR work, the bot and Gemini degrade politely, and `src.train` reproduces 0.733.
- User decision: **don't change the model** (no train+val refit, no tuning).

## Remaining to-do (as of the previous session)

### 1. Wording fixes (no numbers change)
- **Overclaims**
  - Writeup §9 / README: "every number regenerated by one command" is not true for the 24/29 scam-type check, which needs `GEMINI_API_KEY` and `python -m src.scam_type --evaluate`. Say so.
  - `src/scam_type.py` module docstring still says "explicitly **unevaluated**"; it now has a spot-check `evaluate()`. Reword to "advisory; spot-checked, not part of the evaluation".
  - README "Known limitations": "The DistilBERT rung is specified but not built" → "A transformer model was not attempted".
- **Business case (writeup §1)**
  - Add an illustrative yearly benefit figure, with every assumption stated (checks per year × share that are scams × share caught × average loss S$24,500).
  - Source "text messages are a primary way scams arrive" (the SPF annual brief has a breakdown by contact method), or soften it.
  - Temper the Shared Responsibility Framework argument: a voluntary checker does not discharge the bank's SRF duties; it reduces how often customers are phished.
  - Add staff time to the pilot cost table (only labelling is costed now).
  - Name "genuine bank alerts flagged as scams" as an explicit no-go blocker (currently 4 of 5 local notices are flagged; the go/no-go list has a ≤1% criterion for this, so say plainly it is currently failing).
- **Tidy `.gitignore`**: it lists `artifacts/`, `reports/`, `tessdata/`, which are shipped in the submission. Add a comment explaining they are generated and kept out of git, but included in the submission zip.

### 2. Cluster-aware confidence interval (statistics only, model unchanged)
- `src/evaluate.py` `bootstrap_ci` resamples individual messages, but the 101 test scams come from only 86 templates (one Vodafone campaign has 7 copies).
- Change it to resample by template (`text_clean`), or by cluster, and state the effective sample size.
- The grader's cluster bootstrap gave about **0.62–0.83**; re-run and use whatever the code produces. The headline 0.733 stays the same.
- Update the CI in: writeup summary + §5 table, README Results table, and anywhere else "0.648" appears.

### 3. Still required from you
- **Record the 3–5 minute video.** Suggested order:
  1. a scam text with the Gemini scam type;
  2. a marketing spam;
  3. a normal chat message, showing the "not a guarantee" reply;
  4. a screenshot with a caption;
  5. the honest 48% local result from the writeup.
- Optional: a phone screenshot of a real bot exchange for writeup §7.
- Optional: add the official MAS/IMDA link for reference [3].

## How to finish after making changes

1. If code changed: from `Indiv/`, run `python main.py --skip-download`, then `python -m pytest tests -p no:cacheprovider` (expect 18 passed) and `python build_notebook.py` (writes and executes the notebook).
2. Writeup: edit `writeup_src/writeup.html`. Run `python make_figures.py` if the SG results changed. Print to PDF with Edge headless:
   ```
   "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="D:\Jon\Uni\BC3415\Project\writeup_src\writeup_draft.pdf" "file:///D:/Jon/Uni/BC3415/Project/writeup_src/writeup.html"
   ```
   Then copy `writeup_draft.pdf` to `Indiv/Smishing_Triage_Writeup.pdf`.
3. Re-sync the submission folder (from `D:\Jon\Uni\BC3415\Project\Indiv`, Git Bash):
   ```
   rm -rf ../Smishing_Triage && mkdir ../Smishing_Triage && tar --exclude='./.env' --exclude='./PROJECT_BRIEF.md' --exclude='./Text_Classification_Assignment.docx' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ipynb_checkpoints' --exclude='.gitkeep' -cf - . | (cd ../Smishing_Triage && tar -xf -)
   ```
4. Check the submission: no `.env`, no token- or key-like strings, no `__pycache__`, file hashes match `Indiv/` minus the excluded files.

## Bot

- Run from `Indiv/`: `..\..\.venv\Scripts\python.exe -m app.bot` (reads `.env`; restart after any code change).
- t.me/bc3415_smishing_bot. Gemini model `gemini-flash-lite-latest` (from `.env`), falls back to `gemini-flash-latest`, 15 s per attempt.
- The bot token was printed once in an earlier session log (since fixed). Optional: `/revoke` with @BotFather and update `.env`.
- Git: repo at `BC3415/`; the last commit is 560f99e (20 Oct). Today's laptop changes are not committed.

## Session of 22 Oct: journey and human-in-the-loop sections

- New writeup sections: **§6 How the project got here** (versions 717efbe → 9dd2738 → 560f99e; 1,807 of the 2,317 near-copy rows dropped were LLM-generated, so that corpus was the main leak carrier) and **§9 Human in the loop**. Later sections are renumbered (Explainability 7, Application 8, Limitations 10, Reproducing 11). Reference [5] is Chow (1970).
- Human review is implemented in code: `src/review.py` (Chow's reject option with the cost matrix), `review.cost: 0.5` and `review.grid` in config.yaml, `Prediction.needs_review` with a bot reply line, main.py stage 6 "review" (demo is now stage 7), a notebook section 4c, and a new test (**19 tests**). Output: `reports/human_review.csv`.
- At 0.5: test 9.7% reviewed, including 25/27 missed scams (99/101 caught or reviewed); SG set 61.5% reviewed, 24/31 missed (53/60 caught or reviewed). The model is unchanged (0.733).
- Good video moment: "Hi mum this is my new number… PayNow me $500 urgently" is called legitimate at 96% but routed to review.
- Fact-checked by a context-free agent; claims corrected (§6 "most of the fall", generated corpus +3.8 single split / +2.1 over 6 splits, review cost chosen with test visible — disclosed). Reviewed "no scam signals" replies show ❔ instead of ✅.
- Submission folder rebuilt: 58 files; PDF 14 pages; writeup dated 22 Oct. Today's work is not committed to git.

## Session of 22 Oct (later): cluster split (version 4) — supersedes the numbers above

The user questioned the split, so a split study was run (`src/split_study.py`, main stage 5 "splits"). Steps 4 and 5 (template split, then deleting training near-copies) were replaced by **`preprocess.near_copy_clusters` + `cluster_split`**: link near-copies (template or ≥0.7 cosine on raw/clean), then randomly assign whole clusters with StratifiedGroupKFold (1 in 5 to test, 1 in 7 of the rest to validation). No real rows are deleted; val and test are also kept apart. The CI now resamples by cluster (`cluster` column in the CSVs).
- New results (seed 42): test recall **0.761** (CI 0.563–0.893, 43 clusters), precision 0.783, macro F1 0.813, accuracy 0.943, Brier 0.079. 7 test scams are called ham (all 7 reviewed). SG ham false alarms 0.21% (18/8,547). SG scams **36/60**, warned 41; genuine notices 5/5 flagged. Robustness 7/12. Real training scams 374.
- Generated corpus: single split +9.5, repeated cluster splits −1.7 (better 1/6), so it stays dropped.
- Review at 0.5: test 10.0% reviewed, all 26 missed scams reviewed; SG set 41.5%, 18/24 missed, 54/60 caught or reviewed.
- Gemini spot check: 30/36 (1 timeout).
- The writeup was rewritten throughout; §6 now has a version 4 row plus "Testing the split itself" with references [6]–[9] (sklearn grouped CV, CheXNet, Saeb 2017, Allamanis 2019). 16 pages; 60 files in Smishing_Triage/.
- Not done (optional): refit the shipped model on all data after evaluation (mentioned in §10 "Next version").

## Session of 24 Oct (laptop): video script and README

- Checked the brief: Option A deliverables are code, a model and a 3–5 min video. **No report is required**, so assume the marker may never read the PDF. The video has to carry the business case, the human-review threshold and the two-step rationale.
- The professor's tips: say where the human is in the loop and how the threshold was set; explain why the design is two steps (ML classifier, then LLM) and what that saves; aim at a CFO and CTO together.
- **Video script: `Project/VIDEO_SCRIPT.md`** (595 spoken words, about 4:30 with demo time). Graded by `bc3415-grader` as if the video follows it: **about 82% (A−)**, range 80–84. All of its script fixes are applied.
- Measured on 24 Oct (not in reports/): a Gemini call is 123 in + 78 out tokens and takes 6–8 s; `predict()` with LIME takes 0.01–0.16 s. 8.8% of test messages reach the LLM (106/1,202). Sending all 50,000 checks a year would cost about US$12, gated about US$3, at US$0.30 / US$2.50 per million tokens (price not certain for the flash-lite alias).
- README now has a "How it maps to the brief" paragraph, the review line for each verdict (no scam signals: 2.5%; spam: about 5%; likely scam: about 25% chance it's legitimate) and a "Why two steps" design decision. Copied to `Smishing_Triage/` and the hashes match `Indiv/` (60 files). No code or numbers changed, so the pipeline, notebook and PDF were not rerun.
- **Remaining: record the video, add it to `Smishing_Triage/`, zip it.** Not committed to git.

## Session of 25 Oct (desktop, `D:\Jon\Uni\BC3415\Project`): this machine brought up to date

- The code here was current (git be83a46), but the untracked outputs were from 20 Oct (version 3, recall 0.733) and `Smishing_Triage/` had only 29 files. Re-ran `main.py --skip-download`: every version 4 number reproduced (0.761, CI 0.563–0.893 over 43 clusters, SG 36/60, review 10.0% / 41.5%, robustness 7/12).
- `python -m src.scam_type --evaluate`: 30 of 36, with all 36 answered this time (no timeout). README and writeup §8 no longer say "one call timed out".
- 19 tests pass, notebook rebuilt, figure redrawn, PDF reprinted, `Smishing_Triage/` rebuilt (60 files, hashes match `Indiv/`, no `.env` or key-like strings).
- **Remaining: record the video, add it to `Smishing_Triage/`, zip it.** Not committed to git.
- Later on 25 Oct: added **`Smishing_Triage_Slides.pptx`** (15 slides after the SRF slide was added as slide 3; was 14, in `Indiv/` and `Smishing_Triage/`, now 61 files). It follows VIDEO_SCRIPT.md section by section, with the spoken lines in the speaker notes. Slide 6 is blank for the demo recording. Section 1 now has a "Why would a bank pay" (Shared Responsibility Framework) passage, worded to match writeup §1; the plan runs about 4:50. Generator: `Project/slides_src/build.js` (pptxgenjs, not in the submission). VIDEO_SCRIPT.md "Screen:" cues now name slide numbers, and section 2 lists each demo message inline (all re-checked against the rebuilt model).

## Session of 25 Oct (late): video added, submission folder ready

- Video recorded: `Indiv/Video/VideoSubmission.mp4` (6:04, 4096×2160, 140 MB). The brief says "3–5 min (roughly, not exactly)", so it runs about a minute long.
- README now points to the video and the slides (top paragraph). No code or numbers changed.
- `Smishing_Triage/` rebuilt: 62 files, hashes match `Indiv/`, no `.env` or key-like strings. Also excluded: `Video/Video.pds` (editor project), `Video/video2978572168.mp4` (raw 88 s clip) and the `~$` Office lock file. Add `--exclude='./~$*' --exclude='./Video/Video.pds' --exclude='./Video/video2978572168.mp4'` to the sync command.
- **Remaining: the user zips `Smishing_Triage/` and submits.** Not committed to git.
