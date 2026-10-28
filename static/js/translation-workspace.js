(function () {
  "use strict";
  const form = document.getElementById("translation-form");
  const list = document.getElementById("translation-list");
  const status = document.getElementById("translation-status");
  const role = document.querySelector(".feature-page")?.dataset.userRole;
  if (!form || !list) return;

  const csrf = () => document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=").slice(1).join("=") || "";
  const request = async (url, options = {}) => {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrf()) }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Translation request failed.");
    return data;
  };
  const escape = (value) => String(value ?? "").replace(/[&<>\"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[character]));
  const tokenize = (value) => String(value ?? "").split(/(\s+)/).filter(Boolean);
  const diffMarkup = (source, target) => {
    const left = tokenize(source); const right = tokenize(target); const matrix = Array.from({ length: left.length + 1 }, () => Array(right.length + 1).fill(0));
    for (let i = left.length - 1; i >= 0; i -= 1) for (let j = right.length - 1; j >= 0; j -= 1) matrix[i][j] = left[i] === right[j] ? matrix[i + 1][j + 1] + 1 : Math.max(matrix[i + 1][j], matrix[i][j + 1]);
    let i = 0; let j = 0; let sourceHtml = ""; let targetHtml = "";
    while (i < left.length || j < right.length) {
      if (i < left.length && j < right.length && left[i] === right[j]) { sourceHtml += escape(left[i]); targetHtml += escape(right[j]); i += 1; j += 1; }
      else if (j < right.length && (i === left.length || matrix[i][j + 1] >= matrix[i + 1][j])) { targetHtml += `<ins>${escape(right[j])}</ins>`; j += 1; }
      else { sourceHtml += `<del>${escape(left[i])}</del>`; i += 1; }
    }
    return { sourceHtml, targetHtml };
  };
  const fieldLabel = (field) => field.charAt(0).toUpperCase() + field.slice(1);

  async function showComparison(button) {
    const panel = document.getElementById(`translation-comparison-${button.dataset.id}`);
    if (panel.dataset.loaded === "true") { panel.hidden = !panel.hidden; return; }
    button.disabled = true; button.textContent = "Loading…";
    try {
      const payload = await request(`/articles/api/v2/translations/${button.dataset.id}/compare/`);
      panel.innerHTML = `<div class="translation-comparison__heading"><strong>Source vs ${escape(payload.translation.language_code)}</strong><span>${escape(payload.translation.status.replace("_", " "))}</span></div>${payload.fields.map((field) => { const diff = diffMarkup(payload.source[field], payload.translation[field]); return `<section class="translation-comparison__field"><h3>${fieldLabel(field)}</h3><div class="translation-comparison__columns"><div><small>Source</small><p>${diff.sourceHtml || "—"}</p></div><div><small>Translation</small><p>${diff.targetHtml || "—"}</p></div></div></section>`; }).join("")}<p class="translation-comparison__legend"><del>Removed from translation</del> <ins>Added to translation</ins></p>`;
      panel.dataset.loaded = "true"; panel.hidden = false; button.textContent = "Hide comparison";
    } catch (error) { status.textContent = error.message; button.textContent = "Compare source"; } finally { button.disabled = false; }
  }

  async function load() {
    const articleId = form.elements.article_id.value; if (!articleId) return;
    try {
      const items = await request(`/articles/api/v2/articles/${articleId}/translations/`);
      list.innerHTML = items.length ? items.map((item) => `<article class="translation-card"><div><span class="meta-pill">${escape(item.language_code)}</span><h2>${escape(item.title)}</h2><p>${escape(item.summary || item.content.slice(0, 160))}</p><div class="translation-comparison" id="translation-comparison-${item.id}" hidden></div></div><div class="translation-card__actions"><strong>${escape(item.status.replace("_", " "))}</strong><button class="button button--secondary button--small" data-compare="${item.id}">Compare source</button>${role === "Editor" || role === "Admin" ? `<button class="button button--small" data-review="publish" data-id="${item.id}">Publish</button><button class="button button--secondary button--small" data-review="return" data-id="${item.id}">Return</button>` : ""}</div></article>`).join("") : '<p class="account-empty">No translations for this article yet.</p>';
      status.textContent = `${items.length} translation(s) loaded.`;
    } catch (error) { status.textContent = error.message; status.classList.add("is-error"); }
  }

  form.addEventListener("submit", async (event) => { event.preventDefault(); const articleId = form.elements.article_id.value; const payload = Object.fromEntries(new FormData(form).entries()); delete payload.article_id; try { await request(`/articles/api/v2/articles/${articleId}/translations/`, { method: "POST", body: JSON.stringify(payload) }); await load(); status.textContent = "Translation saved as a draft."; } catch (error) { status.textContent = error.message; status.classList.add("is-error"); } });
  list.addEventListener("click", async (event) => {
    const compare = event.target.closest("[data-compare]");
    if (compare) { await showComparison(compare); return; }
    const review = event.target.closest("[data-review]"); if (!review) return; review.disabled = true;
    try { await request(`/articles/api/v2/translations/${review.dataset.id}/review/`, { method: "PATCH", body: JSON.stringify({ decision: review.dataset.review }) }); await load(); } catch (error) { review.disabled = false; status.textContent = error.message; }
  });
  form.elements.article_id.addEventListener("change", load);
})();
