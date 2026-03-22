/* camera.js — shared webcam & frame capture utilities */

const Camera = (() => {
  let stream = null;

  async function start(videoEl) {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false
      });
      videoEl.srcObject = stream;
      return true;
    } catch (err) {
      console.error("Camera error:", err);
      return false;
    }
  }

  function stop() {
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
  }

  /**
   * Capture a single frame from the video element.
   * Returns a base64 data-URI JPEG string.
   * @param {HTMLVideoElement} videoEl
   * @param {number} quality  — JPEG quality 0–1
   */
  function captureFrame(videoEl, quality = 0.85) {
    const canvas = document.createElement("canvas");
    canvas.width  = videoEl.videoWidth  || 640;
    canvas.height = videoEl.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    // Draw mirrored (undo CSS mirror so backend gets correct orientation)
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", quality);
  }

  /**
   * Capture multiple frames with a delay between each.
   * @param {HTMLVideoElement} videoEl
   * @param {number} count
   * @param {number} interval  — ms between captures
   * @param {Function} onEach  — callback(frame, index)
   * @returns {Promise<string[]>} array of base64 frames
   */
  async function captureFrames(videoEl, count = 8, interval = 250, onEach = null) {
    const frames = [];
    for (let i = 0; i < count; i++) {
      const frame = captureFrame(videoEl);
      frames.push(frame);
      if (onEach) onEach(frame, i);
      await new Promise(r => setTimeout(r, interval));
    }
    return frames;
  }

  return { start, stop, captureFrame, captureFrames };
})();
