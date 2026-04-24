const state = {
  sessionId: null,
  profile: null,
  capabilities: null,
  isBusy: false,
  lastAssistantMessage: "",
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
const labWebsiteUrl = document.getElementById("labWebsiteUrl");
const labAllowedDomains = document.getElementById("labAllowedDomains");
const labDomainHint = document.getElementById("labDomainHint");
const labCurrentPage = document.getElementById("labCurrentPage");
const labRagContext = document.getElementById("labRagContext");
const indexWebsiteBtn = document.getElementById("indexWebsiteBtn");
const runMatrixBtn = document.getElementById("runMatrixBtn");
const matrixReportEl = document.getElementById("matrixReport");
const matrixTableWrap = document.getElementById("matrixTableWrap");
const matrixTableBody = document.getElementById("matrixTableBody");
const clearChatBtn = document.getElementById("clearChatBtn");
const copyLastBtn = document.getElementById("copyLastBtn");
const exportChatBtn = document.getElementById("exportChatBtn");
const authChip = document.getElementById("authChip");
const adapterChip = document.getElementById("adapterChip");
const v2Chip = document.getElementById("v2Chip");
const quickPromptsEl = document.getElementById("quickPrompts");
const stepAuth = document.getElementById("stepAuth");
const stepContext = document.getElementById("stepContext");
const stepRun = document.getElementById("stepRun");
const stepReview = document.getElementById("stepReview");

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

function updateStatusStrip() {
  const isLoggedIn = Boolean(state.profile);
  authChip.textContent = isLoggedIn
    ? `Auth: ${state.profile.role} (${state.profile.user_id})`
    : "Auth: signed out";

  const adapter = state.capabilities?.adapter_mode || "unknown";
  adapterChip.textContent = `Adapter: ${adapter}`;

  const v2Enabled = state.capabilities?.v2_enabled;
  const provider = state.capabilities?.v2_research_provider || "n/a";
  v2Chip.textContent = `V2: ${v2Enabled ? "on" : "off"} (${provider})`;
}

function updateStepper() {
  const hasAuth = Boolean(state.profile);
  const hasContext = Boolean((labWebsiteUrl?.value || "").trim()) && Boolean((labRagContext?.value || "").trim());
  const hasRun = messagesEl.querySelectorAll(".bubble.user").length > 0;
  const hasReview = messagesEl.querySelectorAll(".bubble.assistant").length > 1;

  const steps = [
    [stepAuth, hasAuth],
    [stepContext, hasAuth && hasContext],
    [stepRun, hasAuth && hasRun],
    [stepReview, hasAuth && hasReview],
  ];
  steps.forEach(([el, done]) => {
    if (!el) return;
    el.classList.toggle("done", Boolean(done));
  });
}

function setBusy(flag) {
  state.isBusy = Boolean(flag);
  const disabled = state.isBusy;
  [loginBtn, logoutBtn, sendSampleBtn, sendAdminSampleBtn, sendResearchSampleBtn, clearChatBtn, copyLastBtn, exportChatBtn].forEach((el) => {
    el.disabled = disabled;
  });
  chatForm.querySelectorAll("button").forEach((btn) => {
    btn.disabled = disabled;
  });
  messageInput.disabled = disabled;
  modeSelect.disabled = disabled;
}

function resetMessages() {
  messagesEl.innerHTML = "";
  addBubble("assistant", "Assistant ready. Login and send a message. Use mode switch for V2 research.");
  state.lastAssistantMessage = "";
  updateStepper();
}

function readTranscript() {
  const rows = [];
  const bubbles = messagesEl.querySelectorAll(".bubble");
  bubbles.forEach((bubble) => {
    const role = bubble.classList.contains("user") ? "User" : "Assistant";
    rows.push(`[${role}] ${bubble.textContent || ""}`);
  });
  return rows.join("\n\n");
}

function parseAllowedDomains(raw) {
  return String(raw || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildWebsiteContextPayload() {
  return {
    website_url: labWebsiteUrl.value.trim() || null,
    allowed_domains: parseAllowedDomains(labAllowedDomains.value),
    domain_type_hint: labDomainHint.value.trim() || null,
    domain_type: labDomainHint.value.trim() || null,
    current_page: labCurrentPage.value.trim() || null,
    current_page_context: "Current page for website-bound testing.",
    site_metadata: "Website metadata supplied from frontend testing lab.",
    navigation_context: "Dashboard, Budgets, Transactions, Goals, Help",
    product_service_context: "Budget planner, expense tracker, savings goals",
    rag_context: labRagContext.value.trim() || null,
  };
}

function renderMatrixTable(rows) {
  matrixTableBody.innerHTML = "";
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const values = [row.provider, row.scenario, String(row.status), row.intent, row.mode, row.source];
    values.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value;
      tr.appendChild(td);
    });

    const resultTd = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = row.pass ? "badge pass" : "badge fail";
    badge.textContent = row.pass ? "PASS" : "FAIL";
    resultTd.appendChild(badge);
    tr.appendChild(resultTd);
    matrixTableBody.appendChild(tr);
  });
}

