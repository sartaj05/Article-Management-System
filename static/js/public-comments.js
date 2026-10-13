(function () {
  "use strict";
  const section = document.querySelector(".article-comments");
  const form = document.getElementById("public-comment-form");
  const list = document.getElementById("public-comments-list");
  const status = document.getElementById("comment-status");
  if (!section || !form) return;
  const articleId = section.dataset.articleId;
  const csrf = () => document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=").slice(1).join("=") || "";
  const request = async (url, options = {}) => { const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrf()) }, ...options }); const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || "Comment request failed."); return data; };
  form.addEventListener("submit", async (event) => { event.preventDefault(); const button = form.querySelector("button"); button.disabled = true; try { const comment = await request(`/articles/api/v2/articles/${articleId}/comments/`, { method: "POST", body: JSON.stringify({ content: form.elements.content.value }) }); const author = comment.author_name || "You"; const item = document.createElement("article"); item.className = "public-comment"; item.innerHTML = `<strong>${author}</strong><time>Just now</time><p></p>`; item.querySelector("p").textContent = comment.content; list.prepend(item); form.reset(); status.textContent = "Comment posted and sent through moderation."; } catch (error) { status.textContent = error.message; status.classList.add("is-error"); } finally { button.disabled = false; } });
  list.addEventListener("click", async (event) => { const button = event.target.closest("[data-report-comment]"); if (!button) return; const reason = window.prompt("Why are you reporting this comment?"); if (!reason) return; try { await request(`/articles/api/v2/comments/${button.dataset.reportComment}/report/`, { method: "POST", body: JSON.stringify({ reason }) }); button.textContent = "Reported"; button.disabled = true; } catch (error) { status.textContent = error.message; status.classList.add("is-error"); } });
})();
