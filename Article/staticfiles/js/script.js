// document.getElementById('next-to-page2').addEventListener('click',()=>{
//     document.getElementById('page2').style.display='none'
// })
$(document).ready(function () {
    // Cache common DOM elements for performance
    const $homeLink = $('#home-link');
    const $createArticleLink = $('#create-article-link');
    const $articleListLink = $('#article-list-link');
    const $logoutLink = $('#logout-link');
    const $userName = $('#user-name');
    const $userEmail = $('#user-email');
    const $articleCount = $('#article-count');
    const $homeArticleList = $('#home-article-list');
    const $articleList = $('#article-list');
    const $articleForm = $('#article-form');
    const $articleDetailModal = $('#article-detail-modal');
    const $articleDetailContent = $('#article-detail-content');
    const $closeArticleModal = $('#close-article-modal');  // Close button for modal

    // Sidebar navigation logic
    $homeLink.click(function () {
        showPage('home-page');
    });

    $createArticleLink.click(function () {
        showPage('create-article-page');
    });

    $articleListLink.click(function () {
        showPage('article-list-page');
        fetchArticles();  // Fetch and display articles
    });

    $logoutLink.click(function () {
        localStorage.removeItem('access_token');
        localStorage.removeItem('lastActivePage');
        updateSidebar();
        window.location.href = '/login/';
    });

    // Helper function to show pages
    function showPage(pageId) {
        $('.page').removeClass('active');
        $('#' + pageId).addClass('active');
        localStorage.setItem('lastActivePage', pageId);
    }

    // Check if the user is logged in and update the sidebar
    function updateSidebar() {
        const token = localStorage.getItem('access_token');
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

    // // Check the last active page and activate it
    // function activateLastPage() {
    //     const lastActivePage = localStorage.getItem('lastActivePage');
    //     if (lastActivePage) {
    //         showPage(lastActivePage);
    //     } else {
    //         showPage('home-page');
    //     }
    // }

    // Activate the last active page on page load
    // activateLastPage();

    // Fetch user details to display on the dashboard
    function fetchUserDetails() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            alert("Please log in to view user details.");
            return;
        }

        $.ajax({
            url: '/users/profile/',
            type: 'GET',
            headers: { 'Authorization': 'Bearer ' + token },
            success: function (response) {
                $userName.text(response.username);
                $userEmail.text(response.email);
            },
            error: function () {
                alert("Error fetching user details.");
            }
        });
    }

    // Fetch total number of articles
    function fetchArticleCount() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            alert("Please log in to view article count.");
            return;
        }

        $.ajax({
            url: '/journalist/dashboard/articles/api/articles/count/',
            type: 'GET',
            headers: { 'Authorization': 'Bearer ' + token },
            success: function (response) {
                $articleCount.text(response.count || 0);
            },
            error: function () {
                alert("Error fetching article count.");
            }
        });
    }
    $(document).ready(function() {
        // Handle page navigation for multi-page form
        $(document).on('click', '#next-to-page2', function () {
            // Check if all required fields on Page 1 are filled
            const title = $('#title').val();
            const content = $('#content').val();
            const email = $('#email').val();
    
            let isValid = true;
    
            if (!title || title.length < 5 || title.length > 50) {
                $('#title-error').text('Please enter a valid title (5-50 characters)');
                isValid = false;
            } else {
                $('#title-error').text('');
            }
    
            if (!content || content.length < 10) {
                $('#content-error').text('Content must be at least 10 characters long');
                isValid = false;
            } else {
                $('#content-error').text('');
            }
    
            if (!email || !validateEmail(email)) {
                $('#email-error').text('Please enter a valid email address');
                isValid = false;
            } else {
                $('#email-error').text('');
            }
    
            if (isValid) {
                $('#page1').removeClass('active');
                $('#page2').addClass('active');
            } else {
                alert("Please fill all required fields on Page 1.");
            }
        });
    
        $(document).on('click', '#prev-to-page1', function () {
            $('#page2').removeClass('active');
            $('#page1').addClass('active');
        });
    
        // Simple email validation function
        function validateEmail(email) {
            const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
            return re.test(email);
        }
    });
    
    $articleForm.submit(function (e) {
        e.preventDefault();
    
        // Get form field values
        const title = $('#title').val();
        const subtitle = $('#subtitle').val();
        const content = $('#content').val();
        const email = $('#email').val();
        const tags = $('#tags').val();
        const category = $('#category').val();
        const publishDate = $('#publish_date').val();
        const image = $('#image')[0].files[0];
        const token = localStorage.getItem('access_token');
    
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
    
        // Validate email format
        const emailPattern = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}$/;
        if (!email || !emailPattern.test(email)) {
            alert("Please enter a valid email address.");
            return;
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
            alert("The publish date cannot be in the past. Please select a present or future date.");
            return;
        }
    
        // Validation for image (optional, but check file type and size)
        if (image && !image.type.startsWith('image/')) {
            alert("Please upload a valid image file.");
            return;
        }
    
        if (image && image.size > 5 * 1024 * 1024) { // 5MB max size
            alert("Image size must be less than 5MB.");
            return;
        }
    
        // Check if user is logged in
        if (!token) {
            alert("Please log in to create an article.");
            window.location.href = '/login/';
            return;
        }
    
        // Create FormData object to send the data
        const formData = new FormData(this);
    
        // Send AJAX request to create the article
        $.ajax({
            url: '/journalist/dashboard/articles/api/articles/create/',
            type: 'POST',
            data: formData,
            contentType: false,
            processData: false,
            headers: { 'Authorization': 'Bearer ' + token },
            success: function (response) {
                alert("Article created successfully!");
                appendArticle(response);
                fetchArticles();
                fetchArticleCount();
                $articleForm[0].reset();
                showPage('article-list-page');
            },
            error: function () {
                alert("Error creating article.");
            }
        });
    });
    
    

   // Append article to the list
    function appendArticle(article) {
        const imageUrl = article.imageUrl ? `/media/articles/images/${article.imageUrl}` : ''; 
        console.log(imageUrl)
        const articleItem = `
            <tr id="article-${article.id}">
                <td>${article.id}</td> <!-- Article ID column -->
                <td>${article.id || 'No Title'}</td> <!-- Article Title column -->
                <td>${article.category || 'No Category'}</td> <!-- Article Category column -->
                <td>${article.publish_date || 'No Date'}</td> <!-- Article Publish Date column -->
                <td>${article.status || 'No Status'}</td> <!-- Article Status column -->
                <td><img src="${article.image}" alt="${article.imageUrl}" width="100" /></td> 
                <td>
                    <button class="view-article" data-id="${article.id}">View</button>
                    <button class="edit-article" data-id="${article.id}">Edit</button>
                    <button class="delete-article" data-id="${article.id}">Delete</button>
                </td> 
            </tr>
        `;
        // Append the article item as a table row
        $('#article-list').append(articleItem);
    }

    // Fetch and display articles
    function fetchArticles() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            alert("Please log in to view articles.");
            return;
        }

        $.ajax({
            url: '/articles/search/',
            type: 'GET',
            headers: { 'Authorization': 'Bearer ' + token },
            success: function (response) {
                const articles = response.articles || [];
                $('#article-list').empty();  // Clear the current list

                if (articles.length === 0) {
                    $('#no-articles-message').show();  // Show message if no articles
                } else {
                    $('#no-articles-message').hide();  // Hide message if articles are available
                    articles.forEach(appendArticle);  // Append each article to the table
                }
            },
            error: function () {
                alert("Error fetching articles.");
            }
        });
    }

    // Event listener for "View Article" button
    document.querySelectorAll('.view-article').forEach(function (viewButton) {
        viewButton.addEventListener('click', function () {
            const articleId = this.getAttribute('data-id');
            const token = localStorage.getItem('access_token');

            if (!articleId) {
                console.error("Article ID is missing from the 'view' button.");
                return;
            }

            if (!token) {
                alert("Please log in to view the article.");
                return;
            }

            console.log(`Fetching article details for ID: ${articleId}`);

            fetch(`/api/articles/${articleId}/`, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${token}` }
            })
            .then(response => response.json())
            .then(data => {
                if (data.article) {
                    const article = data.article;
                    const articleDetails = `
                        <h3>${article.title}</h3>
                        <p><strong>Subtitle:</strong> ${article.subtitle}</p>
                        <p><strong>Content:</strong> ${article.content}</p>
                        <p><strong>Tags:</strong> ${article.tags}</p>
                        <p><strong>Category:</strong> ${article.category}</p>
                        <p><strong>Publish Date:</strong> ${article.publish_date}</p>
                        <img src="/media/${article.image}" alt="${article.image}" width="200" />
                    `;
                    articleDetailContent.innerHTML = articleDetails;
                    articleDetailModal.style.display = 'block'; // Show the modal
                } else {
                    alert("Article not found.");
                }
            })
            .catch(error => {
                alert("Error fetching article details.");
                console.error("Error fetching article details:", error);
            });
        });
    });

    // Close the article detail modal
    closeArticleModal.addEventListener('click', function () {
        articleDetailModal.style.display = 'none'; // Hide the modal
    });

    // Event listener for "Edit Article" button
    document.querySelectorAll('.edit-article').forEach(function (editButton) {
        editButton.addEventListener('click', function () {
            const articleId = this.getAttribute('data-id');

            if (!articleId) {
                console.error("Article ID is missing from the 'edit' button.");
                return;
            }

            console.log(`Redirecting to edit page for Article ID: ${articleId}`);

            // Redirect to the edit page
            window.location.href = `/journalist/dashboard/articles/edit/${articleId}/`;
        });
    });

    // Handle delete article action
    $(document).on('click', '.delete-article', function () {
        const articleId = $(this).data('id');
        if (confirm('Are you sure you want to delete this article?')) {
            const token = localStorage.getItem('access_token');
            $.ajax({
                url: `/journalist/dashboard/articles/delete/${articleId}/`,
                type: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + token },
                success: function () {
                    alert("Article deleted successfully!");
                    $(`#article-${articleId}`).remove();  // Remove article from the list
                    fetchArticleCount();
                },
                error: function () {
                    alert("Error deleting article.");
                }
            });
        }
    });
});
