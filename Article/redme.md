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
        <button class="view-article" data-id="${article.id}">View</button>
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
  
 $(document).ready(function () {
    const token = localStorage.getItem("access_token");
    const $userName = $('#username');
    const $userEmail = $('#email');
    const $articleCount = $('#article-count');
    const $logoutLink = $("#logout-btn");
    const $userfullname = $('#userfullname');
    const $userrole = $('#role');

    // Logout functionality
    $logoutLink.off("click").click(function () {
        localStorage.removeItem("access_token");
        localStorage.removeItem("lastActivePage");
        alert("You have been logged out.");
        window.location.href = "/login/";
    });

    // Fetch article count
    function fetchArticleCount() {
        const user = JSON.parse(localStorage.getItem('user'));
        if (!token) {
            alert("Please log in to view article count.");
            return;
        }

        $.ajax({
            url: '/articles/api/articles/count/',
            type: 'GET',
            headers: { 'Authorization': 'Bearer ' + token },
            success: function (response) {
                $articleCount.text(response.article_count || 0);
                $userfullname.text(user.first_name + " " + user.last_name);
                $userName.text(user.username);
                $userrole.text(user.role);
                $userEmail.text(user.email);
            },
            error: function () {
                alert("Error fetching article count.");
            }
        });
    }
    // Fetch articles based on search and category
function fetchArticles(url, searchQuery = '', category = '', targetContainer, emptyMessageContainer, generateRowFunction) {
    $.ajax({
        url: url,
        type: 'GET',
        data: {
            search: searchQuery,
            category: category
        },
        success: function (data) {
            if (data.length === 0) {
                $(emptyMessageContainer).show();
                $(targetContainer).hide();
            } else {
                $(emptyMessageContainer).hide();
                $(targetContainer).show();
                $(targetContainer).html(''); // Clear previous data
                data.forEach(item => {
                    const row = generateRowFunction(item);
                    $(targetContainer).append(row);
                });
            }
        },
        error: function (xhr, status, error) {
            console.error("Error fetching articles:", error);
        }
    });
}

// Function to generate article rows for the table
function generateArticleRow(article) {
    return `
        <tr>
            <td>${article.id}</td>
            <td>${article.title}</td>
            <td>${article.category}</td>
            <td>${article.publish_date}</td>
            <td>${article.status}</td>
            <td><img src="${article.image_url}" alt="Article Image" width="50"></td>
            <td>
                <button class="edit-btn" data-id="${article.id}">Edit</button>
                <button class="delete-btn" data-id="${article.id}">Delete</button>
            </td>
        </tr>
    `;
}

// Event listener for category filter change
$("#category-filter").change(function () {
    const selectedCategory = $(this).val();
    const searchQuery = $("#search-bar").val(); // Get search query
    fetchArticles('/articles/search/', searchQuery, selectedCategory, "#article-list", "#no-articles-message", generateArticleRow);
});

// Event listener for search bar input change
$("#search-bar").keyup(function () {
    const searchQuery = $(this).val();
    const selectedCategory = $("#category-filter").val(); // Get selected category
    fetchArticles('/articles/search/', searchQuery, selectedCategory, "#article-list", "#no-articles-message", generateArticleRow);
});


    // Generic function to fetch articles
    function fetchArticles(endpoint, containerId, emptyMessageId, rowGeneratorCallback) {
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
            }
        });
    }

    // Generate article row
    function generateArticleRow(article, index) {
        const isPublished = article.status === "published";
        const isApproved = article.status === "approved";

        return `
            <tr>
                <td>${index + 1}</td>
                <td>${article.title}</td>
                <td>${article.category}</td>
                <td>${new Date(article.publish_date).toLocaleDateString()}</td>
                <td>${article.status}</td>
                <td><img src="${article.image || '/static/images/default.jpg'}" alt="Image" width="50"></td>
                <td>
                    <a href="/articles/edit/${article.id}/" class="edit-btn">Edit</a>
                    <button class="approve-btn" data-id="${article.id}" style="display: ${isApproved || isPublished ? 'none' : 'inline-block'};">Approve</button>
                    <button class="reject-btn" data-id="${article.id}">Reject</button>
                </td>
            </tr>
        `;
    }

    // Approve article functionality
    $(document).on("click", ".approve-btn", function () {
        const articleId = $(this).data("id");

        // Show a confirmation dialog before approving the article
        const confirmApproval = confirm("Are you sure you want to approve this article?");
        if (!confirmApproval) {
            return; // Exit if the user cancels the action
        }

        $.ajax({
            url: `/articles/approve/${articleId}/`,
            type: "PATCH", // Use PATCH as per your RESTful convention
            headers: { Authorization: "Bearer " + token },
            success: function (response) {
                if (response.status === "approved") {
                    alert("Article is already approved!");
                } else {
                    alert("Article approved successfully!");
                    // Refresh the list of articles after approval
                    fetchArticlesToApprove(); // Refresh pending approval articles
                    fetchArticles('/articles/search/', "#article-list", "#no-articles-message", generateArticleRow);
                    fetchArticles('/articles/approved/', "#approve-article-list", "#no-approve-articles-message", generateArticleRow); // Update the list of approved articles
                }
            },
            error: function (xhr) {
                if (xhr.status === 400 && xhr.responseJSON.detail === "Article already approved") {
                    alert("This article has already been approved.");
                } else {
                    console.error("Error approving article:", xhr.responseText);
                    alert("An error occurred while approving the article.");
                }
            }
        });
    });

 
