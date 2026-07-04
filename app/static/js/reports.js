// Asset Reports: historical trends, allocation, and a selectable ratio bar.
// Values are stored/served in KRW; the currency toggle converts to USD on the
// fly. The period toggle switches monthly vs yearly.
(function () {
  "use strict";
  const D = window.REPORT_DATA;
  if (!D || !D.hasData) return;

  if (window.Chart) {
    Chart.defaults.color = "#A49C90";
    Chart.defaults.borderColor = "rgba(255,255,255,0.05)";
    Chart.defaults.font.family = "'Switzer','Pretendard',sans-serif";
  }

  let cur = "KRW";
  let period = "month";
  let rate = window.CACHED_RATE || 1350;
  let charts = [];

  const conv = (v) => (cur === "USD" ? v / rate : v);
  function full(v) {
    if (cur === "USD") return "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
    return "₩" + Math.round(v).toLocaleString();
  }
  function compact(v) {
    if (cur === "USD") {
      if (Math.abs(v) >= 1000) return "$" + (v / 1000).toFixed(1) + "k";
      return "$" + Math.round(v);
    }
    if (Math.abs(v) >= 1e8) return "₩" + (v / 1e8).toFixed(1) + "억";
    if (Math.abs(v) >= 1e4) return "₩" + Math.round(v / 1e4) + "만";
    return "₩" + Math.round(v);
  }

  function aggregate(labels, series) {
    if (period === "month") return { labels: labels.slice(), series: series.slice() };
    const byYear = new Map();
    labels.forEach((m, i) => byYear.set(m.slice(0, 4), series[i]));
    return { labels: Array.from(byYear.keys()), series: Array.from(byYear.values()) };
  }

  function destroy() { charts.forEach((c) => c.destroy()); charts = []; }

  const axisOpts = () => ({
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (c) => `${c.dataset.label || ""} ${full(c.parsed.y ?? c.parsed)}`.trim() } },
    },
    scales: {
      x: { grid: { display: false } },
      y: { ticks: { callback: (v) => compact(v) }, grid: { color: "rgba(255,255,255,0.05)" } },
    },
  });

  function lineMulti(id, rawLabels, datasets) {
    const ctx = document.getElementById(id);
    if (!ctx) return;
    const agg = aggregate(rawLabels, datasets[0].data);
    const ds = datasets.map((d) => ({
      label: d.label, data: aggregate(rawLabels, d.data).series.map(conv),
      borderColor: d.color, backgroundColor: d.fill ? d.color + "22" : "transparent",
      fill: !!d.fill, tension: 0.3, pointRadius: 2.5, pointBackgroundColor: d.color, borderWidth: 2.5,
    }));
    charts.push(new Chart(ctx, { type: "line", data: { labels: agg.labels, datasets: ds }, options: axisOpts() }));
  }

  function line(id, rawLabels, rawSeries, color, label) {
    lineMulti(id, rawLabels, [{ label, data: rawSeries, color, fill: true }]);
  }

  function bar(id, rawLabels, rawSeries, color, label) {
    const ctx = document.getElementById(id);
    if (!ctx) return;
    const { labels, series } = aggregate(rawLabels, rawSeries);
    charts.push(new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ label, data: series.map(conv), backgroundColor: color, borderRadius: 6 }] },
      options: axisOpts(),
    }));
  }

  function doughnut(id, labels, values, colors) {
    const ctx = document.getElementById(id);
    if (!ctx) return;
    charts.push(new Chart(ctx, {
      type: "doughnut",
      data: { labels, datasets: [{ data: values.map(conv), backgroundColor: colors, borderWidth: 2, borderColor: "#2E2A25" }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12 } },
          tooltip: { callbacks: { label: (c) => `${c.label}: ${full(c.parsed)}` } },
        },
      },
    }));
  }

  // ----- selectable ratio bar (Sector-Allocation style) -------------------
  const ratioCats = (D.ratioCategories || []).map((c, i) => ({ ...c, on: !!c.default, idx: i }));

  function renderRatioPicker() {
    const picker = document.getElementById("ratio-picker");
    if (!picker) return;
    picker.innerHTML = "";
    ratioCats.forEach((c) => {
      const label = document.createElement("label");
      label.className = "chip-check" + (c.on ? " on" : "");
      label.innerHTML =
        `<input type="checkbox" ${c.on ? "checked" : ""}>` +
        `<span><i style="background:${c.color};"></i>${c.name}</span>`;
      label.querySelector("input").addEventListener("change", (e) => {
        c.on = e.target.checked;
        label.classList.toggle("on", c.on);
        renderRatioBar();
      });
      picker.appendChild(label);
    });
  }

  function renderRatioBar() {
    const barEl = document.getElementById("ratio-bar");
    const legEl = document.getElementById("ratio-legend");
    if (!barEl || !legEl) return;
    const selected = ratioCats.filter((c) => c.on && c.value > 0);
    const total = selected.reduce((s, c) => s + c.value, 0);
    barEl.innerHTML = "";
    legEl.innerHTML = "";
    if (total <= 0) {
      barEl.innerHTML = `<div class="ratio-empty">선택한 항목에 금액이 없어요.</div>`;
      return;
    }
    selected.forEach((c) => {
      const pct = (c.value / total) * 100;
      const seg = document.createElement("div");
      seg.className = "ratio-seg";
      seg.style.width = pct + "%";
      seg.style.background = c.color;
      seg.title = `${c.name} ${pct.toFixed(1)}%`;
      if (pct >= 8) seg.textContent = pct.toFixed(0) + "%";
      barEl.appendChild(seg);

      const li = document.createElement("span");
      li.className = "ratio-leg-item";
      li.innerHTML = `<i style="background:${c.color};"></i><b>${c.name}</b> ${pct.toFixed(1)}% · ${full(c.value)}`;
      legEl.appendChild(li);
    });
  }

  function render() {
    destroy();
    const gm = D.groupMeta;
    lineMulti("chart-networth", D.months, [
      { label: "순자산", data: D.netWorth, color: "#9DBE8A", fill: true },
      { label: "부동산 제외 순자산", data: D.netWorthExclRe, color: "#C8B66E", fill: false },
    ]);
    bar("chart-growth", D.months, D.totalAssets, "#7FA9B8", "총자산");
    line("chart-investment", D.months, D.groups.investment, gm.investment.color, gm.investment.label);
    line("chart-cash", D.months, D.groups.cash, gm.cash.color, gm.cash.label);
    line("chart-safe", D.months, D.groups.safe, gm.safe.color, gm.safe.label);

    doughnut(
      "chart-allocation",
      D.allocation.map((a) => a.label),
      D.allocation.map((a) => a.value),
      D.allocation.map((a) => D.categoryColors[a.label] || "#9aa0b4")
    );

    // req5: 현금성 투자자산(=cash group, 현금 제외) vs 투자(중·고위험)
    const cashEquiv = ratioCats.filter((c) => c.group === "cash" && c.name !== "현금")
      .reduce((s, c) => s + c.value, 0);
    const invest = ratioCats.filter((c) => c.group === "investment")
      .reduce((s, c) => s + c.value, 0);
    doughnut("chart-invcash", ["현금성 투자자산", "투자 (중·고위험)"],
      [cashEquiv, invest], ["#7FA9B8", "#A99BD6"]);

    renderRatioBar();

    const note = document.getElementById("report-rate");
    if (note) note.textContent = cur === "USD"
      ? `달러 환산 표시 · 1 USD = ₩${Math.round(rate).toLocaleString()}`
      : "원화(KRW) 기준 표시";
  }

  function bindSeg(attr, apply) {
    document.querySelectorAll(`.seg-btn[data-${attr}]`).forEach((btn) => {
      btn.addEventListener("click", () => {
        apply(btn.dataset[attr]);
        btn.parentElement.querySelectorAll(".seg-btn").forEach((b) => b.classList.toggle("active", b === btn));
        render();
      });
    });
  }
  bindSeg("cur", (v) => (cur = v));
  bindSeg("period", (v) => (period = v));

  renderRatioPicker();
  render();

  fetch(window.FX_RATE_URL)
    .then((r) => r.json())
    .then((j) => { if (j && j.rate) { rate = j.rate; if (cur === "USD") render(); } })
    .catch(() => {});
})();
