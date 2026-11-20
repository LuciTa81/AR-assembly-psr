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
const screwAEl = document.getElementById("screwA");
const screwBEl = document.getElementById("screwB");
const screwCEl = document.getElementById("screwC");
const screwDEl = document.getElementById("screwD");
const yoloAgeEl = document.getElementById("yoloAge");
const driverVisibleEl = document.getElementById("driverVisible");
const targetToolEl = document.getElementById("targetTool");
const targetDistEl = document.getElementById("targetDist");
const confidenceEl = document.getElementById("confidence");
const warningEl = document.getElementById("warning");

const targetByState = {
  S2: "a",
  S3: "b",
  S4: "c",
  S5: "d",
};

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
    screwAEl.textContent = Number(data.extra?.screw_a_done_score_smooth ?? data.extra?.screw_a_done_score ?? 0).toFixed(2);
    screwBEl.textContent = Number(data.extra?.screw_b_done_score_smooth ?? data.extra?.screw_b_done_score ?? 0).toFixed(2);
    screwCEl.textContent = Number(data.extra?.screw_c_done_score_smooth ?? data.extra?.screw_c_done_score ?? 0).toFixed(2);
    screwDEl.textContent = Number(data.extra?.screw_d_done_score_smooth ?? data.extra?.screw_d_done_score ?? 0).toFixed(2);
    const yoloAge = data.extra?.yolo_age_frames ?? data.yolo_age_ms;
    yoloAgeEl.textContent = Number(yoloAge ?? -1) >= 0 ? `${Number(yoloAge).toFixed(0)} fr` : "-";
    driverVisibleEl.textContent = Number(data.extra?.driver_visible ?? 0).toFixed(0);
    const target = targetByState[data.current_state ?? ""];
    targetToolEl.textContent = target ? Number(data.extra?.[`tool_score_${target}`] ?? 0).toFixed(2) : "0.00";
    const targetDist = target ? Number(data.extra?.[`tool_dist_${target}`] ?? -1) : -1;
    targetDistEl.textContent = targetDist >= 0 ? `${targetDist.toFixed(0)} px` : "-";
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
