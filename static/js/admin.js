$(document).ready(function () {
    const {escapeHtml: escape, request, allArticles, statusBadge, editArticle} = WorkflowUI;
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    async function fetchArticles() {
        try {
            const articles = await allArticles();
            $('#articles-list').html(articles.map((article, index) => `<tr data-article-id="${article.id}">
                <td>${index + 1}</td><td>${escape(article.title)}</td><td>${statusBadge(article.workflow_status)}</td>
                <td>${escape(article.category || '—')}</td><td>${escape(article.publish_date || '—')}</td>
                <td>${article.image ? `<img src="${escape(article.image)}" alt="${escape(article.title)}" width="50">` : 'No image'}</td>
                <td><button class="edit-btn" data-id="${article.id}">Edit</button>
                ${article.available_actions?.includes('review') ? `<button class="approve-btn" data-id="${article.id}">Approve</button>` : ''}
                ${article.available_actions?.includes('publish') ? `<button class="publish-btn" data-id="${article.id}">Publish</button>` : ''}
                <button class="delete-article-btn" data-id="${article.id}">Move to trash</button></td></tr>`).join(''));
            $('#no-articles-message').toggle(!articles.length);
        } catch (error) { alert(error.message); }
    }
    async function fetchUsers() {
        try {
            let url = '/api/user-list/'; const users = [];
            while (url) { const data = await request(url); users.push(...(data.results || data)); url = data.next; }
            $('#user-list').html(users.map(account => `<tr><td>${escape(account.username)}</td><td>${escape(account.email)}</td><td>${escape(account.role)}</td><td>${account.username === user.username ? 'Current account' : `<button class="delete-user-btn" data-id="${account.id}">Delete</button>`}</td></tr>`).join(''));
            $('#no-users-message').toggle(!users.length);
        } catch (error) { alert(error.message); }
    }
    $('.nav-link[data-page]').on('click', function (event) {
        event.preventDefault(); const users = this.dataset.page === 'users';
        $('#articles-section').toggle(!users); $('#users-section').toggle(users);
        $('.nav-link[data-page]').removeAttr('aria-current');
        $(`.nav-link[data-page="${this.dataset.page}"]`).attr('aria-current', 'page');
        if (users) fetchUsers(); else fetchArticles();
    });
    $(document).on('click', '.edit-btn', function () { editArticle(this.dataset.id, fetchArticles); });
    $(document).on('click', '.approve-btn, .publish-btn, .delete-article-btn, .delete-user-btn', async function () {
        const id = this.dataset.id;
        const deletingUser = this.classList.contains('delete-user-btn');
        const trash = this.classList.contains('delete-article-btn');
        const publish = this.classList.contains('publish-btn');
        const message = deletingUser ? 'Delete this user and their articles? This cannot be undone.' : trash ? 'Move this article to the trash?' : publish ? 'Publish this approved article?' : 'Approve this submitted article?';
        if (!(await window.appConfirm(message))) return;
        this.disabled = true;
        try {
            const url = deletingUser ? `/api/users/${id}/delete/` : `/articles/api/v2/articles/${id}/${trash ? 'trash' : publish ? 'publish' : 'review'}/`;
            await request(url, {method: deletingUser ? 'DELETE' : trash || publish ? 'POST' : 'PATCH', ...(deletingUser ? {} : {body: JSON.stringify({decision:'approve'})})});
            if (deletingUser) await fetchUsers(); else await fetchArticles();
        } catch (error) { alert(error.message); }
        finally { this.disabled = false; }
    });
    $('#articles-section').show(); fetchArticles();
});
