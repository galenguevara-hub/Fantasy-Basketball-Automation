export type JsonRecord = Record<string, unknown>;

export interface AuthPayload {
  authenticated: boolean;
  user_name?: string;
}

export interface ConfigPayload {
  league_id: string;
  has_session: boolean;
}

export interface TeamRow extends JsonRecord {
  team_name: string;
  rank: number | null;
  total_points: number | null;
  stats: Record<string, string | number | null>;
  roto_points: Record<string, string | number | null>;
}

export interface OverviewPayload {
  has_data: boolean;
  league_id: string;
  scraped_at: string | null;
  categories: string[];
  teams: TeamRow[];
  per_game_rows: JsonRecord[];
  ranking_rows: JsonRecord[];
}

export interface AnalysisCategory extends JsonRecord {
  category: string;
  display: string;
  tag: "TARGET" | "DEFEND" | null;
  is_target: boolean;
  is_defend: boolean;
  value: number | null;
  rank: number | null;
  next_better_team: string | null;
  next_better_value: number | null;
  gap_up: number | null;
  z_gap_up: number | null;
  next_worse_team: string | null;
  next_worse_value: number | null;
  gap_down: number | null;
  z_gap_down: number | null;
  target_score: number | null;
}

export interface AnalysisPayload {
  has_data: boolean;
  league_id: string;
  scraped_at: string | null;
  team_names: string[];
  selected_team: string | null;
  analysis: AnalysisCategory[];
  team_cluster: Record<string, JsonRecord>;
  team_pg_rank: Record<string, string>;
  league_summary: JsonRecord[];
}

export interface GamesPlayedPayload {
  has_data: boolean;
  league_id: string;
  scraped_at: string | null;
  rows: JsonRecord[];
  start_str: string;
  end_str: string;
  total_games: number;
  elapsed_days: number | null;
  remaining_days: number | null;
  date_valid: boolean;
  date_error: string | null;
}
