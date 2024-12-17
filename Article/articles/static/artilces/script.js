$(document).ready(function () {
    // Hide all sections initially
    $('#home-section').show();
    $('#manage-section').hide();
    $('#create-section').hide();
    $('#page2').hide(); // Initially hide page2 if it's part of a form

    // Navigate to Home section
    $('#home-link').click(function () {
        $('#home-section').show();
        $('#manage-section').hide();
        $('#create-section').hide();
    });

    // Navigate to Manage Articles section
    $('#manage-link').click(function () {
        $('#home-section').hide();
        $('#manage-section').show();
        $('#create-section').hide();
    });

    // Navigate to Create Article section
    $('#create-link').click(function () {
        $('#home-section').hide();
        $('#manage-section').hide();
        $('#create-section').show();
    });

    // Logout functionality
    $('#logout-link').click(function (event) {
        event.preventDefault();
        // Remove JWT token from localStorage to log out
        localStorage.removeItem('access_token');

        // Optionally, redirect the user to the login page after logout
        window.location.href = '/login/'; // Or replace with the appropriate URL
    });

    // Form navigation between pages
    $('#next-to-page2').click(function () {
        $('#page1').hide();  // Hide page 1
        $('#page2').show();  // Show page 2
    });

    $('#prev-to-page1').click(function () {
        $('#page2').hide();  // Hide page 2
        $('#page1').show();  // Show page 1
    });

    // Fetch articles
    function fetchArticles() {
        const token = localStorage.getItem('access_token'); // Assuming JWT token in localStorage
        
        $.ajax({
            url: '/articles/api/articles/', // API endpoint to fetch articles
            type: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token // Add the token to the Authorization header
            },
            success: function (articles) {
                const tableBody = $('#articles-table tbody');
                tableBody.empty(); // Clear existing rows

                articles.forEach(article => {
                    const row = `
                        <tr>
                            <td>${article.title}</td>
                            <td>${article.subtitle}</td>
                            <td>${article.category.name}</td>
                            <td>${article.publish_date}</td>
                            <td>
                                <button class="edit" data-id="${article.id}">Edit</button>
                                <button class="delete" data-id="${article.id}">Delete</button>
                            </td>
                        </tr>
                    `;
                    tableBody.append(row);
                });
            },
            error: function (jqXHR, textStatus, errorThrown) {
                // console.error('Error fetching articles:', textStatus, errorThrown);
                console.log(textStatus)
            }
        });
    }

    // Fetch articles on page load
    fetchArticles();

    // Edit article functionality
    $(document).on('click', '.edit', function () {
        const articleId = $(this).data('id');
        window.location.href = `/article/edit/${articleId}/`;  // Redirect to the article edit page
    });

    // Delete article functionality
    $(document).on('click', '.delete', function () {
        const articleId = $(this).data('id');
        const token = localStorage.getItem('access_token'); // JWT token from localStorage

        if (confirm('Are you sure you want to delete this article?')) {
            $.ajax({
                url: `/api/articles/${articleId}/`,  // API endpoint to delete article
                type: 'DELETE',
                headers: {
                    'Authorization': 'Bearer ' + token // Authorization header with token
                },
                success: function () {
                    alert('Article deleted successfully!');
                    fetchArticles(); // Refresh articles list
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    alert('Error deleting article: ' + errorThrown);
                }
            });
        }
    });

    // Fetch tags dynamically for the article creation form
    function fetchTags() {
        const tagsContainer = $('#tags-container');
        tagsContainer.empty(); // Clear existing checkboxes

        const token = localStorage.getItem('access_token'); // Assuming the JWT token is stored in localStorage
        console.log(token)
        $.ajax({
            url: '/api/tags/', // Your API endpoint for fetching tags
            type: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token // Add the token to the Authorization header
            },
            success: function (tags) {
                tags.forEach(tag => {
                    // Create a checkbox for each tag
                    const checkbox = `
                        <label>
                            <input type="checkbox" name="tags" value="${tag.id}"> ${tag.name}
                        </label><br>
                    `;
                    tagsContainer.append(checkbox);
                });
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.error('Error fetching tags:', textStatus, errorThrown);
                alert('Failed to load tags.');
            }
        });
    }

    // Fetch categories dynamically for the article creation form
    function fetchCategories() {
        const categorySelect = $('#category');
        categorySelect.empty(); // Clear existing options
        categorySelect.append('<option value="" disabled selected>Select a category</option>');

        // Predefined categories
        categorySelect.append('<option value="news">News</option>');
        categorySelect.append('<option value="opinion">Opinion</option>');
        categorySelect.append('<option value="sport">Sport</option>');

        const token = localStorage.getItem('access_token'); // Assuming the JWT token is stored in localStorage

        $.ajax({
            url: '/articles/api/categories/', // Your API endpoint for fetching categories
            type: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token // Add the token to the Authorization header
            },
            success: function (categories) {
                categories.forEach(category => {
                    // Dynamically append the fetched categories
                    categorySelect.append(new Option(category.name, category.id));
                });
            },
            error: function (jqXHR, textStatus, errorThrown) {
                console.error('Error fetching categories:', textStatus, errorThrown);
                alert('Failed to load categories.');
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        const page1 = document.getElementById('page1');
        const page2 = document.getElementById('page2');
        const nextButton = document.getElementById('next-to-page2');
        const prevButton = document.getElementById('prev-to-page1');

        // Next Button Click: Move from Page 1 to Page 2
        nextButton.addEventListener('click', function () {
            if (validatePage1()) {
                page1.style.display = 'none';
                page2.style.display = 'block';
            }
        });

        // Previous Button Click: Move from Page 2 to Page 1
        prevButton.addEventListener('click', function () {
            page2.style.display = 'none';
            page1.style.display = 'block';
        });

        // Validate Page 1 Inputs
        function validatePage1() {
            let valid = true;

            // Title Validation
            const title = document.getElementById('title');
            const titleError = document.getElementById('title-error');
            if (title.value.trim() === '') {
                titleError.innerText = 'Title is required.';
                valid = false;
            } else {
                titleError.innerText = '';
            }

            // Content Validation
            const content = document.getElementById('content');
            const contentError = document.getElementById('content-error');
            if (content.value.trim() === '') {
                contentError.innerText = 'Content is required.';
                valid = false;
            } else {
                contentError.innerText = '';
            }

            // Email Validation
            const email = document.getElementById('email');
            const emailError = document.getElementById('email-error');
            if (!validateEmail(email.value)) {
                emailError.innerText = 'Enter a valid email address.';
                valid = false;
            } else {
                emailError.innerText = '';
            }

            return valid;
        }

        // Email Validation Function
        function validateEmail(email) {
            const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return emailPattern.test(email);
        }
    });

    //
});
