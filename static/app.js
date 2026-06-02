/* ── Theme ── */
(function () {
  const t = localStorage.getItem("cc-theme") || "light";
  document.documentElement.setAttribute("data-theme", t);
})();

function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("cc-theme", next);
  const btn = document.getElementById("theme-btn");
  if (btn) btn.textContent = next === "dark" ? "☀ Light" : "☾ Dark";
}

/* ── Toast ── */
function showToast(message, type = "info") {
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => { requestAnimationFrame(() => toast.classList.add("show")); });
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ── Price API ── */
async function fetchPrice(symbol) {
  try {
    const r = await fetch(`/api/price/${encodeURIComponent(symbol)}`);
    return await r.json();
  } catch { return null; }
}

/* ── Watchlist ── */
const WL_KEY = "cc-watchlist";
const getWatchlist  = () => { try { return JSON.parse(localStorage.getItem(WL_KEY) || "[]"); } catch { return []; } };
const saveWatchlist = (l) => localStorage.setItem(WL_KEY, JSON.stringify(l));

function toggleWatchlist(symbol) {
  const list = getWatchlist();
  const idx  = list.indexOf(symbol);
  if (idx === -1) { list.push(symbol); showToast(`${symbol} added to watchlist`, "success"); }
  else            { list.splice(idx, 1); showToast(`${symbol} removed`, "info"); }
  saveWatchlist(list);
  refreshWatchlistBtn(symbol);
}

function refreshWatchlistBtn(symbol) {
  const btn = document.getElementById("wl-btn");
  if (!btn) return;
  const active = getWatchlist().includes(symbol);
  btn.textContent = active ? "★ Watchlisted" : "☆ Watchlist";
  btn.classList.toggle("wl-active", active);
}

async function refreshTickers() {
  const cards = document.querySelectorAll("[data-ticker]");
  await Promise.all([...cards].map(async (card) => {
    const symbol = card.dataset.ticker;
    const data   = await fetchPrice(symbol);
    if (!data || data.error) return;
    const pe = card.querySelector(".ticker-price");
    const ce = card.querySelector(".ticker-change");
    if (pe) pe.textContent = Number(data.price).toFixed(4);
    if (ce) {
      const sign = data.change_pct >= 0 ? "+" : "";
      ce.textContent = `${sign}${data.change_pct}%`;
      ce.className = "ticker-change " + (data.change_pct >= 0 ? "positive" : "negative");
    }
  }));
}

function renderWatchlistPage() {
  const container = document.getElementById("wl-container");
  if (!container) return;
  const list = getWatchlist();
  if (!list.length) {
    container.innerHTML = `<div class="wl-empty"><p>Your watchlist is empty.</p><p>Run a <a href="/forex">Forex</a> or <a href="/options">Options</a> analysis and click "☆ Watchlist".</p></div>`;
    return;
  }
  container.innerHTML = list.map(sym => `
    <div class="wl-card" data-ticker="${sym}">
      <div class="wl-card-top">
        <span class="wl-symbol">${sym}</span>
        <button class="wl-remove" onclick="removeFromWL('${sym}')">✕</button>
      </div>
      <div class="ticker-price">—</div>
      <div class="ticker-change">—</div>
      <div class="wl-actions">
        <a href="/forex?pair=${encodeURIComponent(sym)}" class="btn btn-sm btn-primary">Forex →</a>
        <a href="/options?symbol=${encodeURIComponent(sym)}" class="btn btn-sm btn-outline">Options →</a>
      </div>
    </div>`).join("");
  refreshTickers();
  clearInterval(window._wlInterval);
  window._wlInterval = setInterval(refreshTickers, 30000);
}

function removeFromWL(symbol) {
  const list = getWatchlist().filter(s => s !== symbol);
  saveWatchlist(list);
  renderWatchlistPage();
  showToast(`${symbol} removed`, "info");
}

/* ── Portfolio ── */
const PF_KEY = "cc-portfolio";
const getPortfolio  = () => { try { return JSON.parse(localStorage.getItem(PF_KEY) || "[]"); } catch { return []; } };
const savePortfolio = (p) => localStorage.setItem(PF_KEY, JSON.stringify(p));

