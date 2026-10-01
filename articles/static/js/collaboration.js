(function () {
  "use strict";
  window.ArticleCollaboration = {
    start(articleId, token, onPresence) {
      const url = `/articles/api/v2/articles/${encodeURIComponent(articleId)}/collaboration/`;
      const headers = { Accept: "application/json", Authorization: `Bearer ${token}` };
      const heartbeat = (state = {}) => fetch(url, { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(state) });
      const refresh = () => fetch(url, { headers }).then((response) => response.ok ? response.json() : []).then((sessions) => onPresence?.(sessions));
      heartbeat(); refresh();
      const timer = window.setInterval(refresh, 30000);
      return { heartbeat, stop: () => { window.clearInterval(timer); fetch(url, { method: "DELETE", headers }); } };
    }
  };
})();
