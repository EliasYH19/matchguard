/*
  MatchGuard - tiny fetch wrapper shared by every page.

  We talk to the backend through relative /api/... paths. In production
  (and in docker-compose) nginx sits in front of the two Flask
  microservices and reverse-proxies /api/tournaments, /api/packages and
  /api/registrations to tournament-service, and /api/scans to
  scan-service - see frontend/nginx.conf. The browser never needs to know
  there even are two separate services.

  Author: Elias
*/

const MatchGuardAPI = (() => {
  async function request(path, options = {}) {
    const res = await fetch(path, options);
    let body = null;
    try {
      body = await res.json();
    } catch (e) {
      // some responses (like the local-blob file server) aren't JSON
    }
    if (!res.ok) {
      const message = (body && body.error) || `Request to ${path} failed with ${res.status}`;
      throw new Error(message);
    }
    return body;
  }

  return {
    getPackages: () => request("/api/packages"),
    getTournaments: () => request("/api/tournaments"),
    getTournament: (id) => request(`/api/tournaments/${id}`),
    createTournament: (formData) =>
      request("/api/tournaments", { method: "POST", body: formData }),
    purchasePackage: (tournamentId) =>
      request(`/api/tournaments/${tournamentId}/purchase`, { method: "POST" }),
    getRegistrations: (tournamentId) =>
      request(`/api/tournaments/${tournamentId}/registrations`),
    registerPlayer: (tournamentId, gamertag, email) =>
      request(`/api/tournaments/${tournamentId}/registrations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gamertag, email }),
      }),
    submitScan: (formData) =>
      request("/api/scans", { method: "POST", body: formData }),
    getFlaggedScans: (tournamentId) =>
      request(`/api/scans/flagged${tournamentId ? `?tournament_id=${tournamentId}` : ""}`),
    getScansForTournament: (tournamentId) =>
      request(`/api/scans/tournament/${tournamentId}`),
  };
})();