function addPosition(symbol, qty, entryPrice, type) {
  const pf = getPortfolio();
  pf.push({ id: Date.now().toString(), symbol: symbol.toUpperCase(), qty: parseFloat(qty), entryPrice: parseFloat(entryPrice), type, date: new Date().toISOString().slice(0, 10) });
  savePortfolio(pf);
  showToast(`${symbol.toUpperCase()} position added`, "success");
  renderPortfolio();
}

function removePosition(id) {
  savePortfolio(getPortfolio().filter(p => p.id !== id));
  renderPortfolio();
  showToast("Position removed", "info");
}

async function renderPortfolio() {
  const container = document.getElementById("portfolio-container");
  if (!container) return;
  const pf = getPortfolio();

  if (!pf.length) {
    container.innerHTML = `<div class="wl-empty"><p>No positions yet.</p><p>Add your first position above.</p></div>`;
    document.getElementById("portfolio-summary")?.setAttribute("style","display:none");
    return;
  }

  document.getElementById("portfolio-summary")?.removeAttribute("style");
  container.innerHTML = `<div style="text-align:center;padding:20px;color:var(--muted);font-size:13px;">Loading prices…</div>`;

  // Fetch all prices
  const prices = {};
  await Promise.all([...new Set(pf.map(p => p.symbol))].map(async sym => {
    const d = await fetchPrice(sym);
    if (d && !d.error) prices[sym] = d.price;
  }));

  let totalValue = 0, totalCost = 0;
  const rows = pf.map(p => {
    const current = prices[p.symbol] || p.entryPrice;
    const cost    = p.qty * p.entryPrice;
    const value   = p.qty * current;
    const pnl     = p.type === "long" ? value - cost : cost - value;
    const pnlPct  = (pnl / cost) * 100;
    totalValue += value;
    totalCost  += cost;
    return { ...p, current, cost, value, pnl, pnlPct };
  });

  const totalPnl    = totalValue - totalCost;
  const totalPnlPct = (totalPnl / totalCost) * 100;

  // Summary
  const sumEl = document.getElementById("portfolio-summary");
  if (sumEl) {
    sumEl.innerHTML = `
      <div class="psummary-stat"><div class="psummary-label">Total Value</div><div class="psummary-value">$${totalValue.toLocaleString("en",{minimumFractionDigits:2,maximumFractionDigits:2})}</div></div>
      <div class="psummary-stat"><div class="psummary-label">Total Cost</div><div class="psummary-value">$${totalCost.toLocaleString("en",{minimumFractionDigits:2,maximumFractionDigits:2})}</div></div>
      <div class="psummary-stat"><div class="psummary-label">P&amp;L</div><div class="psummary-value ${totalPnl>=0?"positive":"negative"}">${totalPnl>=0?"+":""}$${totalPnl.toLocaleString("en",{minimumFractionDigits:2,maximumFractionDigits:2})}</div></div>
      <div class="psummary-stat"><div class="psummary-label">Return</div><div class="psummary-value ${totalPnlPct>=0?"positive":"negative"}">${totalPnlPct>=0?"+":""}${totalPnlPct.toFixed(2)}%</div></div>`;
  }

  // Table
  container.innerHTML = `<table class="portfolio-table">
    <thead><tr><th>Symbol</th><th>Type</th><th>Qty</th><th>Entry</th><th>Current</th><th>Value</th><th>P&amp;L</th><th>Return</th><th></th></tr></thead>
    <tbody>${rows.map(r => `<tr>
      <td>${r.symbol}</td>
      <td><span class="badge ${r.type==="long"?"badge-up":"badge-down"}">${r.type.toUpperCase()}</span></td>
      <td>${r.qty.toLocaleString()}</td>
      <td>${r.entryPrice.toFixed(4)}</td>
      <td>${r.current.toFixed(4)}</td>
      <td>$${r.value.toLocaleString("en",{minimumFractionDigits:2,maximumFractionDigits:2})}</td>
      <td class="${r.pnl>=0?"positive":"negative"}">${r.pnl>=0?"+":""}$${r.pnl.toLocaleString("en",{minimumFractionDigits:2,maximumFractionDigits:2})}</td>
      <td class="${r.pnlPct>=0?"positive":"negative"}">${r.pnlPct>=0?"+":""}${r.pnlPct.toFixed(2)}%</td>
      <td><button class="btn btn-xs btn-danger" onclick="removePosition('${r.id}')">Remove</button></td>
    </tr>`).join("")}</tbody>
  </table>`;

  // Pie chart
  if (typeof Plotly !== "undefined") {
    const isDark  = document.documentElement.getAttribute("data-theme") === "dark";
    const textCol = isDark ? "#94a3b8" : "#111";
    Plotly.newPlot("portfolio-pie", [{
      labels: rows.map(r => r.symbol),
      values: rows.map(r => Math.abs(r.value)),
      type: "pie",
      hole: 0.45,
      textinfo: "label+percent",
      textfont: { color: textCol, size: 12 },
      marker: { colors: ["#3b82f6","#10b981","#f59e0b","#8b5cf6","#ef4444","#06b6d4","#ec4899","#84cc16"] },
    }], {
      paper_bgcolor: "transparent",
      margin: { t: 8, r: 8, b: 8, l: 8 },
      showlegend: false,
      font: { family: "Inter, sans-serif", color: textCol },
    }, { responsive: true, displayModeBar: false });
  }
}

