$(document).ready(function () {
  // Cache common DOM elements for performance
  const $homeLink = $("#home-link");
  const $createArticleLink = $("#create-article-link");
  const $articleListLink = $("#article-list-link");
  const $logoutLink = $("#logout-link");
  const $userName = $("#username");
  const $userEmail = $("#email");
  const $articleCount = $("#article-count");
  const $userfullname = $("#userfullname");
  const $userrole = $("#role");
  const $homeArticleList = $("#home-article-list");
  const $articleList = $("#article-list");
  const $articleForm = $("#article-form");
  const $articleDetailModal = $("#article-detail-modal");
  const $articleDetailContent = $("#article-detail-content");
  const $closeArticleModal = $("#close-article-modal"); // Close button for modal
  const $closeEditModal=$("#close-edit-modal")
  // Sidebar navigation logic
  $homeLink.click(function () {
    showPage("home-page");
  });
  $closeEditModal.click(function (){
    $("#editArticleModal").hide();
  })
  
  $createArticleLink.click(function () {
    showPage("create-article-page");
  });

  $articleListLink.click(function () {
    showPage("article-list-page");
    fetchArticles(); // Fetch and display articles
  });

  // Helper function to show pages
  function showPage(pageId) {
    $(".page").removeClass("active");
    $("#" + pageId).addClass("active");
    $("[data-page-link]").removeClass("is-active").removeAttr("aria-current");
    $("[data-page-link='" + pageId + "']").addClass("is-active").attr("aria-current", "page");
    localStorage.setItem("lastActivePage", pageId);
  }

  // Check if the user is logged in and update the sidebar
  function updateSidebar() {
    const token = localStorage.getItem("access_token");
    if (token) {
      $createArticleLink.show();
      $articleListLink.show();
      $logoutLink.show();
    } else {
      $createArticleLink.hide();
      $articleListLink.hide();
      $logoutLink.hide();
    }
  }

  // Initial sidebar update based on login status
  updateSidebar();

  // Check the last active page and activate it
  function activateLastPage() {
    const lastActivePage = localStorage.getItem("lastActivePage");
    if (lastActivePage) {
      showPage(lastActivePage);
    } else {
      showPage("home-page");
    }
  }

  // Activate the last active page on page load
  activateLastPage();
  if (localStorage.getItem("lastActivePage") === "article-list-page") fetchArticles();

  // Fetch user details to display on the dashboard
  function fetchUserDetails() {
    const token = localStorage.getItem("access_token");
    if (!token) {
      window.location.replace("/");
      return;
    }

    $.ajax({
      url: "/users/profile/",
      type: "GET",
      headers: { Authorization: "Bearer " + token },
      success: function (response) {
        $userName.text(response.username);
        $userEmail.text(response.email);
      },
      error: function () {
        alert("Error fetching user details.");
      },
    });
  }

  // Fetch total number of articles
  async function fetchArticleCount() {
    let token;
    try { token = await WorkspaceUI.ensureAccess(); }
    catch (error) { $articleCount.text("Sign in again"); return; }
    const user = JSON.parse(localStorage.getItem("user"));
    if (!token) {
      window.location.replace("/");
      return;
    }

    $.ajax({
      url: "/articles/api/articles/count/",
      type: "GET",
      headers: { Authorization: "Bearer " + token },
      success: function (response) {
        // console.log(response);
        $articleCount.text(response.article_count || 0);
        $userfullname.text([user.first_name, user.last_name].filter(Boolean).join(" ") || user.username);
        $userName.text(user.username);
        $userrole.text(user.role);
        $userEmail.text(user.email);
      },
      error: function (xhr) {
        if (xhr.status === 401 || xhr.status === 403) {
          ["access_token", "refresh_token", "user"].forEach((key) => localStorage.removeItem(key));
          window.location.replace("/");
          return;
        }
        $articleCount.text("—");
      },
    });
  }
  $articleForm.submit(async function (e) {
    e.preventDefault();

    if (!this.reportValidity()) return;
    let token;
    try { token = await WorkspaceUI.ensureAccess(); }
    catch (error) { alert(error.message); return; }
    const image = $('#image')[0].files[0];
    if (image && (!image.type.startsWith('image/') || image.size > 5 * 1024 * 1024)) {
      alert('Choose an image smaller than 5 MB.');
      return;
    }
    const formData = new FormData(this);
    for (const field of ['latitude', 'longitude', 'image']) {
      if (field === 'image' ? !image : !formData.get(field)) formData.delete(field);
    }
    formData.set('agreed_to_terms', 'true');
    const submit = this.querySelector('[type="submit"]');
    if (submit.disabled) return;
    submit.disabled = true;

    // Send AJAX request to create the article
    $.ajax({
      url: "/articles/api/articles/create/",
      type: "POST",
      data: formData,
      contentType: false,
      processData: false,
      headers: { Authorization: "Bearer " + token },
      success: function (response) {
        console.log("Article created successfully!");
        appendArticle(response);
        fetchArticles();
        fetchArticleCount();
        $articleForm[0].reset();
        showPage("article-list-page");
        // Show Success Modal
        showSuccessModal();
      },
      error: function (xhr) {
        alert(JSON.stringify(xhr.responseJSON || "Unable to save the draft."));
      },
      complete: function () { submit.disabled = false; },
    });
  });
  function showSuccessModal() {
    // Show the success message modal after successful article creation
    const successModal = $('#success-modal');
    successModal.fadeIn();
  
    // Auto-close modal after a few seconds
    setTimeout(function () {
      successModal.fadeOut();
    }, 2000);
  }

  window.onload = () => {
    fetchArticleCount();
  };

  

// Function to append the article to the table
function appendArticle(article) {
  article = Object.fromEntries(Object.entries(article).map(([key, value]) => [key, typeof value === "string" ? WorkflowUI.escapeHtml(value) : value]));
  const tableBody = $("#article-list");
  // Calculate Serial Number
  const srNo = tableBody.children("tr").length + 1;

  // Default values for missing article properties
  const title = article.title || "No Title";
  const category = article.category || "No Category";
  const publishDate = article.publish_date || "No Date";
  const status = article.workflow_status || article.status || "No Status";
  const statusKey = String(status).toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const imageUrl = article.image || "";
  const imageAlt = article.title || "Article Image"; // Use the article title as alt text
  const imageMarkup = imageUrl
    ? `<img src="${imageUrl}" alt="${imageAlt}" width="100" />`
    : '<span class="image-placeholder">No image</span>';

  // Create the article row using template literals
  const articleItem = `
    <tr id="article-${article.id}">
      <td>${srNo}</td>
      <td>${title}</td>
      <td>${category}</td>
      <td>${publishDate}</td>
      <td><div class="workflow-summary">${window.WorkflowUI ? WorkflowUI.statusBadge(status) : `<span class="status-badge status-badge--${statusKey}">${status}</span>`}${window.WorkflowUI ? WorkflowUI.timeline(article.workflow_steps) : ""}${article.rejection_reason ? `<span class="workflow-summary__reason">${article.rejection_reason}</span>` : ""}</div></td>
      <td>${imageMarkup}</td>
      <td class="table-actions">
       
 <button type="button" class="table-action table-action--view view-article" data-id="${article.id}" data-content='${article.content}'   data-id='${article.id}'data-tags='${article.tags}' data-email='${article.email}' data-subtitle='${article.subtitle}' data-title="${title}" data-category="${category}" data-publish-date="${publishDate}" data-status="${status}" data-image="${imageUrl}">View</button>
 ${status === "published" ? "" : `<button type="button" class="table-action table-action--edit edit-article" data-id="${article.id}">Edit</button>`}
        <button type="button" class="table-action table-action--delete delete-article" data-id="${article.id}">Delete</button>
        ${window.WorkflowUI ? WorkflowUI.actionButtons(article.available_actions, article.id) : ""}
      </td>
    </tr>
  `;

  // Append the article item to the table body
  tableBody.append(articleItem);

  // Optional: If no articles are present, display a "No Articles" message
  const noArticlesMessage = $('#no-articles-message');
  if (tableBody.children("tr").length > 0) {
    noArticlesMessage.hide();
  } else {
    noArticlesMessage.show();
  }
}

// Event listener for the "View" button click
$(document).on('click', '.view-article', function () {
  const article = $(this).data();
  // console.log(article)
  // Populate modal with article details
  $('#modal-id').text(`ID: ${article.id}`);
  $('#modal-title').text(`Title: ${article.title}`);
  $('#modal-subtitle').text(`SubTitle: ${article.subtitle}`);
  $('#modal-email').text(`Email: ${article.email}`);
  $('#modal-category').text(`Category: ${article.category}`);
  $('#modal-tags').text(`Tags: ${article.tags}`);
  $('#modal-publish-date').text(`Published Date: ${article.publishDate}`);
  $('#modal-status').text(`Status: ${article.status}`);
  const $modalImage = $('#modal-image');
  if (article.image) {
    $modalImage.attr('src', article.image).show();
  } else {
    $modalImage.removeAttr('src').hide();
  }
  $modalImage.off('error').on('error', function () {
    $(this).removeAttr('src').hide();
  });
  $('#modal-content').text(`Content: ${article.content}`);
  // Show the modal
  $('#article-modal').show();
});

// Event listener for the "Close" button click
$(document).on('click', '.modal-close, .close-modal', function () {
  $(this).closest('.modal').hide();
});

// Keep legacy dashboard modals consistent with the shared dialog behavior.
$(document).on('keydown', function (event) {
  if (event.key !== 'Escape') return;
  const $visibleModal = $('.modal:visible').last();
  if (!$visibleModal.length) return;
  event.preventDefault();
  $visibleModal.hide();
});

  

  // Load every page so older drafts remain available in the dashboard.
  async function fetchArticles() {
    try {
      const articles = await WorkflowUI.allArticles();
      $('#article-list').empty();
      articles.forEach(appendArticle);
      $('#no-articles-message').toggle(!articles.length);
      $('#search-bar').trigger('input');
    } catch (error) { alert(error.message); }
  }
  $('#search-bar').on('input', function () {
    const query = this.value.trim().toLowerCase();
    $('#article-list tr').each(function () {
      $(this).toggle($(this).text().toLowerCase().includes(query));
    });
  });
$(document).ready(function () {
    // Edit Article (Dynamic Content Event Delegation)
    $(document).on('click', '.edit-article', async function () {
      const articleId = $(this).data('id');
      
      if (!articleId) {
        console.error("Article ID is missing.");
        return;
      }
  
      let token;
      try { token = await WorkspaceUI.ensureAccess(); }
      catch (error) { alert(error.message); return; }
      if (!token) {
        alert("Please log in to edit the article.");
        return;
      }
  
      console.log(`Fetching article details for editing: ID ${articleId}`);
  
      // Fetch the article details via AJAX
      $.ajax({
        url: `/articles/api/v2/articles/${articleId}/`, // Ensure the correct API URL
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
        success: function (response) {
          if (response.id) {
            const article = response;
  
            // Populate the modal fields with article data
            $('#editTitle').val(article.title);
            $('#editSubtitle').val(article.subtitle);
            $('#editContent').val(article.content);
            $('#editCategory').val(article.category);
            $('#editTags').val(article.tags);  // Ensure it's an array of tags
            $('#editArticleId').val(article.id);  // Set hidden input for article ID
  
            // Open the modal to edit the article
            $('#editArticleModal').show();
          } else {
            alert("Article not found.");
          }
        },
        error: function (error) {
          alert("Error fetching article details.");
          console.error(error);
        },
      });
    });
  
    // Save Edited Article (Submit Changes)
    $('#edit-article-form').on('submit', async function (e) {
      e.preventDefault();
  
      const articleId = $('#editArticleId').val();
      let token;
      try { token = await WorkspaceUI.ensureAccess(); }
      catch (error) { alert(error.message); return; }
      if (!token) {
        alert("Please log in to save the article.");
        return;
      }
  
      // Collect updated article data from the form
      const updatedArticle = {
        title: $('#editTitle').val(),
        subtitle: $('#editSubtitle').val(),
        content: $('#editContent').val(),
        category: $('#editCategory').val(),
        tags: $('#editTags').val(),  // Convert tags string to an array
      };
  
      // Send the updated article data via AJAX
      $.ajax({
        url: `/articles/api/v2/articles/${articleId}/`,  // Ensure the update URL is correct
        method: "PATCH",  // Method to update the article
        headers: { Authorization: `Bearer ${token}` },
        data: updatedArticle,
        success: function (response) {
          $('#editArticleModal').hide();
          fetchArticles();
          $('#successModal').show();
        },
        error: function (err) {
          alert("Error updating article.");
          console.error(err);
        }
      });
       // Close the success modal
    $('.modal-close').on('click', function () {
      $('#successModal').hide();
    });
    });
  
   
  });
  

// Handle delete article action
$(document).on("click", ".delete-article", function () {
  const articleId = $(this).data("id");
  
  // Show the custom confirmation modal
  $('#confirmation-modal').fadeIn();
  
  // When the "Yes" button is clicked
  $('#confirm-delete').off('click').on('click', async function () {
    let token;
    try { token = await WorkspaceUI.ensureAccess(); }
    catch (error) { alert(error.message); return; }
    $.ajax({
      url: `/articles/delete/${articleId}/`,
      type: "DELETE",
      headers: { Authorization: "Bearer " + token },
      success: function () {
        console.log("Article deleted successfully!");
        $(`#article-${articleId}`).remove(); // Remove article from the list
        fetchArticleCount();
        $('#confirmation-modal').fadeOut();  // Close the modal
      },
      error: function () {
        alert("Error deleting article.");
        $('#confirmation-modal').fadeOut();  
      },
    });
  });
  $('#cancel-delete').off('click').on('click', function () {
    $('#confirmation-modal').fadeOut();  
  });
});

});
