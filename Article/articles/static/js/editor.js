$(document).ready(function () {
    const token = localStorage.getItem("access_token");
    const $userName = $("#username");
    const $userEmail = $("#email");
    const $articleCount = $("#article-count");
    const $userfullname = $("#userfullname");
    const $userrole = $("#role");
   

    $(document).ready(function () {
        const $logoutLink = $("#logout-btn");
    
        // Show the logout confirmation modal
        $logoutLink.on("click", function () {
            $("#logout-modal").css("display", "block");
        });
    
        // Confirm logout: Show success modal and handle redirection
        $("#confirm-logout").on("click", function () {
            // Perform logout actions
            localStorage.removeItem("access_token");
            localStorage.removeItem("lastActivePage");
    
            // Hide the logout modal and show the success modal
            $("#logout-modal").css("display", "none");
            $("#success-modal").css("display", "block");
    
            // Automatically hide success modal and redirect to login
            setTimeout(function () {
                $("#success-modal").css("display", "none");
                window.location.href = "/login/"; // Redirect to login page
            }, 1000);
        });
    
        // Cancel logout modal
        $("#cancel-logout").on("click", function () {
            $("#logout-modal").css("display", "none");
        });
    
        // Close success modal manually
        $("#close-success-modal").on("click", function () {
            $("#success-modal").css("display", "none");
        });
    
        // Close logout modal manually
        $("#close-logout-modal").on("click", function () {
            $("#logout-modal").css("display", "none");
        });
    });
    
    // Fetch article count
    function fetchArticleCount() {
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

    $(document).on("click", ".publish-btn", function () {
        const articleId = $(this).data("id");
    
        // Confirmation dialog
        if (!confirm("Are you sure you want to publish this article?")) {
            return;
        }
    
        $.ajax({
            url: `/articles/publish/${articleId}/`,
            type: "POST",
            headers: { Authorization: "Bearer " + token },
            success: function (response) {
                if (response.status === "published") {
                    alert(response.message || "Article published successfully!");
    
                    // Refresh published articles
                    showSection("published-articles-page");
                    fetchPublishedArticles();
                } else {
                    alert("Failed to publish the article. Please try again.");
                }
            },
            error: function (xhr) {
                if (xhr.status === 400 && xhr.responseJSON.error === "This article is already published.") {
                    alert(xhr.responseJSON.error);
                } else if (xhr.status === 403) {
                    alert("You do not have permission to publish this article.");
                } else {
                    alert("An error occurred while publishing the article.");
                    console.error("Error:", xhr.responseText);
                }
            },
        });
    });
    


   // Fetch published articles
function fetchPublishedArticles() {
    $.ajax({
        url: "/articles/published/", // Adjust endpoint to fetch only published articles
        type: "GET",
        headers: { Authorization: "Bearer " + token },
        success: function (response) {
            // const articles = response.articles;
            const articles = response.published_articles; // Adjust key if needed
            const publishedArticleList = $("#published-article-list");
            publishedArticleList.empty();
            
            if (articles.length === 0) {
                $("#no-published-articles-message").show();
            } else {
                $("#no-published-articles-message").hide();
                articles.forEach(function (article, index) {
                    const articleRow = `
                        <tr>
                            <td>${index + 1}</td>
                            <td>${article.title}</td>
                            <td>${article.category}</td>
                            <td>${new Date(article.publish_date).toLocaleDateString()}</td>
                            <td>${article.status}</td>
                            <td>
                                <button class="view-btn" 
                                    data-id="${article.id}" 
                                    data-content='${article.content}' 
                                    data-tags='${article.tags}' 
                                    data-email='${article.email}' 
                                    data-subtitle='${article.subtitle}' 
                                    data-title="${article.title}" 
                                    data-category="${article.category}" 
                                    data-publish-date="${article.publishDate}" 
                                    data-status="${article.status}" 
                                    data-image="${article.image}">
                                    View
                                </button>
                            </td>
                            <td><img src="${article.image ||
                                "/static/images/default.jpg"
                                }" alt="Image" width="50"></td>
                        </tr>
                    `;
                    publishedArticleList.append(articleRow);
                });
            }
        },
        error: function () {
            alert("Error fetching published articles.");
        },
    });
}

    $(document).ready(function () {
  // Generalized search function
  function applySearch(searchInputId, tableBodyId, noResultsMessageId) {
    $(`#${searchInputId}`).on("keyup", function () {
      const searchTerm = $(this).val().toLowerCase();
      let visibleRows = 0;

      $(`#${tableBodyId} tr`).each(function () {
        const rowText = $(this).text().toLowerCase();
        if (rowText.includes(searchTerm)) {
          $(this).show();
          visibleRows++;
        } else {
          $(this).hide();
        }
      });

      // Show or hide "no results" message
      if (visibleRows === 0) {
        $(`#${noResultsMessageId}`).show();
      } else {
        $(`#${noResultsMessageId}`).hide();
      }
    });
  }

  // Apply search for each section
  applySearch("search-bar", "article-list", "no-articles-message");
  applySearch("search-approve-bar", "approve-article-list", "no-approve-articles-message");
  applySearch("search-reject-bar", "reject-article-list", "no-reject-articles-message");
  applySearch("search-published-bar", "published-article-list", "no-published-articles-message");
});


    // Generic function  Manage Article table to fetch articles
    function fetchArticles(
        endpoint,
        containerId,
        emptyMessageId,
        rowGeneratorCallback
    ) {
        $.ajax({
            url: endpoint,
            type: "GET",
            headers: { Authorization: "Bearer " + token },
            success: function (response) {
                const articles = response.articles;
                const $container = $(containerId);
                $container.empty();

                if (articles.length === 0) {
                    $(emptyMessageId).show();
                } else {
                    $(emptyMessageId).hide();
                    articles.forEach((article, index) => {
                        const row = rowGeneratorCallback(article, index);
                        $container.append(row);
                    });
                }
            },
            error: function () {
                alert("Error fetching articles.");
            },
        });
    }
    function generateArticleRow(article, index) {
        const isPublished = article.status === "published";
        const isApproved = article.status === "Approved";
        const isRejected = article.status === "rejected";
        // const isPending = article.status === "draft";
    
        return `
            <tr>
                <td>${index + 1}</td>
                <td>${article.title}</td>
                <td>${article.category}</td>
                <td>${new Date(article.publish_date).toLocaleDateString()}</td>
                <td>${article.status}</td>
                <td><img src="${article.image || "/static/images/default.jpg"}" alt="Image" width="50"></td>
                <td>
                    <div class="button-container">
                        <button class="view-btn" 
                            data-id="${article.id}" 
                            data-content='${article.content}' 
                            data-tags='${article.tags}' 
                            data-email='${article.email}' 
                            data-subtitle='${article.subtitle}' 
                            data-title="${article.title}" 
                            data-category="${article.category}" 
                            data-publish-date="${article.publishDate}" 
                            data-status="${article.status}" 
                            data-image="${article.image}">
                            View
                        </button>
                        <button class="edit-btn" 
                            onclick="window.location.href='/articles/edit/${article.id}/'" 
                            style="display: ${isPublished || isApproved ? "none" : "inline-block"};">
                            Edit
                        </button>
                        <button class="approve-btn" 
                            data-id="${article.id}" 
                            style="display: ${isApproved || isPublished ? "none" : "inline-block"};">
                            Approve
                        </button>
                        <button class="publish-btn" 
                            data-id="${article.id}" 
                            style="display: ${isApproved ? "inline-block" : "none"};">
                            Publish
                        </button>
                        <button class="reject-btn" 
                            data-id="${article.id}" 
                            style="display: ${isPublished || isRejected ? "none" : "inline-block"};">
                            Reject
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }
    
    
    
    

    // Event listener for the "View" button click
    $(document).on("click", ".view-btn", function () {
        const article = $(this).data();
        console.log(article)
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
        $('#article-modal').show();
    });

    // Event listener for the "Close" button click
    $(document).on("click", "#close-modal", function () {
        $('#article-modal').hide();
    });

    // Approve article functionality
    $(document).on("click", ".approve-btn", function () {
        const articleId = $(this).data("id");

        const confirmApproval = confirm("Are you sure you want to approve this article?");
        if (!confirmApproval) {
            return;
        }

        $.ajax({
            url: `/articles/approve/${articleId}/`,
            type: "PATCH", 
            headers: { Authorization: "Bearer " + token },
            success: function (response) {
                let message = "Article approved successfully!";
                if (response.message === "This article is already approved.") {
                    message = "This article has already been approved.";
                }

                $('#modal-title').text("Approval Status");
                $('#modal-message').text(message);
                $('#approval-rejection-modal').show();
            },
            error: function (xhr) {
                const error = xhr.responseJSON.error;
                let message = "An error occurred while approving the article.";
                if (xhr.status === 400 && error === "This article is already approved.") {
                    message = "This article has already been approved.";
                }

                $('#modal-title').text("Approval Failed");
                $('#modal-message').text(message);
                $('#approval-rejection-modal').show();
            },
        });
    });

    // Reject article functionality
    $(document).on("click", ".reject-btn", function () {
        const articleId = $(this).data("id");

        if (!confirm("Are you sure you want to reject this article?")) {
            return;
        }

        $.ajax({
            url: `/articles/reject/${articleId}/`,
            type: "PATCH",
            headers: { Authorization: "Bearer " + token },
            success: function (response) {
                let message = response.message || "Article rejected successfully!";
                $('#modal-title').text("Rejection Status");
                $('#modal-message').text(message);
                $('#approval-rejection-modal').show();
                fetchArticlesToApprove(); 
            },
            error: function (xhr) {
                const error = xhr.responseJSON.error;
                let message = "An error occurred while rejecting the article.";
                if (xhr.status === 400) {
                    if (error === "This article has already been rejected.") {
                        message = "This article is already rejected.";
                    } else if (error === "This article has already been approved and cannot be rejected.") {
                        message = "This article is approved and cannot be rejected.";
                    }
                }

                $('#modal-title').text("Rejection Failed");
                $('#modal-message').text(message);
                $('#approval-rejection-modal').show();
            },
        });
    });

    // Close the modal when the close button is clicked
    $(document).on('click', '#modal-close-btn', function () {
        $('#approval-rejection-modal').hide();
    });



    // Fetch articles pending approval to approved article
    function fetchArticlesToApprove() {
        $.ajax({
            url: "/articles/search/",
            type: "GET",
            headers: { Authorization: "Bearer " + token },
            success: function (response) {
                const articles = response.articles;
                const approveArticleList = $("#approve-article-list");
                approveArticleList.empty();
                console.log(articles);
                if (articles.length === 0) {
                    $("#no-approve-articles-message").show();
                } else {
                    $("#no-approve-articles-message").hide();
                    articles.forEach(function (article, index) {
                        console.log(article);
                        if (article.status == "Approved") {
                            const articleRow = `
                                <tr>
                                    <td>${index + 1}</td>
                                    <td>${article.title}</td>
                                    <td>${article.category}</td>
                                    
                                    <td>${new Date(
                                article.publish_date
                            ).toLocaleDateString()}</td>
                                    <td><img src="${article.image ||
                                "/static/images/default.jpg"
                                }" alt="Image" width="50"></td>
                                <td>${article.status}</td>
                                    <td>
                                        <button class="publish-btn" data-id="${article.id
                                }">Published</button>
                                        <button class="reject-btn" data-id="${article.id
                                }">Reject</button>
                            <button class="view-btn" data-id="${article.id}" data-content='${article.content}' data-id='${article.id}'data-tags='${article.tags}' data-email='${article.email}' data-subtitle='${article.subtitle}' data-title="${article.title}" data-category="${article.category}" data-publish-date="${article.publishDate}" data-status="${article.status}" data-image="${article.image}">View</button>

                                    </td>
                                </tr>
                            `;
                            approveArticleList.append(articleRow);
                        }
                    });
                }
            },
            error: function () {
                alert("Error fetching articles for approval.");
            },
        });
    }
    // Fetch articles rejected
    function fetchRejectedArticles() {
        $.ajax({
            url: "/articles/search/",
            type: "GET",
            headers: { Authorization: "Bearer " + token },
            success: function (response) {
                const articles = response.articles;
                const rejectArticleList = $("#reject-article-list");
                rejectArticleList.empty();
                console.log(articles);
                if (articles.length === 0) {
                    $("#no-reject-articles-message").show();
                } else {
                    $("#no-reject-articles-message").hide();
                    articles.forEach(function (article, index) {
                        console.log(article);
                        if (article.status == "rejected") {
                            const articleRow = `
                            <tr>
                                <td>${index + 1}</td>
                                <td>${article.title}</td>
                                
                                <td>${article.category}</td>
                                <td>${new Date(
                                article.publish_date
                            ).toLocaleDateString()}</td>
                                <td><img src="${article.image || "/static/images/default.jpg"
                                }" alt="Image" width="50"></td>
                                <td>${article.status}</td>
                                <td> <button class="view-btn" data-id="${article.id}" data-content='${article.content}' data-id='${article.id}'data-tags='${article.tags}' data-email='${article.email}' data-subtitle='${article.subtitle}' data-title="${article.title}" data-category="${article.category}" data-publish-date="${article.publishDate}" data-status="${article.status}" data-image="${article.image}">View</button>
                                
                                </td>
                            </tr>
                        `;
                            rejectArticleList.append(articleRow);
                        }
                    });
                }
            },
            error: function () {
                alert("Error fetching rejected articles.");
            },
        });
    }

    // Navigation event listeners
    function showSection(sectionId) {
        $(".page").hide();
        $(`#${sectionId}`).show();
    }
    // Event listeners for navigation
    $("#home-btn").click(function (e) {
        e.preventDefault();
        document.getElementById("home-section").style.display = "";
        showSection("home-section");
    });

    $("#manage-articles-btn").click(function (e) {
        e.preventDefault();
        document.getElementById("home-section").style.display = "none";
        showSection("article-list-page");
        fetchArticles(
            "/articles/search/",
            "#article-list",
            "#no-articles-message",
            generateArticleRow
        );
    });

    $("#approve-articles-btn").click(function (e) {
        e.preventDefault();
        document.getElementById("home-section").style.display = "none";
        showSection("approve-articles-page");
        fetchArticlesToApprove();
    });

    $("#reject-articles-btn").click(function (e) {
        e.preventDefault();
        document.getElementById("home-section").style.display = "none";
        showSection("reject-articles-page");
        fetchRejectedArticles();
    });

    $("#published-articles-btn").click(function (e) {
        e.preventDefault();
        document.getElementById("home-section").style.display = "none";
        showSection("published-articles-page");
        fetchPublishedArticles();
    });

    // Initialize
    fetchArticleCount();
});
