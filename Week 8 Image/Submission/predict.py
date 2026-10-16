"""Pneumonia chest X-ray classifier - inference and web demo.

Uses the model and settings saved by Section 9 of
"W6-01 CNN (Plain Vanilla) Pneumonia v003.ipynb" (folder `deploy/`).

    python predict.py path/to/xray.jpeg [more.jpeg ...]    # command line
    python predict.py --web                                # Gradio web app (pip install gradio)

Coursework demo only, not for clinical use.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2

DEPLOY = Path(__file__).resolve().parent / 'deploy'


def preprocess(path, size, clip_limit=2.0, tile=(8, 8)):
    # identical to the notebook: greyscale -> CLAHE -> centre crop -> resize
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f'cannot read image: {path}')
    img = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tuple(tile)).apply(img)
    h, w = img.shape
    s = min(h, w)
    img = img[(h - s) // 2:(h - s) // 2 + s, (w - s) // 2:(w - s) // 2 + s]
    return cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)


class PneumoniaClassifier:
    def __init__(self, folder=DEPLOY):
        import keras
        folder = Path(folder)
        self.cfg = json.loads((folder / 'pneumonia_config.json').read_text())
        self.model = keras.models.load_model(folder / self.cfg['model'])

    def predict(self, path):
        c = self.cfg
        x = preprocess(path, c['img_size'], c['clahe']['clipLimit'], c['clahe']['tileGridSize'])
        p = float(self.model.predict(x[None, ..., None].astype('float32'), verbose=0)[0, 1])
        return {'prediction': c['classes'][int(p >= c['threshold'])], 'p_pneumonia': round(p, 4)}


def web(clf):
    import gradio as gr

    def ui(path):
        p = clf.predict(path)['p_pneumonia']
        return {'PNEUMONIA': p, 'NORMAL': 1 - p}

    gr.Interface(ui, gr.Image(type='filepath', label='Chest X-ray'), gr.Label(label='Prediction'),
                 title='Pneumonia chest X-ray classifier',
                 description=f"Decision threshold {clf.cfg['threshold']}. BC3415 coursework demo, not for clinical use."
                 ).launch()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('images', nargs='*', help='chest X-ray image files')
    ap.add_argument('--web', action='store_true', help='launch the Gradio web app')
    args = ap.parse_args()
    if not args.images and not args.web:
        ap.print_help(); sys.exit(1)
    clf = PneumoniaClassifier()
    for f in args.images:
        print(f, json.dumps(clf.predict(f)))
    if args.web:
        web(clf)
