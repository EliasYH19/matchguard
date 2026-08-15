// Handles the browse grid + create form on tournaments.html
// Author: Elias

function statusPill(status) {
  const map = {
    active: '<span class="pill pill-clear">Active</span>',
    pending_payment: '<span class="pill pill-pending">Awaiting payment</span>',
  };
  return map[status] || `<span class="pill pill-pending">${status}</span>`;
}

async function loadPackageOptions() {
  const select = document.getElementById("package_id");
  try {
    const packages = await MatchGuardAPI.getPackages();
    select.innerHTML = packages
      .map((p) => `<option value="${p.id}">${p.name} - $${p.price_usd}</option>`)
      .join("");

    // pre-select a package if the user arrived from packages.html?package=silver
    const params = new URLSearchParams(window.location.search);
    const preselect = params.get("package");
    if (preselect) {
      select.value = preselect;
    }
  } catch (err) {
    select.innerHTML = `<option value="">Could not load packages</option>`;
  }
}

async function loadTournaments() {
  const grid = document.getElementById("tournaments-grid");
  const errorBox = document.getElementById("tournaments-error");
  try {
    const tournaments = await MatchGuardAPI.getTournaments();
    if (tournaments.length === 0) {
      grid.innerHTML = `<div class="empty-state">No tournaments yet - create the first one above.</div>`;
      return;
    }
    grid.innerHTML = "";
    tournaments.forEach((t) => {
      const card = document.createElement("a");
      card.href = `tournament.html?id=${t.id}`;
      card.style.display = "block";
      card.className = "card";
      card.innerHTML = `
        <h3>${t.name} ${statusPill(t.status)}</h3>
        <p class="muted">${t.game} &middot; ${t.format.toUpperCase()} &middot; starts ${t.start_date}</p>
        <p class="muted">Organizer: ${t.organizer_name}</p>
        <span class="tag-code">package: ${t.package_id}</span>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    errorBox.innerHTML = `<div class="alert alert-error">Could not load tournaments: ${err.message}</div>`;
  }
}

async function handleCreateSubmit(evt) {
  evt.preventDefault();
  const form = evt.target;
  const errorBox = document.getElementById("create-error");
  const successBox = document.getElementById("create-success");
  errorBox.innerHTML = "";
  successBox.innerHTML = "";

  const submitBtn = form.querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.textContent = "Creating…";

  try {
    const formData = new FormData(form);
    const tournament = await MatchGuardAPI.createTournament(formData);
    successBox.innerHTML = `<div class="alert alert-success">Tournament "${tournament.name}" created. Redirecting to checkout&hellip;</div>`;
    setTimeout(() => {
      window.location.href = `tournament.html?id=${tournament.id}`;
    }, 900);
  } catch (err) {
    errorBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Create tournament";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadPackageOptions();
  loadTournaments();
  document.getElementById("create-tournament-form").addEventListener("submit", handleCreateSubmit);

  const params = new URLSearchParams(window.location.search);
  if (params.get("create") === "1") {
    document.getElementById("create-tournament-card").scrollIntoView({ behavior: "smooth" });
  }
});
