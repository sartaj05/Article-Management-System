(function () {
  "use strict";
  const container = document.getElementById("articles-container");
  const status = document.getElementById("feed-status");
  const loadMore = document.getElementById("load-more");
  const search = document.getElementById("article-search");
  const sort = document.getElementById("article-sort");
  const navToggle = document.querySelector(".nav-toggle");
  const nav = document.getElementById("site-nav");
  const themeToggle = document.querySelector(".theme-toggle");
  const state = { mode: "featured", query: "", sort: "recent", next: null, loading: false };

  const escapeHTML = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  const formatDate = (value) => {
    if (!value) return "Recently published";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "Recently published" : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  };
  const articleLink = (article) => article.slug ? `/articles/read/${encodeURIComponent(article.slug)}/` : `/articles/articles/${encodeURIComponent(article.id)}/`;

  function renderCard(article) {
    const title = escapeHTML(article.title || "Untitled article");
    const summary = escapeHTML(article.summary || article.subtitle || "A new story from the Article Studio community.");
    const author = escapeHTML(article.author_name || article.author || "Article Studio");
    const category = escapeHTML(article.category || "General");
    const image = article.image ? `<img src="${escapeHTML(article.image)}" alt="" loading="lazy">` : `<div class="article-cover--placeholder"><i class="fa-solid fa-feather-pointed" aria-hidden="true"></i></div>`;
    return `<article class="article-card"><div class="article-cover">${image}</div><div class="article-info"><div class="article-meta"><span class="meta-pill"><i class="fa-regular fa-folder" aria-hidden="true"></i>${category}</span><span class="meta-pill"><i class="fa-regular fa-calendar" aria-hidden="true"></i>${formatDate(article.published_at || article.publish_date)}</span></div><h3>${title}</h3><p class="article-summary">${summary}</p><div class="article-meta"><span><i class="fa-regular fa-user" aria-hidden="true"></i> ${author}</span><span><i class="fa-regular fa-eye" aria-hidden="true"></i> ${Number(article.views_count || 0)}</span></div><a class="article-link" href="${articleLink(article)}">Read article <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a></div></article>`;
  }
  function setStatus(message, isError) { if (!status) return; status.textContent = message || ""; status.classList.toggle("is-error", Boolean(isError)); }
  function endpoint() { return state.query ? `/articles/api/v2/articles/search/?q=${encodeURIComponent(state.query)}&sort=${encodeURIComponent(state.sort)}` : `/articles/api/v2/discover/?mode=${encodeURIComponent(state.mode)}`; }

  async function loadArticles(url, append) {
    if (!container || state.loading || (!url && !state.next)) return;
    state.loading = true;
    if (!append) container.innerHTML = `<div class="loading-state">Loading the newsroom...</div>`;
    if (loadMore) loadMore.disabled = true;
    setStatus(append ? "Loading more stories..." : "");
    try {
      const response = await fetch(url || state.next, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const payload = await response.json();
      const articles = Array.isArray(payload) ? payload : (payload.results || []);
      if (!append) container.innerHTML = "";
      if (!articles.length && !append) container.innerHTML = `<div class="empty-state"><strong>No published articles yet.</strong><br>Try another search or check back soon.</div>`;
      else container.insertAdjacentHTML("beforeend", articles.map(renderCard).join(""));
      state.next = Array.isArray(payload) ? null : payload.next;
      if (loadMore) loadMore.hidden = !state.next;
      setStatus(articles.length ? `${articles.length} ${articles.length === 1 ? "story" : "stories"} ready to read.` : "");
    } catch (error) {
      if (!append) container.innerHTML = `<div class="empty-state"><strong>We couldn't load the newsroom.</strong><br>Please refresh and try again.</div>`;
      setStatus("The article feed is temporarily unavailable.", true);
      if (loadMore) loadMore.hidden = true;
      console.error("Article feed error:", error);
    } finally { state.loading = false; if (loadMore) loadMore.disabled = false; }
  }
  function resetFeed() { state.next = endpoint(); loadArticles(state.next, false); }

  if (container) {
    resetFeed();
    document.querySelectorAll("[data-feed-mode]").forEach((button) => button.addEventListener("click", () => {
      state.mode = button.dataset.feedMode; state.query = ""; if (search) search.value = "";
      document.querySelectorAll("[data-feed-mode]").forEach((item) => item.setAttribute("aria-pressed", String(item === button))); resetFeed();
    }));
    sort?.addEventListener("change", () => { state.sort = sort.value; resetFeed(); });
    let timer;
    search?.addEventListener("input", () => { window.clearTimeout(timer); timer = window.setTimeout(() => { state.query = search.value.trim(); resetFeed(); }, 300); });
    loadMore?.addEventListener("click", () => loadArticles(state.next, true));
  }
  navToggle?.addEventListener("click", () => { const open = nav?.classList.toggle("is-open"); navToggle.setAttribute("aria-expanded", String(Boolean(open))); });
  themeToggle?.addEventListener("click", () => { const dark = document.documentElement.classList.toggle("theme-dark"); window.localStorage.setItem("article-studio-theme", dark ? "dark" : "light"); });
  if (window.localStorage.getItem("article-studio-theme") === "dark") document.documentElement.classList.add("theme-dark");
})();
