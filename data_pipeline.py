"""
Data Pipeline for Bank Nifty LSTM Prediction
=============================================

Handles the complete data lifecycle:
  1. Fetch historical OHLCV data via yfinance
  2. Compute technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, etc.)
  3. Engineer additional features (log-returns, rolling volatility, momentum)
  4. Scale features with configurable scaler
  5. Create sliding-window sequences for LSTM input
  6. Split into train / validation / test sets respecting temporal order
"""

import os
import logging
from datetime import datetime
from typing import Tuple, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler, StandardScaler, RobustScaler
import joblib

from config import data_cfg, DATA_DIR, ARTIFACTS_DIR

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# ──────────────────────────────────────────────────────────────
# 1. Data Download
# ──────────────────────────────────────────────────────────────


def fetch_data(
    ticker: str = data_cfg.ticker,
    start: str = data_cfg.start_date,
    end: str = data_cfg.end_date,
    save_path: Optional[str] = data_cfg.raw_csv,
) -> pd.DataFrame:
    """
    Download historical OHLCV data from Yahoo Finance.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol (default: ^NSEBANK).
    start, end : str
        Date range in 'YYYY-MM-DD' format.
    save_path : str or None
        If provided, persist raw data to CSV.

    Returns
    -------
    pd.DataFrame with columns [Open, High, Low, Close, Volume] indexed by Date.
    """
    logger.info("Fetching %s data from %s to %s …", ticker, start, end)
    df = yf.download(ticker, start=start, end=end, progress=False)

    if df.empty:
        raise ValueError(f"No data returned for {ticker}. Check ticker / date range.")

    # Flatten multi-level columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(inplace=True)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        df.to_csv(save_path)
        logger.info("Raw data saved → %s  (%d rows)", save_path, len(df))

    return df


# ──────────────────────────────────────────────────────────────
# 2. Technical Indicators
# ──────────────────────────────────────────────────────────────


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute and append standard technical indicators."""
    df = df.copy()

    # Simple Moving Averages
    df["MA_7"] = df["Close"].rolling(window=7).mean()
    df["MA_21"] = df["Close"].rolling(window=21).mean()

    # Exponential Moving Averages
    df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["EMA_26"] = df["Close"].ewm(span=26, adjust=False).mean()

    # MACD
    df["MACD"] = df["EMA_12"] - df["EMA_26"]
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # Bollinger Bands (20-day, 2σ)
    bb_ma = df["Close"].rolling(window=20).mean()
    bb_std = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = bb_ma + 2 * bb_std
    df["BB_Lower"] = bb_ma - 2 * bb_std
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / bb_ma

    # RSI (14-day)
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.finfo(float).eps)
    df["RSI_14"] = 100 - (100 / (1 + rs))

    # ATR (14-day)
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR_14"] = true_range.rolling(window=14).mean()

    # Log Returns
    df["Log_Return"] = np.log(df["Close"] / df["Close"].shift(1))

    # Rolling Volatility (30-day annualised)
    df["Volatility_30d"] = df["Log_Return"].rolling(window=30).std() * np.sqrt(252)

    # Momentum (10-day log ratio)
    df["Momentum_10d"] = np.log(df["Close"] / df["Close"].shift(10))

    logger.info("Added %d technical indicators", 15)
    return df


# ──────────────────────────────────────────────────────────────
# 3. Preprocessing
# ──────────────────────────────────────────────────────────────

SCALER_MAP = {
    "minmax": MinMaxScaler,
    "standard": StandardScaler,
    "robust": RobustScaler,
}


def preprocess(
    df: pd.DataFrame,
    feature_cols: list = data_cfg.feature_cols,
    scale_method: str = data_cfg.scale_method,
) -> Tuple[pd.DataFrame, object]:
    """
    Clean, select features, and fit a scaler on the training portion.

    Returns
    -------
    (scaled_df, scaler)
    """
    df = df.copy()

    # Drop rows with NaN introduced by indicators
    initial_len = len(df)
    df.dropna(subset=feature_cols, inplace=True)
    logger.info(
        "Dropped %d rows with NaN (remaining: %d)", initial_len - len(df), len(df)
    )

    # Select features
    df_features = df[feature_cols].copy()

    # Fit scaler on training portion only
    split_date = pd.Timestamp(data_cfg.train_split_date)
    train_mask = df_features.index <= split_date
    scaler_cls = SCALER_MAP.get(scale_method, MinMaxScaler)
    scaler = scaler_cls()
    scaler.fit(df_features.loc[train_mask])

    # Transform full dataset
    scaled_values = scaler.transform(df_features)
    df_scaled = pd.DataFrame(scaled_values, index=df_features.index, columns=feature_cols)

    # Persist scaler for inference
    scaler_path = os.path.join(ARTIFACTS_DIR, "feature_scaler.pkl")
    joblib.dump(scaler, scaler_path)
    logger.info("Scaler saved → %s", scaler_path)

    return df_scaled, scaler


# ──────────────────────────────────────────────────────────────
# 4. Sequence Creation
# ──────────────────────────────────────────────────────────────


def create_sequences(
    data: np.ndarray,
    target_idx: int,
    seq_length: int = data_cfg.sequence_length,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build sliding-window sequences for LSTM.

    Parameters
    ----------
    data : np.ndarray of shape (n_samples, n_features)
    target_idx : int
        Column index of the target variable within `data`.
    seq_length : int
        Number of past time-steps in each input window.

    Returns
    -------
    X : np.ndarray of shape (n_sequences, seq_length, n_features)
    y : np.ndarray of shape (n_sequences,)
    """
    X, y = [], []
    for i in range(seq_length, len(data)):
        X.append(data[i - seq_length : i])
        y.append(data[i, target_idx])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


