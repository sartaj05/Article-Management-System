$(document).ready(function () {
    const {escapeHtml: escape, request, allArticles, statusBadge, editArticle} = WorkflowUI;
    let articles = [];
    const tables = [
        ['article-list', 'no-articles-message', null],
        ['approve-article-list', 'no-approve-articles-message', 'approved'],
        ['reject-article-list', 'no-reject-articles-message', 'rejected'],
        ['published-article-list', 'no-published-articles-message', 'published'],
    ];
    function actions(article) {
        const button = (name, label) => `<button type="button" class="${name}-btn" data-id="${article.id}">${label}</button>`;
        let html = button('view', 'View') + button('edit', 'Edit');
        if (article.available_actions?.includes('review')) html += button('approve', 'Approve') + button('reject', 'Reject');
        if (article.available_actions?.includes('publish')) html += button('publish', 'Publish');
        return `<div class="button-container">${html}</div>`;
    }
    function render() {
        for (const [id, empty, status] of tables) {
            const rows = articles.filter(article => !status || article.workflow_status === status);
            document.getElementById(id).innerHTML = rows.map((article, index) => {
                const image = article.image ? `<img src="${escape(article.image)}" alt="${escape(article.title)}" width="50">` : '<span class="image-placeholder">No image</span>';
                const badge = statusBadge(article.workflow_status);
                const common = `<td>${index + 1}</td><td>${escape(article.title)}</td><td>${escape(article.category || '—')}</td><td>${escape(article.publish_date || '—')}</td>`;
                const end = status === 'published' ? `<td>${badge}</td><td>${actions(article)}</td><td>${image}</td>` : status ? `<td>${image}</td><td>${badge}</td><td>${actions(article)}</td>` : `<td>${badge}</td><td>${image}</td><td>${actions(article)}</td>`;
                return `<tr data-article-id="${article.id}">${common}${end}</tr>`;
            }).join('');
            document.getElementById(empty).style.display = rows.length ? 'none' : '';
        }
        $('.page input[type="text"]').trigger('input');
    }
    async function refresh() {
        try { articles = await allArticles(); render(); }
        catch (error) { alert(error.message); }
    }
    function showSection(id) {
        $('#home-section, .page').hide(); $('#' + id).show();
    }
    const sections = {'home-btn':'home-section', 'manage-articles-btn':'article-list-page', 'approve-articles-btn':'approve-articles-page', 'reject-articles-btn':'reject-articles-page', 'published-articles-btn':'published-articles-page'};
    for (const [link, section] of Object.entries(sections)) $('#' + link).on('click', function (event) {
        event.preventDefault(); showSection(section); if (section !== 'home-section') refresh();
    });
    $('.page input[type="text"]').on('input', function () {
        const query = this.value.toLowerCase();
        $(this).closest('.page').find('tbody tr').each(function () { $(this).toggle($(this).text().toLowerCase().includes(query)); });
    });
    $(document).on('click', '.view-btn', function () {
        const article = articles.find(item => item.id === Number(this.dataset.id));
        if (!article) return;
        for (const field of ['id','title','subtitle','email','category','tags','content']) $('#modal-' + field).text(`${field}: ${article[field] || '—'}`);
        $('#modal-publish-date').text(article.publish_date || '—');
        $('#modal-status').text(article.workflow_status);
        $('#modal-image').attr('src', article.image || '').toggle(Boolean(article.image));
        $('#article-modal').show();
    });
    $(document).on('click', '#close-modal', () => $('#article-modal').hide());
    $(document).on('click', '.edit-btn', function () { editArticle(this.dataset.id, refresh); });
    $(document).on('click', '.approve-btn, .reject-btn, .publish-btn', async function () {
        const id = this.dataset.id;
        const decision = this.classList.contains('approve-btn') ? 'approve' : this.classList.contains('reject-btn') ? 'reject' : 'publish';
        let reason;
        if (decision === 'reject') {
            reason = await window.appPrompt('Explain what the author should change before resubmitting.', {title:'Reject article'});
            if (!reason) return;
        } else if (!(await window.appConfirm(`Are you sure you want to ${decision} this article?`, {title: decision === 'approve' ? 'Approve article' : 'Publish article'}))) return;
        this.disabled = true;
        try {
            await request(`/articles/api/v2/articles/${id}/${decision === 'publish' ? 'publish' : 'review'}/`, {
                method: decision === 'publish' ? 'POST' : 'PATCH', body: JSON.stringify({decision, reason})
            });
            await refresh();
            if (decision === 'publish') showSection('published-articles-page');
            window.appAlert(decision === 'publish' ? 'Article published successfully.' : decision === 'approve' ? 'Article approved successfully.' : 'Article returned to the author with your feedback.', {kind:'success'});
        } catch (error) { alert(error.message); }
        finally { this.disabled = false; }
    });
    $(document).on('keydown', event => { if (event.key === 'Escape') $('.modal:visible').hide(); });
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    $('#username').text(user.username); $('#email').text(user.email); $('#role').text(user.role);
    $('#userfullname').text([user.first_name, user.last_name].filter(Boolean).join(' ') || user.username);
    request('/articles/api/articles/count/').then(data => $('#article-count').text(data.article_count)).catch(error => alert(error.message));
});
