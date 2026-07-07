import "./styles.css";

const STATUS_ASSETS = {
  judgment: "/assets/judgment.png",
  detect: "/assets/detect.png",
  safety: "/assets/safety.png",
};
const STRONG_SPOOF_SCORE = 0.8;

function getDefaultApiBase() {
  const { protocol, hostname } = window.location;

  if (protocol === "http:" && (hostname === "127.0.0.1" || hostname === "localhost")) {
    return "http://127.0.0.1:8000";
  }
  if (protocol === "http:" && hostname) {
    return `http://${hostname}:8000`;
  }
  return "http://10.0.2.2:8000";
}

function getInitialApiBase() {
  const savedApiBase = localStorage.getItem("isfam_api_base");
  const { protocol, hostname } = window.location;
  const isLocalWebPreview =
    protocol === "http:" && (hostname === "127.0.0.1" || hostname === "localhost");
  const isNetworkWebPreview =
    protocol === "http:" && hostname && hostname !== "127.0.0.1" && hostname !== "localhost";
  const isAndroidAppPreview = protocol === "https:" && hostname === "localhost";

  if (!savedApiBase) {
    return getDefaultApiBase();
  }
  if (
    isNetworkWebPreview &&
    (savedApiBase.includes("127.0.0.1") ||
      savedApiBase.includes("localhost") ||
      savedApiBase.includes("10.0.2.2"))
  ) {
    return getDefaultApiBase();
  }
  if (isLocalWebPreview && savedApiBase.includes("10.0.2.2")) {
    return "http://127.0.0.1:8000";
  }
  if (isAndroidAppPreview && savedApiBase.includes("127.0.0.1")) {
    return "http://10.0.2.2:8000";
  }
  return savedApiBase;
}

const defaultApiBase = getDefaultApiBase();
const state = {
  apiBase: getInitialApiBase(),
  callFile: null,
  callerNumber: localStorage.getItem("isfam_caller_number") || "010-0000-0000",
  familyName:
    localStorage.getItem("isfam_family_name") ||
    localStorage.getItem("isfam_caller_name") ||
    "엄마",
  startedAt: null,
  timer: null,
  warningTimer: null,
  analysisPromise: null,
  latestAnalysis: null,
  isCalling: false,
};

const $ = (id) => document.getElementById(id);

function apiUrl(path) {
  return `${state.apiBase.replace(/\/$/, "")}${path}`;
}

function setText(id, value) {
  $(id).textContent = value;
}

function setCard(status, title, message) {
  $("aiCard").className = `ai-card ${status}`;
  $("statusImage").src = STATUS_ASSETS[status];
  setText("warningTitle", title);
  setText("warningMessage", message);
}

function setCallState(message) {
  setText("callState", message);
}

function setSetupHint(message) {
  setText("setupHint", message);
}

function showSetup(open) {
  $("setupSheet").classList.toggle("open", open);
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(apiUrl(path), options);
  } catch (error) {
    throw new Error(`AI 서버 연결 실패: ${state.apiBase}`);
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `HTTP ${response.status}`);
  }
  return payload;
}

async function checkServer() {
  $("apiBaseInput").value = state.apiBase;
  $("callerNumberInput").value = state.callerNumber;
  $("familyNameInput").value = state.familyName;
  applyCallerDisplay();

  try {
    await requestJson("/health");
    setText("networkStatus", "AI 서버 연결됨");
  } catch {
    setText("networkStatus", "AI 서버 연결 필요");
  }
}

function saveSetup() {
  state.apiBase = $("apiBaseInput").value.trim() || defaultApiBase;
  state.callerNumber = $("callerNumberInput").value.trim() || "010-0000-0000";
  state.familyName = $("familyNameInput").value.trim() || "엄마";

  localStorage.setItem("isfam_api_base", state.apiBase);
  localStorage.setItem("isfam_caller_number", state.callerNumber);
  localStorage.setItem("isfam_family_name", state.familyName);

  applyCallerDisplay();
  checkServer();
  setSetupHint("설정이 저장됐습니다.");
}

function applyCallerDisplay() {
  setText("callerNumber", state.callerNumber);
}

function updateFileLabel() {
  state.callFile = $("callAudioFile").files[0] || null;
  setText("callFileName", state.callFile ? state.callFile.name : "파일 선택");
}

function prepareCall() {
  saveSetup();
  updateFileLabel();

  if (!state.callFile) {
    setSetupHint("통화 음성 파일을 먼저 선택하세요.");
    return;
  }

  showSetup(false);
  startCall();
}

function startCall() {
  if (!state.callFile) {
    showSetup(true);
    setSetupHint("통화 음성 파일을 선택한 뒤 통화 시작을 누르세요.");
    return;
  }

  const audio = $("callAudioPlayer");
  audio.pause();
  audio.src = URL.createObjectURL(state.callFile);

  state.isCalling = true;
  state.latestAnalysis = null;
  state.analysisPromise = null;
  state.startedAt = Date.now();

  if (state.timer) clearInterval(state.timer);
  if (state.warningTimer) clearTimeout(state.warningTimer);

  setCallState("통화 중");
  setCard(
    "judgment",
    "AI가 판단 중입니다",
    "IsFAM이 통화 음성을 분석하고 있습니다."
  );

  audio.play().catch(() => {
    setCard(
      "judgment",
      "재생 대기 중입니다",
      "브라우저 정책 때문에 음성이 멈췄습니다. 화면을 한 번 터치해 주세요."
    );
  });

  state.timer = setInterval(updateTimer, 300);
  state.analysisPromise = analyzeFile(state.callFile)
    .then((data) => {
      state.latestAnalysis = data;
      return data;
    })
    .catch((error) => {
      state.latestAnalysis = { error: error.message };
      return state.latestAnalysis;
    });

  state.warningTimer = setTimeout(showAnalysisPopup, 9000);
}

