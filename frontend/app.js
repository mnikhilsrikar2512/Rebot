const state = {
  sessionId: null,
  profile: null,
  capabilities: null,
};

const tenantIdEl = document.getElementById("tenantId");
const emailEl = document.getElementById("email");
const passwordEl = document.getElementById("password");
const loginBtn = document.getElementById("loginBtn");
const logoutBtn = document.getElementById("logoutBtn");
const sessionView = document.getElementById("sessionView");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const messagesEl = document.getElementById("messages");
const metaEl = document.getElementById("meta");
const sendSampleBtn = document.getElementById("sendSampleBtn");
const sendAdminSampleBtn = document.getElementById("sendAdminSampleBtn");
const sendResearchSampleBtn = document.getElementById("sendResearchSampleBtn");
const errorBannerEl = document.getElementById("errorBanner");
const profileButtons = document.querySelectorAll("[data-profile]");
const modeSelect = document.getElementById("modeSelect");
const verboseToggle = document.getElementById("verboseToggle");
const sourceUrlEl = document.getElementById("sourceUrl");
const tuningPanel = document.getElementById("tuningPanel");
const tuneResponseStyle = document.getElementById("tuneResponseStyle");
const tuneMaxRecs = document.getElementById("tuneMaxRecs");
const tuneShowVerdict = document.getElementById("tuneShowVerdict");
const tuneV2Enabled = document.getElementById("tuneV2Enabled");
const tuneV2Provider = document.getElementById("tuneV2Provider");
const loadSettingsBtn = document.getElementById("loadSettingsBtn");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");

const PROFILES = {
  admin: { email: "admin@test.local", password: "Admin@123" },
  user2: { email: "john@test.local", password: "User@123" },
  user3: { email: "jane@test.local", password: "User@123" },
};

function clearErrorBanner() {
  errorBannerEl.hidden = true;
  errorBannerEl.textContent = "";
}

function showErrorBanner(error) {
  const status = Number(error?.status || 0);
  let prefix = "Request failed";
  if (status === 401 || status === 403) prefix = "Authorization error";
  else if (status === 404) prefix = "Not found";
  else if (status === 503) prefix = "Data source unavailable";
  else if (status >= 500) prefix = "Server error";
  const message = error?.message || "Unexpected error";
  errorBannerEl.textContent = `${prefix}: ${message}`;
  errorBannerEl.hidden = false;
}

