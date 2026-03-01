import { supabase } from "@/lib/supabase";
import type { Stock, Prediction, DailyPrice, SentimentScore } from "@/lib/types";
import Link from "next/link";
import StockActions from "@/components/StockActions";

export const revalidate = 60;

interface Props {
  params: { symbol: string };
}

async function getStockDetail(symbol: string) {
  const decodedSymbol = decodeURIComponent(symbol);

  const { data: stocks } = await supabase
    .from("stocks")
    .select("*")
    .eq("symbol", decodedSymbol)
    .limit(1);

  if (!stocks || stocks.length === 0) return null;
  const stock = stocks[0] as Stock;

  const [
    { data: prices },
    { data: predictions },
    { data: sentiments },
    { data: indicators },
    { data: analyst },
  ] = await Promise.all([
    supabase
      .from("daily_prices")
      .select("*")
      .eq("stock_id", stock.id)
      .order("date", { ascending: false })
      .limit(90),
    supabase
      .from("predictions")
      .select("*")
      .eq("stock_id", stock.id)
      .order("prediction_timestamp", { ascending: false })
      .limit(50),
    supabase
      .from("sentiment_scores")
      .select("*")
      .eq("stock_id", stock.id)
      .order("date", { ascending: false })
      .limit(30),
    supabase
      .from("technical_indicators")
      .select("*")
      .eq("stock_id", stock.id)
      .order("date", { ascending: false })
      .limit(1),
    supabase
      .from("analyst_data")
      .select("*")
      .eq("stock_id", stock.id)
      .order("date", { ascending: false })
      .limit(1),
  ]);

  const withOutcome = (predictions || []).filter(
    (p: Prediction) => p.was_correct !== null
  );
  const correct = withOutcome.filter((p: Prediction) => p.was_correct).length;
  const hitRate = withOutcome.length > 0 ? correct / withOutcome.length : 0;

  return {
    stock,
    prices: (prices || []).reverse(),
    predictions: predictions || [],
    sentiments: sentiments || [],
    latestIndicators: (indicators || [])[0] || null,
    latestAnalyst: (analyst || [])[0] || null,
    hitRate,
    totalPredictions: withOutcome.length,
  };
}

