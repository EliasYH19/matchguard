// Logic for tournament.html - detail view, purchase, registration, scan upload
// Author: Elias

const params = new URLSearchParams(window.location.search);
const tournamentId = params.get("id");

function statusPill(status) {
  const map = {
    active: '<span class="pill pill-clear">Active</span>',
    pending_payment: '<span class="pill pill-pending">Awaiting payment</span>',
    not_submitted: '<span class="pill pill-pending">No scan yet</span>',
    clear: '<span class="pill pill-clear">Clear</span>',
    flagged: '<span class="pill pill-flagged">Flagged</span>',
  };
  return map[status] || `<span class="pill pill-pending">${status}</span>`;
}

async function renderHeader() {
  const headerBox = document.getElementById("tournament-header");
  const errorBox = document.getElementById("tournament-error");
  if (!tournamentId) {
    errorBox.innerHTML = `<div class="alert alert-error">No tournament id in the URL. Go back to <a href="tournaments.html">Tournaments</a>.</div>`;
    return null;
  }
  try {
    const t = await MatchGuardAPI.getTournament(tournamentId);
    headerBox.innerHTML = `
      <h1>${t.name} ${statusPill(t.status)}</h1>
      <p class="lead">${t.game} &middot; ${t.format.toUpperCase()} &middot; starts ${t.start_date} &middot; organized by ${t.organizer_name}</p>
      <p class="muted">Package: <strong>${t.package ? t.package.name : t.package_id}</strong>${t.package ? ` ($${t.package.price_usd})` : ""}</p>
      ${t.banner_url ? `<img src="${t.banner_url}" alt="${t.name} banner" style="max-height:220px; border-radius:10px; margin-top:16px;" />` : ""}
    `;
    document.getElementById("purchase-card").style.display = t.status === "pending_payment" ? "block" : "none";
    return t;
  } catch (err) {
    errorBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
    return null;
  }
}

async function handlePurchase() {
  const btn = document.getElementById("purchase-btn");
  const errorBox = document.getElementById("purchase-error");
  btn.disabled = true;
  btn.textContent = "Processing…";
  try {
    await MatchGuardAPI.purchasePackage(tournamentId);
    await renderHeader();
  } catch (err) {
    errorBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Confirm purchase";
  }
}

async function loadRegistrations() {
  const wrap = document.getElementById("registrations-table-wrap");
  const errorBox = document.getElementById("registrations-error");
  const select = document.getElementById("registration_select");
  try {
    const regs = await MatchGuardAPI.getRegistrations(tournamentId);

    if (regs.length === 0) {
      wrap.innerHTML = `<div class="empty-state">No players registered yet.</div>`;
      select.innerHTML = `<option value="">No players registered yet</option>`;
      return;
    }

    select.innerHTML = regs.map((r) => `<option value="${r.id}" data-gamertag="${r.gamertag}">${r.gamertag}</option>`).join("");

    wrap.innerHTML = `
      <table>
        <thead><tr><th>Gamertag</th><th>Email</th><th>Scan status</th><th>Registered</th></tr></thead>
        <tbody>
          ${regs
            .map(
              (r) => `<tr><td>${r.gamertag}</td><td>${r.email}</td><td>${statusPill(r.scan_status)}</td><td>${new Date(r.created_at).toLocaleString()}</td></tr>`
            )
            .join("")}
        </tbody>
      </table>
    `;
  } catch (err) {
    errorBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

async function handleRegisterSubmit(evt) {
  evt.preventDefault();
  const errorBox = document.getElementById("register-error");
  const successBox = document.getElementById("register-success");
  errorBox.innerHTML = "";
  successBox.innerHTML = "";
  const gamertag = document.getElementById("gamertag").value;
  const email = document.getElementById("email").value;

  try {
    await MatchGuardAPI.registerPlayer(tournamentId, gamertag, email);
    successBox.innerHTML = `<div class="alert alert-success">${gamertag} registered.</div>`;
    evt.target.reset();
    await loadRegistrations();
  } catch (err) {
    errorBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

async function handleScanSubmit(evt) {
  evt.preventDefault();
  const errorBox = document.getElementById("scan-error");
  const successBox = document.getElementById("scan-success");
  errorBox.innerHTML = "";
  successBox.innerHTML = "";

  const form = evt.target;
  const select = document.getElementById("registration_select");
  const gamertag = select.selectedOptions[0] ? select.selectedOptions[0].dataset.gamertag : "";
  const submitBtn = form.querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.textContent = "Scanning…";

  try {
    const formData = new FormData(form);
    formData.append("tournament_id", tournamentId);
    formData.append("gamertag", gamertag);
    const result = await MatchGuardAPI.submitScan(formData);

    const verdictHtml =
      result.verdict === "clear"
        ? `<div class="alert alert-success">Scan complete: <strong>CLEAR</strong>. Certificate: <a href="${result.certificate_url}" target="_blank">view</a></div>`
        : `<div class="alert alert-error">Scan complete: <strong>FLAGGED</strong> (matched: ${result.matched_signatures.join(", ")})</div>`;
    successBox.innerHTML = verdictHtml;
    await loadRegistrations();
  } catch (err) {
    errorBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Run scan";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await renderHeader();
  await loadRegistrations();
  document.getElementById("purchase-btn").addEventListener("click", handlePurchase);
  document.getElementById("register-form").addEventListener("submit", handleRegisterSubmit);
  document.getElementById("scan-form").addEventListener("submit", handleScanSubmit);
});
