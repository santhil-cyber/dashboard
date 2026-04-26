"""
Evaluation & Metrics for Bank Nifty LSTM Prediction
=====================================================
Computes regression metrics, generates prediction intervals via
bootstrapping, and produces publication-quality diagnostic plots.
"""

import os
import json
import logging
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    mean_absolute_percentage_error,
    r2_score,
)
from scipy import stats
import tensorflow as tf

from config import eval_cfg, train_cfg, ARTIFACTS_DIR

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

PLOT_DIR = eval_cfg.plot_dir
os.makedirs(PLOT_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# Style
# ──────────────────────────────────────────────────────────────

plt.style.use("seaborn-v0_8-darkgrid")
sns.set_palette("husl")
COLORS = {"actual": "#6366f1", "pred": "#f59e0b", "error": "#f43f5e", "conf": "#8b5cf6"}


# ──────────────────────────────────────────────────────────────
# Core Metrics
# ──────────────────────────────────────────────────────────────

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Compute standard regression evaluation metrics.

    Returns dict with RMSE, MAE, MAPE, R², Directional Accuracy, Max Error.
    """
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    mape = float(mean_absolute_percentage_error(y_true, y_pred) * 100)
    r2 = float(r2_score(y_true, y_pred))

    # Directional accuracy
    if len(y_true) > 1:
        actual_dir = np.sign(np.diff(y_true))
        pred_dir = np.sign(np.diff(y_pred))
        dir_acc = float(np.mean(actual_dir == pred_dir) * 100)
    else:
        dir_acc = 0.0

    max_err = float(np.max(np.abs(y_true - y_pred)))

    metrics = {
        "RMSE": round(rmse, 4),
        "MAE": round(mae, 4),
        "MAPE": round(mape, 2),
        "R2": round(r2, 4),
        "Directional_Accuracy": round(dir_acc, 2),
        "Max_Error": round(max_err, 4),
    }
    return metrics


# ──────────────────────────────────────────────────────────────
# Prediction Intervals (Bootstrap)
# ──────────────────────────────────────────────────────────────

def bootstrap_prediction_intervals(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    confidence: float = eval_cfg.confidence_level,
    n_bootstrap: int = eval_cfg.bootstrap_samples,
) -> dict:
    """
    Estimate prediction intervals via residual bootstrapping.

    Returns lower and upper bounds plus the standard error.
    """
    residuals = y_true - y_pred
    alpha = 1 - confidence

    boot_means = []
    rng = np.random.default_rng(42)
    for _ in range(n_bootstrap):
        sample = rng.choice(residuals, size=len(residuals), replace=True)
        boot_means.append(np.mean(sample))

    boot_means = np.array(boot_means)
    lower_q = np.percentile(boot_means, (alpha / 2) * 100)
    upper_q = np.percentile(boot_means, (1 - alpha / 2) * 100)

    return {
        "lower_bound": y_pred + lower_q - 1.96 * np.std(residuals),
        "upper_bound": y_pred + upper_q + 1.96 * np.std(residuals),
        "std_error": float(np.std(residuals)),
        "mean_residual": float(np.mean(residuals)),
    }


# ──────────────────────────────────────────────────────────────
# Diagnostic Plots
# ──────────────────────────────────────────────────────────────

def plot_actual_vs_predicted(
    dates, y_true, y_pred, save_name="actual_vs_predicted.png"
):
    """Overlay plot of actual vs predicted prices."""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(dates, y_true, color=COLORS["actual"], linewidth=1.5, label="Actual", alpha=0.9)
    ax.plot(dates, y_pred, color=COLORS["pred"], linewidth=1.5, linestyle="--", label="Predicted", alpha=0.9)
    ax.set_title("Bank Nifty — Actual vs LSTM Predicted", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (₹)")
    ax.legend(frameon=True, fancybox=True)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, save_name), dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", save_name)


def plot_residuals(y_true, y_pred, save_name="residual_distribution.png"):
    """Histogram + KDE of prediction residuals."""
    residuals = y_true - y_pred
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram
    axes[0].hist(residuals, bins=40, color=COLORS["error"], alpha=0.65, edgecolor="white")
    axes[0].axvline(0, color="white", linestyle="--", linewidth=1)
    axes[0].set_title("Residual Distribution", fontweight="bold")
    axes[0].set_xlabel("Residual (₹)")
    axes[0].set_ylabel("Frequency")

    # QQ plot
    stats.probplot(residuals, dist="norm", plot=axes[1])
    axes[1].set_title("Q-Q Plot (Normality Check)", fontweight="bold")
    axes[1].get_lines()[0].set_color(COLORS["pred"])
    axes[1].get_lines()[1].set_color(COLORS["error"])

    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, save_name), dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", save_name)


def plot_scatter(y_true, y_pred, save_name="scatter_actual_predicted.png"):
    """Scatter plot with perfect-prediction line."""
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(y_true, y_pred, alpha=0.35, s=10, color=COLORS["actual"], label="Predictions")
    lims = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
    ax.plot(lims, lims, "--", color=COLORS["error"], linewidth=1.5, label="Perfect Fit")
    ax.set_title("Actual vs Predicted Scatter", fontweight="bold")
    ax.set_xlabel("Actual Price (₹)")
    ax.set_ylabel("Predicted Price (₹)")
    ax.legend()
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, save_name), dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", save_name)


def plot_training_history(history_path: str = train_cfg.history_path,
                          save_name="training_curves.png"):
    """Plot training & validation loss curves from saved history."""
    with open(history_path) as f:
        hist = json.load(f)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    epochs = range(1, len(hist["loss"]) + 1)
    axes[0].plot(epochs, hist["loss"], label="Train Loss", color=COLORS["actual"])
    axes[0].plot(epochs, hist["val_loss"], label="Val Loss", color=COLORS["pred"], linestyle="--")
    axes[0].set_title("Loss Curves", fontweight="bold")
    axes[0].set_xlabel("Epoch")
    axes[0].legend()

    if "mae" in hist:
        axes[1].plot(epochs, hist["mae"], label="Train MAE", color=COLORS["actual"])
        axes[1].plot(epochs, hist["val_mae"], label="Val MAE", color=COLORS["pred"], linestyle="--")
        axes[1].set_title("MAE Curves", fontweight="bold")
        axes[1].set_xlabel("Epoch")
        axes[1].legend()

    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, save_name), dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", save_name)


# ──────────────────────────────────────────────────────────────
# Full Evaluation
# ──────────────────────────────────────────────────────────────

def evaluate(
    model_path: str = train_cfg.final_model_path,
    splits: Optional[dict] = None,
) -> dict:
    """
    Load trained model, run predictions, compute metrics, generate plots.
    """
    logger.info("=" * 60)
    logger.info("MODEL EVALUATION")
    logger.info("=" * 60)

    # Load model
    model = tf.keras.models.load_model(model_path, compile=False)
    logger.info("Model loaded from %s", model_path)

    # Get test data
    if splits is None:
        from data_pipeline import run_pipeline
        splits = run_pipeline()

    X_test, y_test = splits["X_test"], splits["y_test"]
    test_dates = splits["test_dates"]

    # Predict
    y_pred = model.predict(X_test, verbose=0).flatten()

    # Inverse-scale if scaler available
    scaler = splits.get("scaler")
    if scaler is not None:
        target_idx = splits["target_idx"]
        dummy = np.zeros((len(y_test), scaler.n_features_in_))
        dummy[:, target_idx] = y_test
        y_test_inv = scaler.inverse_transform(dummy)[:, target_idx]
        dummy[:, target_idx] = y_pred
        y_pred_inv = scaler.inverse_transform(dummy)[:, target_idx]
    else:
        y_test_inv, y_pred_inv = y_test, y_pred

    # Metrics
    metrics = compute_metrics(y_test_inv, y_pred_inv)
    logger.info("Metrics: %s", json.dumps(metrics, indent=2))

    # Confidence intervals
    ci = bootstrap_prediction_intervals(y_test_inv, y_pred_inv)
    metrics["Std_Error"] = ci["std_error"]
    metrics["Mean_Residual"] = ci["mean_residual"]

    # Save report
    report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "model_path": model_path,
        "test_samples": len(y_test),
        "metrics": metrics,
    }
    with open(eval_cfg.report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Report saved → %s", eval_cfg.report_path)

    # Plots
    plot_actual_vs_predicted(test_dates, y_test_inv, y_pred_inv)
    plot_residuals(y_test_inv, y_pred_inv)
    plot_scatter(y_test_inv, y_pred_inv)

    if os.path.exists(train_cfg.history_path):
        plot_training_history()

    logger.info("✓ Evaluation complete")
    return report


if __name__ == "__main__":
    report = evaluate()
    print(f"\n{'='*50}")
    for k, v in report["metrics"].items():
        print(f"  {k:25s}: {v}")
    print(f"{'='*50}")
