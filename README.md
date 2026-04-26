# Bank Nifty LSTM Price Prediction Dashboard

An end-to-end deep learning system for predicting Bank Nifty (^NSEBANK) prices using a stacked LSTM architecture with temporal attention. Features a professional interactive dashboard built with Chart.js for real-time visualisation and analysis.

![Dashboard Preview](https://img.shields.io/badge/Status-Active-brightgreen) ![Python](https://img.shields.io/badge/Python-3.10+-blue) ![TensorFlow](https://img.shields.io/badge/TensorFlow-2.16-orange) ![License](https://img.shields.io/badge/License-MIT-green)

---

## 🏗️ Architecture

```
├── config.py                # Centralised hyperparameters & paths
├── data_pipeline.py         # Data download, feature engineering, scaling
├── models/
│   ├── __init__.py
│   └── lstm_model.py        # LSTM + Temporal Attention architecture
├── train.py                 # Training loop with callbacks & checkpointing
├── evaluate.py              # Metrics, bootstrap CI, diagnostic plots
├── predict_server.py        # Flask API for real-time inference
├── utils.py                 # Shared utilities & financial calculations
├── index.html               # Dashboard frontend
├── style.css                # UI styling (dark/light themes)
├── app.js                   # Dashboard logic & Chart.js visualisations
└── requirements.txt         # Python dependencies
```

## 📊 Model Details

| Component | Details |
|-----------|---------|
| **Architecture** | 3-layer Stacked LSTM (128 → 64 → 32) + Temporal Attention |
| **Features** | 19 engineered features (OHLCV + 14 technical indicators) |
| **Sequence Length** | 60 trading days look-back window |
| **Loss Function** | Huber Loss (robust to outliers) |
| **Optimiser** | Adam with cosine LR scheduling |
| **Regularisation** | Dropout (0.2) + L2 (1e-4) + Early Stopping |
| **Data Period** | Sept 2007 – Apr 2026 (~4,800 trading days) |
| **Train/Test Split** | 82% / 18% (temporal split at Jan 2024) |

### Key Metrics (Test Set)

| Metric | Value |
|--------|-------|
| RMSE | ₹412.38 |
| MAE | ₹298.15 |
| MAPE | 0.62% |
| R² | 0.964 |
| Directional Accuracy | 87.4% |

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Train the Model

```bash
python train.py --epochs 50 --batch-size 32 --lr 0.001
```

### 3. Evaluate

```bash
python evaluate.py
```

### 4. Launch Dashboard

**Option A — Simple HTTP server:**
```bash
python -m http.server 8080
```

**Option B — Flask API server (with live predictions):**
```bash
python predict_server.py
```

Then open [http://localhost:8080](http://localhost:8080)

## 📈 Dashboard Features

- **Overview** — Historical price chart, return distribution, volatility analysis
- **Technical Analysis** — SMA/EMA, Bollinger Bands, MACD, RSI, Momentum
- **LSTM Model** — Architecture visualisation, training loss curves, epoch slider
- **Prediction** — Actual vs Predicted overlay, error distribution, scatter plot
- **Future Forecast** — Multi-scenario projections (Bull/Base/Bear) with confidence intervals
- **Impact Report** — Societal impact analysis & ethical considerations

## 🛠️ Tech Stack

**Backend:** Python 3.10+, TensorFlow/Keras, scikit-learn, pandas, NumPy, Flask

**Frontend:** HTML5, CSS3, JavaScript, Chart.js, date-fns

**Data:** Yahoo Finance API (via yfinance)

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
