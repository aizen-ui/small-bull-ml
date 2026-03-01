"use client";

import { useEffect, useState, useCallback } from "react";
import { createBrowserClient } from "@/lib/supabase";
import type { Stock, SentimentScore } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Headline {
  title: string;
  score: number;
  category?: string;
  timestamp?: string;
  link?: string;
  source?: string;
  date?: string;
}

interface SentimentBucket {
  weighted_sentiment: number;
  avg_sentiment: number;
  max_sentiment: number;
  min_sentiment: number;
  news_count: number;
}

interface StockSentimentData {
  symbol: string;
  company_name: string;
  sector: string;
  overall: SentimentBucket;
  stock_sentiment: SentimentBucket;
  industry_sentiment: SentimentBucket;
  market_sentiment: SentimentBucket;
  headlines: Headline[];
  indianapi_news: Headline[];
  history: { date: string; weighted_sentiment: number; avg_sentiment: number; news_count: number }[];
  is_weekday: boolean;
}

interface MarketSentimentData {
  label: string;
  overall: SentimentBucket;
  headlines: Headline[];
  trending: any;
  nifty_history: { date: string; nifty50_close: number; nifty50_change_pct: number; market_breadth_score: number }[];
}

// Heatmap data from Supabase
interface HeatmapEntry {
  stock_id: number;
  symbol: string;
  weighted_sentiment: number;
}

