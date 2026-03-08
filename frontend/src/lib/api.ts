import type {
  AnalysisPayload,
  AuthPayload,
  ConfigPayload,
  ExecutiveSummaryPayload,
  GamesPlayedPayload,
  OverviewPayload
} from "./types";

export class ApiError extends Error {
  status: number;
  retryAfter?: number;
  constructor(status: number, message: string, retryAfter?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    let retryAfter: number | undefined;
    try {
      const payload = (await response.json()) as { error?: string; retry_after?: number };
      if (payload?.error) {
        detail = payload.error;
      }
      if (payload?.retry_after) {
        retryAfter = payload.retry_after;
      }
    } catch {
      // ignore JSON parsing failures
    }
    throw new ApiError(response.status, detail, retryAfter);
  }

  return (await response.json()) as T;
}

export function getAuthStatus(signal?: AbortSignal) {
  return fetchJson<AuthPayload>("/api/auth/status", { signal });
}

export function logout() {
  return fetchJson<{ status: string }>("/logout", { method: "POST" });
}

export function submitAuthCode(code: string) {
  return fetchJson<{ status: string; user_name: string }>("/auth/code", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export function getConfig(signal?: AbortSignal) {
  return fetchJson<ConfigPayload>("/api/config", { signal });
}

export function saveConfig(leagueId: string) {
  return fetchJson<{ status: string; league_id: string }>("/api/config", {
    method: "POST",
    body: JSON.stringify({ league_id: leagueId })
  });
}

export function refreshStandings() {
  return fetchJson<{ status: string; teams_updated?: number }>("/refresh", {
    method: "POST"
  });
}

export function getOverview(signal?: AbortSignal) {
  return fetchJson<OverviewPayload>("/api/overview", { signal });
}

export function getAnalysis(team?: string, signal?: AbortSignal) {
  const query = team ? `?team=${encodeURIComponent(team)}` : "";
  return fetchJson<AnalysisPayload>(`/api/analysis${query}`, { signal });
}

export function getGamesPlayed(params: {
  start?: string;
  end?: string;
  totalGames?: string;
  signal?: AbortSignal;
}) {
  const search = new URLSearchParams();
  if (params.start) search.set("start", params.start);
  if (params.end) search.set("end", params.end);
  if (params.totalGames) search.set("total_games", params.totalGames);

  const query = search.toString();
  const url = query ? `/api/games-played?${query}` : "/api/games-played";
  return fetchJson<GamesPlayedPayload>(url, { signal: params.signal });
}

export function getExecutiveSummary(team?: string, signal?: AbortSignal) {
  const search = new URLSearchParams();
  if (team) {
    search.set("team", team);
  }
  const query = search.toString();
  const url = query ? `/api/executive-summary?${query}` : "/api/executive-summary";
  return fetchJson<ExecutiveSummaryPayload>(url, { signal });
}
