// Asset Overview: currency display toggle (Separate vs Combined) + charts.
// Data is embedded server-side as window.ASSET_OVERVIEW; the live FX rate is
// fetched from window.FX_RATE_URL (falls back to the cached rate offline).
(function () {
  "use strict";
  const data = window.ASSET_OVERVIEW;
  if (!data) return;

  if (window.Chart) {
    Chart.defaults.color = "#A49C90";
    Chart.defaults.borderColor = "rgba(255,255,255,0.05)";
    Chart.defaults.font.family = "'Switzer','Pretendard',sans-serif";
  }

  let rate = data.cachedRate || 1350;
  let mode = localStorage.getItem("assetOverviewMode") || "separate";
  let charts = [];

  const $summary = document.getElementById("overview-summary");
  const $charts = document.getElementById("overview-charts");
  const $rate = document.getElementById("overview-rate");
  const $btns = Array.from(document.querySelectorAll("#asset-overview .seg-btn"));

  const fmtKRW = (v) => "₩" + Math.round(v).toLocaleString();
  const fmtUSD = (v) => "$" + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function destroyCharts() {
    charts.forEach((c) => c.destroy());
    charts = [];
  }

  function statBlock(title, assets, liabilities, net, fmt, accent) {
    return `
      <div class="card stat" style="background:linear-gradient(160deg, var(--surface), ${accent}12); border-color:${accent}33;">
        <div class="label">${title}</div>
        <div class="value" style="color:${accent};">${fmt(assets)}</div>
        <div class="stat-sub">부채 ${fmt(liabilities)} · 순자산 <b>${fmt(net)}</b></div>
      </div>`;
  }

  function allocationNative(cur) {
    const c = data.byCurrency[cur];
    const labels = [], values = [], colors = [];
    data.categories.forEach((cat) => {
      if (cat.is_liability) return;
      const amt = (c.byCategory[cat.id] || 0);
      if (amt > 0) { labels.push(cat.label); values.push(amt); colors.push(cat.color); }
    });
    return { labels, values, colors };
  }

  function combinedByCategory() {
    const out = {};
    data.categories.forEach((cat) => {
      out[cat.id] = (data.byCurrency.KRW.byCategory[cat.id] || 0)
        + (data.byCurrency.USD.byCategory[cat.id] || 0) * rate;
    });
    return out;
  }

  function pieCard(id, title) {
    return `<div class="card"><h3 style="margin-bottom:6px;">${title}</h3><div class="chart-wrap sm"><canvas id="${id}"></canvas></div></div>`;
  }

  function drawPie(id, labels, values, colors) {
    const ctx = document.getElementById(id);
    if (!ctx) return;
    charts.push(new Chart(ctx, {
      type: "doughnut",
      data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: "#2E2A25" }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { font: { family: "Pretendard" }, boxWidth: 12 } },
          tooltip: { callbacks: { label: (c) => `${c.label}: ${fmtKRW(c.parsed)}` } },
        },
      },
    }));
  }

  function render() {
    destroyCharts();
    const krw = data.byCurrency.KRW;
    const usd = data.byCurrency.USD;

    if (mode === "separate") {
      $rate.style.display = "none";
      $summary.className = "grid cols-2";
      $summary.innerHTML =
        statBlock("₩ 원화 자산 (KRW)", krw.assets, krw.liabilities, krw.assets - krw.liabilities, fmtKRW, "#9DBE8A") +
        statBlock("$ 달러 자산 (USD)", usd.assets, usd.liabilities, usd.assets - usd.liabilities, fmtUSD, "#7FA9B8");

      // One allocation pie per currency that actually holds assets.
      const cards = [];
      if (krw.assets > 0) cards.push(pieCard("pie-krw", "₩ 원화 자산 배분"));
      if (usd.assets > 0) cards.push(pieCard("pie-usd", "$ 달러 자산 배분"));
      $charts.innerHTML = cards.join("");
      $charts.className = cards.length > 1 ? "grid cols-2" : "grid";
      if (krw.assets > 0) { const a = allocationNative("KRW"); drawPie("pie-krw", a.labels, a.values, a.colors); }
      if (usd.assets > 0) { const a = allocationNative("USD"); drawPie("pie-usd", a.labels, a.values, a.colors); }
    } else {
      // Combined: convert everything to KRW at the current rate.
      const byCat = combinedByCategory();
      let assets = 0, liabilities = 0;
      const labels = [], values = [], colors = [];
      data.categories.forEach((cat) => {
        const amt = byCat[cat.id] || 0;
        if (cat.is_liability) { liabilities += amt; }
        else { assets += amt; if (amt > 0) { labels.push(cat.label); values.push(amt); colors.push(cat.color); } }
      });
      $rate.style.display = "block";
      $rate.textContent = `적용 환율: 1 USD = ${fmtKRW(rate)} (원화 환산 합산)`;
      $summary.className = "grid";
      $summary.innerHTML = statBlock("합산 총자산 (KRW 환산)", assets, liabilities, assets - liabilities, fmtKRW, "#9DBE8A");
      $charts.className = "grid";
      $charts.innerHTML = pieCard("pie-combined", "전체 자산 배분 (원화 환산)");
      drawPie("pie-combined", labels, values, colors);
    }
  }

  // Toggle handlers.
  $btns.forEach((btn) => {
    btn.addEventListener("click", () => {
      mode = btn.dataset.mode;
      localStorage.setItem("assetOverviewMode", mode);
      $btns.forEach((b) => b.classList.toggle("active", b === btn));
      render();
    });
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });

  render();

  // Refresh with the live rate (non-blocking); re-render combined view if shown.
  fetch(window.FX_RATE_URL)
    .then((r) => r.json())
    .then((j) => { if (j && j.rate) { rate = j.rate; if (mode === "combined") render(); } })
    .catch(() => { /* offline — keep cached rate */ });
})();
