"""
Utility helpers for the Bank Nifty LSTM pipeline.

Contains reusable functions for logging, timing, data validation,
and common financial calculations.
"""

import os
import time
import logging
import functools
from typing import Callable, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Timing Decorator
# ──────────────────────────────────────────────────────────────

def timer(func: Callable) -> Callable:
    """Decorator that logs the execution time of a function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info("⏱  %s executed in %.2fs", func.__name__, elapsed)
        return result
    return wrapper


# ──────────────────────────────────────────────────────────────
# Data Validation
# ──────────────────────────────────────────────────────────────

def validate_dataframe(df: pd.DataFrame, required_cols: list) -> bool:
    """Check that DataFrame contains all required columns and has no NaN in them."""
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    nan_counts = df[required_cols].isna().sum()
    cols_with_nan = nan_counts[nan_counts > 0]
    if not cols_with_nan.empty:
        logger.warning("Columns with NaN:\n%s", cols_with_nan.to_string())
        return False
    return True


def check_stationarity(series: pd.Series, significance: float = 0.05) -> dict:
    """
    Perform Augmented Dickey-Fuller test for stationarity.

    Returns dict with test statistic, p-value, and whether the series
    is stationary at the given significance level.
    """
    from statsmodels.tsa.stattools import adfuller

    result = adfuller(series.dropna(), autolag="AIC")
    return {
        "test_statistic": round(result[0], 4),
        "p_value": round(result[1], 6),
        "lags_used": result[2],
        "n_observations": result[3],
        "is_stationary": result[1] < significance,
        "critical_values": {k: round(v, 4) for k, v in result[4].items()},
    }


# ──────────────────────────────────────────────────────────────
# Financial Calculations
# ──────────────────────────────────────────────────────────────

def compute_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.065,
    periods_per_year: int = 252,
) -> float:
    """Annualised Sharpe ratio."""
    excess = returns - risk_free_rate / periods_per_year
    if np.std(excess) == 0:
        return 0.0
    return float(np.mean(excess) / np.std(excess) * np.sqrt(periods_per_year))


def compute_max_drawdown(prices: np.ndarray) -> dict:
    """Compute maximum drawdown and its duration."""
    cummax = np.maximum.accumulate(prices)
    drawdown = (prices - cummax) / cummax
    max_dd = float(np.min(drawdown))
    peak_idx = int(np.argmax(cummax[:np.argmin(drawdown) + 1]))
    trough_idx = int(np.argmin(drawdown))
    return {
        "max_drawdown": round(max_dd * 100, 2),
        "peak_index": peak_idx,
        "trough_index": trough_idx,
        "duration_days": trough_idx - peak_idx,
    }


def compute_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.065,
    periods_per_year: int = 252,
) -> float:
    """Annualised Sortino ratio (downside deviation only)."""
    excess = returns - risk_free_rate / periods_per_year
    downside = excess[excess < 0]
    if len(downside) == 0 or np.std(downside) == 0:
        return 0.0
    return float(np.mean(excess) / np.std(downside) * np.sqrt(periods_per_year))


# ──────────────────────────────────────────────────────────────
# Array Helpers
# ──────────────────────────────────────────────────────────────

def sliding_window(arr: np.ndarray, window_size: int) -> np.ndarray:
    """Create a sliding window view of a 1D array."""
    n = len(arr) - window_size + 1
    return np.lib.stride_tricks.as_strided(
        arr, shape=(n, window_size), strides=(arr.strides[0], arr.strides[0])
    )


def normalize_series(series: np.ndarray) -> tuple:
    """Min-max normalise to [0, 1]. Returns (normalised, min, max)."""
    mn, mx = series.min(), series.max()
    rng = mx - mn if mx != mn else 1.0
    return (series - mn) / rng, mn, mx


def inverse_normalize(normalised: np.ndarray, mn: float, mx: float) -> np.ndarray:
    """Reverse min-max normalisation."""
    return normalised * (mx - mn) + mn


# ──────────────────────────────────────────────────────────────
# Logging Setup
# ──────────────────────────────────────────────────────────────

def setup_logger(name: str, log_file: str = None, level=logging.INFO) -> logging.Logger:
    """Create a configured logger with console and optional file handler."""
    log = logging.getLogger(name)
    log.setLevel(level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        log.addHandler(fh)

    return log
