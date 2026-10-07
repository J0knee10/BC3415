"""Configuration loading.

Every module reads its settings from ``config.yaml`` through this module, so
paths and label names are defined in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# The project root is the directory containing config.yaml, i.e. the parent of
# this file's parent. Resolved from __file__ so the pipeline runs identically
# from a notebook, a script or the repo root.
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"


@dataclass(frozen=True)
class Config:
    """Parsed ``config.yaml`` with paths resolved to absolute locations."""

    raw: dict[str, Any]

    # --- labels ---------------------------------------------------------
    @property
    def labels(self) -> list[str]:
        """Class names in a fixed order; this order sets the integer encoding."""
        return list(self.raw["labels"]["names"])

    @property
    def target_label(self) -> str:
        """The class the project is about — smishing."""
        return self.raw["labels"]["target"]

    @property
    def target_index(self) -> int:
        return self.labels.index(self.target_label)

    # --- paths ----------------------------------------------------------
    def path(self, key: str) -> Path:
        """Resolve a configured path to an absolute one, creating it if needed."""
        p = ROOT / self.raw["paths"][key]
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def raw_dir(self) -> Path:
        return self.path("raw")

    @property
    def processed_dir(self) -> Path:
        return self.path("processed")

    @property
    def artifacts_dir(self) -> Path:
        return self.path("artifacts")

    @property
    def reports_dir(self) -> Path:
        return self.path("reports")

    # --- sections -------------------------------------------------------
    @property
    def split(self) -> dict[str, Any]:
        return self.raw["split"]

    @property
    def normalise(self) -> dict[str, str]:
        return self.raw["normalise"]

    @property
    def evaluate(self) -> dict[str, Any]:
        return self.raw["evaluate"]

    def cost_matrix(self) -> list[list[float]]:
        """Cost matrix as a nested list in ``labels`` order (true x predicted)."""
        cm = self.raw["cost_matrix"]
        return [[float(cm[t][p]) for p in self.labels] for t in self.labels]


def load_config(path: Path | str = CONFIG_PATH) -> Config:
    """Read ``config.yaml``. Called once per entry point, not per function."""
    with open(path, "r", encoding="utf-8") as fh:
        return Config(raw=yaml.safe_load(fh))


# A module-level instance for convenience; modules that need isolation can call
# load_config() themselves with a different path.
CFG = load_config()
