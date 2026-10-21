(function () {
  "use strict";
  const panel = document.querySelector("[data-article-follow]");
  if (!panel) return;

  const status = panel.querySelector(".article-follow__status");
  const csrfToken = () => {
    const cookie = document.cookie.split("; ").find((item) => item.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
  };
  const request = async (method, body) => {
    const response = await fetch("/reader/interests/", {
      method,
      credentials: "same-origin",
      headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Your follow preference could not be saved.");
    return payload;
  };
  const buttons = [...panel.querySelectorAll("[data-follow-type]")];
  const matchingInterest = (item, button) => item.interest_type === button.dataset.followType
    && String(item.value).toLocaleLowerCase() === button.dataset.followValue.toLocaleLowerCase();
  const updateButton = (button, followed) => {
    button.dataset.followed = String(followed);
    button.setAttribute("aria-pressed", String(followed));
    button.textContent = followed ? `Following ${button.dataset.followType === "author" ? "author" : button.dataset.followValue}` : `Follow ${button.dataset.followType === "author" ? "author" : button.dataset.followValue}`;
  };

  async function load() {
    try {
      const response = await fetch("/reader/interests/", { credentials: "same-origin", headers: { Accept: "application/json" } });
      const interests = await response.json();
      if (!response.ok) throw new Error(interests.detail || "Follow preferences are unavailable.");
      buttons.forEach((button) => updateButton(button, interests.some((item) => matchingInterest(item, button))));
    } catch (error) {
      status.textContent = error.message;
    }
  }

  panel.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-follow-type]");
    if (!button || button.disabled) return;
    button.disabled = true;
    status.textContent = "Saving your feed preference…";
    const payload = { interest_type: button.dataset.followType, value: button.dataset.followValue };
    try {
      const following = button.dataset.followed === "true";
      await request(following ? "DELETE" : "POST", payload);
      updateButton(button, !following);
      status.textContent = following ? "Follow removed." : "Added to your followed topics.";
    } catch (error) {
      status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });

  load();
})();
