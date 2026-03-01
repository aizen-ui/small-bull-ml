export interface Stock {
  id: number;
  symbol: string;
  indianapi_name: string | null;
  company_name: string;
  sector: string | null;
  industry: string | null;
  market_cap_category: string | null;
  is_nifty50: boolean;
  is_active: boolean;
}

export interface DailyPrice {
  id: number;
  stock_id: number;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface IntradayPrice {
  id: number;
  stock_id: number;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Prediction {
  id: number;
  stock_id: number;
  prediction_timestamp: string;
  prediction_type: "nightly" | "minute";
  model_version: string;
  predicted_direction: "up" | "down" | "neutral";
  predicted_pct_change: number;
  confidence_score: number;
  top_features: string | null;
  actual_direction: string | null;
  actual_pct_change: number | null;
  was_correct: boolean | null;
  stock?: Stock;
}

export interface ModelPerformance {
  id: number;
  model_version: string;
  evaluation_date: string;
  prediction_type: string;
  accuracy: number;
  precision_up: number;
  recall_up: number;
  f1_up: number;
  mae: number;
  rmse: number;
  directional_accuracy: number;
  accuracy_7d: number | null;
  accuracy_30d: number | null;
  total_predictions: number | null;
  correct_predictions: number | null;
}

export interface SentimentScore {
  id: number;
  stock_id: number;
  date: string;
  score: number;
  source: string | null;
}

export interface MarketContext {
  id: number;
  date: string;
  nifty50_close: number | null;
  nifty50_change_pct: number | null;
  top_gainers: any;
  top_losers: any;
  price_shockers: any;
  most_active_nse: any;
  market_breadth_score: number | null;
}

export interface PipelineRun {
  id: number;
  pipeline_name: string;
  status: "running" | "success" | "failed";
  started_at: string;
  finished_at: string | null;
  details: any;
  error_message: string | null;
}
