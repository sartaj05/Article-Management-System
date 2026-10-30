(function () {
  "use strict";
  const list = document.getElementById("distribution-jobs");
  const status = document.getElementById("distribution-job-summary");
  const channelFilter = document.getElementById("distribution-channel");
  const statusFilter = document.getElementById("distribution-status");
  const alert = document.getElementById("distribution-failure-alert");
  const health = document.getElementById("distribution-provider-health");
  const csrf = () => document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=").slice(1).join("=") || "";
  if (!list || !status) return;
  const escape = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character]));
  const date = (value) => value ? new Date(value).toLocaleString() : "No activity yet";
  const request = async (url, options = {}) => {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json", ...(options.method ? { "X-CSRFToken": decodeURIComponent(csrf()) } : {}) }, ...options });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Distribution request failed.");
    return payload;
  };
  function renderHealth(items) {
    if (!health) return;
    health.innerHTML = (items || []).map((item) => `<article class="provider-health provider-health--${escape(item.status)}"><span class="provider-health__dot" aria-hidden="true"></span><div><strong>${escape(item.label)}</strong><small>${escape(item.status)} · ${item.delivered} delivered · ${item.failed} failed</small>${item.last_error ? `<small class="is-error">${escape(item.last_error)}</small>` : `<small>${escape(date(item.last_activity_at))}</small>`}</div></article>`).join("");
  }
  function renderMetrics(data) {
    const summary = data.summary || {};
    document.getElementById("distribution-total")?.replaceChildren(document.createTextNode(data.count ?? 0));
    document.getElementById("distribution-delivered")?.replaceChildren(document.createTextNode(summary.delivered || 0));
    document.getElementById("distribution-queued")?.replaceChildren(document.createTextNode(summary.queued || 0));
    document.getElementById("distribution-failed")?.replaceChildren(document.createTextNode(summary.failed || 0));
    renderHealth(data.provider_health);
    const failure = data.failure_alert || {};
    if (alert) { alert.hidden = !failure.active; alert.textContent = failure.message || ""; }
  }
  async function load() {
    try {
      const params = new URLSearchParams();
      if (channelFilter?.value) params.set("channel", channelFilter.value);
      if (statusFilter?.value) params.set("status", statusFilter.value);
      const data = await request(`/articles/api/v2/distribution-jobs/${params.toString() ? `?${params}` : ""}`);
      renderMetrics(data);
      status.textContent = `${data.count} job(s) · ${data.summary.delivered || 0} delivered · ${data.summary.queued || 0} queued · ${data.summary.awaiting_provider || 0} awaiting provider`;
      list.innerHTML = data.jobs.length ? data.jobs.map((job) => `<article class="integration-item"><span><strong>${escape(job.article)} · ${escape(job.channel)}</strong><small>${escape(job.status)} · attempts ${job.attempts} · ${escape(date(job.last_attempt_at || job.scheduled_for))}${job.last_error ? ` · ${escape(job.last_error)}` : ""}</small></span>${["failed", "awaiting_provider"].includes(job.status) ? `<button class="button button--small" data-retry-distribution="${job.id}">Retry</button>` : ""}</article>`).join("") : '<p class="account-empty">No distribution jobs match these filters.</p>';
    } catch (error) { status.textContent = error.message; }
  }
  async function retry(id) { await request(`/articles/api/v2/distribution-jobs/${id}/`, { method: "PATCH" }); }
  list.addEventListener("click", async (event) => { const button = event.target.closest("[data-retry-distribution]"); if (!button) return; button.disabled = true; try { await retry(button.dataset.retryDistribution); await load(); } catch (error) { status.textContent = error.message; button.disabled = false; } });
  document.getElementById("retry-failed-distribution")?.addEventListener("click", async (event) => { const button = event.currentTarget; button.disabled = true; try { const data = await request("/articles/api/v2/distribution-jobs/?status=failed"); await Promise.all(data.jobs.map((job) => retry(job.id))); await load(); } catch (error) { status.textContent = error.message; } finally { button.disabled = false; } });
  document.getElementById("refresh-distribution-jobs")?.addEventListener("click", load);
  channelFilter?.addEventListener("change", load); statusFilter?.addEventListener("change", load); load();
})();
