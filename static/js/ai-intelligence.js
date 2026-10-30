(function () {
  "use strict";
  const articleId = document.body.dataset.articleId;
  const button = document.getElementById("run-ai-intelligence");
  const result = document.getElementById("ai-intelligence-result");
  const status = document.getElementById("ai-intelligence-status");
  if (!articleId || !button) return;

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function list(title, items, formatter) {
    const section = document.createElement("div");
    section.className = "ai-copilot__suggestion";
    const heading = document.createElement("strong");
    heading.textContent = title;
    section.appendChild(heading);
    const list = document.createElement("ul");
    (items || []).forEach((item) => {
      const row = document.createElement("li");
      row.textContent = formatter(item);
      list.appendChild(row);
    });
    section.appendChild(list);
    return section;
  }

  button.addEventListener("click", async function () {
    button.disabled = true;
    status.textContent = "Comparing this story with newsroom coverage…";
    try {
      const response = await fetch(`/articles/api/v2/articles/${articleId}/intelligence/`, {
        method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrfToken() },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "The intelligence analysis failed.");
      const payload = data.payload;
      result.replaceChildren(
        list(`Duplicate risk: ${payload.duplicate_risk}`, payload.duplicate_candidates, (item) => `${item.title} · ${Math.round(item.score * 100)}% similarity`),
        list("Related coverage", payload.recommendations, (item) => `${item.title} · ${Math.round(item.score * 100)}% relevance`),
      );
      result.hidden = false;
      status.textContent = "Story context updated. Review matches before publishing.";
    } catch (error) {
      status.textContent = error.message;
      status.dataset.state = "error";
    } finally {
      button.disabled = false;
    }
  });
})();