function stopCall() {
  const audio = $("callAudioPlayer");
  audio.pause();
  audio.removeAttribute("src");

  if (state.timer) clearInterval(state.timer);
  if (state.warningTimer) clearTimeout(state.warningTimer);

  state.isCalling = false;
  state.startedAt = null;
  setText("callTimer", "00:00");
  setCallState("통화 종료");
  setCard(
    "judgment",
    "통화가 종료되었습니다",
    "우측 상단 메뉴에서 다른 음성 파일로 다시 시연할 수 있습니다."
  );
}

function updateTimer() {
  if (!state.startedAt) return;
  const seconds = Math.floor((Date.now() - state.startedAt) / 1000);
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  setText("callTimer", `${mm}:${ss}`);
}

async function showAnalysisPopup() {
  if (!state.isCalling) return;

  const data = state.latestAnalysis || (await state.analysisPromise);
  if (!state.isCalling) return;

  if (!data || data.error) {
    setCallState("IsFAM 확인 필요");
    setCard(
      "detect",
      "분석 연결이 지연됩니다",
      data?.error || "AI 서버 응답이 늦어지고 있습니다. 통화 내용을 다시 확인하세요."
    );
    return;
  }

  const result = buildWarning(data);
  setCallState(result.safe ? "IsFAM 안전" : "IsFAM 경고");
  setCard(result.status, result.title, result.message);
}

function buildWarning(data) {
  if (data.risk_level) {
    const reason = data.decision_reasons?.[0];
    if (data.risk_level === "safe" && data.is_trusted) {
      return {
        status: "safety",
        safe: true,
        title: "등록된 가족 목소리입니다",
        message: reason || "IsFAM 위험도 분석에서 안전으로 판단했습니다.",
      };
    }

    if (data.risk_level === "caution") {
      return {
        status: "detect",
        safe: false,
        title: "가족 확인이 필요합니다",
        message: reason || "IsFAM 위험도 분석에서 추가 확인이 필요하다고 판단했습니다.",
      };
    }

    return {
      status: "detect",
      safe: false,
      title: "보이스피싱이 의심됩니다",
      message: reason || "IsFAM 위험도 분석에서 위험 통화로 판단했습니다.",
    };
  }

  const family = data.family_verification;
  const anti = data.anti_spoofing;
  const bestMatch = family?.best_match;
  const displayName = state.familyName || bestMatch?.name || "가족";
  const spoofScore = anti?.spoof_score ?? 0;
  const hasStrongSpoofSignal = Boolean(anti?.is_spoofed && spoofScore >= STRONG_SPOOF_SCORE);

  if (anti?.is_spoofed && !family?.is_registered_family) {
    return {
      status: "detect",
      safe: false,
      title: "보이스피싱이 의심됩니다",
      message: `저장된 ${displayName}의 목소리와 다르고 AI 합성 음성 신호가 감지됐습니다. 통화를 중단하고 직접 확인하세요.`,
    };
  }

  if (!family?.is_registered_family) {
    return {
      status: "detect",
      safe: false,
      title: "보이스피싱이 의심됩니다",
      message: `저장된 ${displayName}의 목소리와 일치하지 않습니다. 통화 내용을 믿기 전에 가족에게 다시 확인하세요.`,
    };
  }

  if (hasStrongSpoofSignal) {
    return {
      status: "detect",
      safe: false,
      title: "AI 음성 신호가 감지됐습니다",
      message: `${displayName}와 비슷하지만 합성 음성 신호가 있습니다. 송금이나 인증번호 요청은 거절하세요.`,
    };
  }

  return {
    status: "safety",
    safe: true,
    title: "등록된 가족 목소리입니다",
    message: `저장된 ${displayName}의 목소리와 일치합니다. 그래도 송금이나 인증번호 요청은 한 번 더 확인하세요.`,
  };
}

async function analyzeFile(file) {
  const formData = new FormData();
  formData.append("audio_file", file);
  return requestJson("/api/v1/voice/verify-family-secure", {
    method: "POST",
    body: formData,
  });
}

function bindEvents() {
  $("saveSetupBtn").addEventListener("click", saveSetup);
  $("prepareCallBtn").addEventListener("click", prepareCall);
  $("stopCallBtn").addEventListener("click", stopCall);
  $("toggleSetupBtn").addEventListener("click", () => showSetup(true));
  $("closeSetupBtn").addEventListener("click", () => showSetup(false));
  $("callAudioFile").addEventListener("change", updateFileLabel);
}

bindEvents();
checkServer();
setCard("judgment", "AI가 판단 중입니다", "통화 음성 파일을 선택하고 통화를 시작하세요.");
