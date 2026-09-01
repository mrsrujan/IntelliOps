from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import httpx, os

app = FastAPI(title="IntelliOps UI")

ORDER_SVC  = os.getenv("ORDER_SERVICE_URL",   "http://localhost:8082")
PAYMENT_SVC = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8081")

# --- Proxy routes ---

@app.get("/api/orders")
async def list_orders():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{ORDER_SVC}/orders")
        return r.json()

@app.post("/api/orders")
async def create_order(req: Request):
    body = await req.json()
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{ORDER_SVC}/orders", json=body)
        return r.json()

@app.put("/api/orders/{order_id}/confirm")
async def confirm_order(order_id: str):
    async with httpx.AsyncClient() as c:
        r = await c.put(f"{ORDER_SVC}/orders/{order_id}/confirm")
        return r.json()

@app.put("/api/orders/{order_id}/cancel")
async def cancel_order(order_id: str):
    async with httpx.AsyncClient() as c:
        r = await c.put(f"{ORDER_SVC}/orders/{order_id}/cancel")
        return r.json()

@app.get("/api/payments")
async def list_payments():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{PAYMENT_SVC}/payments")
        return r.json()

@app.post("/api/pay")
async def process_payment(req: Request):
    body = await req.json()
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{PAYMENT_SVC}/pay", json=body)
        return r.json()

@app.post("/api/refund/{payment_id}")
async def refund(payment_id: str):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{PAYMENT_SVC}/refund/{payment_id}")
        return r.json()

# --- UI ---

