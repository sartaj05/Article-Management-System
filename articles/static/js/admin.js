$(document).ready(function () {
    const token = localStorage.getItem('access_token');

    if (!token) {
        alert('Authorization token is required');
        window.location.href = '/login/';
        return;
    }

    // Common fetch function for articles
    function fetchArticles(filter = {}) {
        $.ajax({
            url: '/articles/search/',
            type: 'GET',
            headers: { 'Authorization': 'Bearer ' + token },
            data: filter,
            success: function (response) {
                const articles = response.articles;
                const articleList = $('#articles-list');
                articleList.empty();

                if (articles.length === 0) {
                    $("#no-articles-message").show();
                } else {
                    $("#no-articles-message").hide();
                    articles.forEach((article, index) => {
                        const articleRow = `
                            <tr>
                                <td>${index + 1}</td>
                                <td>${article.title}</td>
                                <td>${article.status}</td>
                                <td>${article.category}</td>
                                <td>${new Date(article.publish_date).toLocaleDateString()}</td>
                                <td><img src="${article.image || '/static/images/default.jpg'}" width="50"></td>
                                <td>
                                    <a href="/articles/edit/${article.id}/" class="edit-btn">Edit</a> |
                                    <button class="approve-btn" data-id="${article.id}">Approve</button> |
                                    <button class="delete-article-btn" data-id="${article.id}">Delete</button>
                                </td>
                            </tr>
                        `;
                        articleList.append(articleRow);
                    });
                }
            },
            error: function () {
                alert("Error fetching articles.");
            },
        });
    }

    // Fetch and manage users
    function fetchUsers() {
        $.ajax({
            url: '/users/',
            type: 'GET',
            headers: { 'Authorization': 'Bearer ' + token },
            success: function (response) {
                const users = response.users;
                const userList = $('#user-list');
                userList.empty();

                users.forEach(user => {
                    const userRow = `
                        <tr>
                            <td>${user.username}</td>
                            <td>${user.email}</td>
                            <td>${user.role}</td>
                            <td>
                                <a href="/users/edit/${user.id}/" class="edit-btn">Edit</a> |
                                <button class="delete-user-btn" data-id="${user.id}">Delete</button>
                            </td>
                        </tr>
                    `;
                    userList.append(userRow);
                });
            },
            error: function () {
                alert("Error fetching users.");
            },
        });
    }

    // Approve, Reject, Publish Articles
    function updateArticleStatus(articleId, status) {
        const urlMap = {
            approve: `/articles/approve/${articleId}/`,
            reject: `/articles/reject/${articleId}/`,
            publish: `/articles/published/${articleId}/`,
        };

        $.ajax({
            url: urlMap[status],
            type: 'PATCH',
            headers: { 'Authorization': 'Bearer ' + token },
            success: function () {
                alert(`Article ${status}d successfully.`);
                fetchArticles(); // Refresh the list
            },
            error: function () {
                alert(`Error ${status}ing article.`);
            },
        });
    }

    // Delete User
    function deleteUser(userId) {
        $.ajax({
            url: `/users/${userId}/delete/`,
            type: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token },
            success: function () {
                alert("User deleted successfully.");
                fetchUsers(); // Refresh users list
            },
            error: function () {
                alert("Error deleting user.");
            },
        });
    }

    // Delete Article
    function deleteArticle(articleId) {
        $.ajax({
            url: `/articles/${articleId}/delete/`,
            type: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token },
            success: function () {
                alert("Article deleted successfully.");
                fetchArticles(); // Refresh articles list
            },
            error: function () {
                alert("Error deleting article.");
            },
        });
    }

    // Event Handlers
    $(document).on('click', '.approve-btn', function () {
        updateArticleStatus($(this).data('id'), 'approve');
    });

    $(document).on('click', '.delete-user-btn', function () {
        deleteUser($(this).data('id'));
    });

    $(document).on('click', '.delete-article-btn', function () {
        deleteArticle($(this).data('id'));
    });

    // Initialize admin dashboard
    fetchArticles();
    fetchUsers();
});
