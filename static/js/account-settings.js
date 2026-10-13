(function () {
  "use strict";
  const privacyForm = document.getElementById("privacy-preferences-form");
  const privacyStatus = document.getElementById("privacy-status");
  const securityStatus = document.getElementById("security-status");
  const sessions = document.getElementById("security-sessions");
  const events = document.getElementById("security-events");
  const interestForm = document.getElementById("reader-interest-form");
  const interestList = document.getElementById("reader-interests");
  const interestStatus = document.getElementById("interest-status");
  const savedSearchForm = document.getElementById("saved-search-form");
  const savedSearchList = document.getElementById("saved-searches-list");
  const savedSearchStatus = document.getElementById("saved-search-status");

  if (!privacyForm || !sessions || !events) return;

  const csrfToken = () => {
    const cookie = document.cookie.split("; ").find((item) => item.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
  };
  const request = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json", "X-CSRFToken": csrfToken() } : {}) },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "The request could not be completed.");
    return payload;
  };
  const formatDate = (value) => value ? new Date(value).toLocaleString() : "Not available";
  const setStatus = (element, message, error = false) => { element.textContent = message; element.classList.toggle("is-error", error); };

  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[character]));

  function renderInterests(items) {
    if (!interestList) return;
    interestList.innerHTML = items.length ? items.map((item) => `
      <span class="interest-chip"><span><strong>${escapeHtml(item.value)}</strong><small>${escapeHtml(item.interest_type)}</small></span>
      <button type="button" aria-label="Stop following ${escapeHtml(item.value)}" data-remove-interest-type="${escapeHtml(item.interest_type)}" data-remove-interest-value="${escapeHtml(item.value)}"><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>
    </span>`).join("") : '<p class="account-empty">You are not following anything yet.</p>';
    interestList.querySelectorAll("[data-remove-interest-type]").forEach((button) => button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await request("/reader/interests/", { method: "DELETE", body: JSON.stringify({ interest_type: button.dataset.removeInterestType, value: button.dataset.removeInterestValue }) });
        await loadInterests();
        setStatus(interestStatus, "Follow removed.");
      } catch (error) { button.disabled = false; setStatus(interestStatus, error.message, true); }
    }));
  }

  async function loadInterests() {
    if (!interestList) return;
    try { renderInterests(await request("/reader/interests/")); }
    catch (error) { setStatus(interestStatus, error.message, true); }
  }

  function renderSavedSearches(items) {
    if (!savedSearchList) return;
    savedSearchList.innerHTML = items.length ? items.map((item) => `
      <article class="saved-search-item"><div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.query)} · ${escapeHtml(item.frequency)}</span></div>
      <button class="button button--secondary button--small" type="button" data-remove-search="${item.id}">Remove</button></article>`).join("") : '<p class="account-empty">No saved searches yet.</p>';
    savedSearchList.querySelectorAll("[data-remove-search]").forEach((button) => button.addEventListener("click", async () => {
      button.disabled = true;
      try { await request(`/alerts/saved-searches/${button.dataset.removeSearch}/`, { method: "DELETE" }); await loadSavedSearches(); setStatus(savedSearchStatus, "Saved search removed."); }
      catch (error) { button.disabled = false; setStatus(savedSearchStatus, error.message, true); }
    }));
  }

  async function loadSavedSearches() {
    if (!savedSearchList) return;
    try { renderSavedSearches(await request("/alerts/saved-searches/")); }
    catch (error) { setStatus(savedSearchStatus, error.message, true); }
  }

  function renderSessions(items) {
    sessions.innerHTML = items.length ? items.map((item) => `
      <article class="account-session ${item.is_active ? "is-active" : ""}">
        <div><strong>${item.is_active ? "Active session" : "Ended session"}</strong><small>${item.user_agent || "Unknown device"}</small><small>Last seen: ${formatDate(item.last_seen_at)}</small></div>
        ${item.is_active ? `<button class="button button--secondary button--small" type="button" data-revoke-session="${item.id}">Revoke</button>` : ""}
      </article>`).join("") : '<p class="account-empty">No security sessions recorded.</p>';
    sessions.querySelectorAll("[data-revoke-session]").forEach((button) => button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await request(`/api/security/sessions/${button.dataset.revokeSession}/`, { method: "DELETE" });
        setStatus(securityStatus, "Session revoked.");
        await loadSecurity();
      } catch (error) {
        button.disabled = false;
        setStatus(securityStatus, error.message, true);
      }
    }));
  }

  function renderEvents(items) {
    events.innerHTML = items.length ? items.slice(0, 8).map((item) => `<div class="account-event"><strong>${String(item.event_type || "Security event").replaceAll("_", " ")}</strong><span>${formatDate(item.created_at)}</span></div>`).join("") : '<p class="account-empty">No recent security events.</p>';
  }

  async function loadPrivacy() {
    try {
      const preferences = await request("/api/privacy/preferences/");
      ["analytics_enabled", "marketing_enabled", "functional_enabled"].forEach((field) => { privacyForm.elements[field].checked = Boolean(preferences[field]); });
    } catch (error) { setStatus(privacyStatus, error.message, true); }
  }

  async function loadSecurity() {
    try {
      const data = await request("/api/security/center/");
      renderSessions(data.sessions || []);
      renderEvents(data.events || []);
      setStatus(securityStatus, "Security activity is up to date.");
    } catch (error) { setStatus(securityStatus, error.message, true); }
  }

  privacyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = privacyForm.querySelector("button[type='submit']");
    button.disabled = true;
    try {
      await request("/api/privacy/preferences/", { method: "PATCH", body: JSON.stringify(Object.fromEntries(["analytics_enabled", "marketing_enabled", "functional_enabled"].map((field) => [field, privacyForm.elements[field].checked]))) });
      setStatus(privacyStatus, "Privacy preferences saved.");
    } catch (error) { setStatus(privacyStatus, error.message, true); }
    finally { button.disabled = false; }
  });

  interestForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = interestForm.querySelector("button[type='submit']");
    button.disabled = true;
    try {
      const formData = new FormData(interestForm);
      await request("/reader/interests/", { method: "POST", body: JSON.stringify(Object.fromEntries(formData.entries())) });
      interestForm.elements.value.value = "";
      await loadInterests();
      setStatus(interestStatus, "Follow preference saved.");
    } catch (error) { setStatus(interestStatus, error.message, true); }
    finally { button.disabled = false; }
  });

  savedSearchForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = savedSearchForm.querySelector("button[type='submit']");
    button.disabled = true;
    try { await request("/alerts/saved-searches/", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(savedSearchForm).entries())) }); savedSearchForm.reset(); await loadSavedSearches(); setStatus(savedSearchStatus, "Smart alert saved."); }
    catch (error) { setStatus(savedSearchStatus, error.message, true); }
    finally { button.disabled = false; }
  });

  loadPrivacy();
  loadSecurity();
  loadInterests();
  loadSavedSearches();
})();
