// Holdings editor for the account form. Each row submits all six holding_*
// arrays (empty where N/A) so the server can re-align them by row order.
(function () {
  "use strict";
  const list = document.getElementById("holdings-list");
  const tpl = document.getElementById("holding-row-tpl");
  if (!list || !tpl) return;

  function syncRow(row) {
    const kind = row.querySelector(".h-kind").value;
    const isStock = kind === "stock";
    row.querySelector(".h-label").style.display = isStock ? "none" : "";
    row.querySelector(".h-amount").style.display = isStock ? "none" : "";
    row.querySelector(".h-ticker").style.display = isStock ? "" : "none";
    row.querySelector(".h-qty").style.display = isStock ? "" : "none";
  }

  function addRow(data) {
    const frag = tpl.content.cloneNode(true);
    const row = frag.querySelector(".holding-row");
    const d = data || {};
    row.querySelector(".h-kind").value = d.kind || "cash";
    row.querySelector(".h-cur").value = d.currency || "KRW";
    row.querySelector(".h-label").value = d.label || "";
    row.querySelector(".h-amount").value = d.amount ? d.amount : "";
    row.querySelector(".h-ticker").value = d.ticker || "";
    row.querySelector(".h-qty").value = d.qty ? d.qty : "";
    row.querySelector(".h-kind").addEventListener("change", () => syncRow(row));
    row.querySelector(".h-del").addEventListener("click", () => {
      row.remove();
      if (!list.querySelector(".holding-row")) addRow({ kind: "cash" });
    });
    list.appendChild(row);
    syncRow(row);
  }

  // Seed from existing holdings (edit) or start with one empty cash row (new).
  const seed = Array.isArray(window.HOLDINGS) ? window.HOLDINGS : [];
  if (seed.length) seed.forEach(addRow);
  else addRow({ kind: "cash" });

  document.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => addRow({ kind: btn.dataset.add }));
  });
})();
