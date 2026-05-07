const state = {
  profile: null,
  sessionId: null,
  isBusy: false,
  websitePresets: [],
};

const tenantIdEl = document.getElementById("tenantId");
const emailEl = document.getElementById("email");
const passwordEl = document.getElementById("password");
const statusEl = document.getElementById("status");
const errorEl = document.getElementById("error");
const loginBtn = document.getElementById("loginBtn");
const logoutBtn = document.getElementById("logoutBtn");
const clearBtn = document.getElementById("clearBtn");
const composerEl = document.getElementById("composer");
const messageInputEl = document.getElementById("messageInput");
const messagesEl = document.getElementById("messages");
const sendBtn = document.getElementById("sendBtn");
const modeSelectEl = document.getElementById("modeSelect");
const presetWrapEl = document.getElementById("presetWrap");
const presetSelectEl = document.getElementById("presetSelect");
const streamToggleEl = document.getElementById("streamToggle");
const streamWrapEl = document.getElementById("streamWrap");
const sourceWrapEl = document.getElementById("sourceWrap");
const sourceUrlEl = document.getElementById("sourceUrl");
const sourceListWrapEl = document.getElementById("sourceListWrap");
const sourceUrlsEl = document.getElementById("sourceUrls");
const modeHintEl = document.getElementById("modeHint");

function parseSourceUrls(raw) {
  const seen = new Set();
  return String(raw || "")
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter((url) => {
      if (!url || seen.has(url)) return false;
      seen.add(url);
      return true;
    });
}

function selectedPreset() {
  const id = presetSelectEl.value;
  if (!id || id === "custom") return null;
  return state.websitePresets.find((item) => item.preset_id === id) || null;
}

function applyPresetSelection() {
  const preset = selectedPreset();
  if (!preset) return;

  const urls = Array.isArray(preset.source_urls) ? preset.source_urls.filter(Boolean) : [];
  sourceUrlEl.value = urls[0] || preset.website_url || "";
  sourceUrlsEl.value = urls.join("\n");
}

async function loadWebsitePresets() {
  try {
    const response = await fetch("/v1/website/presets");
    if (!response.ok) return;
    const data = await response.json();
    if (!Array.isArray(data)) return;

    state.websitePresets = data;
    presetSelectEl.innerHTML = "";

    const custom = document.createElement("option");
    custom.value = "custom";
    custom.textContent = "Custom (manual)";
    presetSelectEl.appendChild(custom);

    data.forEach((preset) => {
      const option = document.createElement("option");
      option.value = preset.preset_id;
      option.textContent = preset.label;
      presetSelectEl.appendChild(option);
    });

    const finly = data.find((item) => item.preset_id === "finly_demo");
    if (finly) {
      presetSelectEl.value = finly.preset_id;
      applyPresetSelection();
    }
  } catch {
    state.websitePresets = [];
  }
}

function showError(message) {
  if (!message) {
    errorEl.hidden = true;
    errorEl.textContent = "";
    return;
  }
  errorEl.hidden = false;
  errorEl.textContent = message;
}

function updateStatus() {
  if (!state.profile) {
    statusEl.textContent = "Signed out";
    return;
  }
  statusEl.textContent = `Signed in as ${state.profile.user_id} (${state.profile.role})`;
}

function updateModeUI() {
  const isResearch = modeSelectEl.value === "research";
  const isAuto = modeSelectEl.value === "auto";
  presetWrapEl.classList.add("is-hidden");
  sourceWrapEl.classList.add("is-hidden");
  sourceListWrapEl.classList.add("is-hidden");
  streamWrapEl.classList.toggle("is-hidden", isResearch || isAuto);
  if (isResearch) {
    streamToggleEl.checked = false;
    modeHintEl.textContent = "Current mode: V2 Research. Website context is auto-applied from predefined domain presets.";
  } else if (isAuto) {
    streamToggleEl.checked = false;
    modeHintEl.textContent = "Current mode: Auto. The API routes complex requests to V2 automatically.";
  } else {
    modeHintEl.textContent = `Current mode: V1 Chat. Streaming ${streamToggleEl.checked ? "on" : "off"}.`;
  }
}

