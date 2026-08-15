// Small shared behaviours: active nav link highlight + footer year.
// Author: Elias

document.addEventListener("DOMContentLoaded", () => {
  const here = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a").forEach((link) => {
    const target = link.getAttribute("href");
    if (target === here) {
      link.classList.add("active");
    }
  });

  const yearEl = document.getElementById("footer-year");
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }
});
