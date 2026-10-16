# W6-01 CNN (Plain Vanilla) Pneumonia — v003

**BC3415 Artificial Intelligence in Accounting & Finance**
Week 8 (Image) workshop submission — Option 2

Configure and deploy the `WS_Colab_Image` CNN notebook on the Pneumonia chest X-ray data, judged on
**data pre-processing** and **F1 score**.

**Approach:** the CNN from `W6-01 CNN (Plain Vanilla) Pneumonia v002` is kept unchanged. It is run as supplied
(*before*), then trained again on pre-processed data (*after*). Since the model is the same, the improvement comes
from the data.

---

## Result

Official Kaggle test set, 624 images, which was not used for any decision:

| | F1 (pneumonia) | macro-F1 | accuracy | healthy children correctly cleared | test errors |
|---|---|---|---|---|---|
| Before: `v002` as supplied | 0.830 | 0.661 | 0.745 | 77 / 234 | 159 |
| **After: same CNN, pre-processed data** | **0.867** | **0.770** | **0.811** | **121 / 234** | **118** |

**41 fewer mistakes (−26%).** Pneumonia recall stays at about 99% (385 of 390 found) while false alarms on healthy
children drop from 157 to 113.

The *before* F1 of 0.830 flatters the original notebook. Answering PNEUMONIA for every image would already score
0.769, because 62.5% of the test set is pneumonia. Macro-F1 (0.661 → 0.770) shows the real change.

---

## Files

| File | What it is |
|---|---|
| `W6-01 CNN (Plain Vanilla) Pneumonia v003.ipynb` | The submission. Fully executed, all outputs and plots saved. |
| `deploy/pneumonia_cnn.keras` | The trained model (includes the 0–1 pixel scaling). |
| `deploy/pneumonia_config.json` | Image size, CLAHE settings, decision threshold (0.54), class names, test scores. |
| `predict.py` | Deployment script: predicts from image files on the command line, or runs a Gradio web app with `--web`. |
| `requirements.txt` | Exact package versions used for the run. |
| `README.md` | This file. |

The dataset (Kaggle `paultimothymooney/chest-xray-pneumonia`, about 1.2 GB) is not included. The notebook downloads it
automatically.

### Running it

**Google Colab:** upload the notebook and choose Run all. The first cell installs `kagglehub`, and Section 2
downloads the dataset (no Kaggle account needed). It also looks in the original `v002` Drive folder
`/content/drive/MyDrive/AI4AnF/Data/Pneumonia` if Drive is mounted.

**Locally:** Python 3.13:

```bash
pip install -r requirements.txt
jupyter notebook "W6-01 CNN (Plain Vanilla) Pneumonia v003.ipynb"
```

About 15 minutes on a laptop CPU, of which 10 minutes is the 30-epoch *before* run.

**Using the deployed model:**

```bash
python predict.py chest_xray.jpeg            # -> {"prediction": "PNEUMONIA", "p_pneumonia": 0.9962}
python predict.py --web                      # browser demo (pip install gradio)
```

---

## Configuration fix

`v002` does not run on current Colab. It loads images with `ImageDataGenerator`, which was removed in Keras 3, so the
import fails. It is replaced with `keras.utils.image_dataset_from_directory`, which with default options gives the same
data (raw 0–255 RGB pixels, one-hot labels). The hard-coded Drive path is replaced by a loader that finds or
downloads the dataset.

---

## Data audit: what was wrong with the data as supplied

1. **The `val` folder has 16 images.** Validation accuracy swung between 62.5% and 100% from one epoch to the next.
   It cannot be used to choose anything.
2. **Class imbalance:** 74% PNEUMONIA in training vs 62.5% in test.
3. **Mixed colour modes:** 283 files stored as RGB, the rest greyscale. They are all greyscale X-rays.
4. **32 byte-identical duplicate files.**
5. **Image shape gives away the class.** PNEUMONIA films are smaller and wider (median aspect 1.49) than NORMAL ones
   (1.23). Aspect ratio alone, with no pixels used, predicts the class with ROC-AUC 0.84. Squashing every film into a
   square distorts the two classes differently and gives the network a shortcut.
6. **Several images per patient:** 5,216 training images come from 2,846 patients.

## Pre-processing

| Step | What | Why |
|---|---|---|
| P1 | Remove exact duplicates | a duplicate in both training and validation inflates the score |
| P2 | Merge `train` + `val`, hold out 1/7 of **patients** as a new validation set (744 images), stratified | a usable validation set, with no child on both sides |
| P3 | Greyscale, 1 channel | X-rays are single-channel |
| P4 | Centre-crop to square, then resize to 150×150 | removes the shape shortcut (audit point 5) without distorting anatomy |
| P5 | CLAHE contrast enhancement | evens out exposure differences between X-ray machines |
| P6 | Scale pixels to 0–1 | `v002` fed raw 0–255 values into the network |
| P7 | Augmentation (rotation ±5°, zoom, shift, contrast; **no flips**) | variety in positioning and exposure; a mirrored X-ray puts the heart on the wrong side |
| P8 | Class weights (NORMAL 1.93, PNEUMONIA 0.67) | counter the 74% majority |

The new validation set also makes two training-side improvements possible:
- **Keep the best epoch** (lowest validation loss) instead of the last one.
- **Choose the decision threshold** on validation (0.54, maximising macro-F1). The test set is not used.

---

## Limitations

- **Validation is easier than test:** macro-F1 0.94 on validation vs 0.77 on test. Validation comes from the same
  pool as training; the test images, especially NORMAL ones, differ. 113 of the 118 remaining errors are healthy
  children labelled PNEUMONIA. This is a known property of this dataset.
- **One training run per configuration** (no repeated seeds). The 41-error gap is well above run-to-run noise.
- **The pre-processing steps are applied together** and not scored one by one, to keep the run short.
- **Paediatric X-rays from a single source.** Coursework only, **not for clinical use**.
