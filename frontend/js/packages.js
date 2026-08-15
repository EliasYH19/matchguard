// Renders the pricing grid on packages.html
// Author: Elias

async function loadPackages() {
  const grid = document.getElementById("packages-grid");
  const errorBox = document.getElementById("packages-error");
  try {
    const packages = await MatchGuardAPI.getPackages();
    grid.innerHTML = "";
    packages.forEach((pkg, index) => {
      const card = document.createElement("div");
      card.className = "card package-card" + (index === 1 ? " featured" : "");
      const featuresHtml = pkg.features.map((f) => `<li>${f}</li>`).join("");
      const cap = pkg.max_players === null ? "Unlimited players" : `Up to ${pkg.max_players} players`;
      card.innerHTML = `
        <h3>${pkg.name}${index === 1 ? ' <span class="pill pill-clear">Most popular</span>' : ""}</h3>
        <p class="muted">${pkg.tagline}</p>
        <div class="price">$${pkg.price_usd}<span> / tournament</span></div>
        <p class="muted">${cap}</p>
        <ul>${featuresHtml}</ul>
        <a href="tournaments.html?create=1&package=${pkg.id}" class="btn btn-primary">Choose ${pkg.name}</a>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    errorBox.innerHTML = `<div class="alert alert-error">Could not load packages: ${err.message}</div>`;
    grid.innerHTML = "";
  }
}

document.addEventListener("DOMContentLoaded", loadPackages);
