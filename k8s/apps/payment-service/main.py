from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time, random

app = FastAPI()

REQUEST_COUNT = Counter("payment_requests_total", "Total requests", ["method", "status"])
REQUEST_LATENCY = Histogram("payment_request_duration_seconds", "Request latency")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    return {"status": "ready"}

@app.post("/pay")
def pay():
    start = time.time()
    time.sleep(random.uniform(0.01, 0.1))  # simulate work
    status = "success" if random.random() > 0.05 else "error"
    REQUEST_COUNT.labels(method="POST", status=status).inc()
    REQUEST_LATENCY.observe(time.time() - start)
    if status == "error":
        return Response(status_code=500, content="payment failed")
    return {"transaction_id": f"txn-{int(time.time())}"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