$(document).on("click", ".reject-btn", function () {
    const articleId = $(this).data("id");

    $.ajax({
        url: `/articles/reject/${articleId}/`,
        type: "PATCH",
        headers: {
            Authorization: "Bearer " + token,
    
        },
        success: function () {
            alert("Article rejected!");
            fetchArticlesToApprove(); // Refresh the list after rejection
        },
        error: function (xhr) {
            console.error("Error rejecting article:", xhr.responseText);
            alert("An error occurred while rejecting the article.");
        }
    });
});
    // Fetch articles pending approval
    function fetchArticlesToApprove() {
        $.ajax({
            url: "/articles/pending_approval/",
            type: "GET",
            headers: { Authorization: "Bearer " + token },
            success: function (response) {
                const articles = response.articles;
                const approveArticleList = $("#approve-article-list");
                approveArticleList.empty();

                if (articles.length === 0) {
                    $("#no-approve-articles-message").show();
                } else {
                    $("#no-approve-articles-message").hide();
                    articles.forEach(function (article, index) {
                        if (article.status == "draft") {
                            const articleRow = `
                                <tr>
                                    <td>${index + 1}</td>
                                    <td>${article.title}</td>
                                    <td>${article.category}</td>
                                    <td>${new Date(article.publish_date).toLocaleDateString()}</td>
                                    <td><img src="${article.image || '/static/images/default.jpg'}" alt="Image" width="50"></td>
                                    <td>
                                        <a href="/articles/edit/${article.id}/" class="edit-btn">Edit</a>
                                        <button class="approve-btn" data-id="${article.id}">Approve</button>
                                        <button class="reject-btn" data-id="${article.id}">Reject</button>
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
            }
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
         document.getElementById('home-section').style.display=''
        showSection('home-section');
        
    });

    $("#manage-articles-btn").click(function (e) {
        e.preventDefault();
        document.getElementById('home-section').style.display='none'
        showSection('article-list-page');
        fetchArticles('/articles/search/', "#article-list", "#no-articles-message", generateArticleRow);
    });

    $("#approve-articles-btn").click(function (e) {
        e.preventDefault();
        document.getElementById('home-section').style.display='none'
        showSection('approve-articles-page');
        fetchArticlesToApprove();
    });

    $("#reject-articles-btn").click(function (e) {
        e.preventDefault();
        document.getElementById('home-section').style.display='none'
        showSection('reject-articles-page');
        fetchRejectedArticles();
    });

    $("#published-articles-btn").click(function (e) {
        e.preventDefault();
        document.getElementById('home-section').style.display='none'
        showSection('published-articles-page');
        fetchPublishedArticles();
    });
    

    // Initialize
    fetchArticleCount();
    
});
 

is my js code for dynamicli render for articles hare i am thinking thats  <button class="view-article" data-id="${article.id}">View</button> for click and render a pupup model and show the details for redarding these article i m not use for only use js can you render if user click any article than received full details regarding the article