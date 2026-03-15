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
  category_config?: CategoryMeta[];
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

export interface GapChartRow {
  category: string;
  display: string;
  key: string;
  higher_is_better: boolean;
  is_percentage: boolean;
  my_value: number;
  above_team: string | null;
  above_value: number | null;
  below_team: string | null;
  below_value: number | null;
  league_min: number;
  league_max: number;
  my_zscore: number | null;
  above_zscore: number | null;
  below_zscore: number | null;
  z_min: number | null;
  z_max: number | null;
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
  gap_chart: GapChartRow[];
}

export interface CategoryMeta {
  key: string;
  display: string;
  stat_id: number;
  higher_is_better: boolean;
  is_percentage: boolean;
  per_game_key: string | null;
  per_game_display: string;
  rank_key: string;
}

export interface CountingCategoryMeta {
  key: string;
  display: string;
}

export interface GamesPlayedPayload {
  has_data: boolean;
  league_id: string;
  scraped_at: string | null;
  rows: JsonRecord[];
  projected_totals: JsonRecord[];
  projected_ranks: JsonRecord[];
  counting_categories: CountingCategoryMeta[];
  start_str: string;
  end_str: string;
  total_games: number;
  elapsed_days: number | null;
  remaining_days: number | null;
  date_valid: boolean;
  date_error: string | null;
}

export interface TrendsCategoryInfo {
  key: string;
  display: string;
  higher_is_better: boolean;
  is_percentage: boolean;
}

export interface TrendsCategoryStat {
  value: number | null;
  vs_own_avg: number | null;
  vs_league_best: number | null;
  league_best_value: number | null;
  league_best_team: string | null;
  trend: "up" | "down" | "flat";
}

export interface TrendsWindowData {
  available: boolean;
  actual_days: number;
  categories: Record<string, TrendsCategoryStat>;
}

export interface TrendsChartPoint {
  date: string;
  teams: Record<string, Record<string, number | null>>;
}

export interface TrendsPayload {
  has_data: boolean;
  snapshot_coverage?: {
    first_date: string;
    last_date: string;
    total_snapshots: number;
  };
  team_names: string[];
  selected_team: string | null;
  scorecard?: {
    windows: Record<string, TrendsWindowData>;
  };
  chart_data?: TrendsChartPoint[];
  categories?: TrendsCategoryInfo[];
  season_averages?: Record<string, Record<string, number | null>>;
}

export interface ExecutiveSummaryPayload {
  has_data: boolean;
  league_id: string;
  scraped_at: string | null;
  team_names: string[];
  selected_team: string | null;
  summary_card: JsonRecord;
  per_game_vs_raw_rows: JsonRecord[];
  per_game_vs_raw_label: string | null;
  category_opportunities: JsonRecord[];
  best_categories_to_target: JsonRecord[];
  categories_at_risk: JsonRecord[];
  multi_point_swings: JsonRecord[];
  games_pace: JsonRecord;
  nearby_teams: JsonRecord[];
  nearby_team_insights: string[];
  projected_standings: JsonRecord[];
  projected_finish: number | null;
  category_competition: JsonRecord[];
  category_stability: JsonRecord[];
  high_leverage_categories: string[];
  actionable_insights: JsonRecord[];
  trade_hints: string[];
  momentum: JsonRecord;
  start_str: string;
  end_str: string;
  total_games: number;
  date_error: string | null;
}
