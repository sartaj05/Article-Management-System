(function () {
  "use strict";
  const players = document.querySelectorAll("audio[data-audio-article]");
  if (!players.length) return;

  const csrfToken = () => {
    const cookie = document.cookie.split("; ").find((item) => item.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
  };
  const formatTime = (seconds) => {
    const value = Math.max(0, Math.floor(Number(seconds) || 0));
    return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
  };
  const readLocal = (key) => {
    try { return JSON.parse(window.localStorage.getItem(key) || "null"); } catch (_) { return null; }
  };
  const writeLocal = (key, value) => {
    try { window.localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* Storage can be disabled by the browser. */ }
  };

  players.forEach((audio) => {
    const articleId = audio.dataset.audioArticle;
    const mediaKey = audio.dataset.audioMedia || "";
    const key = `article-audio:${articleId}:${mediaKey}`;
    const status = audio.parentElement.querySelector(".article-audio-status");
    const useAccount = audio.dataset.audioAccount === "true";
    let lastSaved = 0;
    let savePending = false;
    let saveAgain = false;
    let sourceReady = false;
    let savedPosition = 0;

    const setStatus = (message) => { if (status) status.textContent = message; };
    const restorePosition = () => {
      if (!sourceReady || savedPosition < 5 || !Number.isFinite(audio.duration)) return;
      if (savedPosition >= audio.duration - 3) {
        setStatus("You finished listening to this audio.");
        return;
      }
      audio.currentTime = savedPosition;
      setStatus(`Resume from ${formatTime(savedPosition)}. Your place saves automatically.`);
    };
    const currentProgress = () => ({
      media_key: mediaKey,
      progress_percent: audio.duration > 0 ? Math.min(99, Math.floor((audio.currentTime / audio.duration) * 100)) : 0,
      position_seconds: Math.floor(audio.currentTime || 0),
      completed: false,
    });
    const save = async (force = false) => {
      if (!Number.isFinite(audio.currentTime) || (!force && audio.currentTime - lastSaved < 5)) return;
      lastSaved = audio.currentTime;
      const value = currentProgress();
      writeLocal(key, value);
      if (!useAccount) return;
      if (savePending) { saveAgain = true; return; }
      savePending = true;
      try {
        const response = await fetch(`/articles/api/v2/articles/${articleId}/progress/`, {
          method: "PATCH",
          credentials: "same-origin",
          headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
          body: JSON.stringify(value),
        });
        if (!response.ok) throw new Error("Progress sync failed.");
        setStatus(`Listening position saved at ${formatTime(value.position_seconds)}.`);
      } catch (_) {
        setStatus(`Listening position saved in this browser at ${formatTime(value.position_seconds)}.`);
      } finally {
        savePending = false;
        if (saveAgain) { saveAgain = false; save(true); }
      }
    };

    audio.addEventListener("loadedmetadata", () => { sourceReady = true; restorePosition(); });
    audio.addEventListener("timeupdate", () => save(false));
    audio.addEventListener("pause", () => save(true));
    audio.addEventListener("ended", async () => {
      const value = { media_key: mediaKey, progress_percent: 100, position_seconds: Math.floor(audio.duration || audio.currentTime || 0), completed: true };
      writeLocal(key, value);
      setStatus("Listening complete.");
      if (!useAccount) return;
      try {
        await fetch(`/articles/api/v2/articles/${articleId}/progress/`, {
          method: "PATCH", credentials: "same-origin",
          headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
          body: JSON.stringify(value),
        });
      } catch (_) { /* The local position remains available if account sync is offline. */ }
    });

    const local = readLocal(key);
    savedPosition = Number(local?.position_seconds) || 0;
    if (useAccount) {
      fetch(`/articles/api/v2/articles/${articleId}/progress/?media_key=${encodeURIComponent(mediaKey)}`, { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then((response) => response.ok ? response.json() : null)
        .then((progress) => {
          if (!progress) return;
          savedPosition = Number(progress.position_seconds) || savedPosition;
          restorePosition();
        })
        .catch(() => { if (savedPosition) setStatus(`Resume from ${formatTime(savedPosition)}. Your place saves in this browser.`); });
    } else if (savedPosition) {
      setStatus(`Resume from ${formatTime(savedPosition)}. Your place saves in this browser.`);
    }
  });
})();