# ──────────────────────────────────────────────────────────────
# 5. Train / Test Split
# ──────────────────────────────────────────────────────────────


def temporal_split(
    df_scaled: pd.DataFrame,
    seq_length: int = data_cfg.sequence_length,
    target_col: str = data_cfg.target_col,
) -> dict:
    """
    Split into train and test sets at `train_split_date`, then create
    LSTM-ready sequences.

    Returns
    -------
    dict with keys: X_train, y_train, X_test, y_test, train_dates, test_dates
    """
    split_date = pd.Timestamp(data_cfg.train_split_date)

    # Find target column index
    target_idx = list(df_scaled.columns).index(target_col)

    train_df = df_scaled.loc[df_scaled.index <= split_date]
    test_df = df_scaled.loc[df_scaled.index > split_date]

    logger.info("Train samples: %d | Test samples: %d", len(train_df), len(test_df))

    # We need seq_length rows before test starts for context
    context_start = max(0, len(train_df) - seq_length)
    full_test_data = pd.concat([train_df.iloc[context_start:], test_df])

    X_train, y_train = create_sequences(train_df.values, target_idx, seq_length)
    X_test, y_test = create_sequences(full_test_data.values, target_idx, seq_length)

    # Corresponding dates (offset by seq_length)
    train_dates = train_df.index[seq_length:]
    test_dates = full_test_data.index[seq_length:]

    logger.info(
        "Sequences — Train: %s | Test: %s", X_train.shape, X_test.shape
    )

    return {
        "X_train": X_train,
        "y_train": y_train,
        "X_test": X_test,
        "y_test": y_test,
        "train_dates": train_dates,
        "test_dates": test_dates,
        "target_idx": target_idx,
        "n_features": X_train.shape[2],
    }


# ──────────────────────────────────────────────────────────────
# Convenience runner
# ──────────────────────────────────────────────────────────────


def run_pipeline() -> dict:
    """Execute the full data pipeline end-to-end."""
    df = fetch_data()
    df = add_technical_indicators(df)

    # Save processed data
    df.to_csv(data_cfg.processed_csv)
    logger.info("Processed data → %s", data_cfg.processed_csv)

    df_scaled, scaler = preprocess(df)
    splits = temporal_split(df_scaled)
    splits["scaler"] = scaler
    splits["raw_df"] = df

    logger.info("✓ Data pipeline complete")
    return splits


if __name__ == "__main__":
    splits = run_pipeline()
    print(f"\nTrain X shape : {splits['X_train'].shape}")
    print(f"Train y shape : {splits['y_train'].shape}")
    print(f"Test  X shape : {splits['X_test'].shape}")
    print(f"Test  y shape : {splits['y_test'].shape}")
    print(f"Features      : {splits['n_features']}")
