"""Validated difference-in-differences analysis for the paid-search example.

The original notebook assumed a case-insensitive filesystem and a particular
working directory.  These helpers make the bundled-data workflow portable and
fail closed when the panel is malformed instead of silently dropping DMAs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "date",
    "dma",
    "treatment_period",
    "search_stays_on",
    "revenue",
}
DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "08_Returns_to_ads" / "PaidSearch.csv"


@dataclass(frozen=True)
class DidResult:
    rows: int
    dmas: int
    treated_dmas: int
    control_dmas: int
    treated_log_change: float
    control_log_change: float
    log_effect: float
    standard_error: float
    ci_lower: float
    ci_upper: float
    revenue_ratio: float
    revenue_ratio_ci_lower: float
    revenue_ratio_ci_upper: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_paid_search(path: str | Path | None = None) -> tuple[pd.DataFrame, Path]:
    """Load the bundled dataset or an explicit CSV path.

    Resolving the default relative to this module makes execution independent
    of the caller's current working directory and preserves Linux filename
    casing.
    """

    dataset = Path(path).expanduser().resolve() if path is not None else DEFAULT_DATASET
    if not dataset.is_file():
        raise FileNotFoundError(f"paid-search dataset not found: {dataset}")
    return pd.read_csv(dataset), dataset


def _validated_dma_changes(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("dataset must contain at least one row")

    numeric = frame[["dma", "treatment_period", "search_stays_on", "revenue"]]
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("analysis columns must contain only finite values")
    if not set(frame["treatment_period"].unique()).issubset({0, 1}):
        raise ValueError("treatment_period must contain only 0 (pre) and 1 (post)")
    if set(frame["treatment_period"].unique()) != {0, 1}:
        raise ValueError("dataset must contain both pre and post periods")
    if not set(frame["search_stays_on"].unique()).issubset({0, 1}):
        raise ValueError("search_stays_on must contain only 0 or 1")
    if (frame["revenue"] <= 0).any():
        raise ValueError("revenue must be strictly positive before log transformation")

    assignments = frame.groupby("dma", sort=True)["search_stays_on"].nunique()
    if (assignments != 1).any():
        bad = assignments[assignments != 1].index.tolist()
        raise ValueError(f"treatment assignment changes within DMA(s): {bad[:5]}")

    work = frame.copy()
    work["log_revenue"] = np.log(work["revenue"].astype(float))
    panel = work.pivot_table(
        index=["dma", "search_stays_on"],
        columns="treatment_period",
        values="log_revenue",
        aggfunc="mean",
    )
    incomplete = panel[panel.isna().any(axis=1)]
    if not incomplete.empty:
        bad = [str(index[0]) for index in incomplete.index[:5]]
        raise ValueError(f"DMA(s) missing a pre or post period: {', '.join(bad)}")
    panel = panel.rename(columns={0: "pre", 1: "post"}).reset_index()
    panel["log_change"] = panel["post"] - panel["pre"]
    return panel


def analyze_paid_search(frame: pd.DataFrame) -> tuple[DidResult, pd.DataFrame]:
    """Compute the DMA-level difference in mean daily log revenue.

    ``search_stays_on == 0`` identifies treated DMAs where paid search was
    switched off.  The estimate is their pre/post log change minus the change
    among control DMAs where paid search stayed on.
    """

    panel = _validated_dma_changes(frame)
    treated = panel.loc[panel["search_stays_on"] == 0, "log_change"]
    control = panel.loc[panel["search_stays_on"] == 1, "log_change"]
    if len(treated) < 2 or len(control) < 2:
        raise ValueError("analysis requires at least two treated and two control DMAs")

    treated_mean = float(treated.mean())
    control_mean = float(control.mean())
    effect = treated_mean - control_mean
    standard_error = float(np.sqrt(treated.var(ddof=1) / len(treated) + control.var(ddof=1) / len(control)))
    lower = effect - 1.96 * standard_error
    upper = effect + 1.96 * standard_error
    result = DidResult(
        rows=len(frame),
        dmas=len(panel),
        treated_dmas=len(treated),
        control_dmas=len(control),
        treated_log_change=treated_mean,
        control_log_change=control_mean,
        log_effect=effect,
        standard_error=standard_error,
        ci_lower=lower,
        ci_upper=upper,
        revenue_ratio=float(np.exp(effect)),
        revenue_ratio_ci_lower=float(np.exp(lower)),
        revenue_ratio_ci_upper=float(np.exp(upper)),
    )
    return result, panel
