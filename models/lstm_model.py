"""
LSTM Model Architecture for Bank Nifty Price Prediction
========================================================
Supports stacked LSTM, optional temporal attention, bidirectional
wrapping, L2 regularisation, and batch-normalised dense head.
"""

import tensorflow as tf
from tensorflow.keras import layers, models, regularizers, Input
from tensorflow.keras.layers import (
    LSTM, Bidirectional, Dense, Dropout,
    BatchNormalization, Layer,
)
import logging
from config import model_cfg

logger = logging.getLogger(__name__)


class TemporalAttention(Layer):
    """Bahdanau-style additive attention over LSTM time-steps."""

    def __init__(self, units: int = 64, **kwargs):
        super().__init__(**kwargs)
        self.W = Dense(units, activation="tanh", name="attn_tanh")
        self.V = Dense(1, name="attn_score")

    def call(self, inputs):
        score = self.V(self.W(inputs))
        weights = tf.nn.softmax(score, axis=1)
        context = tf.reduce_sum(inputs * weights, axis=1)
        return context, weights


def build_lstm_model(
    input_shape: tuple,
    lstm_units: list = model_cfg.lstm_units,
    dropout: float = model_cfg.dropout_rate,
    recurrent_dropout: float = model_cfg.recurrent_dropout,
    dense_units: list = model_cfg.dense_units,
    use_attention: bool = model_cfg.use_attention,
    use_bidirectional: bool = model_cfg.use_bidirectional,
    l2_reg: float = model_cfg.kernel_regularizer_l2,
) -> tf.keras.Model:
    """Construct a multi-layer LSTM model for time-series regression."""
    inputs = Input(shape=input_shape, name="lstm_input")
    x = inputs

    for i, units in enumerate(lstm_units):
        return_sequences = (i < len(lstm_units) - 1) or use_attention
        lstm_layer = LSTM(
            units, return_sequences=return_sequences,
            kernel_regularizer=regularizers.l2(l2_reg),
            recurrent_dropout=recurrent_dropout,
            name=f"lstm_{i+1}",
        )
        if use_bidirectional:
            lstm_layer = Bidirectional(lstm_layer, name=f"bi_lstm_{i+1}")
        x = lstm_layer(x)
        x = Dropout(dropout, name=f"dropout_{i+1}")(x)

    if use_attention:
        x, _ = TemporalAttention(units=lstm_units[-1], name="temporal_attention")(x)

    for i, units in enumerate(dense_units):
        x = Dense(units, activation=model_cfg.activation,
                  kernel_regularizer=regularizers.l2(l2_reg), name=f"dense_{i+1}")(x)
        x = BatchNormalization(name=f"bn_{i+1}")(x)
        x = Dropout(dropout * 0.5, name=f"head_dropout_{i+1}")(x)

    output = Dense(model_cfg.output_units, activation="linear", name="prediction")(x)
    model = models.Model(inputs=inputs, outputs=output, name="BankNifty_LSTM")
    logger.info("Model built — %s params", f"{model.count_params():,}")
    return model


if __name__ == "__main__":
    import numpy as np
    model = build_lstm_model(input_shape=(60, 19))
    model.summary()
    dummy = np.random.randn(8, 60, 19).astype(np.float32)
    print(f"Smoke test — {dummy.shape} → {model.predict(dummy, verbose=0).shape}")
