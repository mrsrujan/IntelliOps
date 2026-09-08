# SageMaker LSTM — anomaly detection reference implementation

An LSTM-based time-series anomaly detector for service request metrics
(rate / error-rate / latency), presented as a demonstrable ML artifact
alongside the runtime path (which uses managed anomaly detection).

## Why this exists

The runtime anomaly pipeline in this project uses **CloudWatch Alarms
with anomaly-detection bands** because they need no training data, no
endpoint to manage, and no ~$70/month baseline cost. (Amazon Lookout
for Metrics was AWS's other managed-ML anomaly option — it was retired
in October 2025.)

This notebook shows what the alternative — a **bring-your-own LSTM** — would
look like, using the same synthetic traffic pattern the runtime path
observes. It's here as a portfolio artefact demonstrating end-to-end ML
capability, not as part of the deploy loop.

## Files

- `train.ipynb` — Jupyter notebook: generate synthetic traffic → train LSTM → evaluate
- `inference.py` — standalone script to load a trained model and score new points
- `requirements.txt` — Python deps for both

## Running locally

```bash
cd ai/anomaly-model
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook train.ipynb
```

## Running on SageMaker

Upload the notebook to a SageMaker Studio notebook instance (any small
CPU instance is enough). Same code runs unchanged.

## Deploying as an endpoint (optional)

The last cell in `train.ipynb` shows how to package the trained model as a
`.tar.gz` and register it with SageMaker. Endpoint hosting is left as a
manual step because it's the ~$72/month portion the runtime path
intentionally avoids.