/* ── Alerts ── */
const AL_KEY = "cc-alerts";
const getAlerts  = () => { try { return JSON.parse(localStorage.getItem(AL_KEY) || "[]"); } catch { return []; } };
const saveAlerts = (a) => localStorage.setItem(AL_KEY, JSON.stringify(a));

function addAlert(symbol, condition, price) {
  const alerts = getAlerts();
  alerts.push({ id: Date.now().toString(), symbol: symbol.toUpperCase(), condition, price: parseFloat(price), active: true, triggered: false, createdAt: new Date().toISOString() });
  saveAlerts(alerts);
  showToast(`Alert set: ${symbol.toUpperCase()} ${condition} ${price}`, "info");
  renderAlerts();
}

function removeAlert(id) {
  saveAlerts(getAlerts().filter(a => a.id !== id));
  renderAlerts();
}

function renderAlerts() {
  const container = document.getElementById("alert-list");
  if (!container) return;
  const alerts = getAlerts();
  if (!alerts.length) {
    container.innerHTML = `<div class="wl-empty"><p>No alerts set.</p><p>Create one above to get notified when a price is reached.</p></div>`;
    return;
  }
  container.innerHTML = alerts.map(a => `
    <div class="alert-item ${a.triggered?"triggered":""}">
      <span class="alert-sym">${a.symbol}</span>
      <span class="alert-cond">${a.condition}</span>
      <span class="alert-price">${a.price}</span>
      <span class="alert-badge ${a.triggered?"triggered":"active"}">${a.triggered?"✓ Triggered":"Active"}</span>
      <button class="btn btn-xs btn-outline" onclick="removeAlert('${a.id}')">Remove</button>
    </div>`).join("");
}

async function checkAlerts() {
  const active = getAlerts().filter(a => a.active && !a.triggered);
  if (!active.length) return;
  const all = getAlerts();
  for (const alert of active) {
    const data = await fetchPrice(alert.symbol);
    if (!data || data.error) continue;
    const hit = (alert.condition === "above" && data.price >= alert.price) ||
                (alert.condition === "below" && data.price  <= alert.price);
    if (hit) {
      const idx = all.findIndex(a => a.id === alert.id);
      if (idx !== -1) all[idx].triggered = true;
      showToast(`🔔 ${alert.symbol} ${alert.condition} ${alert.price}`, "warning");
      if (Notification.permission === "granted") {
        new Notification("ChoiceCLASH Alert", { body: `${alert.symbol} is now ${alert.condition} ${alert.price}` });
      }
    }
  }
  saveAlerts(all);
  renderAlerts();
}

function requestNotifications() {
  if ("Notification" in window) Notification.requestPermission().then(p => {
    showToast(p === "granted" ? "Notifications enabled!" : "Notifications blocked", p === "granted" ? "success" : "error");
  });
}

/* ── Init ── */
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("theme-btn");
  if (btn) btn.textContent = document.documentElement.getAttribute("data-theme") === "dark" ? "☀ Light" : "☾ Dark";

  renderWatchlistPage();
  renderPortfolio();
  renderAlerts();

  const sym = document.getElementById("wl-btn")?.dataset?.symbol;
  if (sym) refreshWatchlistBtn(sym);

  // Check alerts every 60s
  setInterval(checkAlerts, 60000);
  checkAlerts();
});
