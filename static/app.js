/* ── Dark mode ── */
(function () {
  const saved = localStorage.getItem("cc-theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("cc-theme", next);
  const btn = document.getElementById("theme-btn");
  if (btn) btn.textContent = next === "dark" ? "☀ Light" : "☾ Dark";
}

/* ── Watchlist (localStorage) ── */
const WL_KEY = "cc-watchlist";

function getWatchlist() {
  try { return JSON.parse(localStorage.getItem(WL_KEY) || "[]"); }
  catch { return []; }
}

function saveWatchlist(list) {
  localStorage.setItem(WL_KEY, JSON.stringify(list));
}

function addToWatchlist(symbol) {
  const list = getWatchlist();
  if (!list.includes(symbol)) {
    list.push(symbol);
    saveWatchlist(list);
  }
  refreshWatchlistBtn(symbol);
}

function removeFromWatchlist(symbol) {
  const list = getWatchlist().filter(s => s !== symbol);
  saveWatchlist(list);
  refreshWatchlistBtn(symbol);
}

function toggleWatchlist(symbol) {
  getWatchlist().includes(symbol) ? removeFromWatchlist(symbol) : addToWatchlist(symbol);
}

function refreshWatchlistBtn(symbol) {
  const btn = document.getElementById("wl-btn");
  if (!btn) return;
  const inList = getWatchlist().includes(symbol);
  btn.textContent = inList ? "★ Watchlisted" : "☆ Add to Watchlist";
  btn.classList.toggle("wl-active", inList);
}

/* ── Live ticker on watchlist page ── */
async function fetchPrice(symbol) {
  try {
    const res = await fetch(`/api/price/${encodeURIComponent(symbol)}`);
    return await res.json();
  } catch { return null; }
}

async function refreshTickers() {
  const cards = document.querySelectorAll("[data-ticker]");
  await Promise.all([...cards].map(async (card) => {
    const symbol = card.dataset.ticker;
    const data = await fetchPrice(symbol);
    if (!data || data.error) return;
    const priceEl = card.querySelector(".ticker-price");
    const changeEl = card.querySelector(".ticker-change");
    if (priceEl) priceEl.textContent = data.price.toFixed(4);
    if (changeEl) {
      const sign = data.change_pct >= 0 ? "+" : "";
      changeEl.textContent = `${sign}${data.change_pct}%`;
      changeEl.className = "ticker-change " + (data.change_pct >= 0 ? "positive" : "negative");
    }
  }));
}

/* ── Watchlist page render ── */
function renderWatchlistPage() {
  const container = document.getElementById("wl-container");
  if (!container) return;
  const list = getWatchlist();

  if (list.length === 0) {
    container.innerHTML = `<div class="wl-empty">
      <p>Your watchlist is empty.</p>
      <p>Run a <a href="/forex">Forex</a> or <a href="/options">Options</a> analysis and click "Add to Watchlist".</p>
    </div>`;
    return;
  }

  container.innerHTML = list.map(symbol => `
    <div class="wl-card" data-ticker="${symbol}">
      <div class="wl-card-top">
        <span class="wl-symbol">${symbol}</span>
        <button class="wl-remove" onclick="removeFromWatchlistAndRefresh('${symbol}')">✕</button>
      </div>
      <div class="ticker-price">—</div>
      <div class="ticker-change">—</div>
      <div class="wl-actions">
        <a href="/forex?pair=${encodeURIComponent(symbol)}" class="btn btn-sm btn-primary">Forex →</a>
        <a href="/options?symbol=${encodeURIComponent(symbol)}" class="btn btn-sm btn-outline">Options →</a>
      </div>
    </div>
  `).join("");

  refreshTickers();
  setInterval(refreshTickers, 30000);
}

function removeFromWatchlistAndRefresh(symbol) {
  removeFromWatchlist(symbol);
  renderWatchlistPage();
}

document.addEventListener("DOMContentLoaded", () => {
  // Init theme button label
  const btn = document.getElementById("theme-btn");
  if (btn) {
    const theme = document.documentElement.getAttribute("data-theme");
    btn.textContent = theme === "dark" ? "☀ Light" : "☾ Dark";
  }
  // Render watchlist page if present
  renderWatchlistPage();
  // Init watchlist button state
  const sym = document.getElementById("wl-btn")?.dataset?.symbol;
  if (sym) refreshWatchlistBtn(sym);
});
