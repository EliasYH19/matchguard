// Organizer dashboard logic - flagged players feed + basic stats
// Author: Elias

async function populateTournamentFilter() {
  const select = document.getElementById("tournament-filter");
  try {
    const tournaments = await MatchGuardAPI.getTournaments();
    tournaments.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      select.appendChild(opt);
    });
  } catch (err) {
    // non-fatal, filter just stays as "All tournaments"
  }
}

function renderStats(flagged) {
  const statsBox = document.getElementById("dashboard-stats");
  const uniqueTournaments = new Set(flagged.map((s) => s.tournament_id)).size;
  statsBox.innerHTML = `
    <div class="stat-box"><div class="num">${flagged.length}</div><div class="label">Flagged scans</div></div>
    <div class="stat-box"><div class="num">${uniqueTournaments}</div><div class="label">Tournaments affected</div></div>
  `;
}

async function loadFlagged() {
  const wrap = document.getElementById("flagged-table-wrap");
  const errorBox = document.getElementById("dashboard-error");
  const tournamentId = document.getElementById("tournament-filter").value;
  try {
    const flagged = await MatchGuardAPI.getFlaggedScans(tournamentId || null);
    renderStats(flagged);

    if (flagged.length === 0) {
      wrap.innerHTML = `<div class="empty-state">No flagged players yet - either nobody's cheating, or nobody's scanned yet.</div>`;
      return;
    }

    wrap.innerHTML = `
      <table>
        <thead>
          <tr><th>Player</th><th>Tournament</th><th>Matched signatures</th><th>File</th><th>Submitted</th><th>Evidence</th></tr>
        </thead>
        <tbody>
          ${flagged
            .map(
              (s) => `
            <tr>
              <td>${s.gamertag}</td>
              <td><a href="tournament.html?id=${s.tournament_id}">${s.tournament_id.slice(0, 8)}&hellip;</a></td>
              <td>${s.matched_signatures.join(", ")}</td>
              <td>${s.filename}</td>
              <td>${new Date(s.created_at).toLocaleString()}</td>
              <td><a href="${s.evidence_url}" target="_blank">view</a></td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    `;
  } catch (err) {
    errorBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await populateTournamentFilter();
  await loadFlagged();
  document.getElementById("tournament-filter").addEventListener("change", loadFlagged);
});
