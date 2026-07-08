// Progressive enhancement + interaction layer (throxy-style UX).
// Everything here is non-essential: the app works fully without JavaScript.

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// --- friendly relative timestamps ----------------------------------------
function relativeTime(iso) {
  const then = new Date(iso);
  const secs = Math.floor((Date.now() - then.getTime()) / 1000);
  if (secs < 60) return "방금 전";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}일 전`;
  return then.toLocaleDateString("ko-KR");
}

// --- animated count-up for hero metrics ----------------------------------
// Markup: <span data-countup="129925000" data-prefix="₩" data-decimals="0">
function animateCountup(el) {
  const target = parseFloat(el.dataset.countup);
  if (isNaN(target)) return;
  const prefix = el.dataset.prefix || "";
  const decimals = parseInt(el.dataset.decimals || "0", 10);
  const negative = target < 0;
  const abs = Math.abs(target);

  const fmt = (v) =>
    (negative && v > 0 ? "-" : "") +
    prefix +
    v.toLocaleString("ko-KR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

  if (REDUCED) { el.textContent = fmt(abs); return; }

  const duration = 900;
  const start = performance.now();
  function tick(now) {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
    el.textContent = fmt(abs * eased);
    if (t < 1) requestAnimationFrame(tick);
    else el.textContent = fmt(abs);
  }
  requestAnimationFrame(tick);
}

// --- staggered reveal-on-scroll ------------------------------------------
function setupReveal() {
  const targets = Array.from(document.querySelectorAll("[data-reveal]"));
  if (!targets.length) return;

  if (REDUCED || !("IntersectionObserver" in window)) {
    targets.forEach((el) => el.classList.add("in"));
    return;
  }

  const io = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const delay = parseInt(el.dataset.revealDelay || "0", 10);
        el.style.transitionDelay = `${delay}ms`;
        el.classList.add("in");
        // fire count-ups once the card is on screen
        el.querySelectorAll("[data-countup]").forEach(animateCountup);
        obs.unobserve(el);
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
  );
  targets.forEach((el) => io.observe(el));
}

// Auto-tag the page's cards/groups for staggered reveal so individual
// templates don't each need to opt in.
function tagReveals() {
  const groups = document.querySelectorAll(".page .card, .page .asset-group");
  let i = 0;
  groups.forEach((el) => {
    if (el.hasAttribute("data-reveal")) return;
    el.setAttribute("data-reveal", "");
    el.dataset.revealDelay = String(Math.min(i, 6) * 55);
    i += 1;
  });
}

// --- sticky navbar: subtle shadow once scrolled --------------------------
function setupNavbar() {
  const bar = document.querySelector(".navbar");
  if (!bar) return;
  const onScroll = () => bar.classList.toggle("scrolled", window.scrollY > 4);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
}

// --- user dropdown menu --------------------------------------------------
function setupUserMenu() {
  const menu = document.getElementById("user-menu");
  if (!menu) return;
  const btn = menu.querySelector("button");
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = menu.classList.toggle("open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.addEventListener("click", (e) => {
    if (!menu.contains(e.target)) {
      menu.classList.remove("open");
      btn.setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { menu.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); }
  });
}

// --- live thousands separators on money inputs ----------------------------
// Inputs opt in with data-comma="1". Commas are stripped again on submit so
// the server-side parsers (WTForms DecimalField, int()) see a plain number.
function setupCommaInputs() {
  const inputs = document.querySelectorAll('input[data-comma]');
  if (!inputs.length) return;
  const format = (el) => {
    const digits = el.value.replace(/[^\d]/g, "");
    el.value = digits ? Number(digits).toLocaleString("ko-KR") : "";
  };
  inputs.forEach((el) => {
    format(el); // format any server-rendered initial value
    el.addEventListener("input", () => format(el));
    if (el.form && !el.form.dataset.commaHooked) {
      el.form.dataset.commaHooked = "1";
      el.form.addEventListener("submit", () => {
        el.form.querySelectorAll('input[data-comma]').forEach((f) => {
          f.value = f.value.replace(/,/g, "");
        });
      });
    }
  });
}

// --- PWA service worker ----------------------------------------------------
// Registration only succeeds on secure contexts (HTTPS or localhost); on
// plain LAN HTTP the call silently no-ops, which is fine.
function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("time[data-ts]").forEach((el) => {
    el.textContent = relativeTime(el.dataset.ts);
    el.title = new Date(el.dataset.ts).toLocaleString("ko-KR");
  });

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        const original = btn.textContent;
        btn.textContent = "복사됨 ✓";
        setTimeout(() => (btn.textContent = original), 1500);
      } catch (e) { /* clipboard unavailable */ }
    });
  });

  setupNavbar();
  setupUserMenu();
  tagReveals();
  setupReveal();
  setupCommaInputs();
  registerServiceWorker();

  // Count-ups not inside a reveal target (e.g. above the fold) run immediately.
  document.querySelectorAll("[data-countup]").forEach((el) => {
    const inReveal = el.closest("[data-reveal]");
    if (!inReveal) animateCountup(el);
  });
});
