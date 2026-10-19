"""Robustness probes — does the model hold up when the message is perturbed?

Run with::

    python -m src.robustness

The test set measures messages like the ones the model trained on. These
probes ask targeted questions it cannot: does the verdict survive the
obfuscation smishing uses (``DB5``, ``acc0unt``)? Does it depend on the
``http://`` prefix rather than the message? Does an ordinary message with a
harmless link get called a scam?

Each probe is a small set of variants of one message, written for this check.
They are constructed, not collected, so they are reported as behaviour, never
as an accuracy figure. Results go to ``reports/robustness_probes.csv``.
"""

from __future__ import annotations

import sys

import pandas as pd

from .config import CFG
from .predict import predict

# (probe, variant, text, the verdict a user would want)
PROBES = [
    # Obfuscation: the same scam, spelled the way scammers spell it.
    ("obfuscation", "plain", "Your DBS account has been locked. Verify now at http://dbs-sg-verify.top", "smishing"),
    ("obfuscation", "leetspeak", "Y0ur DB5 acc0unt has been l0cked. Verify now at http://dbs-sg-verify.top", "smishing"),
    ("obfuscation", "plain", "Your OCBC card is suspended. Reactivate at http://ocbc-secure.co/login", "smishing"),
    ("obfuscation", "leetspeak", "Y0ur 0CBC card is susp3nded. Reactivate at http://ocbc-secure.co/login", "smishing"),
    # Link form: does the verdict hinge on the http:// prefix?
    ("link_form", "http", "Your parcel is held at customs. Pay the fee at http://sgpost-clear.co/pay", "smishing"),
    ("link_form", "bare domain", "Your parcel is held at customs. Pay the fee at sgpost-clear.co/pay", "smishing"),
    ("link_form", "no link", "Your parcel is held at customs. Reply with your card number to pay the fee", "smishing"),
    # Harmless links: ordinary messages that happen to carry a URL.
    ("benign_link", "news", "check out this article https://www.straitstimes.com/singapore/abc", "ham"),
    ("benign_link", "maps", "Meet here later ok https://maps.google.com/?q=bugis+junction", "ham"),
    ("benign_link", "photos", "Uploaded the trip photos https://photos.app.goo.gl/xyz", "ham"),
    # Chat-style scams with no link, the weak spot on the Singapore set.
    ("no_link_scam", "new number", "Hi mum this is my new number, my phone broke. Can you PayNow me $500 urgently", "smishing"),
    ("no_link_scam", "job", "Hi, I am Jessica from Lazada HR. Part time job, earn $300-$800 daily. Interested?", "smishing"),
]


def run() -> pd.DataFrame:
    target = CFG.target_label
    rows = []
    for probe, variant, text, want in PROBES:
        p = predict(text, explain=False)
        rows.append(
            {
                "probe": probe,
                "variant": variant,
                "text": text,
                "wanted": want,
                "predicted": p.label,
                f"p_{target}": round(p.scores.get(target, 0.0), 3),
                "ok": p.label == want,
            }
        )
    table = pd.DataFrame(rows)

    print(f"{'=' * 60}\nROBUSTNESS PROBES (constructed messages; behaviour, not accuracy)")
    print(table.drop(columns="text").to_string(index=False))
    print(f"\n{table['ok'].sum()} of {len(table)} probes get the verdict a user would want")
    table.to_csv(CFG.reports_dir / "robustness_probes.csv", index=False)
    return table


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    run()
    sys.exit(0)
