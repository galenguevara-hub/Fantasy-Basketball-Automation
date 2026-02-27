async function fetchJson(url, init) {
    const response = await fetch(url, {
        ...init,
        headers: {
            "Content-Type": "application/json",
            ...(init?.headers ?? {})
        }
    });
    if (!response.ok) {
        let detail = `${response.status} ${response.statusText}`;
        try {
            const payload = (await response.json());
            if (payload?.error) {
                detail = payload.error;
            }
        }
        catch {
            // ignore JSON parsing failures
        }
        throw new Error(detail);
    }
    return (await response.json());
}
export function getConfig(signal) {
    return fetchJson("/api/config", { signal });
}
export function saveConfig(leagueId) {
    return fetchJson("/api/config", {
        method: "POST",
        body: JSON.stringify({ league_id: leagueId })
    });
}
export function refreshStandings() {
    return fetchJson("/refresh", {
        method: "POST"
    });
}
export function getOverview(signal) {
    return fetchJson("/api/overview", { signal });
}
export function getAnalysis(team, signal) {
    const query = team ? `?team=${encodeURIComponent(team)}` : "";
    return fetchJson(`/api/analysis${query}`, { signal });
}
export function getGamesPlayed(params) {
    const search = new URLSearchParams();
    if (params.start)
        search.set("start", params.start);
    if (params.end)
        search.set("end", params.end);
    if (params.totalGames)
        search.set("total_games", params.totalGames);
    const query = search.toString();
    const url = query ? `/api/games-played?${query}` : "/api/games-played";
    return fetchJson(url, { signal: params.signal });
}
