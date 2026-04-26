"""
Training Script for Bank Nifty LSTM Prediction
================================================
Orchestrates model compilation, callback setup, training loop,
and artefact persistence (checkpoints, history, plots).

Usage:
    python train.py
    python train.py --epochs 100 --batch-size 64
"""

import os
import json
import argparse
import logging
from datetime import datetime

import numpy as np
import tensorflow as tf
from tensorflow.keras.callbacks import (
    EarlyStopping,
    ModelCheckpoint,
    ReduceLROnPlateau,
    TensorBoard,
    CSVLogger,
)
from tensorflow.keras.optimizers import Adam, SGD
from tensorflow.keras.losses import Huber, MeanSquaredError, MeanAbsoluteError

from config import train_cfg, model_cfg, data_cfg, LOG_DIR, ARTIFACTS_DIR
from data_pipeline import run_pipeline
from models.lstm_model import build_lstm_model

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)


# ──────────────────────────────────────────────────────────────
# Reproducibility
# ──────────────────────────────────────────────────────────────

def set_seeds(seed: int = train_cfg.random_seed):
    """Set all random seeds for reproducibility."""
    np.random.seed(seed)
    tf.random.set_seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    logger.info("Random seeds set → %d", seed)


# ──────────────────────────────────────────────────────────────
# Loss & Optimiser
# ──────────────────────────────────────────────────────────────

LOSS_MAP = {
    "mse": MeanSquaredError,
    "mae": MeanAbsoluteError,
    "huber": Huber,
}

OPTIM_MAP = {
    "adam": lambda lr: Adam(learning_rate=lr, clipnorm=1.0),
    "adamw": lambda lr: tf.keras.optimizers.AdamW(learning_rate=lr, clipnorm=1.0),
    "sgd": lambda lr: SGD(learning_rate=lr, momentum=0.9, nesterov=True),
}


# ──────────────────────────────────────────────────────────────
# Callbacks
# ──────────────────────────────────────────────────────────────

def get_callbacks() -> list:
    """Build standard training callbacks."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cb = [
        EarlyStopping(
            monitor="val_loss",
            patience=train_cfg.early_stopping_patience,
            restore_best_weights=True,
            verbose=1,
        ),
        ModelCheckpoint(
            filepath=train_cfg.checkpoint_path,
            monitor="val_loss",
            save_best_only=True,
            verbose=1,
        ),
        ReduceLROnPlateau(
            monitor="val_loss",
            factor=train_cfg.lr_decay_rate,
            patience=train_cfg.reduce_lr_patience,
            min_lr=train_cfg.min_lr,
            verbose=1,
        ),
        TensorBoard(
            log_dir=os.path.join(LOG_DIR, f"run_{timestamp}"),
            histogram_freq=1,
            write_graph=True,
        ),
        CSVLogger(
            os.path.join(LOG_DIR, f"training_log_{timestamp}.csv"),
            append=False,
        ),
    ]
    return cb


# ──────────────────────────────────────────────────────────────
# Training
# ──────────────────────────────────────────────────────────────

def train(
    epochs: int = train_cfg.epochs,
    batch_size: int = train_cfg.batch_size,
    learning_rate: float = train_cfg.learning_rate,
) -> dict:
    """
    End-to-end training: data → model → fit → save.

    Returns
    -------
    dict with 'model', 'history', 'splits'
    """
    set_seeds()

    # ── Data ──
    logger.info("=" * 60)
    logger.info("PHASE 1 — Data Pipeline")
    logger.info("=" * 60)
    splits = run_pipeline()

    X_train, y_train = splits["X_train"], splits["y_train"]
    X_test, y_test = splits["X_test"], splits["y_test"]

    logger.info("Train: %s → %s", X_train.shape, y_train.shape)
    logger.info("Test : %s → %s", X_test.shape, y_test.shape)

    # ── Model ──
    logger.info("=" * 60)
    logger.info("PHASE 2 — Model Construction")
    logger.info("=" * 60)
    input_shape = (X_train.shape[1], X_train.shape[2])
    model = build_lstm_model(input_shape=input_shape)

    loss_fn = LOSS_MAP.get(train_cfg.loss_function, Huber)()
    optimizer = OPTIM_MAP.get(train_cfg.optimizer, OPTIM_MAP["adam"])(learning_rate)

    model.compile(
        optimizer=optimizer,
        loss=loss_fn,
        metrics=["mae", "mse"],
    )
    model.summary(print_fn=lambda s: logger.info(s))

    # ── Fit ──
    logger.info("=" * 60)
    logger.info("PHASE 3 — Training (%d epochs, batch %d)", epochs, batch_size)
    logger.info("=" * 60)

    history = model.fit(
        X_train, y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=train_cfg.validation_split,
        callbacks=get_callbacks(),
        shuffle=train_cfg.shuffle_train,
        verbose=1,
    )

    # ── Save ──
    model.save(train_cfg.final_model_path)
    logger.info("Final model saved → %s", train_cfg.final_model_path)

    # Persist training history
    hist_dict = {k: [float(v) for v in vals] for k, vals in history.history.items()}
    hist_dict["best_epoch"] = int(np.argmin(hist_dict["val_loss"])) + 1
    hist_dict["best_val_loss"] = float(min(hist_dict["val_loss"]))
    hist_dict["total_epochs_run"] = len(hist_dict["loss"])

    with open(train_cfg.history_path, "w") as f:
        json.dump(hist_dict, f, indent=2)
    logger.info("History saved → %s", train_cfg.history_path)

    logger.info("=" * 60)
    logger.info("✓ Training complete — Best val_loss: %.6f (epoch %d)",
                hist_dict["best_val_loss"], hist_dict["best_epoch"])
    logger.info("=" * 60)

    return {"model": model, "history": history, "splits": splits}


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Train Bank Nifty LSTM model")
    parser.add_argument("--epochs", type=int, default=train_cfg.epochs)
    parser.add_argument("--batch-size", type=int, default=train_cfg.batch_size)
    parser.add_argument("--lr", type=float, default=train_cfg.learning_rate)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = train(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )
    print(f"\n{'='*50}")
    print(f"  Model params : {result['model'].count_params():,}")
    print(f"  Epochs run   : {len(result['history'].history['loss'])}")
    print(f"  Final val MAE: {result['history'].history['val_mae'][-1]:.6f}")
    print(f"{'='*50}")
