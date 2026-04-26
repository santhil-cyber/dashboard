"""
Inference API — Flask server for real-time LSTM predictions.

Serves the dashboard frontend and exposes a REST endpoint
for on-demand prediction from the trained model.

Endpoints:
    GET  /                  → Dashboard (index.html)
    POST /api/predict       → Run prediction for given date range
    GET  /api/health        → Health check
    GET  /api/model-info    → Model metadata & metrics
"""

import os
import json
import logging
from datetime import datetime

import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from config import train_cfg, eval_cfg, ARTIFACTS_DIR, BASE_DIR

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# ──────────────────────────────────────────────────────────────
# App Setup
# ──────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
CORS(app)

# Lazy-loaded model
_model = None
_scaler = None


def get_model():
    """Load the trained LSTM model (singleton)."""
    global _model
    if _model is None:
        import tensorflow as tf
        model_path = train_cfg.final_model_path
        if not os.path.exists(model_path):
            model_path = train_cfg.checkpoint_path
        if os.path.exists(model_path):
            _model = tf.keras.models.load_model(model_path, compile=False)
            logger.info("Model loaded from %s", model_path)
        else:
            logger.warning("No trained model found at %s", model_path)
    return _model


def get_scaler():
    """Load the fitted feature scaler."""
    global _scaler
    if _scaler is None:
        import joblib
        scaler_path = os.path.join(ARTIFACTS_DIR, "feature_scaler.pkl")
        if os.path.exists(scaler_path):
            _scaler = joblib.load(scaler_path)
            logger.info("Scaler loaded from %s", scaler_path)
    return _scaler


# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────

@app.route("/")
def serve_dashboard():
    """Serve the main dashboard page."""
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/health")
def health():
    """Health check endpoint."""
    model = get_model()
    return jsonify({
        "status": "healthy",
        "model_loaded": model is not None,
        "timestamp": datetime.now().isoformat(),
        "version": "2.1.0",
    })


@app.route("/api/model-info")
def model_info():
    """Return model metadata and latest evaluation metrics."""
    info = {
        "architecture": "Stacked LSTM + Temporal Attention",
        "layers": "3x LSTM (128→64→32) + 2x Dense (64→32)",
        "parameters": None,
        "training_epochs": None,
        "metrics": None,
    }

    model = get_model()
    if model:
        info["parameters"] = model.count_params()

    # Load training history
    if os.path.exists(train_cfg.history_path):
        with open(train_cfg.history_path) as f:
            hist = json.load(f)
        info["training_epochs"] = hist.get("total_epochs_run")
        info["best_val_loss"] = hist.get("best_val_loss")

    # Load evaluation metrics
    if os.path.exists(eval_cfg.report_path):
        with open(eval_cfg.report_path) as f:
            report = json.load(f)
        info["metrics"] = report.get("metrics")

    return jsonify(info)


@app.route("/api/predict", methods=["POST"])
def predict():
    """
    Run prediction on provided input sequence.

    Expects JSON: { "sequence": [[f1, f2, ...], ...] }
    Returns: { "prediction": float, "confidence": {...} }
    """
    model = get_model()
    if model is None:
        return jsonify({"error": "Model not loaded. Run train.py first."}), 503

    data = request.get_json(force=True)
    sequence = np.array(data.get("sequence", []), dtype=np.float32)

    if sequence.ndim != 2:
        return jsonify({"error": "Expected 2D array (seq_length, n_features)"}), 400

    # Reshape for model: (1, seq_length, n_features)
    X = sequence.reshape(1, *sequence.shape)
    pred = model.predict(X, verbose=0).flatten()

    # Inverse transform if scaler available
    scaler = get_scaler()
    if scaler:
        dummy = np.zeros((1, scaler.n_features_in_))
        close_idx = 3  # 'Close' column index in feature list
        dummy[0, close_idx] = pred[0]
        pred_price = scaler.inverse_transform(dummy)[0, close_idx]
    else:
        pred_price = float(pred[0])

    return jsonify({
        "prediction": round(pred_price, 2),
        "raw_scaled": float(pred[0]),
        "timestamp": datetime.now().isoformat(),
    })


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting prediction server on port %d …", port)
    app.run(host="0.0.0.0", port=port, debug=False)
