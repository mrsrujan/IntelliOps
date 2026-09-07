"""
Standalone inference script — loads a trained LSTM checkpoint and scores
incoming time-series points for anomaly.

Usage:
    python inference.py --checkpoint model.pt --window "1.2,1.3,1.5,1.8,3.4"

Returns JSON with predicted next value, actual, and anomaly score.
"""

import argparse
import json

import numpy as np
import torch
import torch.nn as nn


class LSTMForecaster(nn.Module):
    """Same architecture as train.ipynb — kept in sync manually."""

    def __init__(self, input_size: int = 1, hidden_size: int = 32, num_layers: int = 2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


def score(window: list[float], checkpoint_path: str) -> dict:
    """Predict next value from window and compute anomaly score against the last observed value."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)

    model = LSTMForecaster(**checkpoint.get("model_config", {}))
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    scaler = checkpoint["scaler"]
    scaled = [(v - scaler["mean"]) / scaler["std"] for v in window]

    x = torch.tensor(scaled[:-1], dtype=torch.float32).view(1, -1, 1)
    with torch.no_grad():
        predicted_scaled = model(x).item()

    predicted = predicted_scaled * scaler["std"] + scaler["mean"]
    actual = window[-1]

    # Simple z-score against training residuals
    residual = abs(actual - predicted)
    threshold = checkpoint.get("residual_threshold", 3.0)
    anomaly_score = residual / threshold

    return {
        "predicted": round(predicted, 3),
        "actual": round(actual, 3),
        "residual": round(residual, 3),
        "anomaly_score": round(anomaly_score, 3),
        "is_anomaly": anomaly_score > 1.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True, help="Path to model.pt")
    parser.add_argument("--window", required=True, help="Comma-separated window values (last value is 'actual')")
    args = parser.parse_args()

    window = [float(v) for v in args.window.split(",")]
    result = score(window, args.checkpoint)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