@app.get("/", response_class=HTMLResponse)
def ui():
    return HTML

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>IntelliOps — Demo</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
  header{background:#1e293b;border-bottom:1px solid #334155;padding:1rem 2rem;display:flex;align-items:center;gap:1rem}
  header h1{font-size:1.25rem;font-weight:700;color:#38bdf8}
  header span{font-size:.8rem;color:#64748b;background:#0f172a;padding:.25rem .6rem;border-radius:999px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;padding:2rem;max-width:1200px;margin:0 auto}
  .card{background:#1e293b;border:1px solid #334155;border-radius:.75rem;padding:1.5rem}
  .card h2{font-size:1rem;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:1rem}
  input,select{width:100%;background:#0f172a;border:1px solid #334155;border-radius:.4rem;padding:.5rem .75rem;color:#e2e8f0;font-size:.9rem;margin-bottom:.6rem}
  input:focus,select:focus{outline:none;border-color:#38bdf8}
  .btn{padding:.5rem 1.2rem;border:none;border-radius:.4rem;font-size:.85rem;font-weight:600;cursor:pointer;transition:.15s}
  .btn-blue{background:#2563eb;color:#fff}.btn-blue:hover{background:#1d4ed8}
  .btn-green{background:#16a34a;color:#fff}.btn-green:hover{background:#15803d}
  .btn-red{background:#dc2626;color:#fff}.btn-red:hover{background:#b91c1c}
  .btn-sm{padding:.3rem .7rem;font-size:.75rem}
  .row{display:flex;gap:.5rem;margin-bottom:.6rem;flex-wrap:wrap}
  table{width:100%;border-collapse:collapse;font-size:.82rem}
  th{text-align:left;color:#64748b;padding:.4rem .5rem;border-bottom:1px solid #334155}
  td{padding:.5rem .5rem;border-bottom:1px solid #1e293b;vertical-align:middle}
  .badge{display:inline-block;padding:.15rem .5rem;border-radius:999px;font-size:.72rem;font-weight:600}
  .badge-pending{background:#78350f;color:#fcd34d}
  .badge-confirmed{background:#1e3a5f;color:#38bdf8}
  .badge-cancelled{background:#3f1515;color:#f87171}
  .badge-success{background:#14532d;color:#4ade80}
  .badge-refunded{background:#312e81;color:#a5b4fc}
  .toast{position:fixed;bottom:1.5rem;right:1.5rem;background:#1e293b;border:1px solid #334155;border-radius:.5rem;padding:.75rem 1.25rem;font-size:.85rem;display:none;z-index:99}
  .toast.show{display:block}
  .section-full{grid-column:1/-1}
  .items-row{display:flex;gap:.5rem;align-items:center;margin-bottom:.4rem}
  .items-row input{margin:0;flex:1}
  label{font-size:.8rem;color:#94a3b8;display:block;margin-bottom:.25rem}
</style>
</head>
<body>
<header>
  <h1>🚀 IntelliOps</h1>
  <span>payment-service + order-service</span>
</header>

<div class="grid">

  <!-- Create Order -->
  <div class="card">
    <h2>📦 Create Order</h2>
    <label>Customer ID</label>
    <input id="custId" value="cust-001" placeholder="customer id"/>
    <label>Shipping Address</label>
    <input id="addr" value="123 Main St, Austin TX" placeholder="address"/>
    <label>Items</label>
    <div id="itemsList">
      <div class="items-row">
        <input placeholder="Product ID" class="iid" value="prod-laptop"/>
        <input placeholder="Name" class="iname" value="Laptop"/>
        <input placeholder="Qty" class="iqty" value="1" style="max-width:60px"/>
        <input placeholder="Price" class="iprice" value="999.99" style="max-width:80px"/>
      </div>
    </div>
    <div class="row" style="margin-top:.5rem">
      <button class="btn btn-blue btn-sm" onclick="addItem()">+ Item</button>
      <button class="btn btn-green" onclick="createOrder()">Place Order</button>
    </div>
  </div>

  <!-- Process Payment -->
  <div class="card">
    <h2>💳 Process Payment</h2>
    <label>Order ID</label>
    <input id="payOrderId" placeholder="paste order id here"/>
    <label>Amount (USD)</label>
    <input id="payAmount" placeholder="e.g. 999.99" type="number"/>
    <label>Card Last 4</label>
    <input id="payCard" placeholder="4242" maxlength="4" value="4242"/>
    <div class="row" style="margin-top:.5rem">
      <button class="btn btn-green" onclick="processPayment()">Pay Now</button>
    </div>
  </div>

  <!-- Orders Table -->
  <div class="card section-full">
    <h2>📋 Orders <button class="btn btn-blue btn-sm" style="float:right" onclick="loadOrders()">↻ Refresh</button></h2>
    <table>
      <thead><tr><th>ID</th><th>Customer</th><th>Total</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody id="ordersBody"><tr><td colspan="5" style="color:#64748b">Loading...</td></tr></tbody>
    </table>
  </div>

  <!-- Payments Table -->
  <div class="card section-full">
    <h2>💰 Payments <button class="btn btn-blue btn-sm" style="float:right" onclick="loadPayments()">↻ Refresh</button></h2>
    <table>
      <thead><tr><th>ID</th><th>Order ID</th><th>Amount</th><th>Card</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody id="paymentsBody"><tr><td colspan="6" style="color:#64748b">Loading...</td></tr></tbody>
    </table>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
function toast(msg, ok=true) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = ok ? '#16a34a' : '#dc2626';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

function badge(status) {
  return `<span class="badge badge-${status}">${status}</span>`;
}

function shortId(id) {
  return id ? id.substring(0,8)+'...' : '';
}

function addItem() {
  const div = document.createElement('div');
  div.className = 'items-row';
  div.innerHTML = `<input placeholder="Product ID" class="iid"/><input placeholder="Name" class="iname"/><input placeholder="Qty" class="iqty" style="max-width:60px" value="1"/><input placeholder="Price" class="iprice" style="max-width:80px"/>`;
  document.getElementById('itemsList').appendChild(div);
}

async function createOrder() {
  const items = [...document.querySelectorAll('#itemsList .items-row')].map(r => ({
    product_id: r.querySelector('.iid').value,
    name: r.querySelector('.iname').value,
    quantity: parseInt(r.querySelector('.iqty').value),
    unit_price: parseFloat(r.querySelector('.iprice').value)
  }));
  const body = { customer_id: document.getElementById('custId').value, items, shipping_address: document.getElementById('addr').value };
  const r = await fetch('/api/orders', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
  const data = await r.json();
  if (r.ok) {
    toast(`Order created: ${data.id.substring(0,8)} — $${data.total}`);
    document.getElementById('payOrderId').value = data.id;
    document.getElementById('payAmount').value = data.total;
    loadOrders();
  } else toast(data.detail || 'Error creating order', false);
}

async function processPayment() {
  const body = { order_id: document.getElementById('payOrderId').value, amount: parseFloat(document.getElementById('payAmount').value), currency:'USD', card_last4: document.getElementById('payCard').value };
  const r = await fetch('/api/pay', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
  const data = await r.json();
  if (r.ok) { toast(`Payment successful: $${data.amount}`); loadPayments(); }
  else toast(data.detail || 'Payment failed', false);
}

async function confirmOrder(id) {
  const r = await fetch(`/api/orders/${id}/confirm`, {method:'PUT'});
  const data = await r.json();
  r.ok ? (toast('Order confirmed'), loadOrders()) : toast(data.detail, false);
}

async function cancelOrder(id) {
  const r = await fetch(`/api/orders/${id}/cancel`, {method:'PUT'});
  const data = await r.json();
  r.ok ? (toast('Order cancelled'), loadOrders()) : toast(data.detail, false);
}

async function refundPayment(id) {
  const r = await fetch(`/api/refund/${id}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  const data = await r.json();
  r.ok ? (toast('Payment refunded'), loadPayments()) : toast(data.detail, false);
}

async function loadOrders() {
  const r = await fetch('/api/orders');
  const data = await r.json();
  const tbody = document.getElementById('ordersBody');
  if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" style="color:#64748b">No orders yet</td></tr>'; return; }
  tbody.innerHTML = data.map(o => `
    <tr>
      <td title="${o.id}" style="font-family:monospace;font-size:.75rem">${shortId(o.id)}</td>
      <td>${o.customer_id}</td>
      <td>$${o.total}</td>
      <td>${badge(o.status)}</td>
      <td>
        <div class="row">
          ${o.status==='pending'?`<button class="btn btn-green btn-sm" onclick="confirmOrder('${o.id}')">Confirm</button>`:''}
          ${['pending','confirmed'].includes(o.status)?`<button class="btn btn-red btn-sm" onclick="cancelOrder('${o.id}')">Cancel</button>`:''}
          <button class="btn btn-blue btn-sm" onclick="document.getElementById('payOrderId').value='${o.id}';document.getElementById('payAmount').value='${o.total}'">Pay</button>
        </div>
      </td>
    </tr>`).join('');
}

async function loadPayments() {
  const r = await fetch('/api/payments');
  const data = await r.json();
  const tbody = document.getElementById('paymentsBody');
  if (!data.length) { tbody.innerHTML = '<tr><td colspan="6" style="color:#64748b">No payments yet</td></tr>'; return; }
  tbody.innerHTML = data.map(p => `
    <tr>
      <td title="${p.id}" style="font-family:monospace;font-size:.75rem">${shortId(p.id)}</td>
      <td title="${p.order_id}" style="font-family:monospace;font-size:.75rem">${shortId(p.order_id)}</td>
      <td>$${p.amount}</td>
      <td>****${p.card_last4}</td>
      <td>${badge(p.status)}</td>
      <td>${p.status==='success'?`<button class="btn btn-red btn-sm" onclick="refundPayment('${p.id}')">Refund</button>`:''}</td>
    </tr>`).join('');
}

loadOrders(); loadPayments();
setInterval(() => { loadOrders(); loadPayments(); }, 10000);
</script>
</body>
</html>
"""
