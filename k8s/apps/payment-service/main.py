import asyncio
import logging
import os
import random
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel
from pythonjsonlogger import jsonlogger
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# ── Observability setup ─────────────────────────────────────────────────────────
SERVICE_NAME = "payment-service"
FAULT_INJECTION_ENABLED = os.getenv("ENABLE_FAULT_INJECTION", "false").lower() == "true"

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx.get()
        record.service = SERVICE_NAME
        return True


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(jsonlogger.JsonFormatter(
    "%(asctime)s %(service)s %(levelname)s %(request_id)s %(message)s",
    rename_fields={"asctime": "timestamp", "levelname": "level"},
    datefmt="%Y-%m-%dT%H:%M:%S%z",
))
_handler.addFilter(ContextFilter())

for name in ("", SERVICE_NAME, "uvicorn", "uvicorn.access", "uvicorn.error"):
    lg = logging.getLogger(name)
    lg.handlers = [_handler]
    lg.setLevel(logging.INFO)
    lg.propagate = False

logger = logging.getLogger(SERVICE_NAME)

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(title="Payment Service", version="1.0.0", description="IntelliOps Payment Microservice")

REQUEST_COUNT   = Counter("payment_requests_total", "Total requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("payment_duration_seconds", "Request latency", ["endpoint"])
PAYMENT_AMOUNT  = Counter("payment_amount_total", "Total payment amount processed in USD")

payments: dict = {}

_latency_ms = 0
_latency_until = 0.0
_error_rate = 0.0
_errors_until = 0.0
_leaked: list = []


# ── Middleware ─────────────────────────────────────────────────────────────────
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_ctx.set(rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        request_id_ctx.reset(token)


@app.middleware("http")
async def fault_injection_middleware(request: Request, call_next):
    if request.url.path.startswith("/admin"):
        return await call_next(request)
    now = time.time()
    if _latency_ms and now < _latency_until:
        await asyncio.sleep(_latency_ms / 1000)
    if _error_rate and now < _errors_until and random.random() < _error_rate:
        logger.warning("injected_error", extra={"path": request.url.path})
        return JSONResponse({"detail": "Injected error for chaos testing"}, status_code=500)
    return await call_next(request)


# ── Models ─────────────────────────────────────────────────────────────────────
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


# ── Routes ─────────────────────────────────────────────────────────────────────
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
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/ready")
def ready():
    return {"status": "ready", "service": SERVICE_NAME}


@app.post("/pay", response_model=Payment, status_code=201)
def process_payment(req: PaymentRequest):
    start = time.time()
    time.sleep(random.uniform(0.01, 0.08))

    # Baseline 5% failure rate so metrics have realistic variance
    if random.random() < 0.05:
        REQUEST_COUNT.labels(method="POST", endpoint="/pay", status="500").inc()
        logger.warning("payment_failed", extra={
            "order_id": req.order_id,
            "amount": req.amount,
            "reason": "gateway_timeout",
        })
        raise HTTPException(status_code=500, detail="Payment gateway timeout")

    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=req.order_id,
        amount=req.amount,
        currency=req.currency,
        card_last4=req.card_last4,
        status="success",
        created_at=datetime.utcnow().isoformat(),
    )
    payments[payment.id] = payment.model_dump()
    PAYMENT_AMOUNT.inc(req.amount)
    REQUEST_COUNT.labels(method="POST", endpoint="/pay", status="201").inc()
    REQUEST_LATENCY.labels(endpoint="/pay").observe(time.time() - start)
    logger.info("payment_success", extra={
        "payment_id": payment.id,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "card_last4": payment.card_last4,
    })
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
    logger.info("payment_refunded", extra={
        "payment_id": payment_id,
        "reason": req.reason,
    })
    return payments[payment_id]


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Fault injection (chaos demos; gated by ENABLE_FAULT_INJECTION env) ────────
@app.post("/admin/inject/cpu")
def inject_cpu(seconds: int = 30):
    if not FAULT_INJECTION_ENABLED:
        raise HTTPException(403, "Fault injection disabled")
    logger.info("fault_injection", extra={"type": "cpu", "seconds": seconds})
    start = time.time()
    while time.time() - start < seconds:
        pass
    return {"status": "cpu burn complete", "seconds": seconds}


@app.post("/admin/inject/memory-leak")
def inject_memory(mb: int = 50):
    if not FAULT_INJECTION_ENABLED:
        raise HTTPException(403, "Fault injection disabled")
    _leaked.append(bytearray(mb * 1024 * 1024))
    total = sum(len(b) for b in _leaked) // (1024 * 1024)
    logger.info("fault_injection", extra={"type": "memory", "mb": mb, "total_mb": total})
    return {"status": "leaked", "mb": mb, "total_mb": total}


@app.post("/admin/inject/latency")
def inject_latency(ms: int = 1000, duration: int = 60):
    if not FAULT_INJECTION_ENABLED:
        raise HTTPException(403, "Fault injection disabled")
    global _latency_ms, _latency_until
    _latency_ms = ms
    _latency_until = time.time() + duration
    logger.info("fault_injection", extra={"type": "latency", "ms": ms, "duration": duration})
    return {"status": "latency active", "ms": ms, "duration": duration}


@app.post("/admin/inject/errors")
def inject_errors(rate: float = 0.5, duration: int = 60):
    if not FAULT_INJECTION_ENABLED:
        raise HTTPException(403, "Fault injection disabled")
    global _error_rate, _errors_until
    _error_rate = min(1.0, max(0.0, rate))
    _errors_until = time.time() + duration
    logger.info("fault_injection", extra={"type": "errors", "rate": rate, "duration": duration})
    return {"status": "error injection active", "rate": rate, "duration": duration}
