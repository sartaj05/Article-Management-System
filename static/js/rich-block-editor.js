(function () {
  "use strict";
  const editor = document.getElementById("content");
  const toolbar = document.querySelector(".block-editor-toolbar");
  if (!editor || !toolbar) return;

  const blocks = {
    heading: "<h2>Section heading</h2>\n",
    quote: "<blockquote>Write a source-backed quote here.</blockquote>\n",
    pullquote: "<aside class=\"pull-quote\">A memorable idea worth highlighting.</aside>\n",
    list: "<ul>\n  <li>First point</li>\n  <li>Second point</li>\n</ul>\n",
    image: "<figure><img src=\"IMAGE_URL\" alt=\"Describe this image\"><figcaption>Image caption</figcaption></figure>\n",
    embed: "<div class=\"article-embed\" data-embed-url=\"EMBED_URL\">Embedded media</div>\n",
  };
  toolbar.querySelectorAll("[data-block]").forEach((button) => button.addEventListener("click", () => {
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    const selected = editor.value.slice(start, end);
    const block = blocks[button.dataset.block].replace("Section heading", selected || "Section heading");
    editor.setRangeText(block, start, end, "end");
    editor.focus();
    editor.dispatchEvent(new Event("input", { bubbles: true }));
  }));
})();