export default async function StockDetailPage({ params }: Props) {
  const data = await getStockDetail(params.symbol);
  if (!data) {
    return <p className="text-[#787b86] p-8">Stock not found.</p>;
  }

  const { stock, prices, predictions, sentiments, latestIndicators, latestAnalyst, hitRate } = data;
  const latestPrice = prices.length > 0 ? prices[prices.length - 1] : null;
  const prevPrice = prices.length > 1 ? prices[prices.length - 2] : null;
  const pChange = latestPrice && prevPrice
    ? (Number(latestPrice.close) - Number(prevPrice.close)) / Number(prevPrice.close)
    : 0;
  const latestSentiment = sentiments.length > 0 ? sentiments[0] : null;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/stocks" className="text-[#787b86] hover:text-[#d1d4dc] text-xs">
          &larr; Back
        </Link>
        <div>
          <h1 className="text-lg font-bold text-[#e0e3eb]">
            {stock.symbol.replace(".NS", "")}
            <span className="text-sm text-[#787b86] font-normal ml-2">
              {stock.company_name}
            </span>
          </h1>
          <div className="flex gap-2 text-[10px] text-[#787b86] mt-0.5">
            <span>{stock.sector}</span>
            <span>&middot;</span>
            <span>{stock.industry}</span>
            {stock.is_nifty50 && (
              <>
                <span>&middot;</span>
                <span className="text-[#2962ff]">Nifty 50</span>
              </>
            )}
          </div>
        </div>
        {latestPrice && (
          <div className="ml-auto text-right font-tabular">
            <p className="text-xl font-bold text-[#e0e3eb]">
              ₹{Number(latestPrice.close).toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </p>
            <p className={`text-xs font-medium ${pChange > 0 ? "text-[#26a69a]" : pChange < 0 ? "text-[#ef5350]" : "text-[#787b86]"}`}>
              {pChange > 0 ? "+" : ""}{(pChange * 100).toFixed(2)}%
            </p>
          </div>
        )}
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
        {[
          ["Hit Rate", `${(hitRate * 100).toFixed(1)}%`, `${data.totalPredictions} pred`],
          ["RSI (14)", latestIndicators?.rsi_14 ? Number(latestIndicators.rsi_14).toFixed(1) : "—", Number(latestIndicators?.rsi_14 || 50) > 70 ? "Overbought" : Number(latestIndicators?.rsi_14 || 50) < 30 ? "Oversold" : "Neutral"],
          ["MACD", latestIndicators?.macd ? Number(latestIndicators.macd).toFixed(2) : "—", ""],
          ["ADX", latestIndicators?.adx_14 ? Number(latestIndicators.adx_14).toFixed(1) : "—", ""],
          ["Sentiment", latestSentiment ? ((latestSentiment.score ?? 0) > 0 ? "+" : "") + (latestSentiment.score ?? 0).toFixed(3) : "—", ""],
          ["Target", latestAnalyst?.target_price ? `₹${Number(latestAnalyst.target_price).toLocaleString()}` : "—", latestAnalyst?.upside_pct ? `${Number(latestAnalyst.upside_pct).toFixed(1)}% upside` : ""],
        ].map(([label, val, sub]) => (
          <div key={label} className="tv-card p-3">
            <p className="text-[10px] text-[#787b86] uppercase tracking-wider">{label}</p>
            <p className="text-sm font-bold text-[#e0e3eb] mt-1 font-tabular">{val}</p>
            {sub && <p className="text-[10px] text-[#787b86] mt-0.5">{sub}</p>}
          </div>
        ))}
      </div>

      {/* Per-stock predict / train */}
      <StockActions symbol={stock.symbol} />

      {/* Technicals detail */}
      {latestIndicators && (
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">Technical Indicators</span>
          </div>
          <div className="p-4 grid grid-cols-4 md:grid-cols-8 gap-3 text-xs">
            {[
              ["SMA 20", latestIndicators.sma_20],
              ["SMA 50", latestIndicators.sma_50],
              ["EMA 12", latestIndicators.ema_12],
              ["EMA 26", latestIndicators.ema_26],
              ["BB Upper", latestIndicators.bb_upper],
              ["BB Lower", latestIndicators.bb_lower],
              ["ATR", latestIndicators.atr_14],
              ["Stoch K", latestIndicators.stoch_k],
            ].map(([l, v]) => (
              <div key={l as string}>
                <p className="text-[#787b86] text-[10px]">{l as string}</p>
                <p className="text-[#d1d4dc] font-tabular font-medium mt-0.5">
                  {v ? Number(v).toFixed(2) : "—"}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}


      {/* Prediction History */}
      <div className="tv-card">
        <div className="tv-card-header">
          <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
            Prediction History
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#2a2e39] text-[#787b86]">
                <th className="text-left py-2 px-3 font-medium">Time</th>
                <th className="text-left py-2 px-3 font-medium">Type</th>
                <th className="text-center py-2 px-3 font-medium">Direction</th>
                <th className="text-right py-2 px-3 font-medium">Predicted</th>
                <th className="text-right py-2 px-3 font-medium">Confidence</th>
                <th className="text-right py-2 px-3 font-medium">Actual</th>
                <th className="text-center py-2 px-3 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {predictions.map((p: Prediction) => (
                <tr key={p.id} className="border-b border-[#1e222d] hover:bg-[#2a2e39]/30">
                  <td className="py-1.5 px-3 text-[#787b86] font-tabular">
                    {new Date(p.prediction_timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </td>
                  <td className="py-1.5 px-3">
                    <span className={p.prediction_type === "minute" ? "text-[#26a69a]" : "text-[#2962ff]"}>
                      {p.prediction_type}
                    </span>
                  </td>
                  <td className="py-1.5 px-3 text-center">
                    <span className={`badge-${p.predicted_direction}`}>
                      {p.predicted_direction.toUpperCase()}
                    </span>
                  </td>
                  <td className={`py-1.5 px-3 text-right font-tabular ${p.predicted_pct_change > 0 ? "text-[#26a69a]" : p.predicted_pct_change < 0 ? "text-[#ef5350]" : "text-[#787b86]"}`}>
                    {p.predicted_pct_change > 0 ? "+" : ""}{(p.predicted_pct_change * 100).toFixed(3)}%
                  </td>
                  <td className="py-1.5 px-3 text-right font-tabular text-[#d1d4dc]">
                    {(p.confidence_score * 100).toFixed(1)}%
                  </td>
                  <td className={`py-1.5 px-3 text-right font-tabular ${p.actual_pct_change !== null ? (p.actual_pct_change > 0 ? "text-[#26a69a]" : "text-[#ef5350]") : "text-[#787b86]"}`}>
                    {p.actual_pct_change !== null ? `${p.actual_pct_change > 0 ? "+" : ""}${(p.actual_pct_change * 100).toFixed(3)}%` : "..."}
                  </td>
                  <td className="py-1.5 px-3 text-center">
                    {p.was_correct === null ? <span className="text-[#787b86]">...</span> : p.was_correct ? <span className="text-[#26a69a]">✓</span> : <span className="text-[#ef5350]">✗</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
