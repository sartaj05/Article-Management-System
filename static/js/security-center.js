(function () {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const status = $("#security-center-status");
  const csrfToken = () => {
    const cookie = document.cookie.split("; ").find((item) => item.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
  };
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character]));
  const formatDate = (value) => value ? new Date(value).toLocaleString() : "Not available";
  const setStatus = (element, message, error = false) => {
    if (!element) return;
    element.textContent = message || "";
    element.classList.toggle("is-error", error);
  };
  const request = async (url, options = {}) => {
    const method = String(options.method || "GET").toUpperCase();
    const mutating = !["GET", "HEAD", "OPTIONS"].includes(method);
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}), ...(mutating ? { "X-CSRFToken": csrfToken() } : {}) },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "The request could not be completed.");
    return payload;
  };
  const confirm = (message, options) => window.appConfirm ? window.appConfirm(message, options || {}) : Promise.resolve(window.confirm(message));
  const copyValue = async (value, message) => {
    try {
      await navigator.clipboard.writeText(value);
      setStatus(status, message || "Copied to clipboard.");
    } catch (error) {
      setStatus(status, "Copy failed. Select and copy the value manually.", true);
    }
  };

  function renderSessions(items) {
    const target = $("#security-sessions");
    if (!target) return;
    target.innerHTML = items.length ? items.map((item) => `
      <article class="security-list__item ${item.is_active ? "is-active" : ""}">
        <div><strong>${item.is_active ? "Active session" : "Ended session"}</strong><span>${escapeHtml(item.user_agent || "Unknown device")}</span><small>${escapeHtml(item.ip_address || "Unknown IP")} · Last seen ${formatDate(item.last_seen_at)}</small></div>
        ${item.is_active ? `<button class="button button--secondary button--small" type="button" data-revoke-session="${item.id}">Revoke</button>` : `<span class="security-badge security-badge--neutral">Ended</span>`}
      </article>`).join("") : '<p class="security-empty">No security sessions recorded.</p>';
    target.querySelectorAll("[data-revoke-session]").forEach((button) => button.addEventListener("click", async () => {
      const shouldRevoke = await confirm("Revoke this session? The device will need to sign in again.", { title: "Revoke session" });
      if (!shouldRevoke) return;
      button.disabled = true;
      try { await request(`/security/sessions/${button.dataset.revokeSession}/`, { method: "DELETE" }); await loadSecurity(); setStatus(status, "Session revoked."); }
      catch (error) { button.disabled = false; setStatus(status, error.message, true); }
    }));
  }

  function renderEvents(items) {
    const target = $("#security-events");
    if (!target) return;
    target.innerHTML = items.length ? items.slice(0, 10).map((item) => `<article class="security-list__item"><div><strong>${escapeHtml(String(item.event_type || "Security event").replaceAll("_", " "))}</strong><small>${escapeHtml(item.ip_address || "Unknown IP")} · ${formatDate(item.created_at)}</small></div><span class="security-badge ${item.success ? "security-badge--success" : "security-badge--danger"}">${item.success ? "Success" : "Failed"}</span></article>`).join("") : '<p class="security-empty">No recent security events.</p>';
  }

  async function loadSecurity() {
    try {
      const data = await request("/security/center/");
      renderSessions(data.sessions || []);
      renderEvents(data.events || []);
    } catch (error) { setStatus(status, error.message, true); }
  }

  async function loadMfa() {
    try {
      const data = await request("/two-factor/");
      const badge = $("#mfa-badge");
      const state = $("#mfa-state");
      badge.textContent = data.enabled ? "Protected" : "Action needed";
      badge.className = `security-badge ${data.enabled ? "security-badge--success" : "security-badge--warning"}`;
      state.textContent = data.enabled ? "Authenticator-based MFA is protecting this account." : "MFA is not enabled. Set it up before sharing administrator access.";
      $("#mfa-setup").hidden = Boolean(data.enabled);
      $("#mfa-disable").hidden = !data.enabled;
      if (!data.enabled) {
        $("#mfa-secret").textContent = data.secret || data.otp_uri || "Use the authenticator setup URI returned by the server.";
      }
    } catch (error) { setStatus($("#mfa-state"), error.message, true); }
  }

  function renderKeys(items) {
    const target = $("#api-keys");
    if (!target) return;
    target.innerHTML = items.length ? `<div class="security-table__header"><span>Name</span><span>Scopes</span><span>Last used</span><span>Actions</span></div>${items.map((item) => `<article class="security-table__row ${item.is_active ? "" : "is-muted"}"><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.prefix)}••••</small></div><span>${(item.scopes || []).map(escapeHtml).join(", ")}</span><span>${formatDate(item.last_used_at)}</span><div class="security-table__actions">${item.is_active ? `<button class="button button--secondary button--small" data-rotate-key="${item.id}" type="button">Rotate</button><button class="button button--danger button--small" data-revoke-key="${item.id}" type="button">Revoke</button>` : '<span class="security-badge security-badge--neutral">Revoked</span>'}</div></article>`).join("")}` : '<p class="security-empty">No API keys have been created.</p>';
    target.querySelectorAll("[data-rotate-key]").forEach((button) => button.addEventListener("click", async () => {
      if (!await confirm("Rotating this key immediately invalidates its current value.", { title: "Rotate API key" })) return;
      button.disabled = true;
      try { const data = await request(`/developer/keys/${button.dataset.rotateKey}/`, { method: "POST", body: "{}" }); showKey(data.key, "api-key"); await loadKeys(); }
      catch (error) { button.disabled = false; setStatus(status, error.message, true); }
    }));
    target.querySelectorAll("[data-revoke-key]").forEach((button) => button.addEventListener("click", async () => {
      if (!await confirm("Revoke this API key? Existing integrations will stop working.", { title: "Revoke API key" })) return;
      button.disabled = true;
      try { await request(`/developer/keys/${button.dataset.revokeKey}/`, { method: "DELETE" }); await loadKeys(); setStatus(status, "API key revoked."); }
      catch (error) { button.disabled = false; setStatus(status, error.message, true); }
    }));
  }

  async function loadKeys() {
    try { renderKeys(await request("/developer/keys/")); }
    catch (error) { setStatus(status, error.message, true); }
  }

  function showKey(value, kind) {
    const prefix = kind === "scim" ? "scim-token" : "api-key";
    const reveal = $(`#${prefix}-reveal`);
    const output = $(`#${prefix}-value`);
    if (!reveal || !output) return;
    output.textContent = value;
    reveal.hidden = false;
    output.dataset.copyValue = value;
    reveal.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderSso(items) {
    const target = $("#sso-providers");
    if (!target) return;
    target.innerHTML = items.length ? items.map((item) => `<article class="security-provider"><div><strong>${escapeHtml(item.provider.toUpperCase())}</strong><span>${escapeHtml(item.client_id || "No client ID")}</span><small>Default role: ${escapeHtml(item.default_role)} · Auto-provision: ${item.auto_provision ? "on" : "off"}</small></div><span class="security-badge ${item.is_enabled ? "security-badge--success" : "security-badge--neutral"}">${item.is_enabled ? "Enabled" : "Disabled"}</span></article>`).join("") : '<p class="security-empty">No SSO providers configured.</p>';
  }

  async function loadSso() {
    if (!$("#sso-form")) return;
    try { renderSso(await request("/sso/providers/")); }
    catch (error) { setStatus($("#sso-status"), error.message, true); }
  }

  async function loadWorkspaces() {
    const select = $("#scim-workspace");
    if (!select) return;
    try {
      const workspaces = await request("/workspaces/");
      select.innerHTML = workspaces.length ? workspaces.map((item) => `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.name)} (${escapeHtml(item.slug)})</option>`).join("") : '<option value="">No workspaces available</option>';
      await loadScimTokens();
    } catch (error) { setStatus($("#scim-status"), error.message, true); }
  }

  async function loadScimTokens() {
    const slug = $("#scim-workspace")?.value;
    const target = $("#scim-tokens");
    if (!slug || !target) { if (target) target.innerHTML = '<p class="security-empty">Select a workspace to view SCIM tokens.</p>'; return; }
    try {
      const items = await request(`/workspaces/${encodeURIComponent(slug)}/scim/tokens/`);
      target.innerHTML = items.length ? `<div class="security-table__header"><span>Token</span><span>Status</span><span>Expires</span><span>Last used</span></div>${items.map((item) => `<article class="security-table__row"><div><strong>${escapeHtml(item.prefix)}••••</strong></div><span class="security-badge ${item.is_active ? "security-badge--success" : "security-badge--neutral"}">${item.is_active ? "Active" : "Inactive"}</span><span>${formatDate(item.expires_at)}</span><span>${formatDate(item.last_used_at)}</span></article>`).join("")}` : '<p class="security-empty">No SCIM tokens have been created.</p>';
    } catch (error) { setStatus($("#scim-status"), error.message, true); }
  }

  $("#refresh-sessions")?.addEventListener("click", loadSecurity);
  $("#mfa-enable")?.addEventListener("click", async () => {
    const button = $("#mfa-enable"); button.disabled = true;
    try { const data = await request("/two-factor/", { method: "POST", body: JSON.stringify({ code: $("#mfa-setup-code").value.trim() }) }); $("#mfa-backup-codes").textContent = `Save these backup codes: ${(data.backup_codes || []).join(", ")}`; $("#mfa-backup-codes").hidden = false; await loadMfa(); setStatus(status, "MFA enabled successfully."); }
    catch (error) { setStatus($("#mfa-state"), error.message, true); }
    finally { button.disabled = false; }
  });
  $("#mfa-disable-button")?.addEventListener("click", async () => {
    if (!await confirm("Disable MFA for this account?", { title: "Disable MFA" })) return;
    const button = $("#mfa-disable-button"); button.disabled = true;
    try { await request("/two-factor/", { method: "PUT", body: JSON.stringify({ code: $("#mfa-disable-code").value.trim() }) }); await loadMfa(); setStatus(status, "MFA disabled."); }
    catch (error) { setStatus($("#mfa-state"), error.message, true); }
    finally { button.disabled = false; }
  });
  $("#api-key-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget; const button = form.querySelector("button"); button.disabled = true;
    try { const data = await request("/developer/keys/", { method: "POST", body: JSON.stringify({ name: form.elements.name.value.trim(), scopes: [form.elements.scopes.value] }) }); showKey(data.key, "api-key"); form.reset(); await loadKeys(); setStatus(status, "API key created. Copy it before leaving this page."); }
    catch (error) { setStatus(status, error.message, true); }
    finally { button.disabled = false; }
  });
  $("#copy-api-key")?.addEventListener("click", () => copyValue($("#api-key-value").dataset.copyValue || $("#api-key-value").textContent, "API key copied."));
  $("#copy-scim-token")?.addEventListener("click", () => copyValue($("#scim-token-value").dataset.copyValue || $("#scim-token-value").textContent, "SCIM token copied."));
  $("#sso-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget; const button = form.querySelector("button"); button.disabled = true;
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.auto_provision = form.elements.auto_provision.checked; payload.is_enabled = form.elements.is_enabled.checked;
    if (!payload.client_secret) delete payload.client_secret;
    try { await request("/sso/providers/", { method: "PATCH", body: JSON.stringify(payload) }); form.elements.client_secret.value = ""; await loadSso(); setStatus($("#sso-status"), "SSO provider saved."); }
    catch (error) { setStatus($("#sso-status"), error.message, true); }
    finally { button.disabled = false; }
  });
  $("#scim-workspace")?.addEventListener("change", loadScimTokens);
  $("#create-scim-token")?.addEventListener("click", async () => {
    const slug = $("#scim-workspace")?.value; if (!slug) return;
    const button = $("#create-scim-token"); button.disabled = true;
    try { const data = await request(`/workspaces/${encodeURIComponent(slug)}/scim/tokens/`, { method: "POST", body: "{}" }); showKey(data.token, "scim"); await loadScimTokens(); setStatus($("#scim-status"), "SCIM token created. Copy it before leaving this page."); }
    catch (error) { setStatus($("#scim-status"), error.message, true); }
    finally { button.disabled = false; }
  });

  loadSecurity();
  loadMfa();
  loadKeys();
  loadSso();
  loadWorkspaces();
}());
