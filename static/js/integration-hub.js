(function () {
  "use strict";
  const keyForm = document.getElementById("api-key-form");
  const webhookForm = document.getElementById("webhook-form");
  const keys = document.getElementById("api-keys");
  const webhooks = document.getElementById("webhooks");
  const deliveries = document.getElementById("deliveries");
  if (!keyForm || !webhookForm) return;
  const csrf = () => document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=").slice(1).join("=") || "";
  const request = async (url, options = {}) => {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrf()) }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Integration request failed.");
    return data;
  };
  const escape = (value) => String(value || "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
  async function load() {
    try {
      const filter = document.getElementById("delivery-status-filter")?.value;
      const deliveryUrl = filter ? `/developer/webhook-deliveries/?status=${encodeURIComponent(filter)}` : "/developer/webhook-deliveries/";
      const [keyItems, webhookItems, deliveryItems] = await Promise.all([request("/developer/keys/"), request("/developer/webhooks/"), request(deliveryUrl)]);
      keys.innerHTML = keyItems.length ? keyItems.map((item) => `<div class="integration-item"><span><strong>${escape(item.name)}</strong><small>${escape(item.prefix)}… · ${item.is_active ? "Active" : "Revoked"}</small></span><button class="button button--secondary button--small" data-revoke-key="${item.id}">Revoke</button></div>`).join("") : '<p class="account-empty">No API keys yet.</p>';
      webhooks.innerHTML = webhookItems.length ? webhookItems.map((item) => `<div class="integration-item"><span><strong>${escape(item.url)}</strong><small>${escape((item.events || []).join(", ") || "All events")}</small></span></div>`).join("") : '<p class="account-empty">No webhooks yet.</p>';
      deliveries.innerHTML = deliveryItems.length ? deliveryItems.map((item) => `<div class="integration-item"><span><strong>${escape(item.event_type)} · ${escape(item.status)}</strong><small>${escape(item.endpoint_url || "Webhook endpoint")} · attempts: ${item.attempts} · ${escape(item.last_error || "Delivered")}</small></span>${item.status === "failed" ? `<button class="button button--small" data-retry-delivery="${item.id}">Retry</button>` : ""}</div>`).join("") : '<p class="account-empty">No deliveries match this filter.</p>';
    } catch (error) { document.getElementById("delivery-status").textContent = error.message; }
  }
  keyForm.addEventListener("submit", async (event) => { event.preventDefault(); try { const data = Object.fromEntries(new FormData(keyForm).entries()); data.scopes = [...keyForm.querySelectorAll('input[name="scopes"]:checked')].map((input) => input.value); const result = await request("/developer/keys/", { method: "POST", body: JSON.stringify(data) }); document.getElementById("api-key-status").textContent = `Copy this key now — it will not be shown again: ${result.key}`; keyForm.reset(); await load(); } catch (error) { document.getElementById("api-key-status").textContent = error.message; } });
  webhookForm.addEventListener("submit", async (event) => { event.preventDefault(); try { const data = Object.fromEntries(new FormData(webhookForm).entries()); data.events = data.events.split(",").map((item) => item.trim()).filter(Boolean); await request("/developer/webhooks/", { method: "POST", body: JSON.stringify(data) }); webhookForm.reset(); document.getElementById("webhook-status").textContent = "Webhook endpoint added."; await load(); } catch (error) { document.getElementById("webhook-status").textContent = error.message; } });
  document.addEventListener("click", async (event) => { const revoke = event.target.closest("[data-revoke-key]"); const retry = event.target.closest("[data-retry-delivery]"); if (revoke) { revoke.disabled = true; await request(`/developer/keys/${revoke.dataset.revokeKey}/`, { method: "DELETE" }); await load(); } if (retry) { retry.disabled = true; await request("/developer/webhook-deliveries/", { method: "POST", body: JSON.stringify({ delivery_id: retry.dataset.retryDelivery }) }); await load(); } });
  document.getElementById("refresh-deliveries")?.addEventListener("click", load);
  document.getElementById("delivery-status-filter")?.addEventListener("change", load);
  load();
})();
