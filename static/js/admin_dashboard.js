/* admin_dashboard.js — live stats and clock */

// ── Clock ──────────────────────────────────────────────────────────────────
const timeEl = document.getElementById("dashTime");
function updateTime() {
  timeEl.textContent = new Date().toLocaleTimeString("en-IN", {
    hour: "2-digit", minute: "2-digit", second: "2-digit"
  });
}
updateTime();
setInterval(updateTime, 1000);

// ── Load stats ─────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const users = await fetch("/api/users").then(r => r.json());

    const total    = users.length;
    const admins   = users.filter(u => u.role === "admin").length;
    const enrolled = users.filter(u => u.has_face).length;

    animateCount("statTotal",    total);
    animateCount("statAdmins",   admins);
    animateCount("statEnrolled", enrolled);
    animateCount("statLogins",   "—"); // placeholder — would need a separate endpoint
  } catch {
    // Silently fail — stats are cosmetic
    ["statTotal","statAdmins","statEnrolled","statLogins"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = "—";
    });
  }
}

function animateCount(elId, target) {
  const el = document.getElementById(elId);
  if (!el) return;
  if (typeof target !== "number") { el.textContent = target; return; }

  let current = 0;
  const step = Math.ceil(target / 20);
  const timer = setInterval(() => {
    current = Math.min(current + step, target);
    el.textContent = current;
    if (current >= target) clearInterval(timer);
  }, 40);
}

loadStats();