function setBusy(flag) {
  state.isBusy = Boolean(flag);
  [loginBtn, logoutBtn, clearBtn, sendBtn, modeSelectEl, streamToggleEl].forEach((el) => {
    el.disabled = state.isBusy;
  });
  messageInputEl.disabled = state.isBusy;
  presetSelectEl.disabled = state.isBusy;
  sourceUrlEl.disabled = state.isBusy;
  sourceUrlsEl.disabled = state.isBusy;
}

function addBubble(role, content) {
  const el = document.createElement("article");
  el.className = `bubble ${role}`;
  el.textContent = content;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

function buildResearchReply(data) {
  const summary = String(data?.summary || "No summary.").trim();
  const recommendations = Array.isArray(data?.recommendations) ? data.recommendations.filter(Boolean) : [];
  if (!recommendations.length) {
    return summary;
  }

  const lowerSummary = summary.toLowerCase();
  const alreadyStructured =
    lowerSummary.includes("actions:") ||
    lowerSummary.includes("option 1") ||
    lowerSummary.includes("key improvement areas") ||
    lowerSummary.includes("recommended next steps");

  if (alreadyStructured) {
    return summary;
  }

  return [summary, `\n\nActions:\n- ${recommendations.join("\n- ")}`].join("").trim();
}

function resetChat() {
  messagesEl.innerHTML = "";
  addBubble("assistant", "Hello. Log in and ask me anything about your tenant data.");
}

function buildResearchContextPayload() {
  const manualUrls = parseSourceUrls([sourceUrlEl.value, sourceUrlsEl.value].filter(Boolean).join("\n"));
  const preset = selectedPreset();
  const presetUrls = preset ? parseSourceUrls((preset.source_urls || []).join("\n")) : [];
  const allSourceUrls = parseSourceUrls([...manualUrls, ...presetUrls].join("\n"));
  const primaryUrl = allSourceUrls[0] || "";
  let websiteUrl = null;
  let host = "";

  if (primaryUrl) {
    try {
      const parsed = new URL(primaryUrl);
      websiteUrl = `${parsed.protocol}//${parsed.host}`;
      host = parsed.hostname;
    } catch {
      websiteUrl = null;
    }
  } else if (preset?.website_url) {
    websiteUrl = preset.website_url;
    try {
      host = new URL(preset.website_url).hostname;
    } catch {
      host = "";
    }
  }

  const ragContext = primaryUrl
    ? `Source page: ${primaryUrl}. Request context: budgeting workflow improvement and financial planning guidance.`
    : (preset?.rag_context || "Request context: budgeting workflow improvement and financial planning guidance for a fintech website.");

  const presetAllowedDomains = Array.isArray(preset?.allowed_domains) ? preset.allowed_domains.filter(Boolean) : [];
  const allowedDomains = parseSourceUrls([host, ...presetAllowedDomains].join("\n"));

  return {
    source_urls: allSourceUrls,
    website_url: websiteUrl,
    allowed_domains: allowedDomains,
    domain_type_hint: preset?.domain_type_hint || "fintech",
    domain_type: preset?.domain_type_hint || "fintech",
    current_page: primaryUrl || null,
    current_page_context: primaryUrl ? `User supplied page for website-grounded testing: ${primaryUrl}` : null,
    site_metadata: preset?.site_metadata || "Fintech budgeting assistant with dashboards, spending categories, and savings goals.",
    navigation_context: preset?.navigation_context || "Dashboard, Budgets, Transactions, Goals, Insights, Help",
    product_service_context: preset?.product_service_context || "Budget planner, expense tracking, savings goals, cash-flow monitoring",
    rag_context: ragContext,
  };
}

async function login() {
  const response = await fetch("/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      tenant_id: tenantIdEl.value.trim(),
      email: emailEl.value.trim(),
      password: passwordEl.value,
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || body?.detail || `Login failed (${response.status})`);
  }

  const data = await response.json();
  state.profile = data;
  state.sessionId = null;
  updateStatus();
}

async function logout() {
  await fetch("/v1/auth/logout", { method: "POST", credentials: "include" });
  state.profile = null;
  state.sessionId = null;
  updateStatus();
}

async function sendChat(text, autoRouteV2 = false) {
  const response = await fetch("/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      session_id: state.sessionId,
      channel: "web",
      stream: false,
      strict_grounding: true,
      message: { role: "user", content: text },
      metadata: autoRouteV2 ? { auto_route_v2: true } : {},
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || body?.detail || `Chat failed (${response.status})`);
  }

  const data = await response.json();
  state.sessionId = data.session_id;
  return data;
}