export default function SentimentPage() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>(""); // "" = market/nifty
  const [loading, setLoading] = useState(false);
  const [stockSentiment, setStockSentiment] = useState<StockSentimentData | null>(null);
  const [marketSentiment, setMarketSentiment] = useState<MarketSentimentData | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapEntry[]>([]);
  const [error, setError] = useState("");

  // Load stocks + heatmap from Supabase
  useEffect(() => {
    const supabase = createBrowserClient();
    async function init() {
      const [{ data: stocksData }, { data: sentiments }] = await Promise.all([
        supabase.from("stocks").select("*").eq("is_active", true).order("symbol"),
        supabase.from("sentiment_scores").select("*").order("date", { ascending: false }).limit(500),
      ]);

      if (stocksData) setStocks(stocksData);

      // Build heatmap: latest sentiment per stock
      if (sentiments && stocksData) {
        const stockMap = new Map<number, Stock>();
        stocksData.forEach((s: Stock) => stockMap.set(s.id, s));

        const latest = new Map<number, SentimentScore>();
        sentiments.forEach((s: SentimentScore) => {
          if (!latest.has(s.stock_id)) latest.set(s.stock_id, s);
        });

        const entries: HeatmapEntry[] = Array.from(latest.values())
          .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
          .map((s) => ({
            stock_id: s.stock_id,
            symbol: stockMap.get(s.stock_id)?.symbol.replace(".NS", "").replace(".BO", "") || `#${s.stock_id}`,
            weighted_sentiment: s.score ?? 0,
          }));
        setHeatmap(entries);
      }
    }
    init();
  }, []);

  // Fetch sentiment when selection changes
  const fetchSentiment = useCallback(async () => {
    setLoading(true);
    setError("");
    setStockSentiment(null);
    setMarketSentiment(null);

    try {
      if (selectedSymbol) {
        // Stock-specific sentiment
        const res = await fetch(`${API_BASE}/api/sentiment/${encodeURIComponent(selectedSymbol)}`);
        const data = await res.json();
        if (res.ok) {
          setStockSentiment(data);
        } else {
          setError(data.error || "Failed to fetch sentiment");
        }
      } else {
        // Market / Nifty sentiment
        const res = await fetch(`${API_BASE}/api/sentiment/market`);
        const data = await res.json();
        if (res.ok) {
          setMarketSentiment(data);
        } else {
          setError(data.error || "Failed to fetch market sentiment");
        }
      }
    } catch (e: any) {
      setError(`API server not reachable. Run 'python app.py serve'. (${e.message})`);
    } finally {
      setLoading(false);
    }
  }, [selectedSymbol]);

  // Auto-fetch sentiment on mount and when selection changes
  useEffect(() => {
    fetchSentiment();
  }, [fetchSentiment]);

  const sentimentColor = (score: number) => {
    if (score > 0.05) return "text-[#26a69a]";
    if (score < -0.05) return "text-[#ef5350]";
    return "text-[#787b86]";
  };

  const sentimentBg = (score: number) => {
    if (score > 0.1) return "bg-[#26a69a]/15 border-[#26a69a]/30";
    if (score > 0.05) return "bg-[#26a69a]/8 border-[#26a69a]/20";
    if (score < -0.1) return "bg-[#ef5350]/15 border-[#ef5350]/30";
    if (score < -0.05) return "bg-[#ef5350]/8 border-[#ef5350]/20";
    return "bg-[#2a2e39] border-[#2a2e39]";
  };

  const sentimentLabel = (score: number) => {
    if (score > 0.15) return "Very Bullish";
    if (score > 0.05) return "Bullish";
    if (score < -0.15) return "Very Bearish";
    if (score < -0.05) return "Bearish";
    return "Neutral";
  };

  const sentimentEmoji = (score: number) => {
    if (score > 0.1) return "▲";
    if (score > 0.05) return "△";
    if (score < -0.1) return "▼";
    if (score < -0.05) return "▽";
    return "●";
  };

  // Render a sentiment score card
  const ScoreCard = ({ label, bucket }: { label: string; bucket: SentimentBucket }) => (
    <div className={`tv-card p-3 border ${sentimentBg(bucket.weighted_sentiment)}`}>
      <p className="text-[10px] text-[#787b86] uppercase tracking-wider">{label}</p>
      <div className="flex items-baseline gap-2 mt-1">
        <span className={`text-xl font-bold font-tabular ${sentimentColor(bucket.weighted_sentiment)}`}>
          {bucket.weighted_sentiment > 0 ? "+" : ""}
          {bucket.weighted_sentiment.toFixed(4)}
        </span>
        <span className={`text-xs font-medium ${sentimentColor(bucket.weighted_sentiment)}`}>
          {sentimentLabel(bucket.weighted_sentiment)}
        </span>
      </div>
      <div className="flex gap-3 mt-1.5 text-[10px] text-[#787b86]">
        <span>avg: {bucket.avg_sentiment.toFixed(4)}</span>
        <span>min: {bucket.min_sentiment.toFixed(4)}</span>
        <span>max: {bucket.max_sentiment.toFixed(4)}</span>
        <span>{bucket.news_count} articles</span>
      </div>
    </div>
  );

  // Render headline list
  const HeadlineList = ({ headlines, title, emptyText }: {
    headlines: Headline[];
    title: string;
    emptyText: string;
  }) => (
    <div className="tv-card">
      <div className="tv-card-header">
        <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">{title}</span>
        <span className="text-[10px] text-[#787b86]">{headlines.length} items</span>
      </div>
      <div className="p-3 space-y-1.5 max-h-[400px] overflow-y-auto">
        {headlines.length === 0 && (
          <p className="text-xs text-[#787b86] py-4 text-center">{emptyText}</p>
        )}
        {headlines.map((h, i) => (
          <div key={i} className="flex items-start gap-2 text-xs py-1 border-b border-[#1e222d] last:border-0">
            <span className={`font-tabular font-bold w-12 text-right shrink-0 ${sentimentColor(h.score)}`}>
              {h.score > 0 ? "+" : ""}{h.score.toFixed(3)}
            </span>
            <div className="flex-1 min-w-0">
              {h.link ? (
                <a href={h.link} target="_blank" rel="noopener noreferrer"
                  className="text-[#d1d4dc] hover:text-[#5b9cf6] transition-colors break-words">
                  {h.title}
                </a>
              ) : (
                <span className="text-[#d1d4dc] break-words">{h.title}</span>
              )}
              <div className="flex gap-2 mt-0.5">
                {h.category && (
                  <span className={`text-[10px] px-1 rounded ${
                    h.category === "stock" ? "bg-[#2962ff]/20 text-[#5b9cf6]" :
                    h.category === "industry" ? "bg-[#ff9800]/20 text-[#ff9800]" :
                    "bg-[#787b86]/20 text-[#787b86]"
                  }`}>
                    {h.category}
                  </span>
                )}
                {h.source && <span className="text-[10px] text-[#787b86]">{h.source}</span>}
                {h.timestamp && (
                  <span className="text-[10px] text-[#787b86]">
                    {new Date(h.timestamp).toLocaleDateString([], { month: "short", day: "numeric" })}
                  </span>
                )}
                {h.date && !h.timestamp && (
                  <span className="text-[10px] text-[#787b86]">{h.date}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // Sentiment history mini-chart (text-based sparkline)
  const SentimentHistory = ({ history }: {
    history: { date: string; weighted_sentiment: number; news_count: number }[];
  }) => {
    if (history.length === 0) return null;
    const reversed = [...history].reverse();
    const max = Math.max(0.2, ...reversed.map((h) => Math.abs(h.weighted_sentiment)));
    return (
      <div className="tv-card">
        <div className="tv-card-header">
          <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
            Sentiment History (30d)
          </span>
        </div>
        <div className="p-3">
          <div className="flex items-end gap-0.5" style={{ height: "80px" }}>
            {reversed.map((h, i) => {
              const val = h.weighted_sentiment;
              const heightPct = Math.min(100, (Math.abs(val) / max) * 100);
              const color = val > 0.05 ? "#26a69a" : val < -0.05 ? "#ef5350" : "#787b86";
              return (
                <div
                  key={i}
                  className="flex-1 flex flex-col justify-end items-center"
                  title={`${h.date}: ${val > 0 ? "+" : ""}${val.toFixed(4)} (${h.news_count} articles)`}
                >
                  <div
                    style={{
                      height: `${Math.max(2, heightPct)}%`,
                      backgroundColor: color,
                      opacity: 0.7,
                    }}
                    className="w-full rounded-t-sm min-h-[2px]"
                  />
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-[10px] text-[#787b86] mt-1">
            <span>{reversed[0]?.date}</span>
            <span>{reversed[reversed.length - 1]?.date}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Header + controls */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-sm font-semibold text-[#e0e3eb] uppercase tracking-wider">
          Sentiment Analysis
        </h1>
        <div className="flex items-center gap-3">
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="bg-[#1e222d] border border-[#2a2e39] text-[#e0e3eb] text-xs rounded px-3 py-2 focus:border-[#2962ff] focus:outline-none min-w-[220px]"
          >
            <option value="">Nifty / Market Overview</option>
            {stocks.map((s) => {
              const clean = s.symbol.replace(".NS", "").replace(".BO", "");
              return (
                <option key={s.id} value={clean}>
                  {clean} — {s.company_name}
                </option>
              );
            })}
          </select>
          <button
            onClick={fetchSentiment}
            disabled={loading}
            className={`px-5 py-2 text-xs font-semibold rounded transition-colors ${
              loading
                ? "bg-[#2a2e39] text-[#787b86] cursor-not-allowed"
                : "bg-[#2962ff] text-white hover:bg-[#2962ff]/80"
            }`}
          >
            {loading ? "Analyzing..." : "Analyze Sentiment"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="tv-card p-3 border border-[#ef5350]/30 bg-[#ef5350]/5">
          <p className="text-xs text-[#ef5350]">{error}</p>
        </div>
      )}

      {/* === MARKET / NIFTY VIEW (default) === */}
      {!selectedSymbol && marketSentiment && (
        <>
          {/* Market sentiment banner */}
          <div className={`tv-card border p-5 ${sentimentBg(marketSentiment.overall.weighted_sentiment)}`}>
            <div className="flex items-center gap-4">
              <div>
                <p className="text-[10px] text-[#787b86] uppercase">Market Sentiment</p>
                <p className={`text-3xl font-black mt-1 ${sentimentColor(marketSentiment.overall.weighted_sentiment)}`}>
                  {sentimentEmoji(marketSentiment.overall.weighted_sentiment)}{" "}
                  {marketSentiment.label}
                </p>
              </div>
              <div className="ml-auto text-right">
                <p className={`text-2xl font-bold font-tabular ${sentimentColor(marketSentiment.overall.weighted_sentiment)}`}>
                  {marketSentiment.overall.weighted_sentiment > 0 ? "+" : ""}
                  {marketSentiment.overall.weighted_sentiment.toFixed(4)}
                </p>
                <p className="text-[10px] text-[#787b86] mt-0.5">
                  {marketSentiment.overall.news_count} articles analyzed
                </p>
              </div>
            </div>
          </div>

          {/* Nifty history */}
          {marketSentiment.nifty_history.length > 0 && (
            <div className="tv-card">
              <div className="tv-card-header">
                <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
                  Nifty 50 Recent History
                </span>
              </div>
              <div className="p-3">
                <div className="flex items-end gap-0.5" style={{ height: "80px" }}>
                  {[...marketSentiment.nifty_history].reverse().map((h, i) => {
                    const val = h.nifty50_change_pct || 0;
                    const max = Math.max(2, ...marketSentiment.nifty_history.map((x) => Math.abs(x.nifty50_change_pct || 0)));
                    const heightPct = Math.min(100, (Math.abs(val) / max) * 100);
                    const color = val > 0 ? "#26a69a" : val < 0 ? "#ef5350" : "#787b86";
                    return (
                      <div
                        key={i}
                        className="flex-1 flex flex-col justify-end items-center"
                        title={`${h.date}: ${val > 0 ? "+" : ""}${val.toFixed(2)}% | Nifty: ${h.nifty50_close}`}
                      >
                        <div
                          style={{ height: `${Math.max(2, heightPct)}%`, backgroundColor: color, opacity: 0.7 }}
                          className="w-full rounded-t-sm min-h-[2px]"
                        />
                      </div>
                    );
                  })}
                </div>
                <div className="flex justify-between text-[10px] text-[#787b86] mt-1">
                  <span>{marketSentiment.nifty_history[marketSentiment.nifty_history.length - 1]?.date}</span>
                  <span>{marketSentiment.nifty_history[0]?.date}</span>
                </div>
              </div>
            </div>
          )}

          {/* Trending stocks from IndianAPI */}
          {marketSentiment.trending && (
            <div className="grid md:grid-cols-2 gap-4">
              {marketSentiment.trending.top_gainers && (
                <div className="tv-card">
                  <div className="tv-card-header">
                    <span className="text-xs font-medium text-[#26a69a] uppercase tracking-wider">
                      Top Gainers
                    </span>
                  </div>
                  <div className="p-3 space-y-1">
                    {(Array.isArray(marketSentiment.trending.top_gainers)
                      ? marketSentiment.trending.top_gainers
                      : []
                    ).slice(0, 8).map((g: any, i: number) => (
                      <div key={i} className="flex justify-between text-xs py-0.5">
                        <span className="text-[#d1d4dc] font-medium">{g.symbol || g.company_name || g.name || "—"}</span>
                        <span className="text-[#26a69a] font-tabular">
                          +{parseFloat(g.change_percentage || g.percent_change || "0").toFixed(2)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {marketSentiment.trending.top_losers && (
                <div className="tv-card">
                  <div className="tv-card-header">
                    <span className="text-xs font-medium text-[#ef5350] uppercase tracking-wider">
                      Top Losers
                    </span>
                  </div>
                  <div className="p-3 space-y-1">
                    {(Array.isArray(marketSentiment.trending.top_losers)
                      ? marketSentiment.trending.top_losers
                      : []
                    ).slice(0, 8).map((l: any, i: number) => (
                      <div key={i} className="flex justify-between text-xs py-0.5">
                        <span className="text-[#d1d4dc] font-medium">{l.symbol || l.company_name || l.name || "—"}</span>
                        <span className="text-[#ef5350] font-tabular">
                          {parseFloat(l.change_percentage || l.percent_change || "0").toFixed(2)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Market headlines */}
          <HeadlineList
            headlines={marketSentiment.headlines}
            title="Market News Headlines"
            emptyText="No market news available"
          />
        </>
      )}

      {/* === STOCK-SPECIFIC VIEW === */}
      {selectedSymbol && stockSentiment && (
        <>
          {/* Stock sentiment banner */}
          <div className={`tv-card border p-5 ${sentimentBg(stockSentiment.overall.weighted_sentiment)}`}>
            <div className="flex items-center gap-4 flex-wrap">
              <div>
                <p className="text-[10px] text-[#787b86] uppercase">
                  {stockSentiment.company_name}
                  {stockSentiment.sector && <span> &middot; {stockSentiment.sector}</span>}
                </p>
                <p className={`text-3xl font-black mt-1 ${sentimentColor(stockSentiment.overall.weighted_sentiment)}`}>
                  {sentimentEmoji(stockSentiment.overall.weighted_sentiment)}{" "}
                  {sentimentLabel(stockSentiment.overall.weighted_sentiment)}
                </p>
              </div>
              <div className="ml-auto text-right">
                <p className={`text-2xl font-bold font-tabular ${sentimentColor(stockSentiment.overall.weighted_sentiment)}`}>
                  {stockSentiment.overall.weighted_sentiment > 0 ? "+" : ""}
                  {stockSentiment.overall.weighted_sentiment.toFixed(4)}
                </p>
                <p className="text-[10px] text-[#787b86] mt-0.5">
                  {stockSentiment.overall.news_count} articles
                  {stockSentiment.is_weekday && stockSentiment.indianapi_news.length > 0 && (
                    <span> + {stockSentiment.indianapi_news.length} IndianAPI</span>
                  )}
                </p>
              </div>
            </div>
          </div>

          {/* Score cards: Stock / Industry / Market */}
          <div className="grid md:grid-cols-3 gap-3">
            <ScoreCard label="Stock News" bucket={stockSentiment.stock_sentiment} />
            <ScoreCard label="Industry News" bucket={stockSentiment.industry_sentiment} />
            <ScoreCard label="Market News" bucket={stockSentiment.market_sentiment} />
          </div>

          {/* Sentiment history bar chart */}
          <SentimentHistory history={stockSentiment.history} />

          {/* IndianAPI news (weekday only) */}
          {stockSentiment.indianapi_news.length > 0 && (
            <HeadlineList
              headlines={stockSentiment.indianapi_news}
              title="IndianAPI Live News"
              emptyText="No IndianAPI news"
            />
          )}

          {/* All scored headlines */}
          <HeadlineList
            headlines={stockSentiment.headlines}
            title="RSS News Headlines"
            emptyText="No recent news found"
          />
        </>
      )}

      {/* Heatmap — always visible when we have data, click to select stock */}
      {heatmap.length > 0 && (
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
              Stock Sentiment Heatmap
            </span>
            <span className="text-[10px] text-[#787b86]">click to analyze</span>
          </div>
          <div className="p-4 flex flex-wrap gap-1.5">
            {heatmap.map((entry) => {
              const score = entry.weighted_sentiment;
              const isSelected = entry.symbol === selectedSymbol;
              const bg = isSelected
                ? "bg-[#2962ff]/30 text-[#e0e3eb] border-[#2962ff] ring-1 ring-[#2962ff]"
                : score > 0.1
                  ? "bg-[#26a69a]/25 text-[#26a69a] border-[#26a69a]/30"
                  : score < -0.1
                    ? "bg-[#ef5350]/25 text-[#ef5350] border-[#ef5350]/30"
                    : score > 0.05
                      ? "bg-[#26a69a]/10 text-[#26a69a]/70 border-[#26a69a]/15"
                      : score < -0.05
                        ? "bg-[#ef5350]/10 text-[#ef5350]/70 border-[#ef5350]/15"
                        : "bg-[#2a2e39] text-[#787b86] border-[#2a2e39]";
              return (
                <button
                  key={entry.stock_id}
                  className={`${bg} rounded border px-2 py-1 text-[10px] font-medium cursor-pointer hover:opacity-80 transition-all`}
                  title={`${entry.symbol}: ${score > 0 ? "+" : ""}${score.toFixed(4)}`}
                  onClick={() => setSelectedSymbol(entry.symbol)}
                >
                  {entry.symbol}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="tv-card p-12 text-center">
          <div className="inline-block w-6 h-6 border-2 border-[#2962ff] border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-xs text-[#787b86]">
            Fetching {selectedSymbol ? `${selectedSymbol} news` : "market news"} and analyzing sentiment...
          </p>
        </div>
      )}
    </div>
  );
}
