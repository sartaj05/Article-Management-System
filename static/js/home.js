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
  const params = new URLSearchParams(window.location.search);
  let activeRequest;
  const state = { mode: params.get("mode") || "featured", query: params.get("q") || "", sort: params.get("sort") || "recent", next: null, loading: false };
  if (search) search.value = state.query;
  if (sort) sort.value = state.sort;

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
    const initial = escapeHTML(Array.from(String(article.title || "A"))[0].toUpperCase());
    const image = article.image ? `<img src="${escapeHTML(article.image)}" alt="" loading="lazy" decoding="async">` : `<div class="article-cover--placeholder" aria-hidden="true"><span class="cover-label">THE STUDIO / ${category}</span><span class="cover-letter">${initial}</span><span class="cover-caption"><span>✳</span> A perspective worth exploring.</span></div>`;
    const reason = article.recommendation_reason ? `<span class="recommendation-note"><i class="fa-solid fa-sparkles" aria-hidden="true"></i>${escapeHTML(article.recommendation_reason)}</span>` : "";
    return `<article class="article-card"><div class="article-cover">${image}</div><div class="article-info"><div class="article-meta"><span class="meta-pill"><i class="fa-regular fa-folder" aria-hidden="true"></i>${category}</span><span class="meta-pill"><i class="fa-regular fa-calendar" aria-hidden="true"></i>${formatDate(article.published_at || article.publish_date)}</span></div><h3>${title}</h3><p class="article-summary">${summary}</p>${reason}<div class="article-meta"><span><i class="fa-regular fa-user" aria-hidden="true"></i> ${author}</span><span><i class="fa-regular fa-eye" aria-hidden="true"></i> ${Number(article.views_count || 0)}</span></div><a class="article-link" href="${articleLink(article)}">Read article <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a></div></article>`;
  }
  function setStatus(message, isError) { if (!status) return; status.textContent = message || ""; status.classList.toggle("is-error", Boolean(isError)); }
  function endpoint() {
    const query = state.query ? `?q=${encodeURIComponent(state.query)}&sort=${encodeURIComponent(state.sort)}` : `?mode=${encodeURIComponent(state.mode)}`;
    if (state.mode === "for_you") return "/articles/api/v2/feed/for-you/?limit=20";
    return state.query ? `/articles/api/v2/articles/search/${query}` : `/articles/api/v2/discover/${query}`;
  }
  function syncUrl() {
    const query = new URLSearchParams();
    if (state.query) query.set("q", state.query);
    if (state.query && state.sort !== "recent") query.set("sort", state.sort);
    if (!state.query && state.mode !== "featured") query.set("mode", state.mode);
    const nextUrl = `${window.location.pathname}${query.toString() ? `?${query}` : ""}`;
    window.history.replaceState({}, "", nextUrl);
  }

  async function loadArticles(url, append) {
    if (!container || (append && state.loading) || (!url && !state.next)) return;
    activeRequest?.abort();
    const request = new AbortController();
    activeRequest = request;
    state.loading = true;
    container.setAttribute("aria-busy", "true");
    if (!append) container.innerHTML = `<div class="loading-state">Loading the newsroom...</div>`;
    if (loadMore && !append) loadMore.hidden = true;
    if (loadMore) loadMore.disabled = true;
    setStatus(append ? "Loading more stories..." : "");
    try {
      const response = await fetch(url || state.next, { headers: { Accept: "application/json" }, signal: request.signal });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const payload = await response.json();
      const articles = Array.isArray(payload) ? payload : (payload.results || []);
      if (!append) container.innerHTML = "";
      if (!articles.length && !append) container.innerHTML = `<div class="empty-state"><strong>${state.query ? "No stories match your search." : "Your reading room is waiting."}</strong><br>${state.query ? "Try a different keyword or select Featured to explore the newsroom." : "New perspectives will appear here as soon as they are published."}</div>`;
      else container.insertAdjacentHTML("beforeend", articles.map(renderCard).join(""));
      state.next = Array.isArray(payload) ? null : payload.next;
      if (loadMore) loadMore.hidden = !state.next;
      const count = container.querySelectorAll(".article-card").length;
      setStatus(count ? `${count} ${count === 1 ? "story" : "stories"} ready to read.` : "");
    } catch (error) {
      if (error.name === "AbortError") return;
      if (!append) container.innerHTML = `<div class="empty-state"><strong>We couldn't load the newsroom.</strong><br>Please refresh and try again.</div>`;
      setStatus("The article feed is temporarily unavailable.", true);
      if (loadMore) loadMore.hidden = true;
      console.error("Article feed error:", error);
    } finally {
      if (activeRequest === request) {
        state.loading = false;
        container.setAttribute("aria-busy", "false");
        if (loadMore) loadMore.disabled = false;
      }
    }
  }
  function resetFeed() {
    if (sort) sort.hidden = !state.query;
    state.next = endpoint();
    loadArticles(state.next, false);
  }

  if (container) {
    document.querySelectorAll("[data-feed-mode]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.feedMode === state.mode)));
    resetFeed();
    document.querySelectorAll("[data-feed-mode]").forEach((button) => button.addEventListener("click", () => {
      state.mode = button.dataset.feedMode; state.query = ""; if (search) search.value = "";
      document.querySelectorAll("[data-feed-mode]").forEach((item) => item.setAttribute("aria-pressed", String(item === button))); syncUrl(); resetFeed();
    }));
    sort?.addEventListener("change", () => { state.sort = sort.value; syncUrl(); resetFeed(); });
    let timer;
    search?.addEventListener("input", () => { window.clearTimeout(timer); timer = window.setTimeout(() => { state.query = search.value.trim(); syncUrl(); resetFeed(); }, 300); });
    loadMore?.addEventListener("click", () => loadArticles(state.next, true));
  }
  const readerInsights = document.getElementById("reader-insights-content");
  if (readerInsights) {
    fetch("/articles/api/v2/reader/insights/", { credentials: "same-origin", headers: { Accept: "application/json" } }).then((response) => response.ok ? response.json() : Promise.reject(new Error("Insights unavailable"))).then((data) => {
      const streak = data.streak || {};
      const topics = (data.recommendation_topics || []).slice(0, 3).map((item) => `<span class="insight-chip">${escapeHTML(item.value)}</span>`).join("");
      const resume = (data.resume_reading || [])[0];
      readerInsights.innerHTML = `<div class="insight-stat"><strong>${streak.current || 0}</strong><span>day streak</span></div><div class="insight-stat"><strong>${data.completed_articles || 0}</strong><span>stories completed</span></div>${resume ? `<a class="insight-resume" href="${articleLink(resume)}">Continue: ${escapeHTML(resume.title)} <span>${resume.progress_percent}%</span></a>` : `<div class="insight-topics"><span>Followed topics</span>${topics || "<em>Follow topics to shape your feed.</em>"}</div>`}`;
    }).catch(() => { readerInsights.innerHTML = "<span>Follow stories and return often to build a more useful feed.</span>"; });
  }
  navToggle?.addEventListener("click", () => { const open = nav?.classList.toggle("is-open"); navToggle.setAttribute("aria-expanded", String(Boolean(open))); });
  function closeNavigation() {
    nav?.classList.remove("is-open");
    navToggle?.setAttribute("aria-expanded", "false");
  }
  nav?.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeNavigation));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav?.classList.contains("is-open")) { closeNavigation(); navToggle?.focus(); }
  });
  nav?.querySelectorAll("a").forEach((link) => {
    const target = new URL(link.href);
    if (target.pathname === window.location.pathname && !target.hash) link.setAttribute("aria-current", "page");
  });
  themeToggle?.addEventListener("click", () => { const dark = document.documentElement.classList.toggle("theme-dark"); window.localStorage.setItem("article-studio-theme", dark ? "dark" : "light"); });
  if (window.localStorage.getItem("article-studio-theme") === "dark") document.documentElement.classList.add("theme-dark");
})();
