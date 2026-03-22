/* login.js — face scan authentication flow */

const video     = document.getElementById("video");
const scanBtn   = document.getElementById("scanBtn");
const btnText   = document.getElementById("scanBtnText");
const statusDot = document.getElementById("statusDot");
const statusLbl = document.getElementById("statusLabel");
const scanLine  = document.getElementById("scanLine");
const resultOverlay = document.getElementById("resultOverlay");
const resultIcon    = document.getElementById("resultIcon");
const resultText    = document.getElementById("resultText");
const scoreWrap     = document.getElementById("scoreWrap");
const scoreFill     = document.getElementById("scoreFill");
const scoreValue    = document.getElementById("scoreValue");

let scanning = false;
let camReady = false;

function setStatus(state, label) {
  statusDot.className = `scanner-status ${state}`;
  statusLbl.textContent = label;
}

async function init() {
  setStatus("", "INITIALIZING");
  const ok = await Camera.start(video);
  if (!ok) {
    setStatus("fail", "CAMERA ERROR");
    btnText.textContent = "Camera Unavailable";
    return;
  }
  camReady = true;
  setStatus("active", "READY");
  scanBtn.disabled = false;
  btnText.textContent = "Scan Face";
}

function showResult(success, name = "", role = "", score = null) {
  scanLine.classList.remove("animating");

  if (success) {
    resultIcon.textContent = "✓";
    resultIcon.style.color = "var(--green)";
    resultText.textContent = `Welcome, ${name}`;
    resultText.style.color = "var(--green)";
  } else {
    resultIcon.textContent = "✗";
    resultIcon.style.color = "var(--red)";
    resultText.textContent = name || "Face Not Recognized";
    resultText.style.color = "var(--red)";
  }

  resultOverlay.classList.add("visible");

  if (score !== null) {
    scoreWrap.style.display = "block";
    const pct = Math.min(score / 0.20 * 100, 100);
    scoreFill.style.width = pct + "%";
    scoreFill.className = "score-fill " + (score < 0.08 ? "low" : score < 0.14 ? "mid" : "high");
    scoreValue.textContent = `D = ${score.toFixed(4)}  (threshold: 0.08)`;
  }
}

function resetUI() {
  resultOverlay.classList.remove("visible");
  scoreWrap.style.display = "none";
  scanLine.classList.remove("animating");
  setStatus("active", "READY");
  btnText.textContent = "Scan Face";
  scanBtn.disabled = false;
  scanning = false;
}

scanBtn.addEventListener("click", async () => {
  if (!camReady || scanning) return;
  scanning = true;
  scanBtn.disabled = true;
  btnText.textContent = "Scanning...";
  setStatus("scanning", "SCANNING");
  scanLine.classList.add("animating");

  // Small delay so animation starts before compute
  await new Promise(r => setTimeout(r, 300));

  const frame = Camera.captureFrame(video, 0.90);

  let data;
  try {
    data = await apiPost("/api/authenticate", { frame });
  } catch {
    showResult(false, "Network error. Try again.");
    setTimeout(resetUI, 3000);
    return;
  }

  if (data.authenticated) {
    setStatus("success", "AUTHENTICATED");
    showResult(true, data.name, data.role, data.score);

    setTimeout(() => {
      window.location.href = data.redirect;
    }, 1800);

  } else {
    setStatus("fail", "ACCESS DENIED");
    showResult(false, data.message || "Not recognized", "", data.score);

    setTimeout(resetUI, 3500);
  }
});

init();
