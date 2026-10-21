(function () {
  "use strict";
  const endpoint = "/articles/api/v2/reading-collections/";
  const collectionForm = document.getElementById("reading-collection-form");
  const collectionList = document.getElementById("reading-collection-list");
  const collectionStatus = document.getElementById("reading-collection-status");
  const addForm = document.getElementById("article-add-to-collection");

  const csrfToken = () => {
    const cookie = document.cookie.split("; ").find((item) => item.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
  };
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
  const request = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.method && options.method !== "GET" ? { "X-CSRFToken": csrfToken() } : {}) },
      ...options,
    });
    if (response.status === 204) return null;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "The collection request could not be completed.");
    return payload;
  };
  const setStatus = (element, message, isError = false) => {
    if (!element) return;
    element.textContent = message;
    element.classList.toggle("is-error", isError);
  };

  function renderCollections(collections) {
    if (!collectionList) return;
    collectionList.innerHTML = collections.length ? collections.map((collection) => `
      <article class="reading-collection" data-collection-id="${collection.id}">
        <header><div><h3>${escapeHtml(collection.name)}</h3>${collection.description ? `<p>${escapeHtml(collection.description)}</p>` : ""}<small>${collection.items.length} ${collection.items.length === 1 ? "story" : "stories"}</small></div>
          <button type="button" class="button button--secondary button--small" data-delete-collection="${collection.id}">Delete list</button></header>
        ${collection.items.length ? `<ul>${collection.items.map((item) => `<li><a href="${escapeHtml(item.url)}">${escapeHtml(item.title)}</a><span>${escapeHtml(item.category || "Story")}</span><button type="button" aria-label="Remove ${escapeHtml(item.title)}" data-remove-collection-article="${collection.id}" data-article-id="${item.article_id}">Remove</button></li>`).join("")}</ul>` : '<p class="reading-collection__empty">Save stories to this list from any article.</p>'}
      </article>`).join("") : '<p class="account-empty">No collections yet. Create one for the stories you want to keep.</p>';
  }

  async function loadCollections() {
    const collections = await request(endpoint);
    renderCollections(collections);
    if (addForm) {
      const select = addForm.elements.collection_id;
      select.innerHTML = collections.length
        ? `<option value="">Choose a collection</option>${collections.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("")}`
        : '<option value="">No collections yet</option>';
      select.disabled = !collections.length;
      addForm.querySelector("button[type='submit']").disabled = !collections.length;
      if (!collections.length) setStatus(addForm.querySelector(".account-status"), "Create a collection in account settings, then save this story.");
    }
    return collections;
  }

  collectionForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = collectionForm.querySelector("button[type='submit']");
    button.disabled = true;
    try {
      await request(endpoint, { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(collectionForm).entries())) });
      collectionForm.reset();
      setStatus(collectionStatus, "Collection created.");
      await loadCollections();
    } catch (error) { setStatus(collectionStatus, error.message, true); }
    finally { button.disabled = false; }
  });

  collectionList?.addEventListener("click", async (event) => {
    const deleteButton = event.target.closest("[data-delete-collection]");
    const removeButton = event.target.closest("[data-remove-collection-article]");
    const button = deleteButton || removeButton;
    if (!button || button.disabled) return;
    button.disabled = true;
    try {
      if (deleteButton) {
        await request(`${endpoint}${deleteButton.dataset.deleteCollection}/`, { method: "DELETE" });
        setStatus(collectionStatus, "Collection deleted.");
      } else {
        await request(`${endpoint}${removeButton.dataset.removeCollectionArticle}/articles/${removeButton.dataset.articleId}/`, { method: "DELETE" });
        setStatus(collectionStatus, "Story removed from collection.");
      }
      await loadCollections();
    } catch (error) { button.disabled = false; setStatus(collectionStatus, error.message, true); }
  });

  addForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = addForm.querySelector("button[type='submit']");
    button.disabled = true;
    try {
      const result = await request(`${endpoint}${addForm.elements.collection_id.value}/articles/`, { method: "POST", body: JSON.stringify({ article_id: addForm.dataset.articleId }) });
      setStatus(addForm.querySelector(".account-status"), result.added ? "Story saved to your collection." : "This story is already in that collection.");
    } catch (error) { setStatus(addForm.querySelector(".account-status"), error.message, true); }
    finally { button.disabled = false; }
  });

  if (collectionList || addForm) loadCollections().catch((error) => setStatus(collectionStatus || addForm?.querySelector(".account-status"), error.message, true));
})();
