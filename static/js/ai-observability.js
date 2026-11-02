(function () {
  "use strict";
  const status = document.getElementById("ai-observability-status");
  const metrics = document.getElementById("ai-metric-grid");
  const jobs = document.getElementById("ai-job-status");
  const providers = document.getElementById("ai-provider-status");
  const evaluation = document.getElementById("ai-evaluation-status");
  const refresh = document.getElementById("refresh-ai-observability");

  function metric(label, value, hint) {
    const card = document.createElement("article");
    card.className = "ai-metric";
    const eyebrow = document.createElement("small"); eyebrow.textContent = label;
    const number = document.createElement("strong"); number.textContent = value;
    const note = document.createElement("small"); note.textContent = hint;
    card.append(eyebrow, number, note); return card;
  }
  function list(target, values) {
    target.replaceChildren();
    const ul = document.createElement("ul");
    Object.entries(values || {}).forEach(([key, value]) => { const li = document.createElement("li"); li.textContent = `${key}: ${value}`; ul.appendChild(li); });
    target.appendChild(ul);
  }
  async function load() {
    status.textContent = "Loading AI telemetry…";
    const response = await fetch("/articles/api/v2/assistant/observability/", { credentials: "same-origin" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Telemetry unavailable.");
    metrics.replaceChildren(
      metric("Total tokens", data.usage.total_tokens, `${data.usage.events} usage events`),
      metric("Estimated cost", data.usage.estimated_cost, "Current period"),
      metric("Average latency", `${data.runs.average_latency_ms} ms`, `${data.runs.total} assistant runs`),
      metric("Fallback rate", data.runs.total ? `${Math.round((data.runs.fallbacks / data.runs.total) * 100)}%` : "0%", "Deterministic fallback usage"),
    );
    list(jobs, data.jobs.by_status);
    list(providers, data.runs.providers);
    evaluation.replaceChildren();
    const evaluationText = document.createElement("p");
    evaluationText.textContent = data.latest_evaluation ? `${data.latest_evaluation.score}% score · ${data.latest_evaluation.prompt_version}` : "No evaluation run yet.";
    evaluation.appendChild(evaluationText);
    status.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }
  async function refreshData() { try { await load(); } catch (error) { status.textContent = error.message; status.dataset.state = "error"; } }
  refresh.addEventListener("click", refreshData); refreshData();
})();
