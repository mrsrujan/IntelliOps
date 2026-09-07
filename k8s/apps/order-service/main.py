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
SERVICE_NAME = "order-service"
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
app = FastAPI(title="Order Service", version="1.0.0", description="IntelliOps Order Microservice")

REQUEST_COUNT   = Counter("order_requests_total", "Total requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("order_duration_seconds", "Request latency", ["endpoint"])
ORDERS_CREATED  = Counter("orders_created_total", "Total orders created")

orders: dict = {}

# Fault-injection state (per-pod, in-memory)
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
class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: float


class OrderRequest(BaseModel):
    customer_id: str
    items: list[OrderItem]
    shipping_address: str


class Order(BaseModel):
    id: str
    customer_id: str
    items: list[OrderItem]
    shipping_address: str
    total: float
    status: str
    created_at: str
    updated_at: str


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html><body style="font-family:sans-serif;padding:2rem;background:#0f172a;color:#e2e8f0">
    <h1>📦 Order Service</h1>
    <p>Part of the <b>IntelliOps</b> observability platform.</p>
    <ul>
      <li><a href="/docs" style="color:#38bdf8">Swagger UI →</a></li>
      <li><a href="/orders" style="color:#38bdf8">All Orders →</a></li>
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


@app.post("/orders", response_model=Order, status_code=201)
def create_order(req: OrderRequest):
    start = time.time()
    time.sleep(random.uniform(0.02, 0.12))

    if not req.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")

    total = sum(item.quantity * item.unit_price for item in req.items)
    now = datetime.utcnow().isoformat()
    order = Order(
        id=str(uuid.uuid4()),
        customer_id=req.customer_id,
        items=req.items,
        shipping_address=req.shipping_address,
        total=round(total, 2),
        status="pending",
        created_at=now,
        updated_at=now,
    )
    orders[order.id] = order.model_dump()
    ORDERS_CREATED.inc()
    REQUEST_COUNT.labels(method="POST", endpoint="/orders", status="201").inc()
    REQUEST_LATENCY.labels(endpoint="/orders").observe(time.time() - start)
    logger.info("order_created", extra={
        "order_id": order.id,
        "customer_id": order.customer_id,
        "total": order.total,
        "items": len(order.items),
    })
    return order


@app.get("/orders", response_model=list[Order])
def list_orders(status: Optional[str] = None):
    result = list(orders.values())
    if status:
        result = [o for o in result if o["status"] == status]
    REQUEST_COUNT.labels(method="GET", endpoint="/orders", status="200").inc()
    return result


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    REQUEST_COUNT.labels(method="GET", endpoint="/orders/{id}", status="200").inc()
    return orders[order_id]


@app.put("/orders/{order_id}/confirm", response_model=Order)
def confirm_order(order_id: str):
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    if orders[order_id]["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot confirm order in status: {orders[order_id]['status']}")
    orders[order_id]["status"] = "confirmed"
    orders[order_id]["updated_at"] = datetime.utcnow().isoformat()
    REQUEST_COUNT.labels(method="PUT", endpoint="/orders/{id}/confirm", status="200").inc()
    logger.info("order_confirmed", extra={"order_id": order_id})
    return orders[order_id]


@app.put("/orders/{order_id}/cancel", response_model=Order)
def cancel_order(order_id: str):
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    if orders[order_id]["status"] in ["shipped", "delivered"]:
        raise HTTPException(status_code=400, detail="Cannot cancel a shipped or delivered order")
    orders[order_id]["status"] = "cancelled"
    orders[order_id]["updated_at"] = datetime.utcnow().isoformat()
    REQUEST_COUNT.labels(method="PUT", endpoint="/orders/{id}/cancel", status="200").inc()
    logger.info("order_cancelled", extra={"order_id": order_id})
    return orders[order_id]


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