function addBubble(role, text) {
  const item = document.createElement("article");
  item.className = `bubble ${role}`;
  item.textContent = text;
  messagesEl.appendChild(item);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function loadCapabilities() {
  const response = await fetch("/v1/capabilities");
  if (!response.ok) {
    state.capabilities = null;
    return;
  }
  state.capabilities = await response.json();
  const v2Enabled = Boolean(state.capabilities.v2_enabled);
  const researchOption = Array.from(modeSelect.options).find((opt) => opt.value === "research");
  if (researchOption) {
    researchOption.textContent = v2Enabled ? "V2 Research" : "V2 Research (global off)";
  }
}

function updateTuningPanelVisibility() {
  const isAdmin = state.profile?.role === "admin";
  tuningPanel.hidden = !isAdmin;
}

async function loadTenantSettings() {
  if (!state.profile || state.profile.role !== "admin") return;
  const tenantId = state.profile.tenant_id;
  const response = await fetch(`/v1/admin/settings?tenant_id=${encodeURIComponent(tenantId)}`, {
    credentials: "include",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const error = new Error(err?.error?.message || `Failed to load settings (${response.status})`);
    error.status = response.status;
    throw error;
  }
  const data = await response.json();
  tuneResponseStyle.value = data.response_style || "concise";
  tuneMaxRecs.value = String(data.max_recommendations ?? 3);
  tuneShowVerdict.checked = Boolean(data.show_verdict);
  tuneV2Enabled.checked = Boolean(data.v2_enabled);
  tuneV2Provider.value = data.v2_provider || "";
}

async function saveTenantSettings() {
  if (!state.profile || state.profile.role !== "admin") {
    throw new Error("Only admin can update runtime settings.");
  }
  const payload = {
    tenant_id: state.profile.tenant_id,
    response_style: tuneResponseStyle.value,
    max_recommendations: Number(tuneMaxRecs.value || 3),
    show_verdict: Boolean(tuneShowVerdict.checked),
    v2_enabled: Boolean(tuneV2Enabled.checked),
    v2_provider: tuneV2Provider.value || null,
  };
  const response = await fetch("/v1/admin/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const error = new Error(err?.error?.message || `Failed to save settings (${response.status})`);
    error.status = response.status;
    throw error;
  }
  await loadCapabilities();
}

async function login() {
  const payload = {
    tenant_id: tenantIdEl.value.trim(),
    email: emailEl.value.trim(),
    password: passwordEl.value,
  };
  const response = await fetch("/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const error = new Error(err?.error?.message || err.detail || `Login failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  const data = await response.json();
  state.profile = data;
  state.sessionId = null;
  updateTuningPanelVisibility();
  sessionView.textContent = `status: logged in as ${data.role} (${data.user_id})`;
  const v2Label = state.capabilities
    ? `V2: ${state.capabilities.v2_enabled ? "enabled" : "disabled"} (${state.capabilities.v2_research_provider || "n/a"})`
    : "V2: unknown";
  metaEl.textContent = `Logged in. Session will auto-create on first message. ${v2Label}`;
}

async function logout() {
  await fetch("/v1/auth/logout", { method: "POST", credentials: "include" });
  state.profile = null;
  state.sessionId = null;
  updateTuningPanelVisibility();
  sessionView.textContent = "status: not logged in";
}

async function sendChat(rawText) {
  if (!state.profile) {
    throw new Error("Login first.");
  }

  const payload = {
    session_id: state.sessionId,
    message: { role: "user", content: rawText },
    channel: "web",
    stream: false,
    strict_grounding: true,
  };

  const response = await fetch("/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const error = new Error(err?.error?.message || err.detail || `Chat request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }

  const data = await response.json();
  state.sessionId = data.session_id;
  return data;
}

async function sendResearch(rawText) {
  if (!state.profile) {
    throw new Error("Login first.");
  }

  const sourceUrl = sourceUrlEl.value.trim();
  const payload = {
    tenant_id: state.profile.tenant_id,
    user_id: state.profile.user_id,
    query: rawText,
    sources: sourceUrl ? [{ url: sourceUrl }] : [],
    max_sources: 3,
    verbose: Boolean(verboseToggle.checked),
  };

  const response = await fetch("/v2/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const error = new Error(err?.error?.message || err.detail || `Research request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

loginBtn.addEventListener("click", async () => {
  try {
    clearErrorBanner();
    await loadCapabilities();
    await login();
    await loadTenantSettings();
  } catch (error) {
    showErrorBanner(error);
    metaEl.textContent = String(error.message || error);
  }
});

logoutBtn.addEventListener("click", async () => {
  await logout();
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;

  addBubble("user", text);
  messageInput.value = "";
  try {
    clearErrorBanner();
    const mode = modeSelect.value;
    if (mode === "research") {
      const data = await sendResearch(text);
      const recommendations = Array.isArray(data.recommendations) ? data.recommendations : [];
      const reply = [
        data.summary || "No summary.",
        recommendations.length ? `\nActions:\n- ${recommendations.join("\n- ")}` : "",
        data.explanation ? `\n\nExplanation:\n${data.explanation}` : "",
      ].join("");
      addBubble("assistant", reply.trim());
      metaEl.textContent = JSON.stringify(
        {
          mode: "v2_research",
          request_id: data.request_id,
          trace_id: data.trace_id,
          confidence_score: data.confidence_score,
          warnings: data.warnings || [],
        },
        null,
        2,
      );
    } else {
      const data = await sendChat(text);
      addBubble("assistant", data.message.content);
      metaEl.textContent = JSON.stringify(
        {
          mode: "v1_chat",
          request_id: data.request_id,
          trace_id: data.trace_id,
          session_id: data.session_id,
          confidence_score: data.confidence_score,
          needs_clarification: data.needs_clarification,
          missing_data_fields: data.missing_data_fields,
          model: data.usage?.model,
          warnings: data.warnings || [],
        },
        null,
        2,
      );
    }
  } catch (error) {
    showErrorBanner(error);
    addBubble("assistant", `Error: ${error.message || error}`);
    metaEl.textContent = String(error.message || error);
  }
});

sendSampleBtn.addEventListener("click", async () => {
  const sample = "gve my acnt overveiw and hw to do bttr";
  messageInput.value = sample;
  chatForm.requestSubmit();
});

sendAdminSampleBtn.addEventListener("click", async () => {
  const sample = "give me overall platform overview for all users";
  messageInput.value = sample;
  chatForm.requestSubmit();
});

sendResearchSampleBtn.addEventListener("click", async () => {
  modeSelect.value = "research";
  const sample = "How can I improve monthly cash flow?";
  messageInput.value = sample;
  chatForm.requestSubmit();
});

loadSettingsBtn.addEventListener("click", async () => {
  try {
    clearErrorBanner();
    await loadTenantSettings();
    metaEl.textContent = "Runtime settings loaded.";
  } catch (error) {
    showErrorBanner(error);
    metaEl.textContent = String(error.message || error);
  }
});

saveSettingsBtn.addEventListener("click", async () => {
  try {
    clearErrorBanner();
    await saveTenantSettings();
    metaEl.textContent = "Runtime settings saved. New behavior applies to next requests.";
  } catch (error) {
    showErrorBanner(error);
    metaEl.textContent = String(error.message || error);
  }
});

profileButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const key = button.getAttribute("data-profile");
    const profile = PROFILES[key];
    if (!profile) return;
    emailEl.value = profile.email;
    passwordEl.value = profile.password;
    clearErrorBanner();
    metaEl.textContent = `Profile set: ${key}. Click Login.`;
  });
});

loadCapabilities().catch(() => {
  state.capabilities = null;
});

updateTuningPanelVisibility();
