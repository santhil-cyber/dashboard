"""
Configuration module for Bank Nifty LSTM Price Prediction Pipeline.

Centralises all hyperparameters, file paths, feature-engineering settings,
and training options so that experiments are reproducible and easy to tweak.
"""

import os
from dataclasses import dataclass, field
from typing import List

# ──────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "models", "saved")
LOG_DIR = os.path.join(BASE_DIR, "logs")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)


@dataclass
class DataConfig:
    """Data ingestion & preprocessing parameters."""

    ticker: str = "^NSEBANK"
    start_date: str = "2007-09-05"
    end_date: str = "2026-04-25"
    train_split_date: str = "2024-01-31"
    target_col: str = "Close"
    feature_cols: List[str] = field(
        default_factory=lambda: [
            "Open", "High", "Low", "Close", "Volume",
            "MA_7", "MA_21", "EMA_12", "EMA_26",
            "RSI_14", "MACD", "MACD_Signal",
            "BB_Upper", "BB_Lower", "BB_Width",
            "Log_Return", "Volatility_30d",
            "Momentum_10d", "ATR_14",
        ]
    )
    sequence_length: int = 60  # look-back window (trading days)
    scale_method: str = "minmax"  # 'minmax' | 'standard' | 'robust'
    raw_csv: str = os.path.join(DATA_DIR, "bank_nifty_raw.csv")
    processed_csv: str = os.path.join(DATA_DIR, "bank_nifty_processed.csv")


@dataclass
class ModelConfig:
    """LSTM architecture hyper-parameters."""

    lstm_units: List[int] = field(default_factory=lambda: [128, 64, 32])
    dropout_rate: float = 0.2
    recurrent_dropout: float = 0.1
    dense_units: List[int] = field(default_factory=lambda: [64, 32])
    activation: str = "relu"
    output_units: int = 1
    use_attention: bool = True
    use_bidirectional: bool = False
    kernel_regularizer_l2: float = 1e-4


@dataclass
class TrainingConfig:
    """Training loop options."""

    epochs: int = 50
    batch_size: int = 32
    learning_rate: float = 1e-3
    lr_scheduler: str = "cosine"  # 'cosine' | 'step' | 'plateau'
    lr_decay_steps: int = 10
    lr_decay_rate: float = 0.9
    early_stopping_patience: int = 8
    reduce_lr_patience: int = 4
    min_lr: float = 1e-6
    optimizer: str = "adam"  # 'adam' | 'adamw' | 'sgd'
    loss_function: str = "huber"  # 'mse' | 'mae' | 'huber'
    validation_split: float = 0.15
    shuffle_train: bool = False  # time-series — keep order
    random_seed: int = 42
    checkpoint_path: str = os.path.join(MODEL_DIR, "best_model.keras")
    final_model_path: str = os.path.join(MODEL_DIR, "final_model.keras")
    history_path: str = os.path.join(ARTIFACTS_DIR, "training_history.json")


@dataclass
class EvalConfig:
    """Evaluation & reporting options."""

    confidence_level: float = 0.95  # for prediction intervals
    bootstrap_samples: int = 1000
    report_path: str = os.path.join(ARTIFACTS_DIR, "evaluation_report.json")
    plot_dir: str = os.path.join(ARTIFACTS_DIR, "plots")


# ──────────────────────────────────────────────────────────────
# Singleton instances
# ──────────────────────────────────────────────────────────────
data_cfg = DataConfig()
model_cfg = ModelConfig()
train_cfg = TrainingConfig()
eval_cfg = EvalConfig()
