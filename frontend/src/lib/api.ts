// mirrors backend/app/models.py, snake_case kept as-is to match the Pydantic models

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface HoldingInput {
  ticker: string;
  /** Fraction of the portfolio, e.g. 0.25 for 25%. */
  weight: number;
}

export interface AnalyzeRequest {
  holdings: HoldingInput[];
  lookback_years: number;
}

export interface HoldingStats {
  ticker: string;
  weight: number;
  annual_return: number;
  annual_volatility: number;
  sharpe_ratio: number;
}

export interface PortfolioStats {
  annual_return: number;
  annual_volatility: number;
  sharpe_ratio: number;
  value_at_risk_95: number;
}

export interface CorrelationMatrix {
  tickers: string[];
  matrix: number[][];
}

export interface FrontierPoint {
  annual_return: number;
  annual_volatility: number;
}

export interface OptimalPortfolio {
  annual_return: number;
  annual_volatility: number;
  sharpe_ratio: number;
  weights: Record<string, number>;
}

export interface EfficientFrontier {
  points: FrontierPoint[];
  user_portfolio: FrontierPoint;
  max_sharpe: OptimalPortfolio;
  min_volatility: OptimalPortfolio;
}

export interface MonteCarloBand {
  day: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface MonteCarloResult {
  starting_value: number;
  bands: MonteCarloBand[];
  value_at_risk_95: number;
}

export interface BreakdownSlice {
  label: string;
  weight: number;
}

export interface FactorBreakdown {
  sector: BreakdownSlice[];
  market_cap: BreakdownSlice[];
  concentration_warnings: BreakdownSlice[];
}

export interface AnalyzeResponse {
  holdings: HoldingStats[];
  portfolio: PortfolioStats;
  correlation: CorrelationMatrix;
  efficient_frontier: EfficientFrontier;
  monte_carlo: MonteCarloResult;
  factor_breakdown: FactorBreakdown;
  skipped_tickers: string[];
  lookback_years: number;
}

export interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
}

export interface TickerSearchResponse {
  results: TickerSearchResult[];
}

export type BacktestPeriod = "gfc_2008" | "covid_2020" | "rate_hikes_2022" | "custom";

export interface BacktestRequest {
  holdings: HoldingInput[];
  period: BacktestPeriod;
  start_date?: string; // YYYY-MM-DD, required when period === "custom"
  end_date?: string;
}

export interface BacktestResponse {
  period_label: string;
  start_date: string;
  end_date: string;
  dates: string[];
  portfolio_path: number[];
  benchmark_path: number[];
  portfolio_total_return: number;
  benchmark_total_return: number;
  portfolio_max_drawdown: number;
  benchmark_max_drawdown: number;
  alpha: number;
  beta: number;
  skipped_tickers: string[];
}

export interface CurrentHolding {
  ticker: string;
  weight: number;
  current_value: number;
}

export interface RebalanceRequest {
  holdings: CurrentHolding[];
  total_value: number;
}

export interface RebalanceOrder {
  ticker: string;
  action: "buy" | "sell";
  shares: number;
  price: number;
  dollar_amount: number;
  current_value: number;
  target_value: number;
}

export interface RebalanceResponse {
  orders: RebalanceOrder[];
  leftover_cash: number;
  total_value: number;
  skipped_tickers: string[];
}

export type RiskProfile = "conservative" | "balanced" | "growth" | "aggressive";

export interface AIInsightsRequest {
  holdings: HoldingInput[];
  annual_return: number;
  annual_volatility: number;
  sharpe_ratio: number;
  sector_breakdown: BreakdownSlice[];
  correlation: CorrelationMatrix;
}

export interface AIInsightsResponse {
  insights: string[];
  source: "llm" | "rule_based";
}

export interface TickerResearchResponse {
  ticker: string;
  name: string;
  sector: string;
  market_cap_bucket: string;
  trailing_pe: number | null;
  summary: string;
  source: "llm" | "rule_based";
}

export interface HoldingPerformance {
  ticker: string;
  annual_return: number;
  annual_volatility: number;
}

export interface SuggestedAllocationRequest {
  holdings: HoldingPerformance[];
  risk_profile: RiskProfile;
}

export interface SuggestedAllocationResponse {
  risk_profile: RiskProfile;
  weights: Record<string, number>;
  rationale: string;
}

export interface ExportRequest {
  analysis: AnalyzeResponse;
  ai_insights?: string[] | null;
}

export interface ShockSimulationRequest {
  holdings: HoldingInput[];
  origin_ticker: string;
  /** Negative fraction, e.g. -0.15 for a -15% shock. */
  shock_magnitude: number;
  decay_factor: number;
  lookback_years: number;
}

