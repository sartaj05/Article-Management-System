(function () {
  "use strict";

  const articleId = document.body.dataset.articleId;
  const token = window.localStorage.getItem("access_token");
  const status = document.getElementById("collaboration-status");
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

  const setStatus = (text, className = "") => {
    status.textContent = text;
    status.className = `collaboration-status${className ? ` ${className}` : ""}`;
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
      setStatus(error.message || "Autosave unavailable.", "is-conflict");
    }
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
      if (person && person.username !== currentUser) setStatus(`${person.username} is editing this article.`, "is-saving");
    });
    socket.addEventListener("close", () => {
      socketReady = false;
      setStatus("Live collaboration unavailable; using sync fallback.", "is-conflict");
    });
    socket.addEventListener("error", () => { socketReady = false; });
  }

  connectSocket();
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
