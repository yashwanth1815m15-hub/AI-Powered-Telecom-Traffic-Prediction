"""
TeleSense Deep Learning Sequence Models (PyTorch)
Provides LSTM and GRU neural architectures for multi-horizon cellular traffic forecasting:
- 72 to 168 hours historical sliding window input
- Direct 24-hour ahead multi-step prediction
- Exogenous cyclic time features + event flag conditioning
"""

import torch
import torch.nn as nn
from typing import Dict, Any, Optional
import os
import json


class LSTMTrafficPredictor(nn.Module):
    """
    Multi-layer LSTM for cellular traffic forecasting.
    Maps (batch, seq_len, in_features) -> (batch, forecast_horizon).
    """

    def __init__(
        self,
        in_features: int = 7,
        hidden_dim: int = 64,
        num_layers: int = 2,
        forecast_horizon: int = 24,
        dropout: float = 0.2
    ):
        super().__init__()
        self.in_features = in_features
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.forecast_horizon = forecast_horizon

        self.lstm = nn.LSTM(
            input_size=in_features,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, forecast_horizon)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch_size, seq_len, in_features)
        lstm_out, _ = self.lstm(x)
        # Take last time step output
        last_hidden = lstm_out[:, -1, :]
        out = self.fc(last_hidden)
        return out


class GRUTrafficPredictor(nn.Module):
    """
    Gated Recurrent Unit (GRU) model: faster inference and lower memory footprint,
    ideal for frequent real-time retraining cycles.
    """

    def __init__(
        self,
        in_features: int = 7,
        hidden_dim: int = 64,
        num_layers: int = 2,
        forecast_horizon: int = 24,
        dropout: float = 0.2
    ):
        super().__init__()
        self.in_features = in_features
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.forecast_horizon = forecast_horizon

        self.gru = nn.GRU(
            input_size=in_features,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, forecast_horizon)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gru_out, _ = self.gru(x)
        last_hidden = gru_out[:, -1, :]
        out = self.fc(last_hidden)
        return out


def save_model_checkpoint(
    model: nn.Module,
    model_type: str,
    scaler_params: Dict[str, Any],
    metrics: Dict[str, float],
    save_path: str
) -> None:
    """Saves model weights, feature scaler parameters, and test metrics."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    payload = {
        "model_type": model_type,
        "state_dict": model.state_dict(),
        "in_features": model.in_features,
        "hidden_dim": model.hidden_dim,
        "num_layers": model.num_layers,
        "forecast_horizon": model.forecast_horizon,
        "scaler_params": scaler_params,
        "metrics": metrics
    }
    torch.save(payload, save_path)


def load_model_checkpoint(save_path: str, device: str = "cpu"):
    """Loads saved model checkpoint and returns initialized model + metadata."""
    if not os.path.exists(save_path):
        raise FileNotFoundError(f"Checkpoint not found at {save_path}")

    checkpoint = torch.load(save_path, map_location=device)
    model_type = checkpoint.get("model_type", "lstm").lower()
    in_features = checkpoint.get("in_features", 7)
    hidden_dim = checkpoint.get("hidden_dim", 64)
    num_layers = checkpoint.get("num_layers", 2)
    forecast_horizon = checkpoint.get("forecast_horizon", 24)

    if model_type == "gru":
        model = GRUTrafficPredictor(in_features, hidden_dim, num_layers, forecast_horizon)
    else:
        model = LSTMTrafficPredictor(in_features, hidden_dim, num_layers, forecast_horizon)

    model.load_state_dict(checkpoint["state_dict"])
    model.to(device)
    model.eval()

    return model, checkpoint.get("scaler_params", {}), checkpoint.get("metrics", {})

