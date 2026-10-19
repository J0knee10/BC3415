"""Figures for the technical writeup, drawn from Indiv/reports/.

    python make_figures.py     (run with the project venv)
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import pandas as pd

HERE = Path(__file__).parent
REPORTS = HERE.parent / "Indiv" / "reports"
OUT = HERE / "fig"
OUT.mkdir(exist_ok=True)

INK, MUTED, GRID = "#1f1e1d", "#6b6a66", "#e6e5e1"
CAUGHT, WARNED, MISSED = "#3b6fd4", "#cfcdc7", "#e07a7a"  # blue pole, gray midpoint, red pole

plt.rcParams.update(
    {
        "font.family": "Segoe UI",
        "font.size": 9,
        "text.color": INK,
        "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": INK,
    }
)

NAMES = {
    "banking_impersonation": "Bank",
    "job_offer": "Job offer",
    "delivery_parcel": "Parcel delivery",
    "ecommerce": "Carousell / e-commerce",
    "government_impersonation": "Government",
    "other": "Other",
    "telco_impersonation": "Telco",
    "investment": "Investment",
}


def sg_scams() -> None:
    df = pd.read_csv(REPORTS / "sg_scams_predictions.csv")
    s = df[df["label"] == "smishing"]
    g = (
        s.assign(
            caught=s["predicted"].eq("smishing"),
            warned=s["predicted"].eq("spam"),
            missed=s["predicted"].eq("ham"),
        )
        .groupby("scam_type")[["caught", "warned", "missed"]]
        .sum()
    )
    g["n"] = g.sum(axis=1)
    g = g.sort_values(["n", "caught"], ascending=True)

    fig, ax = plt.subplots(figsize=(6.6, 3.0), dpi=200)
    y = range(len(g))
    left = [0] * len(g)
    for col, color, label in [
        ("caught", CAUGHT, "caught as smishing"),
        ("warned", WARNED, "called spam (still warned)"),
        ("missed", MISSED, "passed as legitimate (missed)"),
    ]:
        ax.barh(y, g[col], left=left, color=color, height=0.62, label=label,
                edgecolor="white", linewidth=1.5)
        left = [a + b for a, b in zip(left, g[col])]

    for i, (name, row) in enumerate(g.iterrows()):
        ax.text(row["n"] + 0.25, i, f"{row['caught']} of {row['n']} caught",
                va="center", fontsize=8, color=MUTED)

    ax.set_yticks(list(y), [NAMES.get(t, t) for t in g.index])
    ax.set_xlabel("scam messages")
    ax.set_xlim(0, g["n"].max() + 4.5)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5))
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, frameon=False,
              fontsize=8, handlelength=1.2)
    fig.tight_layout()
    fig.savefig(OUT / "sg_scams.png")
    plt.close(fig)


if __name__ == "__main__":
    sg_scams()
    print("wrote", OUT / "sg_scams.png")
