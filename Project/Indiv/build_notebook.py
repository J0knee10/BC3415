"""Generates notebooks/walkthrough.ipynb.

The notebook is a thin narrative over ``src/`` — it imports and calls, it does
not reimplement. Keeping it generated means it cannot drift from the modules,
and the committed .ipynb stays reviewable.

    python build_notebook.py
"""

from __future__ import annotations

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

Normalise, deduplicate, split. Three decisions worth noticing:

**Placeholders, not deletion.** URLs, phone numbers and amounts become marker
tokens. Their *presence* is predictive even when the value is not.

**Two text columns.** `text_clean` feeds word features; raw `text` feeds
character features, because digits, case and punctuation are exactly what
obfuscated smishing abuses.

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

1. TF-IDF + Multinomial Naive Bayes — the floor
2. TF-IDF + Logistic Regression — linear baseline, readable coefficients
3. **Character n-grams + calibrated LinearSVC** — the obfuscation handler
4. Word + character features combined

Selection is on macro F1 with smishing recall as the tiebreak, applied
mechanically rather than by eye. The ladder is the deliverable as much as the
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

# ---------------------------------------------------------------- ablation
md("""
## 4. Is the synthetic augmentation earning its place? — `src/ablation.py`

Most training smishing examples are LLM-generated, which raises a question the
headline metric cannot answer: is the model learning smishing, or the
generator's style?

The comparison runs on **validation and the Singapore shift set only** — both
real messages. Spending the test set to choose an augmentation setting would be
exactly the leak the evaluation design exists to prevent.
""")

code("""
from src.ablation import run as ablation_run

ablation = ablation_run()
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
    print(f"{message[:58]:60} -> {r.label:9} {r.confidence:.0%}")
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
inventing the labels — undermining the component the rubric weighs most.

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

Known limitations are listed in `README.md`; the assignment framing and scope
boundaries are in `PROJECT_BRIEF.md`.
""")

NB["cells"] = cells
NB["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}

out = Path(__file__).parent / "notebooks" / "walkthrough.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.write(NB, out)
print(f"wrote {out} ({len(cells)} cells)")
