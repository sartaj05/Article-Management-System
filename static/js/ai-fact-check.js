(function () {
  "use strict";

  const articleId = document.body.dataset.articleId;
  const runButton = document.getElementById("run-ai-fact-check");
  const applyButton = document.getElementById("apply-ai-fact-check");
  const result = document.getElementById("ai-fact-check-result");
  const status = document.getElementById("ai-fact-check-status");
  let latestRun = null;

  if (!articleId || !runButton) return;

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function setStatus(message, error) {
    status.textContent = message;
    status.dataset.state = error ? "error" : "ready";
  }

  function renderClaims(claims) {
    result.replaceChildren();
    claims.forEach((claim, index) => {
      const card = document.createElement("article");
      card.className = "ai-copilot__suggestion ai-fact-check__claim";
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = true;
      checkbox.dataset.claimIndex = String(index);
      label.append(checkbox, document.createTextNode(" Queue this claim for certification"));
      const heading = document.createElement("strong");
      heading.textContent = `${claim.verdict} · ${Math.round(Number(claim.confidence || 0) * 100)}% confidence`;
      const text = document.createElement("p");
      text.textContent = claim.claim;
      const explanation = document.createElement("small");
      explanation.textContent = `${claim.explanation}${claim.unresolved ? " Unresolved: editor verification required." : ""}`;
      const sources = document.createElement("div");
      sources.className = "ai-fact-check__sources";
      (claim.source_citations || []).forEach((source) => {
        const link = document.createElement("a");
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = `${source.title || "Source"}${source.publisher ? ` · ${source.publisher}` : ""}`;
        sources.appendChild(link);
      });
      card.append(label, heading, text, explanation, sources);
      result.appendChild(card);
    });
    result.hidden = false;
    applyButton.disabled = !claims.length;
  }

  runButton.addEventListener("click", async function () {
    runButton.disabled = true;
    applyButton.disabled = true;
    setStatus("Extracting claims and matching available sources…");
    try {
      const response = await fetch(`/articles/api/v2/articles/${articleId}/fact-checks/ai/`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "The AI fact check could not run.");
      latestRun = data;
      renderClaims(data.suggestions.claims || []);
      setStatus(`${data.suggestions.claims.length} claims ready for human review. ${data.suggestions.unresolved_count} remain unresolved.`);
    } catch (error) {
      setStatus(error.message, true);
      result.hidden = true;
    } finally {
      runButton.disabled = false;
    }
  });

  applyButton.addEventListener("click", async function () {
    if (!latestRun) return;
    const claimIndexes = [...result.querySelectorAll("[data-claim-index]:checked")].map((input) => Number(input.dataset.claimIndex));
    applyButton.disabled = true;
    setStatus("Queueing claims for editor certification…");
    try {
      const response = await fetch(`/articles/api/v2/assistant/runs/${latestRun.run_id}/fact-check/apply/`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ claim_indexes: claimIndexes }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Claims could not be queued.");
      setStatus(`${data.fact_checks.length} claim(s) queued. An editor must certify them before publication.`);
    } catch (error) {
      setStatus(error.message, true);
      applyButton.disabled = false;
    }
  });
})();
