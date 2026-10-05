(function () {
    const widget = document.querySelector('[data-support-chat]');
    if (!widget) return;

    const openButton = widget.querySelector('[data-support-open]');
    const closeButton = widget.querySelector('[data-support-close]');
    const panel = widget.querySelector('[data-support-panel]');
    const form = widget.querySelector('[data-support-form]');
    const input = widget.querySelector('#support-message');
    const messages = widget.querySelector('[data-support-messages]');

    function addMessage(text, type, links) {
        const message = document.createElement('div');
        message.className = `support-chat__message support-chat__message--${type}`;
        message.textContent = text;

        if (type === 'bot' && Array.isArray(links) && links.length) {
            const linkGroup = document.createElement('div');
            linkGroup.className = 'support-chat__message-links';
            links.forEach(function (link) {
                const anchor = document.createElement('a');
                anchor.href = link.url;
                anchor.textContent = link.label;
                linkGroup.appendChild(anchor);
            });
            message.appendChild(linkGroup);
        }

        messages.appendChild(message);
        messages.scrollTop = messages.scrollHeight;
    }

    function setOpen(isOpen) {
        panel.hidden = !isOpen;
        openButton.setAttribute('aria-expanded', String(isOpen));
        if (isOpen) input.focus();
    }

    async function ask(question) {
        const value = String(question || '').trim();
        if (!value) return;

        addMessage(value, 'user');
        input.value = '';
        input.disabled = true;

        try {
            const response = await fetch('/api/support/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ message: value }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Support request failed.');
            addMessage(data.answer, 'bot', data.links);
        } catch (error) {
            addMessage('Sorry, support is temporarily unavailable. Please use the project navigation or try again.', 'bot');
        } finally {
            input.disabled = false;
            input.focus();
        }
    }

    function getCookie(name) {
        const cookie = document.cookie.split('; ').find(function (item) {
            return item.startsWith(`${name}=`);
        });
        return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
    }

    openButton.addEventListener('click', function () {
        setOpen(panel.hidden);
    });
    closeButton.addEventListener('click', function () {
        setOpen(false);
    });
    form.addEventListener('submit', function (event) {
        event.preventDefault();
        ask(input.value);
    });
    widget.querySelectorAll('[data-support-question]').forEach(function (button) {
        button.addEventListener('click', function () {
            ask(button.dataset.supportQuestion);
        });
    });
})();
