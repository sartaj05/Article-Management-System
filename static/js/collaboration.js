(function () {
  "use strict";

  const articleId = document.body.dataset.articleId;
  const token = window.localStorage.getItem("access_token");
  const status = document.getElementById("collaboration-status");
  const collaboratorCount = document.getElementById("collaborator-count");
  const title = document.getElementById("title");
  const subtitle = document.getElementById("subtitle");
  const content = document.getElementById("content");
  if (!articleId || !token || !status || !title || !content) return;

  const autosaveUrl = `/articles/api/v2/articles/${articleId}/autosave/`;
  const collaborationUrl = `/articles/api/v2/articles/${articleId}/collaboration/`;
  let lastSavedAt = null;
  let saveTimer = null;
  let since = null;
  let socket = null;
  let socketReady = false;
  const offlineDraftKey = `article-studio-offline-draft-${articleId}`;

  const setStatus = (text, className = "") => {
    status.textContent = text;
    status.className = `collaboration-status${className ? ` ${className}` : ""}`;
  };

  const updateCollaborators = (people) => {
    if (!collaboratorCount) return;
    const currentUser = JSON.parse(window.localStorage.getItem("user") || "{}").username;
    const names = [...new Map((people || []).filter((person) => person.username !== currentUser).map((person) => [person.user_id, person.username])).values()];
    collaboratorCount.textContent = names.length ? `${names.length} collaborator${names.length > 1 ? "s" : ""}: ${names.join(", ")}` : "Only you";
  };

  async function saveDraft() {
    const payload = {
      title: title.value,
      subtitle: subtitle?.value || "",
      content: content.value,
      content_format: "plain",
      base_updated_at: lastSavedAt,
    };
    if (!payload.base_updated_at) delete payload.base_updated_at;
    setStatus("Saving draft…", "is-saving");
    try {
      const response = await fetch(autosaveUrl, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (response.status === 409) {
        setStatus("Draft changed elsewhere. Reload before saving.", "is-conflict");
        return;
      }
      if (!response.ok) throw new Error(data.detail || "Autosave failed.");
      lastSavedAt = data.updated_at;
      setStatus("All changes saved.", "is-saved");
    } catch (error) {
      window.localStorage.setItem(offlineDraftKey, JSON.stringify({ payload, queued_at: new Date().toISOString() }));
      setStatus("Offline: draft queued on this device.", "is-conflict");
    }
  }

  async function flushOfflineDraft() {
    const queued = window.localStorage.getItem(offlineDraftKey);
    if (!queued || !navigator.onLine) return;
    try {
      const { payload } = JSON.parse(queued);
      const response = await fetch(autosaveUrl, { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Queued draft could not be synced.");
      lastSavedAt = data.updated_at;
      window.localStorage.removeItem(offlineDraftKey);
      setStatus("Offline draft synced successfully.", "is-saved");
    } catch (_) { setStatus("Offline draft is waiting for a safe connection.", "is-conflict"); }
  }

  const scheduleSave = () => {
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(saveDraft, 900);
  };
  [title, subtitle, content].filter(Boolean).forEach((field) => field.addEventListener("input", scheduleSave));

  async function heartbeat() {
    if (socketReady) {
      socket.send(JSON.stringify({ type: "presence", status: "editing", section: document.activeElement?.id || "content", cursor_position: content.selectionStart || 0 }));
      return;
    }
    try {
      await fetch(collaborationUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: "editing", section: document.activeElement?.id || "content", cursor_position: content.selectionStart || 0 }),
      });
    } catch (_) {}
  }

  async function pollPresence() {
    if (socketReady) return;
    try {
      const query = since ? `?include_events=1&since=${encodeURIComponent(since)}` : "";
      const response = await fetch(`${collaborationUrl}${query}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) return;
      const data = await response.json();
      const currentUser = JSON.parse(window.localStorage.getItem("user") || "{}").username;
      const others = (data.presence || []).filter((person) => person.username !== currentUser);
      updateCollaborators(data.presence || []);
      if (others.length) setStatus(`${others.map((person) => person.username).join(", ")} is editing this article.`, "is-saving");
      if (data.events?.length) since = data.events[data.events.length - 1].created_at;
    } catch (_) {}
  }

  function connectSocket() {
    if (!window.WebSocket) return;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${window.location.host}/ws/articles/${articleId}/collaboration/`);
    socket.addEventListener("open", () => {
      socketReady = true;
      setStatus("Live collaboration connected.", "is-saved");
      heartbeat();
    });
    socket.addEventListener("message", (event) => {
      const data = JSON.parse(event.data || "{}");
      const person = data.presence;
      const currentUser = JSON.parse(window.localStorage.getItem("user") || "{}").username;
      if (person) {
        updateCollaborators([person]);
        if (person.username !== currentUser) setStatus(`${person.username} is editing this article.`, "is-saving");
      }
    });
    socket.addEventListener("close", () => {
      socketReady = false;
      setStatus("Live collaboration unavailable; using sync fallback.", "is-conflict");
    });
    socket.addEventListener("error", () => { socketReady = false; });
  }

  connectSocket();
  flushOfflineDraft();
  window.addEventListener("online", flushOfflineDraft);
  heartbeat();
  pollPresence();
  const heartbeatTimer = window.setInterval(heartbeat, 15000);
  const presenceTimer = window.setInterval(pollPresence, 10000);
  window.addEventListener("beforeunload", () => {
    window.clearInterval(heartbeatTimer);
    window.clearInterval(presenceTimer);
    if (socket && socket.readyState === WebSocket.OPEN) socket.close();
    fetch(collaborationUrl, { method: "DELETE", headers: { Authorization: `Bearer ${token}` }, keepalive: true });
  });
})();
