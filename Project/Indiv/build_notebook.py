"""Generates and executes notebooks/walkthrough.ipynb.

The notebook is a thin narrative over ``src/`` — it imports and calls, it does
not reimplement. Keeping it generated means it cannot drift from the modules,
and the committed .ipynb stays reviewable.

    python build_notebook.py               write the cells, then run them all
    python build_notebook.py --no-execute  write the cells only

Running it retrains the model from data/raw/ (a few minutes), exactly as
``python main.py --skip-download`` does.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat as nbf

NB = nbf.v4.new_notebook()
cells = []


def md(text: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(text.strip()))


def code(text: str) -> None:
    cells.append(nbf.v4.new_code_cell(text.strip()))


# ---------------------------------------------------------------- intro
md("""
# Smishing Triage — walkthrough

Separating **ham**, **commercial spam**, and **smishing** (phishing by SMS).

A binary ham-vs-spam filter puts a marketing blast and a credential-harvesting
message in the same class. For a user, one wastes three seconds and the other
costs them thousands of dollars. Separating them is the point of this project.

This notebook calls the modules in `src/` in the order the pipeline runs. It
contains no logic of its own — open the module named in each section to see how
a step works. `main.py` runs the same sequence headless.
""")

code("""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parent))  # notebooks/ -> project root

import pandas as pd
import matplotlib.pyplot as plt

from src.config import CFG

print("labels      :", CFG.labels)
print("target class:", CFG.target_label, "— recall on this is the headline metric")
print("cost matrix :")
pd.DataFrame(CFG.cost_matrix(), index=CFG.labels, columns=CFG.labels)
""")

# ---------------------------------------------------------------- data
md("""
## 1. Data — `src/datasets.py`

Four corpora, four different formats, one schema. Each loader emits
`text` / `label` / `source`, so nothing downstream needs to know where a
message came from — except where that is used deliberately.

Only the Mendeley smishing set distinguishes commercial spam from smishing.
UCI has a single `spam` class that conflates the two, and the NUS corpus is
ham-only because it was collected from volunteers rather than a spam trap.
""")

code("""
from src.datasets import load_all

raw = load_all()
pd.crosstab(raw["source"], raw["label"], margins=True)
""")

md("""
### The corpora are built on each other

Deduplication is not housekeeping here — it is load-bearing. Mendeley's
smishing set is UCI plus re-labelling, and UCI absorbed part of the NUS corpus.
Split first and the same message lands in train and test.
""")

code("""
from src.preprocess import deduplicate

deduped, conflicts = deduplicate(raw)
print(f"before : {len(raw):,}")
print(f"after  : {len(deduped):,}")
print(f"removed: {len(raw) - len(deduped):,}  ({1 - len(deduped)/len(raw):.0%})")
""")

md("""
### The conflicts are the project's thesis, sitting in the data

Some messages carry *different labels in different corpora*. Almost all of them
are `uci=spam` versus `mendeley=smishing` on identical text — UCI calls a
credential-harvesting message "spam", Mendeley calls it "smishing".

`SOURCE_PRIORITY` in `preprocess.py` resolves them to the finer label. Had UCI
been ranked first, several hundred scams would have trained as marketing.
""")

code("""
from src.preprocess import dedup_key

conflicts = conflicts.assign(_k=conflicts["text"].map(dedup_key))
print(f"{conflicts['_k'].nunique()} messages labelled inconsistently across corpora\\n")

for key, group in list(conflicts.groupby("_k"))[:3]:
    print(" | ".join(f"{r.source}={r.label}" for r in group.itertuples()))
    print(f"   {group['text'].iloc[0][:95]}\\n")
""")

# ---------------------------------------------------------------- splits
md("""
## 2. Preprocessing — `src/preprocess.py`

Normalise, deduplicate, split. Five decisions worth noticing:

**Placeholders, not deletion.** URLs, phone numbers and amounts become marker
tokens. Their *presence* is predictive even when the value is not.

**Two text columns.** `text_clean` feeds word features; raw `text` feeds
character features, because digits, case and punctuation are exactly what
obfuscated smishing abuses.

**The split is made over templates, not rows.** Scam campaigns reuse one
template with a different phone number or prize amount each time; exact
deduplication keeps every variant. Splitting by row put 27% of test smishing
beside a sibling in training. Grouping by normalised text keeps each template
on one side.

