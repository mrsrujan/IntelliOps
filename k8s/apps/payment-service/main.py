from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from typing import Optional
from datetime import datetime
import uuid, time, random

app = FastAPI(title="Payment Service", version="1.0.0", description="IntelliOps Payment Microservice")

# --- Prometheus metrics ---
REQUEST_COUNT  = Counter("payment_requests_total", "Total requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("payment_duration_seconds", "Request latency", ["endpoint"])
PAYMENT_AMOUNT  = Counter("payment_amount_total", "Total payment amount processed in USD")

# --- In-memory store ---
payments: dict = {}

# --- Models ---
class PaymentRequest(BaseModel):
    order_id: str
    amount: float
    currency: str = "USD"
    card_last4: str

class RefundRequest(BaseModel):
    reason: Optional[str] = "customer request"

class Payment(BaseModel):
    id: str
    order_id: str
    amount: float
    currency: str
    card_last4: str
    status: str
    created_at: str

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html><body style="font-family:sans-serif;padding:2rem;background:#0f172a;color:#e2e8f0">
    <h1>💳 Payment Service</h1>
    <p>Part of the <b>IntelliOps</b> observability platform.</p>
    <ul>
      <li><a href="/docs" style="color:#38bdf8">Swagger UI →</a></li>
      <li><a href="/payments" style="color:#38bdf8">All Payments →</a></li>
      <li><a href="/metrics" style="color:#38bdf8">Prometheus Metrics →</a></li>
      <li><a href="/health" style="color:#38bdf8">Health →</a></li>
    </ul>
    </body></html>
    """

@app.get("/health")
def health():
    return {"status": "ok", "service": "payment-service"}

@app.get("/ready")
def ready():
    return {"status": "ready", "service": "payment-service"}

@app.post("/pay", response_model=Payment, status_code=201)
def process_payment(req: PaymentRequest):
    start = time.time()
    time.sleep(random.uniform(0.01, 0.08))

    # simulate 5% failure rate
    if random.random() < 0.05:
        REQUEST_COUNT.labels(method="POST", endpoint="/pay", status="500").inc()
        raise HTTPException(status_code=500, detail="Payment gateway timeout")

    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=req.order_id,
        amount=req.amount,
        currency=req.currency,
        card_last4=req.card_last4,
        status="success",
        created_at=datetime.utcnow().isoformat()
    )
    payments[payment.id] = payment.model_dump()
    PAYMENT_AMOUNT.inc(req.amount)
    REQUEST_COUNT.labels(method="POST", endpoint="/pay", status="201").inc()
    REQUEST_LATENCY.labels(endpoint="/pay").observe(time.time() - start)
    return payment

@app.get("/payments", response_model=list[Payment])
def list_payments():
    REQUEST_COUNT.labels(method="GET", endpoint="/payments", status="200").inc()
    return list(payments.values())

@app.get("/payments/{payment_id}", response_model=Payment)
def get_payment(payment_id: str):
    if payment_id not in payments:
        raise HTTPException(status_code=404, detail="Payment not found")
    REQUEST_COUNT.labels(method="GET", endpoint="/payments/{id}", status="200").inc()
    return payments[payment_id]

@app.post("/refund/{payment_id}", response_model=Payment)
def refund_payment(payment_id: str, req: RefundRequest):
    if payment_id not in payments:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payments[payment_id]["status"] == "refunded":
        raise HTTPException(status_code=400, detail="Already refunded")
    payments[payment_id]["status"] = "refunded"
    REQUEST_COUNT.labels(method="POST", endpoint="/refund", status="200").inc()
    return payments[payment_id]

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
