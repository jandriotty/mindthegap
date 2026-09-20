"""Load and validate the engine configuration (config/*.toml and config/drug_classes.csv)."""
from __future__ import annotations

import csv
import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"

OR_BASES = {"study", "study-derived", "assumed"}


class ConfigError(ValueError):
    """The configuration is missing something or internally inconsistent."""


@dataclass(frozen=True)
class Factor:
    id: str
    label: str
    tier: int
    group: str | None
    or_ref: float
    or_basis: str
    points: float
    levels: dict
    prior: dict
    ask: str | None
    evidence: str


@dataclass(frozen=True)
class DrugEntry:
    drug: str
    cls: str
    factor: str
    level: float
    note: str


@dataclass
class Config:
    factors: dict
    scale: float
    scoring: dict
    icd: dict
    drugs: dict
    directory: Path = field(default=DEFAULT_CONFIG_DIR)

    def band_thresholds(self) -> dict:
        return self.scoring["bands"]


def _read_toml(path: Path) -> dict:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"missing config file: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc


def _load_factors(rules: dict) -> tuple:
    scale = float(rules.get("scale", {}).get("points_per_log_or", 3.0))
    factors = {}
    for fid, spec in rules.get("factors", {}).items():
        for key in ("label", "tier", "or_ref", "or_basis"):
            if key not in spec:
                raise ConfigError(f"factor '{fid}' is missing '{key}'")
        if spec["or_basis"] not in OR_BASES:
            raise ConfigError(f"factor '{fid}': or_basis must be one of {sorted(OR_BASES)}")
        or_ref = float(spec["or_ref"])
        if or_ref <= 1.0:
            raise ConfigError(f"factor '{fid}': or_ref must be > 1 (a risk factor)")
        points = round(scale * math.log(or_ref), 2)
        # A factor that can never be unknown (e.g. recency of service) needs no prior.
        prior = spec.get("prior", {"value": 0.0})
        if "value" not in prior and "base" not in prior:
            raise ConfigError(f"factor '{fid}': prior needs 'value' or 'base'")
        factors[fid] = Factor(
            id=fid, label=spec["label"], tier=int(spec["tier"]), group=spec.get("group"),
            or_ref=or_ref, or_basis=spec["or_basis"], points=points,
            levels=dict(spec.get("levels", {})), prior=dict(prior),
            ask=spec.get("ask"), evidence=spec.get("evidence", ""),
        )
    if not factors:
        raise ConfigError("rules.toml defines no factors")
    return factors, scale


def _load_drugs(path: Path, factors: dict) -> dict:
    drugs = {}
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["factor"] not in factors:
                    raise ConfigError(f"drug '{row['drug']}' maps to unknown factor '{row['factor']}'")
                drugs[row["drug"].strip().lower()] = DrugEntry(
                    row["drug"].strip().lower(), row["class"], row["factor"],
                    float(row["level"]), row.get("note", ""))
    except FileNotFoundError as exc:
        raise ConfigError(f"missing config file: {path}") from exc
    return drugs


def _validate_scoring(scoring: dict) -> None:
    for section in ("bands", "hazard", "confidence", "freshness_days", "reach", "capacity", "hvi"):
        if section not in scoring:
            raise ConfigError(f"scoring.toml is missing [{section}]")
    b = scoring["bands"]
    if not (b["urgent"] > b["high"] > b["moderate"] > 0):
        raise ConfigError("bands must satisfy urgent > high > moderate > 0")
    mult = scoring["hazard"]["level_multiplier"]
    for lvl in range(5):
        if str(lvl) not in mult:
            raise ConfigError(f"hazard.level_multiplier is missing level {lvl}")
    for lead in range(1, 8):
        if str(lead) not in scoring["hazard"]["trust"]["forecast_by_lead"]:
            raise ConfigError(f"hazard.trust.forecast_by_lead is missing lead {lead}")


def load_config(directory: str | Path | None = None) -> Config:
    d = Path(directory) if directory else DEFAULT_CONFIG_DIR
    factors, scale = _load_factors(_read_toml(d / "rules.toml"))
    scoring = _read_toml(d / "scoring.toml")
    _validate_scoring(scoring)
    icd = _read_toml(d / "icd_map.toml")
    drugs = _load_drugs(d / "drug_classes.csv", factors)
    return Config(factors=factors, scale=scale, scoring=scoring, icd=icd, drugs=drugs, directory=d)
