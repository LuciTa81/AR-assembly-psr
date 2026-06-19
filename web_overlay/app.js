const camera = document.getElementById("camera");
const stateEl = document.getElementById("state");
const labelEl = document.getElementById("label");
const nextActionEl = document.getElementById("nextAction");
const fpsEl = document.getElementById("fps");
const latencyEl = document.getElementById("latency");
const markerEl = document.getElementById("marker");
const markerCountEl = document.getElementById("markerCount");
const warpQualityEl = document.getElementById("warpQuality");
const boxScoreEl = document.getElementById("boxScore");
const lidScoreEl = document.getElementById("lidScore");
const confidenceEl = document.getElementById("confidence");
const warningEl = document.getElementById("warning");

async function refreshState() {
  const stamp = Date.now();
  camera.src = `/frame.jpg?t=${stamp}`;
  try {
    const response = await fetch(`/state.json?t=${stamp}`, { cache: "no-store" });
    const data = await response.json();
    stateEl.textContent = data.current_state ?? "S0";
    labelEl.textContent = data.current_label ?? "";
    nextActionEl.textContent = data.next_action ?? "";
    fpsEl.textContent = Number(data.fps ?? 0).toFixed(1);
    latencyEl.textContent = `${data.latency_ms ?? 0} ms`;
    markerEl.textContent = data.marker_status ?? "UNKNOWN";
    markerCountEl.textContent = data.marker_count ?? 0;
    warpQualityEl.textContent = Number(data.warp_quality ?? 0).toFixed(2);
    boxScoreEl.textContent = Number(data.extra?.box_present_score ?? 0).toFixed(2);
    lidScoreEl.textContent = Number(data.extra?.lid_closed_score ?? 0).toFixed(2);
    confidenceEl.textContent = Number(data.confidence ?? 0).toFixed(2);
    if (data.warning) {
      warningEl.textContent = data.warning.message ?? data.warning.code;
      warningEl.classList.remove("hidden");
    } else {
      warningEl.classList.add("hidden");
    }
  } catch (error) {
    warningEl.textContent = "Waiting for realtime server";
    warningEl.classList.remove("hidden");
  }
}

setInterval(refreshState, 120);
refreshState();
