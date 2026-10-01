(function () {
  "use strict";
  const preferences = JSON.parse(window.localStorage.getItem("article-studio-accessibility") || "{}");
  const apply = (key, value) => document.documentElement.dataset[key] = value ? "true" : "false";
  apply("highContrast", preferences.high_contrast);
  apply("largeText", preferences.large_text);
  apply("reduceMotion", preferences.reduce_motion || window.matchMedia("(prefers-reduced-motion: reduce)").matches);
})();
