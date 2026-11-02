(function () {
  "use strict";

  const articleId = document.body.dataset.articleId;
  const action = document.getElementById("ai-copilot-action");
  const runButton = document.getElementById("run-ai-copilot");
  const applyButton = document.getElementById("apply-ai-copilot");
  const result = document.getElementById("ai-copilot-result");
  const status = document.getElementById("ai-copilot-status");
  const metadata = document.getElementById("ai-copilot-meta");
  const feedbackBox = document.getElementById("ai-copilot-feedback");
  let latestRun = null;

  if (!articleId || !runButton) return;

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function setStatus(message, error) {
    status.textContent = message;
    status.dataset.state = error ? "error" : "ready";
  }

  function renderSuggestions(suggestions) {
    result.replaceChildren();
    Object.entries(suggestions).forEach(([field, value]) => {
      const wrapper = document.createElement("div");
      wrapper.className = "ai-copilot__suggestion";
      const heading = document.createElement("strong");
      heading.textContent = field.replaceAll("_", " ");
      wrapper.appendChild(heading);
      if (Array.isArray(value)) {
        const select = document.createElement("select");
        select.dataset.aiField = field;
        value.forEach((item, index) => {
          const option = document.createElement("option");
          option.value = String(index);
          option.textContent = item;
          select.appendChild(option);
        });
        wrapper.appendChild(select);
      } else {
        const text = document.createElement("p");
        text.textContent = value;
        wrapper.appendChild(text);
      }
      result.appendChild(wrapper);
    });
    result.hidden = false;
    applyButton.disabled = false;
    renderFeedback(Object.keys(suggestions).filter((field) => field !== "headlines"));
  }

  function renderFeedback(fields) {
    if (!feedbackBox) return;
    feedbackBox.replaceChildren();
    const label = document.createElement("label");
    label.textContent = "Feedback on";
    const select = document.createElement("select");
    fields.forEach((field) => { const option = document.createElement("option"); option.value = field; option.textContent = field.replaceAll("_", " "); select.appendChild(option); });
    const note = document.createElement("input");
    note.placeholder = "Optional correction or note";
    note.maxLength = 2000;
    const actions = document.createElement("div");
    ["accepted", "rejected", "corrected"].forEach((type) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "btn btn-secondary"; button.textContent = type;
      button.addEventListener("click", () => sendFeedback(type, select.value, note.value));
      actions.appendChild(button);
    });
    label.appendChild(select); feedbackBox.append(label, note, actions); feedbackBox.hidden = false;
  }

  async function sendFeedback(feedbackType, field, note) {
    if (!latestRun) return;
    try {
      const response = await fetch(`/articles/api/v2/assistant/runs/${latestRun.run_id}/feedback/`, {
        method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ feedback_type: feedbackType, field, corrected_value: feedbackType === "corrected" ? note : "", note }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Feedback could not be recorded.");
      setStatus(`Feedback recorded: ${data.feedback_type}.`);
    } catch (error) { setStatus(error.message, true); }
  }

  function syncArticleForm(suggestions) {
    Object.entries(suggestions).forEach(([field, value]) => {
      if (field === "headlines") return;
      const input = document.getElementById(field);
      if (input && typeof value === "string") input.value = value;
    });
  }

  runButton.addEventListener("click", async function () {
    runButton.disabled = true;
    applyButton.disabled = true;
    setStatus("Generating a reviewable draft…");
    try {
      const response = await fetch(`/articles/api/v2/articles/${articleId}/assistant/`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ action: action.value }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "The assistant could not generate suggestions.");
      latestRun = data;
      renderSuggestions(data.suggestions);
      metadata.textContent = `${data.provider}${data.model ? ` · ${data.model}` : ""} · ${data.latency_ms} ms · review before applying`;
      setStatus("Suggestions ready. Review every change before applying.");
    } catch (error) {
      setStatus(error.message, true);
      result.hidden = true;
    } finally {
      runButton.disabled = false;
    }
  });

  applyButton.addEventListener("click", async function () {
    if (!latestRun) return;
    const fields = Object.keys(latestRun.suggestions).filter((field) => field !== "headlines");
    const headlineSelect = result.querySelector('[data-ai-field="headlines"]');
    const payload = { fields };
    if (headlineSelect) {
      payload.fields = ["title"];
      payload.headline_index = Number(headlineSelect.value);
    }
    applyButton.disabled = true;
    setStatus("Applying the reviewed output…");
    try {
      const response = await fetch(`/articles/api/v2/assistant/runs/${latestRun.run_id}/apply/`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "The assistant output could not be applied.");
      syncArticleForm(latestRun.suggestions);
      setStatus(`Applied: ${data.applied.join(", ")}. The article draft is updated.`);
    } catch (error) {
      setStatus(error.message, true);
      applyButton.disabled = false;
    }
  });
})();
