(function () {
  "use strict";
  const articleId = document.body.dataset.articleId;
  const checks = document.getElementById("quality-gate-checks");
  const score = document.getElementById("quality-gate-score");
  const status = document.getElementById("quality-gate-status");
  const plagiarismButton = document.getElementById("run-plagiarism-check");
  if (!articleId || !checks || !score) return;

  const csrf = () => document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=").slice(1).join("=") || "";
  const request = async (url, options = {}) => {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json", ...(options.method ? { "X-CSRFToken": decodeURIComponent(csrf()) } : {}) }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Quality check failed.");
    return data;
  };
  const addCheck = (label, passed, detail) => `<div class="quality-check ${passed ? "is-passed" : "is-pending"}"><i class="fa-solid ${passed ? "fa-circle-check" : "fa-circle-exclamation"}" aria-hidden="true"></i><span><strong>${label}</strong><small>${detail}</small></span></div>`;

  async function runChecks() {
    try {
      const [seo, accessibility, sources, plagiarism] = await Promise.all([
        request(`/articles/api/v2/articles/${articleId}/seo/`),
        request(`/articles/api/v2/articles/${articleId}/accessibility/`),
        request(`/articles/api/v2/articles/${articleId}/sources/`),
        request(`/articles/api/v2/articles/${articleId}/plagiarism/`),
      ]);
      const seoChecks = Object.values(seo.seo_preview?.checks || {});
      const seoPassed = seoChecks.length > 0 && seoChecks.every((item) => item.passed);
      const sourceItems = Array.isArray(sources) ? sources : (sources.sources || []);
      const plagiarismPassed = !plagiarism.check || plagiarism.check.status === "clear" || plagiarism.status === "clear";
      const passedCount = [seoPassed, accessibility.passed, sourceItems.length > 0, plagiarismPassed].filter(Boolean).length;
      score.textContent = `${passedCount}/4 ready`;
      checks.innerHTML = [
        addCheck("SEO metadata", seoPassed, seoPassed ? "Metadata checks passed." : "Complete title, description, canonical URL, image, and keywords."),
        addCheck("Accessibility", Boolean(accessibility.passed), accessibility.passed ? "No blocking accessibility issues." : `${accessibility.errors || 0} blocking issue(s) found.`),
        addCheck("Sources", sourceItems.length > 0, sourceItems.length ? `${sourceItems.length} source(s) attached.` : "Attach at least one source."),
        addCheck("Originality", plagiarismPassed, plagiarism.check ? `Similarity status: ${plagiarism.check.status}.` : "Run the originality check when the draft is ready."),
      ].join("");
      status.textContent = "Checklist refreshed.";
    } catch (error) { score.textContent = "Unavailable"; status.textContent = error.message; status.classList.add("is-error"); }
  }

  plagiarismButton?.addEventListener("click", async () => {
    plagiarismButton.disabled = true;
    status.textContent = "Running originality check…";
    try { await request(`/articles/api/v2/articles/${articleId}/plagiarism/`, { method: "POST" }); await runChecks(); }
    catch (error) { status.textContent = error.message; status.classList.add("is-error"); }
    finally { plagiarismButton.disabled = false; }
  });
  runChecks();
})();