function addBubble(role, text) {
  const item = document.createElement("article");
  item.className = `bubble ${role}`;
  item.textContent = text;
  messagesEl.appendChild(item);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  updateStepper();
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
  updateStatusStrip();
  updateStepper();
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

async function patchTenantSettings(partial) {
  if (!state.profile || state.profile.role !== "admin") {
    throw new Error("Only admin can update runtime settings.");
  }
  const response = await fetch("/v1/admin/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ tenant_id: state.profile.tenant_id, ...partial }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const error = new Error(err?.error?.message || `Failed to patch settings (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function indexWebsiteContext() {
  if (!state.profile || state.profile.role !== "admin") {
    throw new Error("Only admin can index website content.");
  }
  const context = buildWebsiteContextPayload();
  const response = await fetch("/v1/admin/website/index", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      tenant_id: state.profile.tenant_id,
      website_url: context.website_url,
      allowed_domains: context.allowed_domains,
      max_pages: 6,
      max_depth: 1,
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const error = new Error(err?.error?.message || `Website indexing failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
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
  updateStatusStrip();
  updateStepper();
}

async function logout() {
  await fetch("/v1/auth/logout", { method: "POST", credentials: "include" });
  state.profile = null;
  state.sessionId = null;
  updateTuningPanelVisibility();
  sessionView.textContent = "status: not logged in";
  updateStatusStrip();
  updateStepper();
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
    ...buildWebsiteContextPayload(),
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

  if (!state.profile) {
    const err = new Error("Login first.");
    err.status = 401;
    showErrorBanner(err);
    metaEl.textContent = "Login first.";
    return;
  }

  addBubble("user", text);
  messageInput.value = "";
  try {
    setBusy(true);
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
      const finalReply = reply.trim();
      addBubble("assistant", finalReply);
      state.lastAssistantMessage = finalReply;
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
      state.lastAssistantMessage = data.message.content || "";
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
  } finally {
    setBusy(false);
    messageInput.focus();
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

indexWebsiteBtn.addEventListener("click", async () => {
  try {
    clearErrorBanner();
    setBusy(true);
    const data = await indexWebsiteContext();
    metaEl.textContent = `Website index updated: pages=${data.pages_indexed}, chunks=${data.chunks_indexed}`;
  } catch (error) {
    showErrorBanner(error);
    metaEl.textContent = String(error.message || error);
  } finally {
    setBusy(false);
  }
});

runMatrixBtn.addEventListener("click", async () => {
  if (!state.profile) {
    showErrorBanner({ status: 401, message: "Login first to run matrix." });
    return;
  }
  if (state.profile.role !== "admin") {
    showErrorBanner({ status: 403, message: "Admin role is required to run matrix workflow." });
    return;
  }

  const scenarios = [
    ["informational", "What does this website help me do?"],
    ["recommendation", "What should I choose to improve my budget flow here?"],
    ["improvement", "How can I improve this website for better budget planning?"],
    ["audit", "Please audit this website budgeting journey."],
    ["troubleshooting", "The budget page is not working for me. How do I fix it?"],
    ["research", "Research similar websites patterns for improving budget dashboards."],
    ["out_of_scope", "What are the best football tactics this season?"],
  ];

  const providers = ["skeleton", "external"];
  const report = [];
  const rows = [];
  matrixReportEl.hidden = false;
  matrixTableWrap.hidden = false;
  matrixTableBody.innerHTML = "";
  try {
    clearErrorBanner();
    setBusy(true);
    await patchTenantSettings({ v2_enabled: true });
    await indexWebsiteContext();

    for (const provider of providers) {
      await patchTenantSettings({ v2_provider: provider });
      await loadCapabilities();
      report.push(`Provider: ${provider}`);
      for (const [label, query] of scenarios) {
        const payload = {
          tenant_id: state.profile.tenant_id,
          user_id: state.profile.user_id,
          query,
          sources: sourceUrlEl.value.trim() ? [{ url: sourceUrlEl.value.trim() }] : [],
          max_sources: 2,
          verbose: false,
          ...buildWebsiteContextPayload(),
        };
        const response = await fetch("/v2/research", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        const statusCode = Number(response.status || 0);
        const resultPass = statusCode === 200;
        rows.push({
          provider,
          scenario: label,
          status: statusCode,
          intent: data.intent || "n/a",
          mode: data.response_mode || "n/a",
          source: data.source_priority || "n/a",
          pass: resultPass,
        });
        report.push(
          `- ${label}: status=${response.status}, intent=${data.intent || "n/a"}, mode=${data.response_mode || "n/a"}, source=${data.source_priority || "n/a"}`,
        );
      }
      report.push("");
    }

    matrixReportEl.textContent = report.join("\n");
    renderMatrixTable(rows);
    const passCount = rows.filter((row) => row.pass).length;
    metaEl.textContent = `Scenario matrix completed. PASS ${passCount}/${rows.length}.`;
  } catch (error) {
    showErrorBanner(error);
    matrixReportEl.textContent = String(error.message || error);
    matrixTableBody.innerHTML = "";
    metaEl.textContent = String(error.message || error);
  } finally {
    setBusy(false);
  }
});

clearChatBtn.addEventListener("click", () => {
  resetMessages();
  metaEl.textContent = "Transcript cleared.";
});

copyLastBtn.addEventListener("click", async () => {
  try {
    if (!state.lastAssistantMessage) {
      metaEl.textContent = "No assistant reply to copy yet.";
      return;
    }
    await navigator.clipboard.writeText(state.lastAssistantMessage);
    metaEl.textContent = "Last assistant reply copied to clipboard.";
  } catch {
    metaEl.textContent = "Clipboard copy failed. Your browser may block clipboard access.";
  }
});

exportChatBtn.addEventListener("click", () => {
  const transcript = readTranscript();
  if (!transcript.trim()) {
    metaEl.textContent = "No transcript content to export.";
    return;
  }
  const blob = new Blob([transcript], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  a.href = url;
  a.download = `chat-transcript-${stamp}.txt`;
  a.click();
  URL.revokeObjectURL(url);
  metaEl.textContent = "Transcript exported.";
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

messageInput.addEventListener("input", () => {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 200)}px`;
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

if (quickPromptsEl) {
  quickPromptsEl.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const prompt = target.getAttribute("data-prompt");
    if (!prompt) return;
    messageInput.value = prompt;
    messageInput.focus();
  });
}

[labWebsiteUrl, labRagContext].forEach((el) => {
  if (!el) return;
  el.addEventListener("input", () => updateStepper());
});

loadCapabilities().catch(() => {
  state.capabilities = null;
});

updateTuningPanelVisibility();
updateStatusStrip();
updateStepper();
