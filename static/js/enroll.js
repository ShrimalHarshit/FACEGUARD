/* enroll.js — face enrollment flow for admin */

const video       = document.getElementById("video");
const scanLine    = document.getElementById("scanLine");
const captureBtn  = document.getElementById("captureBtn");
const submitBtn   = document.getElementById("submitBtn");
const nameInput   = document.getElementById("userName");
const frameCount  = document.getElementById("frameCount");
const progressFill= document.getElementById("progressFill");
const captureProgress = document.getElementById("captureProgress");
const framesStrip = document.getElementById("framesStrip");
const enrollResult= document.getElementById("enrollResult");

const TOTAL_FRAMES = 8;
let capturedFrames = [];
let camReady = false;

// ── steps ──────────────────────────────────────────────────────────────────
function activateStep(n) {
  document.querySelectorAll(".step").forEach((s, i) => {
    if (i + 1 < n)  s.classList.add("done"), s.removeAttribute("data-active");
    else if (i + 1 === n) s.setAttribute("data-active", "true"), s.classList.remove("done");
    else s.removeAttribute("data-active"), s.classList.remove("done");
  });
}

// ── camera ─────────────────────────────────────────────────────────────────
async function init() {
  const ok = await Camera.start(video);
  if (!ok) {
    captureBtn.textContent = "Camera Error";
    return;
  }
  camReady = true;
  captureBtn.disabled = false;
  activateStep(1);
}

// ── name input watcher ─────────────────────────────────────────────────────
nameInput.addEventListener("input", () => {
  if (nameInput.value.trim().length > 1 && camReady) {
    activateStep(2);
  }
});

// ── capture button ─────────────────────────────────────────────────────────
captureBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();
  if (!name) {
    nameInput.focus();
    showResult("error", "Please enter the user's name first.");
    return;
  }
  if (!camReady) return;

  capturedFrames = [];
  framesStrip.innerHTML = "";
  captureProgress.style.display = "block";
  captureBtn.disabled = true;
  submitBtn.disabled  = true;
  activateStep(3);

  // Animate scan line
  scanLine.className = "scan-line capture-line animating";

  // Capture TOTAL_FRAMES frames with progress
  capturedFrames = await Camera.captureFrames(
    video, TOTAL_FRAMES, 300,
    (frame, i) => {
      // Update progress bar
      const pct = ((i + 1) / TOTAL_FRAMES) * 100;
      progressFill.style.width = pct + "%";
      frameCount.textContent   = i + 1;

      // Thumbnail
      const img = document.createElement("img");
      img.src = frame;
      img.className = "frame-thumb";
      img.alt = `Frame ${i + 1}`;
      framesStrip.appendChild(img);
    }
  );

  scanLine.classList.remove("animating");
  captureBtn.disabled = false;
  submitBtn.disabled  = false;
  activateStep(4);
  showResult("success", `${TOTAL_FRAMES} frames captured. Click Enroll User to save.`);
});

// ── submit button ──────────────────────────────────────────────────────────
submitBtn.addEventListener("click", async () => {
  const name = nameInput.value.trim();
  if (!name) {
    showResult("error", "Please enter a name.");
    return;
  }
  if (capturedFrames.length < 3) {
    showResult("error", "Please capture frames first.");
    return;
  }

  submitBtn.disabled  = true;
  captureBtn.disabled = true;
  submitBtn.textContent = "Enrolling...";

  let data;
  try {
    data = await apiPost("/api/enroll", { name, frames: capturedFrames });
  } catch {
    showResult("error", "Network error. Please try again.");
    submitBtn.disabled = false;
    captureBtn.disabled = false;
    submitBtn.innerHTML = "<span>✓</span> Enroll User";
    return;
  }

  if (data.success) {
    showResult(
      "success",
      `✓ User "${data.name}" enrolled (ID #${data.user_id}). ` +
      `Go to Manage Users to assign a role.`
    );
    // Reset form
    nameInput.value = "";
    capturedFrames = [];
    framesStrip.innerHTML = "";
    frameCount.textContent = "0";
    progressFill.style.width = "0%";
    captureProgress.style.display = "none";
    activateStep(1);
  } else {
    showResult("error", data.error || "Enrollment failed. Try again.");
  }

  submitBtn.disabled = false;
  captureBtn.disabled = false;
  submitBtn.innerHTML = "<span>✓</span> Enroll User";
});

// ── helpers ────────────────────────────────────────────────────────────────
function showResult(type, msg) {
  enrollResult.style.display = "block";
  enrollResult.className = `enroll-result ${type}`;
  enrollResult.textContent = msg;
}

init();