async function sendChatStream(text, onDelta) {
  const response = await fetch("/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      session_id: state.sessionId,
      channel: "web",
      stream: true,
      strict_grounding: true,
      message: { role: "user", content: text },
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || body?.detail || `Chat stream failed (${response.status})`);
  }

  if (!response.body) {
    throw new Error("Streaming response body unavailable in browser.");
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let buffer = "";
  let completedPayload = null;

  const parseFrame = (frameText) => {
    const lines = frameText.split("\n");
    let eventName = "message";
    let dataText = "";
    for (const line of lines) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) {
        const next = line.slice(5).trim();
        dataText = dataText ? `${dataText}\n${next}` : next;
      }
    }
    if (!dataText) return;

    let data;
    try {
      data = JSON.parse(dataText);
    } catch {
      return;
    }

    if (eventName === "response.delta") {
      onDelta(String(data.delta || ""));
    }
    if (eventName === "response.completed") {
      completedPayload = data;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";

    for (const frame of frames) {
      parseFrame(frame);
    }
  }

  if (buffer.trim()) {
    parseFrame(buffer);
  }

  if (!completedPayload) {
    throw new Error("Streaming finished without completion event.");
  }

  state.sessionId = completedPayload.session_id || state.sessionId;
  return completedPayload;
}

async function sendResearch(text) {
  const contextPayload = buildResearchContextPayload();
  const sources = (contextPayload.source_urls || []).map((url) => ({ url }));
  const { source_urls: _unusedSourceUrls, ...requestContext } = contextPayload;
  const maxSources = Math.max(1, Math.min(10, sources.length || 3));
  const response = await fetch("/v2/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      tenant_id: state.profile.tenant_id,
      user_id: state.profile.user_id,
      query: text,
      sources,
      max_sources: maxSources,
      verbose: false,
      ...requestContext,
    }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || body?.detail || `Research failed (${response.status})`);
  }

  return response.json();
}

loginBtn.addEventListener("click", async () => {
  showError("");
  try {
    setBusy(true);
    await login();
  } catch (error) {
    showError(String(error.message || error));
  } finally {
    setBusy(false);
    updateModeUI();
  }
});

logoutBtn.addEventListener("click", async () => {
  showError("");
  try {
    setBusy(true);
    await logout();
  } catch (error) {
    showError(String(error.message || error));
  } finally {
    setBusy(false);
    updateModeUI();
  }
});

clearBtn.addEventListener("click", () => {
  resetChat();
});

composerEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInputEl.value.trim();
  if (!text) return;
  if (!state.profile) {
    showError("Please login before sending a message.");
    return;
  }

  showError("");
  addBubble("user", text);
  messageInputEl.value = "";

  try {
    setBusy(true);
    if (modeSelectEl.value === "research") {
      const data = await sendResearch(text);
      const reply = buildResearchReply(data);
      addBubble("assistant", reply);
      return;
    }

    if (modeSelectEl.value === "auto") {
      const response = await sendChat(text, true);
      const reply = response?.message?.content || "No response content.";
      addBubble("assistant", reply);
      return;
    }

    if (streamToggleEl.checked) {
      const bubble = addBubble("assistant", "");
      let accum = "";
      await sendChatStream(text, (delta) => {
        accum = accum ? `${accum} ${delta}` : delta;
        bubble.textContent = accum;
        messagesEl.scrollTop = messagesEl.scrollHeight;
      });
      if (!bubble.textContent.trim()) {
        bubble.textContent = "No response content.";
      }
      return;
    }

    const response = await sendChat(text);
    const reply = response?.message?.content || "No response content.";
    addBubble("assistant", reply);
  } catch (error) {
    showError(String(error.message || error));
    addBubble("assistant", "I could not process that request. Please try again.");
  } finally {
    setBusy(false);
    updateModeUI();
  }
});

messageInputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composerEl.requestSubmit();
  }
});

modeSelectEl.addEventListener("change", () => {
  updateModeUI();
});

presetSelectEl.addEventListener("change", () => {
  applyPresetSelection();
});

streamToggleEl.addEventListener("change", () => {
  if (modeSelectEl.value === "chat") {
    modeHintEl.textContent = `Current mode: V1 Chat. Streaming ${streamToggleEl.checked ? "on" : "off"}.`;
  }
});

updateStatus();
updateModeUI();
loadWebsitePresets();
