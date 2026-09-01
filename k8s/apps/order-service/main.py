from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time, random, uuid

app = FastAPI()

REQUEST_COUNT = Counter("order_requests_total", "Total requests", ["method", "status"])
REQUEST_LATENCY = Histogram("order_request_duration_seconds", "Request latency")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    return {"status": "ready"}

@app.post("/order")
def create_order():
    start = time.time()
    time.sleep(random.uniform(0.02, 0.15))  # simulate DB write
    status = "success" if random.random() > 0.03 else "error"
    REQUEST_COUNT.labels(method="POST", status=status).inc()
    REQUEST_LATENCY.observe(time.time() - start)
    if status == "error":
        return Response(status_code=500, content="order creation failed")
    return {"order_id": str(uuid.uuid4()), "status": "created"}

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    REQUEST_COUNT.labels(method="GET", status="success").inc()
    return {"order_id": order_id, "status": "processing"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