**Near-copies are removed too.** Templates miss reworded variants ("it has
been resent" → "it ingest been resent") and the same campaign with a different
number. Any training row with character n-gram cosine ≥ 0.7 to a validation or
test message, on the raw or the number-blanked text, is dropped.

**Synthetic rows are barred from evaluation**, structurally — the LLM-generated
corpus is forced into the training split and cannot reach validation or test.
The NUS corpus is held out separately as the Singapore shift set.
""")

code("""
from src.preprocess import normalise_text

for example in [
    "URGENT! Call 09061701461 now to claim your £2000 prize at http://bit.ly/x9",
    "Eh you reaching already? I order first ah",
]:
    print(f"raw   : {example}")
    print(f"clean : {normalise_text(example)}\\n")
""")

code("""
from src.preprocess import build

splits = build()
""")

# ---------------------------------------------------------------- ladder
md("""
## 3. The model ladder — `src/train.py`

Four rungs, cheapest first. Each is scored on **validation**; the test set is
spent once, at the end, by the selected model only.

1. Word counts + Multinomial Naive Bayes — the floor
2. TF-IDF + Logistic Regression — linear baseline, readable coefficients
3. **Character n-grams + calibrated LinearSVC** — spelling- and link-shape features
4. Word + character features combined

Selection is on macro F1 with smishing recall as the tiebreak, among the rungs
that flag at most 1% of real Singaporean messages, applied mechanically rather
than by eye. Rungs within noise of each other on macro F1 differ tenfold on
false alarms, which macro F1 cannot see; the cap was set with the validation
results in view. The ladder is the deliverable as much as the
final model is: one model with a good number says nothing about whether a
simpler one would have done.
""")

code("""
from src.train import run as train_run

leaderboard = train_run()
""")

md("""
### Reading the confusion matrix

Ham is near-perfect. Almost all remaining error sits on the **spam↔smishing**
boundary — which is the interesting part, because that boundary is what this
project exists to draw.
""")

code("""
cm = pd.read_csv(CFG.reports_dir / "confusion_test.csv", index_col=0)

fig, ax = plt.subplots(figsize=(5, 4))
ax.imshow(cm.values, cmap="Blues")
ax.set_xticks(range(len(cm.columns)), cm.columns)
ax.set_yticks(range(len(cm.index)), cm.index)
ax.set_xlabel("predicted"); ax.set_ylabel("true")
ax.set_title("Test confusion matrix")

for i in range(cm.shape[0]):
    for j in range(cm.shape[1]):
        v = cm.values[i, j]
        ax.text(j, i, f"{v:,}", ha="center", va="center",
                color="white" if v > cm.values.max() / 2 else "black")
plt.tight_layout(); plt.show()
""")

md("""
### Choosing the operating point

The model outputs three probabilities; a *decision rule* turns them into one
verdict. **Argmax** takes the most probable class. **Min-cost** takes the class
with the lowest expected cost under the cost matrix in `config.yaml`, where a
missed scam costs 20 and a false scam alarm costs 2 — so it flags a message
as smishing even at modest probability.

Both are scored on validation and the Singapore shift set before the test set
is touched. The matrix prefers min-cost, but it buys a few extra scams with a
large rise in false alarms on real local messages — a cost the matrix leaves
out. `config.yaml` therefore serves argmax.
""")

code("""
pd.read_csv(CFG.reports_dir / "operating_point_val.csv")
""")

md("""
### Real Singapore scams

The NUS shift set only measures false alarms. To measure *misses* on local
scams, a small evaluation-only set of scam texts sent to people in Singapore
was collected from SPF advisories, Mothership and archived ScamAlert stories,
one source URL per message (51 of the 60 scams transcribed from screenshots
with AI assistance). It never touches training or selection.
""")

code("""
sg_path = CFG.reports_dir / "sg_scams_predictions.csv"
if sg_path.exists():
    sg = pd.read_csv(sg_path)
    scams = sg[sg["label"] == CFG.target_label]
    print(f"caught as smishing: {(scams['predicted'] == 'smishing').mean():.0%}  "
          f"flagged at all: {(scams['predicted'] != 'ham').mean():.0%}  (n={len(scams)})")
    display(scams.groupby("scam_type")["predicted"].value_counts().unstack(fill_value=0))
else:
    print("no Singapore scam set in data/raw/sg_scams/")
""")

# ---------------------------------------------------------------- ablation
md("""
## 4. Does the LLM-generated corpus help? — `src/ablation.py`

The corpus is mostly reworded copies of the other corpora. On the single
validation split it appears to help, but over six repeated template splits of
the non-test data it makes no reliable difference (recall +0.02 on average,
macro F1 unchanged), so the served model trains on real data only
(`train.use_synthetic: false`). The repeated splits also show how much one
split can mislead: real-only recall ranges from 0.54 to 0.91 across them.

The comparison runs on **validation and the Singapore shift set only** — both
real messages. Spending the test set to choose an augmentation setting would be
exactly the leak the evaluation design exists to prevent.
""")

code("""
from src.ablation import repeated, run as ablation_run

ablation = ablation_run()
repeats = repeated()
""")

# ---------------------------------------------------------------- robustness
md("""
## 4b. Robustness probes — `src/robustness.py`

The test set measures messages like the training data. These constructed
variants ask what it cannot: do leetspeak spellings (`DB5`, `acc0unt`) survive,
does the verdict hinge on `http://`, and is a harmless link called a scam?
They are reported as behaviour, not accuracy.
""")

code("""
from src.robustness import run as robustness_run

probes = robustness_run()
""")

md("""
### What the model relies on overall

LIME explains one message; the averaged linear weights show the global picture.
The strongest smishing cues are UK premium-rate number prefixes (`08…`, `09…`)
and `http` — which is why the model transfers poorly to Singapore scams.
""")

code("""
top = pd.read_csv(CFG.reports_dir / "top_features.csv")
for cls, group in top.groupby("class"):
    print(f"{cls:9}", "  ".join(repr(f) for f in group["feature"].head(8)))
""")

# ---------------------------------------------------------------- serving
md("""
## 5. Serving — `src/predict.py`

`predict()` is the entry point everything downstream uses: this notebook, the
OCR path, the Telegram bot. Nothing calling it needs to know which rung won.
""")

code("""
from src.predict import predict

for message in [
    "Eh you reaching already? I order first ah",
    "WIN a FREE iPhone! Txt WIN to 85233 now. T and Cs apply",
    "Your DBS account is suspended. Verify at http://dbs-secure.co/login",
]:
    r = predict(message)
    print(f"{message[:58]:60} -> {r.label:9} {r.confidence:.0%}  {r.red_flags}")
""")

md("""
### Why it decided — LIME

The red flags come from LIME. It deletes random subsets of words, re-scores
each variant with the real model, and fits a small linear model to those
scores; each word's weight is its estimated push towards the verdict. Deleting
many words at once is what lets it explain a 95%-confident prediction, where
removing any single word moves nothing.
""")

code("""
from src.predict import explain, load_model

message = "Your DBS account is suspended. Verify at http://dbs-secure.co/login"
col = list(load_model().classes_).index("smishing")
exp = explain(message, "smishing", num_samples=3000)

fig = exp.as_pyplot_figure(label=col)
fig.set_size_inches(7, 3.5)
plt.title("LIME: words pushing towards 'smishing'")
plt.tight_layout()
fig.savefig(CFG.reports_dir / "lime_example.png", dpi=150)
plt.show()
""")

md("""
### The screenshot path — `src/ocr.py`

Users forward screenshots far more readily than they retype a message. OCR
errors land *upstream* of the classifier, so a misread character becomes a
feature the model never saw in training — a genuine weakness, and one the
writeup should name rather than hide.
""")

code("""
from PIL import Image, ImageDraw
from src import ocr

# A mock screenshot, including the UI furniture a real one carries.
img = Image.new("RGB", (620, 250), "white")
draw = ImageDraw.Draw(img)
for i, line in enumerate([
    "Today", "",
    "Your parcel SG8841 is held at customs.",
    "Pay the S$3.20 clearance fee at",
    "http://sgpost-clear.co/pay within 12 hours.",
    "", "14:32   Delivered",
]):
    draw.text((20, 20 + i * 28), line, fill="black")

path = CFG.reports_dir / "mock_screenshot.png"
img.save(path)
display(img)

text = ocr.image_to_text(path)
print(f"\\nOCR read: {text!r}")
print()
print(predict(text).describe())
""")

md("""
### The LLM second stage — `src/scam_type.py`

Scam *type* labels (delivery, banking impersonation, job offer…) do not exist
as public labelled message data, so training a scam-type classifier would mean
inventing the labels — undermining the trained classifier's evaluation.

Instead a zero-shot LLM names the type, and **only on messages the trained
model already flagged as smishing**. The gate lives inside `enrich()`, not in
the caller, so the second stage cannot accidentally run on everything — which
also keeps legitimate messages off the network.

It is explicitly unevaluated. No metric in this project depends on it.
""")

code("""
from src import scam_type

message = "Your parcel is held at customs. Pay S$3.20 at http://sgpost-clear.co/pay"
prediction, scam = scam_type.enrich(message)

print(scam_type.describe(prediction, scam))
if scam is None:
    print("\\n(enrichment off — set GEMINI_API_KEY; the classifier runs either way)")
""")

md("""
## Summary

| | |
|---|---|
| Champion | character n-gram TF-IDF + calibrated LinearSVC |
| Headline | smishing recall, with a bootstrap confidence interval |
| Guardrail | false-alarm rate on real Singaporean ham |
| Front end | `python -m app.bot` — forward a message, get a verdict |

Known limitations, scope boundaries and design decisions are in `README.md`
and the technical writeup.
""")

NB["cells"] = cells
NB["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}

out = Path(__file__).parent / "notebooks" / "walkthrough.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.write(NB, out)
print(f"wrote {out.relative_to(Path(__file__).parent)} ({len(cells)} cells)")

if "--no-execute" not in sys.argv[1:]:
    from nbconvert.preprocessors import ExecutePreprocessor

    print("executing (retrains the model; a few minutes)…")
    ExecutePreprocessor(timeout=1800).preprocess(NB, {"metadata": {"path": str(out.parent)}})
    nbf.write(NB, out)
    print("executed and saved")
