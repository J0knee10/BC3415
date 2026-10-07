# W4 Text Classification — News Category

**BC3415 Artificial Intelligence in Accounting & Finance**
Week 5 (Text / NLP) workshop submission — Option 2

Configure, run and improve the `WS_Colab_Text` notebook on `News Category (Text).csv`, judged on
**data pre-processing** and **F1 score**.

---

## Result

| | macro-F1 | test errors |
|---|---|---|
| `v001` configuration (raw headline → CountVectorizer → LogReg) | 0.9463 | 71 / 1,370 |
| **Final model** (word + char TF-IDF → soft-voting ensemble) | **0.9677** | **43 / 1,370** |

Both figures are measured on the *same* held-out test set of 1,370 articles, which took no part
in any modelling decision. That is a **39% reduction in misclassified articles**.

Per-class on the held-out set:

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| COMEDY | 0.964 | 0.982 | 0.973 | 792 |
| CRIME | 0.975 | 0.950 | 0.962 | 578 |

---

## Files

| File | What it is |
|---|---|
| `W4 Text Classification (News Category) v002.ipynb` | The submission. Fully executed, all outputs and plots saved. |
| `News Category (Text).csv` | The dataset (6,864 HuffPost articles, COMEDY / CRIME). |
| `news_category_model.joblib` | The fitted final pipeline — vectorisers, calibration and all three classifiers in one object. |
| `requirements.txt` | Exact package versions used for the run. |
| `README.md` | This file. |

### Running it

**Locally** — Python 3.11:

```bash
pip install -r requirements.txt
jupyter notebook "W4 Text Classification (News Category) v002.ipynb"
```

Run all cells. Total runtime is about 90 seconds on CPU; the CSV is found automatically because
it sits beside the notebook.

**In Google Colab** — upload the notebook and the CSV, then run all cells. The first cell detects
Colab, mounts Drive and installs the two packages Colab lacks. The loader checks the original
`v001` Drive path (`/content/drive/MyDrive/AI4AnF/Data/`) as well as `/content/`.

Nothing needs a GPU. The optional BERT section (Section 17) is switched off by default.

---

## Data pre-processing

Five cleaning stages were built as separately switchable functions, then **measured** by
stratified 5-fold cross-validation rather than applied on faith (notebook Section 6):

| Stage | Operation | Verdict |
|---|---|---|
| S1 | Unicode NFKD → ASCII, HTML un-escaping, lowercase, whitespace collapse | **kept** |
| S2 | Contraction expansion (`n't` → ` not`) | no gain over S1 |
| S3 | Strip URLs, digits, punctuation | no gain over S1 |
| S4 | Stop-word removal (negations retained) | **harmful** — −0.4 F1 |
| S5 | Lemmatisation | recovers S4's loss, no gain over S1 |

Two findings worth the marker's attention:

1. **Stop-word removal made the model worse.** TF-IDF with `sublinear_tf` already down-weights
   ubiquitous words continuously, without discarding anything, so deleting them is redundant —
   and it destroys bigram evidence (`not guilty` cannot form once `not` is gone).
2. **Lemmatisation added nothing.** With ~6,800 documents there are enough examples of each
   inflected form for the model to learn them separately.

Also applied: the 14 duplicated stories are removed **before** the split (a duplicate straddling
train and test inflates the score), and `short_description` is appended to `headline` with
missing values filled as empty strings — 21% of rows have no description, so it cannot replace
the headline.

### Columns deliberately excluded

`link`, `authors`, `date` and the index column are dropped, and the notebook shows why (Section 4):

- **`authors`** — 782 of 824 bylines (95%) write for exactly one category. A model using it would
  be identifying journalists, not classifying text, and would collapse on an unseen writer.
- **`link`** — the URL slug is a rewritten copy of the headline (69% word overlap), so it adds no
  information while giving character n-grams a second channel to the same text.
- **`date`** — both classes span the identical window.

Restricting the features to `headline` and `short_description` costs some score. It is the
difference between a text classifier and a lookup table.

---

## Modelling

- **Features** — `FeatureUnion` of word 1–2 gram TF-IDF and `char_wb` 3–5 gram TF-IDF, both with
  sublinear term frequency: 53,950 features. Character n-grams were the single largest
  contributor (+1.1 F1 points), because they survive the inflections, names and spellings that
  break word features on short headlines.
- **Model selection** — 10 feature/classifier combinations compared by stratified 5-fold CV
  *inside the training set*, then `GridSearchCV` over `C` and `min_df`, then a soft-voting
  ensemble of LogisticRegression, a calibrated LinearSVC and ComplementNB.
- **Evaluation** — macro-F1 throughout, since the classes are 58/42 and plain accuracy flatters a
  majority-class guesser. The test set was opened once, in Section 13.
- **Everything is a `Pipeline`**, so no transform is ever fitted on data it will later be scored on.
- Also included: decision-threshold tuning (chosen on training folds, applied to test),
  a precision-recall curve, top model coefficients per class, and inspection of the 43 errors.

XGBoost was tried and finished last (0.9303). Axis-aligned splits are a poor fit for tens of
thousands of sparse near-orthogonal TF-IDF columns — linear models still own this problem shape.

---

## Corrections to `v001`

Both are documented in the notebook where they occur rather than silently patched, since each
produces a plausible-looking number instead of an error:

1. **Section 8** — `CountVectorizer().fit_transform(X)` is called on the whole dataset before the
   split, so the vocabulary is learned partly from the test rows. Also `acc = (cm[0,0] + cm[1,1])
   / sum(sum(cm))` reads a 2×2 diagonal by hand; on the full 40-category HuffPost dataset the same
   line silently returns the accuracy of the first two classes only.
2. **Section 9** — a *second* `TfidfTransformer` is fitted on the test set
   (`TfidfTransformer().fit_transform(X_test)`), so train and test end up weighted by different
   IDF vectors. Cost on this data: 0.15 F1 points — small enough to pass unnoticed, which is
   exactly the danger.
3. **Section 17** — in the BERT cells, `model` is reassigned from the SentenceTransformer to the
   classifier, and the fit uses `Y_train`/`Y_test` left over from the previous section rather than
   the `y_train`/`y_test` just created, so that section's reported accuracy was meaningless.
   Corrected in the (optional, off by default) code.

---

## Honest limitations

- The gap between the ensemble and a single tuned linear model is one article out of 1,370 — well
  inside noise. The ensemble is justified by its calibrated probabilities, not its F1.
- Hyper-parameter tuning gained 0.08 points in cross-validation and **nothing** on the test set.
  Reported as measured.
- This is a two-class extract. The full HuffPost dataset has 40+ categories, where macro-F1 falls
  substantially and the class imbalance becomes severe.
- Remaining errors are largely genuine ambiguity — comedians joking about crime, crime stories
  written lightly — which no amount of tuning recovers.
