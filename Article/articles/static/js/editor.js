$(document).ready(function () {
    const token = localStorage.getItem("access_token");
    const $userName = $('#username');
    const $userEmail = $('#email');
    const $articleCount = $('#article-count');
    const $userfullname = $('#userfullname');
    const $userrole = $('#role');

    if (!token) {
        alert("Authorization token is required");
        window.location.href = "/login/";
        return;
    }

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

    // Fetch user details
    function fetchUserDetails() {
        const user = JSON.parse(localStorage.getItem('user'));

        if (user) {
            $userfullname.text(user.first_name + " " + user.last_name);
            $userName.text(user.username);
            $userrole.text(user.role);
            $userEmail.text(user.email);
        } else {
            alert("User details not found.");
        }
    }

    // Fetch articles
    function fetchArticles(searchTerm = "") {
        $.ajax({
            url: "/articles/search/",
            type: "GET",
            data: { search: searchTerm },
            headers: {
                Authorization: "Bearer " + token,
            },
            success: function (response) {
                const articles = response.articles;
                const articleList = $("#article-list");
                articleList.empty();

                if (articles.length === 0) {
                    $("#no-articles-message").show();
                } else {
                    $("#no-articles-message").hide();
                    articles.forEach(function (article, index) {
                        if (article.status == "draft") {
                            const articleRow = `
                                <tr>
                                    <td>${index + 1}</td>
                                    <td>${article.title}</td>
                                    <td>${article.category}</td>
                                    <td>${new Date(article.publish_date).toLocaleDateString()}</td>
                                    <td>${article.status}</td>
                                    <td><img src="${article.image || '/static/images/default.jpg'}" alt="Image" width="50"></td>
                                    <td>
                                        <a href="/articles/edit/${article.id}/" class="edit-btn">Edit</a>
                                        <button class="approve-btn" data-id="${article.id}">Approve</button>
                                        <button class="reject-btn" data-id="${article.id}">Reject</button>
                                        <button class="publish-btn" data-id="${article.id}" style="display: none;">Publish</button>
                                    </td>
                                </tr>
                            `;
                            articleList.append(articleRow);
                        }
                    });
                }
            },
            error: function () {
                alert("Error fetching articles.");
            },
        });
    }

    // Fetch articles pending approval
    function fetchArticlesToApprove() {
        $.ajax({
            url: "/articles/search/", // Endpoint to fetch articles pending approval
            type: "GET",
            headers: {
                Authorization: "Bearer " + token,
            },
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
                                        <button class="publish-btn" data-id="${article.id}" style="display: none;">Publish</button>
                                    </td>
                                </tr>
                            `;
                            approveArticleList.append(articleRow);
                        }
                    });
                }
            },
            error: function () {
                alert("Error fetching articles pending approval.");
            },
        });
    }

    // Approve article
    function approveArticle(articleId) {
        $.ajax({
            url: "/articles/approve/" + articleId + "/",
            type: "PATCH",
            headers: {
                Authorization: "Bearer " + token,
            },
            success: function () {
                $("#approval-modal").show();
                setTimeout(function () {
                    $("#approval-modal").hide();
                }, 1000);
                fetchArticles(); // Refresh the approve articles list
            },
            error: function () {
                alert("Error approving article.");
            },
        });
    }

    // Reject article
    function rejectArticle(articleId) {
        $.ajax({
            url: "/articles/reject/" + articleId + "/",
            type: "PATCH",
            headers: {
                Authorization: "Bearer " + token,
            },
            success: function () {
                alert("Article rejected successfully.");
                window.location.href = "/articles/reject/"; // Redirect to published articles page
                fetchArticlesToApprove(); // Refresh the approve articles list
            },
            error: function () {
                alert("Error rejecting article.");
            },
        });
    }

    // Publish article
    function publishArticle(articleId) {
        $.ajax({
            url: "/articles/published/" + articleId + "/",
            type: "PATCH",
            headers: {
                Authorization: "Bearer " + token,
            },
            success: function () {
                alert("Article published successfully.");
                window.location.href = "/articles/published/"; // Redirect to published articles page
            },
            error: function () {
                alert("Error publishing article.");
            },
        });
    }

    // Handle approve button click
    $(document).on("click", ".approve-btn", function () {
        const articleId = $(this).data("id");
        approveArticle(articleId);
        $(this).siblings(".publish-btn").show(); // Show the "Publish" button after approval
    });

    // Handle reject button click
    $(document).on("click", ".reject-btn", function () {
        const articleId = $(this).data("id");
        rejectArticle(articleId);
    });

    // Handle publish button click
    $(document).on("click", ".publish-btn", function () {
        const articleId = $(this).data("id");
        publishArticle(articleId);
    });

    // Handle search input
    $("#search-bar").on("input", function () {
        const searchTerm = $(this).val();
        fetchArticles(searchTerm);
    });

    // Show home section when clicking "Home"
    $("#home-btn").click(function (e) {
        e.preventDefault();
        $("#home-section").show();
        $("#article-list-page").hide(); // Hide articles section
        $("#approve-articles-page").hide(); // Hide approve section
        fetchUserDetails(); // Fetch user details when clicking on "Home"
    });

    // Show article list when clicking "Manage Articles"
    $("#manage-articles-btn").click(function (e) {
        e.preventDefault();
        $("#home-section").hide(); // Hide home section
        $("#approve-articles-page").hide(); // Hide approve section
        $("#article-list-page").show(); // Show articles section
        sessionStorage.setItem("activePage", "manage-articles");
        fetchArticles(); // Fetch articles for display
    });

    // Show approve article list when clicking "Approve Articles"
    $("#approve-articles-btn").click(function (e) {
        e.preventDefault();
        $("#home-section").hide(); // Hide home section
        $("#article-list-page").hide(); // Hide articles section
        $("#approve-articles-page").show(); // Show approve section
        sessionStorage.setItem("activePage", "approve-articles");
        fetchArticlesToApprove(); // Fetch articles pending approval
    });

    // Show published articles when clicking "Published Articles" in sidebar
    $("#published-articles-btn").click(function (e) {
        e.preventDefault();
        window.location.href = "/articles/published/"; // Redirect to published articles page
    });

    // Logout functionality
    $("#logout-btn").click(function (e) {
        e.preventDefault();
        localStorage.removeItem("access_token");
        window.location.href = "/login/";
    });

    // Close modal when clicking on the close button
    $("#close-modal-btn").click(function () {
        $("#approval-modal").hide();
    });

    // Initialize the dashboard
    fetchUserDetails();
    const activePage = sessionStorage.getItem("activePage") || "home";
    if (activePage === "approve-articles") {
        $("#approve-articles-btn").click(); // Show approve articles page
    } else if (activePage === "manage-articles") {
        $("#manage-articles-btn").click(); // Show manage articles page
    } else {
        $("#home-btn").click(); // Show home page
    }
});
