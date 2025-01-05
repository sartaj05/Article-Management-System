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

  $logoutLink.click(function () {
    localStorage.removeItem("access_token");
    localStorage.removeItem("lastActivePage");
    updateSidebar();
    window.location.href = "/login/";
  });

  // Helper function to show pages
  function showPage(pageId) {
    $(".page").removeClass("active");
    $("#" + pageId).addClass("active");
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

  // Fetch user details to display on the dashboard
  function fetchUserDetails() {
    const token = localStorage.getItem("access_token");
    if (!token) {
      alert("Please log in to view user details.");
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
  function fetchArticleCount() {
    const token = localStorage.getItem("access_token");
    const user = JSON.parse(localStorage.getItem("user"));
    if (!token) {
      alert("Please log in to view article count.");
      return;
    }

    $.ajax({
      url: "/articles/api/articles/count/",
      type: "GET",
      headers: { Authorization: "Bearer " + token },
      success: function (response) {
        // console.log(response);
        $articleCount.text(response.article_count || 0);
        $userfullname.text(user.first_name + " " + user.last_name);
        $userName.text(user.username);
        $userrole.text(user.role);
        $userEmail.text(user.email);
      },
      error: function () {
        alert("Error fetching article count.");
      },
    });
  }
  $articleForm.submit(function (e) {
    e.preventDefault();

    // Get form field values
    const title = $("#title").val();
    const subtitle = $("#subtitle").val();
    const content = $("#content").val();
    const email = $("#email").val();
    const tags = $("#tags").val();
    const category = $("#category").val();
    const publishDate = $("#publish_date").val();
    const image = $("#image")[0].files[0];
    const token = localStorage.getItem("access_token");

    // Validation for the title field (min 5, max 50 characters)
    if (!title || title.length < 5 || title.length > 50) {
      alert("Title is required and must be between 5 and 50 characters.");
      return;
    }

    // Validation for the content field (min 10 characters)
    if (!content || content.length < 10) {
      alert("Content is required and must be at least 10 characters.");
      return;
    }

    if (!email || !validateEmail(email)) {
      $("#email-error").text("Please enter a valid email address");
      isValid = false;
    } else {
      $("#email-error").text("");
    }

    // Validation for subtitle (max 80 characters)
    if (subtitle.length > 80) {
      alert("Subtitle must be less than 80 characters.");
      return;
    }

    // Validation for tags (max 100 characters)
    if (tags.length > 100) {
      alert("Tags must be less than 100 characters.");
      return;
    }

    // Validation for category (must be selected)
    if (!category) {
      alert("Please select a category.");
      return;
    }

    // Validation for publish date (required and must be present or future date)
    if (!publishDate) {
      alert("Please select a publish date.");
      return;
    }

    const currentDate = new Date();
    currentDate.setHours(0, 0, 0, 0); // Set to midnight for comparison
    const selectedPublishDate = new Date(publishDate);

    if (selectedPublishDate < currentDate) {
      alert(
        "The publish date cannot be in the past. Please select a present or future date."
      );
      return;
    }

    // Validation for image (optional, but check file type and size)
    if (image && !image.type.startsWith("image/")) {
      alert("Please upload a valid image file.");
      return;
    }

    if (image && image.size > 5 * 1024 * 1024) {
      // 5MB max size
      alert("Image size must be less than 5MB.");
      return;
    }

    // Check if user is logged in
    if (!token) {
      alert("Please log in to create an article.");
      window.location.href = "/login/";
      return;
    }

    // Create FormData object to send the data
    const formData = new FormData(this);

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
      error: function () {
        alert("Error creating article.");
      },
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
  const tableBody = $("#article-list");
  // Calculate Serial Number
  const srNo = tableBody.children("tr").length + 1;

  // Default values for missing article properties
  const title = article.title || "No Title";
  const category = article.category || "No Category";
  const publishDate = article.publish_date || "No Date";
  const status = article.status || "No Status";
  const imageUrl = article.image || "/path/to/default-image.jpg"; // Default image if not provided
  const imageAlt = article.title || "Article Image"; // Use the article title as alt text

  // Create the article row using template literals
  const articleItem = `
    <tr id="article-${article.id}">
      <td>${srNo}</td>
      <td>${title}</td>
      <td>${category}</td>
      <td>${publishDate}</td>
      <td>${status}</td>
      <td><img src="${imageUrl}" alt="${imageAlt}" width="100" /> </td>
      <td>
       
 <button class="view-article" data-id="${article.id}" data-content='${article.content}'   data-id='${article.id}'data-tags='${article.tags}' data-email='${article.email}' data-subtitle='${article.subtitle}' data-title="${title}" data-category="${category}" data-publish-date="${publishDate}" data-status="${status}" data-image="${imageUrl}">View</button>        
 <button class="edit-article" data-id="${article.id}">Edit</button>
        <button class="delete-article" data-id="${article.id}">Delete</button>
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
  $('#modal-image').attr('src', article.image);
  $('#modal-content').text(`Content: ${article.content}`);
  // Show the modal
  $('#article-modal').show();
});

// Event listener for the "Close" button click
$(document).on('click', '#close-modal', function () {
  // Hide the modal
  $('#article-modal').hide();
});

  

  // Fetch and display articles
  function fetchArticles() {
    const token = localStorage.getItem("access_token");
    if (!token) {
      alert("Please log in to view articles.");
      return;
    }

    $.ajax({
      url: "/articles/search/", // Correct the URL if needed
      type: "GET",
      headers: { Authorization: "Bearer " + token },
      success: function (response) {
        const articles = response.articles || [];
        $("#article-list").empty();
        if (articles.length === 0) {
          $("#no-articles-message").show();
        } else {
          $("#no-articles-message").hide();
          articles.forEach(appendArticle);
        }
      },
      error: function () {
        alert("Error fetching articles.");
      },
    });
  }
$(document).ready(function () {
    // Edit Article (Dynamic Content Event Delegation)
    $(document).on('click', '.edit-article', function () {
      const articleId = $(this).data('id');
      
      if (!articleId) {
        console.error("Article ID is missing.");
        return;
      }
  
      const token = localStorage.getItem('access_token');
      if (!token) {
        alert("Please log in to edit the article.");
        return;
      }
  
      console.log(`Fetching article details for editing: ID ${articleId}`);
  
      // Fetch the article details via AJAX
      $.ajax({
        url: `/articles/edit/${articleId}/`, // Ensure the correct API URL
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
        success: function (response) {
          if (response.article) {
            const article = response.article;
  
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
    $('#edit-article-form').on('submit', function (e) {
      e.preventDefault();
  
      const articleId = $('#editArticleId').val();
      const token = localStorage.getItem('access_token');
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
        tags: $('#editTags').val().split(", "),  // Convert tags string to an array
      };
  
      // Send the updated article data via AJAX
      $.ajax({
        url: `/articles/edit/${articleId}/`,  // Ensure the update URL is correct
        method: "PATCH",  // Method to update the article
        headers: { Authorization: `Bearer ${token}` },
        data: updatedArticle,
        success: function (response) {
          if (response.success) {
            // Show success modal
            showSuccessModal();
            $('#editArticleModal').show();

            $('#editArticleModal').hide(); // Close the edit modal
            
            // Optionally reload the page to reflect changes
            setTimeout(function () {
              location.reload();
            }, 1000);  // Close after 2 seconds or you can hide the modal manually
          } else {
            console.log(" Updating article successfully.");
            $('#editArticleModal').hide();
          }
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
  $('#confirm-delete').click(function () {
    const token = localStorage.getItem("access_token");
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
  $('#cancel-delete').click(function () {
    $('#confirmation-modal').fadeOut();  
  });
});

});