export type ContagionStatus = "healthy" | "at_risk" | "critical";

export interface GraphNode {
  ticker: string;
  weight: number;
  sector: string;
  annual_return: number;
  hop_distance: number | null;
  /** 0 (unaffected) to 1 (the shock origin itself). */
  impact_score: number;
  /** Estimated price change as a fraction, e.g. -0.06 for -6%. */
  price_drawdown: number;
  status: ContagionStatus;
}

export interface GraphEdge {
  source: string;
  target: string;
  correlation: number;
}

export interface ContagionSummary {
  origin_ticker: string;
  shock_magnitude: number;
  decay_factor: number;
  total_portfolio_drawdown: number;
  highest_risk_secondary: GraphNode[];
  risk_narrative: string;
  narrative_source: "llm" | "rule_based";
}

export interface ShockSimulationResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: ContagionSummary;
  skipped_tickers: string[];
}

type FastApiErrorBody = { detail?: string | Array<{ msg: string; loc?: unknown[] }> };

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function extractErrorMessage(body: FastApiErrorBody, fallback: string): string {
  if (!body.detail) return fallback;
  if (typeof body.detail === "string") return body.detail;
  return body.detail.map((e) => e.msg).join("; ") || fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(
      "Couldn't reach the PortfolioLens API. Is the backend running on " +
        `${API_BASE_URL}?`,
      0,
    );
  }

  if (!response.ok) {
    let body: FastApiErrorBody = {};
    try {
      body = await response.json();
    } catch {
      // ignore, fall through to generic message
    }
    throw new ApiError(
      extractErrorMessage(body, `Request failed with status ${response.status}`),
      response.status,
    );
  }

  return response.json() as Promise<T>;
}

export async function searchTickers(
  query: string,
  options?: { signal?: AbortSignal },
): Promise<TickerSearchResult[]> {
  if (!query.trim()) return [];
  const { results } = await request<TickerSearchResponse>(
    `/api/tickers/search?q=${encodeURIComponent(query)}`,
    { signal: options?.signal },
  );
  return results;
}

export async function analyzePortfolio(
  body: AnalyzeRequest,
  options?: { signal?: AbortSignal },
): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/api/portfolio/analyze", {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
  });
}

export async function backtestPortfolio(
  body: BacktestRequest,
  options?: { signal?: AbortSignal },
): Promise<BacktestResponse> {
  return request<BacktestResponse>("/api/portfolio/backtest", {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
  });
}

export async function rebalancePortfolio(
  body: RebalanceRequest,
  options?: { signal?: AbortSignal },
): Promise<RebalanceResponse> {
  return request<RebalanceResponse>("/api/portfolio/rebalance", {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
  });
}

export async function getAIInsights(
  body: AIInsightsRequest,
  options?: { signal?: AbortSignal },
): Promise<AIInsightsResponse> {
  return request<AIInsightsResponse>("/api/ai/insights", {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
  });
}

export async function getTickerResearch(
  ticker: string,
  options?: { signal?: AbortSignal },
): Promise<TickerResearchResponse> {
  return request<TickerResearchResponse>(`/api/ai/research?ticker=${encodeURIComponent(ticker)}`, {
    signal: options?.signal,
  });
}

export async function getSuggestedAllocation(
  body: SuggestedAllocationRequest,
  options?: { signal?: AbortSignal },
): Promise<SuggestedAllocationResponse> {
  return request<SuggestedAllocationResponse>("/api/ai/suggested-allocation", {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
  });
}

// binary response, so this skips the request<T>() JSON helper
async function downloadFile(path: string, body: ExportRequest, filename: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(`Couldn't reach the PortfolioLens API. Is the backend running on ${API_BASE_URL}?`, 0);
  }

  if (!response.ok) {
    throw new ApiError(`Export failed with status ${response.status}`, response.status);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function simulateShock(
  body: ShockSimulationRequest,
  options?: { signal?: AbortSignal },
): Promise<ShockSimulationResponse> {
  return request<ShockSimulationResponse>("/api/v1/simulate-shock", {
    method: "POST",
    body: JSON.stringify(body),
    signal: options?.signal,
  });
}

export function exportCsv(body: ExportRequest): Promise<void> {
  return downloadFile("/api/portfolio/export/csv", body, "portfoliolens-report.csv");
}

export function exportPdf(body: ExportRequest): Promise<void> {
  return downloadFile("/api/portfolio/export/pdf", body, "portfoliolens-report.pdf");
}
