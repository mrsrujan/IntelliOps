from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from typing import Optional
from datetime import datetime
import uuid, time, random

app = FastAPI(title="Order Service", version="1.0.0", description="IntelliOps Order Microservice")

# --- Prometheus metrics ---
REQUEST_COUNT   = Counter("order_requests_total", "Total requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("order_duration_seconds", "Request latency", ["endpoint"])
ORDERS_CREATED  = Counter("orders_created_total", "Total orders created")

# --- In-memory store ---
orders: dict = {}

# --- Models ---
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

# --- Routes ---
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
    return {"status": "ok", "service": "order-service"}

@app.get("/ready")
def ready():
    return {"status": "ready", "service": "order-service"}

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
        updated_at=now
    )
    orders[order.id] = order.model_dump()
    ORDERS_CREATED.inc()
    REQUEST_COUNT.labels(method="POST", endpoint="/orders", status="201").inc()
    REQUEST_LATENCY.labels(endpoint="/orders").observe(time.time() - start)
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
    return orders[order_id]

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
