(function () {
  "use strict";

  function addLabels(table) {
    const headers = [...table.querySelectorAll("thead th")].map((header) => header.textContent.trim());
    table.querySelectorAll("tbody tr").forEach((row) => {
      [...row.children].forEach((cell, index) => {
        if (headers[index]) cell.dataset.label = headers[index];
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".article-table table, table.article-table").forEach((table) => {
      addLabels(table);
      const body = table.querySelector("tbody");
      if (body) new MutationObserver(() => addLabels(table)).observe(body, { childList: true });
    });
  });
})();
