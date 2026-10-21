(function () {
  "use strict";
  const form = document.getElementById("newsletter-form");
  const list = document.getElementById("newsletter-editions");
  const status = document.getElementById("newsletter-status");
  const analyticsSummary = document.getElementById("newsletter-analytics-summary");
  const analyticsList = document.getElementById("newsletter-analytics-list");
  const analyticsStatus = document.getElementById("newsletter-analytics-status");
  if (!form) return;

  const csrf = () => document.cookie.split("; ").find((value) => value.startsWith("csrftoken="))?.split("=").slice(1).join("=") || "";
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
  const request = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrf()) } : {}) },
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Newsletter request failed.");
    return data;
  };
  const formatRevenue = (values) => values?.length ? values.map((value) => `${escape(value.currency)} ${Number(value.total).toFixed(2)}`).join(" · ") : "—";

  async function loadAnalytics() {
    if (!analyticsList) return;
    try {
      const data = await request("/api/newsletter/analytics/");
      const summary = data.summary || {};
      analyticsSummary.innerHTML = [
        ["Recipients", summary.recipients || 0], ["Unique clicks", summary.clicks || 0],
        ["Checkout starts", summary.checkouts || 0], ["Memberships", summary.conversions || 0],
        ["Click conversion", `${summary.conversion_rate || 0}%`], ["Recorded revenue", formatRevenue(summary.revenue_by_currency)],
      ].map(([label, value]) => `<article><span>${label}</span><strong>${escape(value)}</strong></article>`).join("");
      analyticsList.innerHTML = data.campaigns?.length ? data.campaigns.map((campaign) => `
        <article class="newsletter-performance-row">
          <div><strong>${escape(campaign.subject)}</strong><small>${escape(campaign.frequency)} · ${campaign.sent_at ? new Date(campaign.sent_at).toLocaleDateString() : "Sent"}</small></div>
          <span><strong>${campaign.recipient_count}</strong><small>recipients</small></span>
          <span><strong>${campaign.clicks}</strong><small>clicks</small></span>
          <span><strong>${campaign.checkouts}</strong><small>checkouts</small></span>
          <span><strong>${campaign.conversions}</strong><small>memberships · ${campaign.conversion_rate}%</small></span>
          <span><strong>${formatRevenue(campaign.revenue_by_currency)}</strong><small>recorded revenue</small></span>
        </article>`).join("") : '<p class="account-empty">Send a newsletter to begin measuring campaign performance.</p>';
      analyticsStatus.textContent = `${data.campaigns?.length || 0} sent campaign(s) in this report.`;
      analyticsStatus.classList.remove("is-error");
    } catch (error) {
      analyticsStatus.textContent = error.message;
      analyticsStatus.classList.add("is-error");
    }
  }

  async function loadCampaigns() {
    try {
      const items = await request("/api/newsletter/editions/");
      list.innerHTML = items.length ? items.map((item) => `
        <article class="newsletter-edition"><div><strong>${escape(item.subject)}</strong><span>${escape(item.frequency)} · ${escape(item.status)} · ${item.recipient_count} recipients</span></div>
        ${item.status === "draft" ? `<button class="button button--small" data-send="${item.id}">Send</button>` : ""}</article>`).join("") : '<p class="account-empty">No campaigns yet.</p>';
    } catch (error) { status.textContent = error.message; status.classList.add("is-error"); }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    button.disabled = true;
    try {
      await request("/api/newsletter/editions/", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form).entries())) });
      form.reset();
      status.textContent = "Draft saved.";
      status.classList.remove("is-error");
      await loadCampaigns();
    } catch (error) { status.textContent = error.message; status.classList.add("is-error"); }
    finally { button.disabled = false; }
  });

  list.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-send]");
    if (!button || !window.confirm("Send this newsletter to active subscribers?")) return;
    button.disabled = true;
    try {
      await request("/api/newsletter/editions/", { method: "POST", body: JSON.stringify({ action: "send", id: button.dataset.send }) });
      status.textContent = "Newsletter sent with a tracked membership link.";
      status.classList.remove("is-error");
      await Promise.all([loadCampaigns(), loadAnalytics()]);
    } catch (error) { button.disabled = false; status.textContent = error.message; status.classList.add("is-error"); }
  });

  Promise.all([loadCampaigns(), loadAnalytics()]);
})();
