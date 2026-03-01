import { supabase } from "@/lib/supabase";
import Link from "next/link";
import type { Prediction, Stock } from "@/lib/types";

export const revalidate = 60;

async function getPredictionsData() {
  const [{ data: nightlyPreds }, { data: minutePreds }, { data: stocks }] =
    await Promise.all([
      supabase
        .from("predictions")
        .select("*")
        .eq("prediction_type", "nightly")
        .order("prediction_timestamp", { ascending: false })
        .limit(100),
      supabase
        .from("predictions")
        .select("*")
        .eq("prediction_type", "minute")
        .order("prediction_timestamp", { ascending: false })
        .limit(200),
      supabase.from("stocks").select("*"),
    ]);

  const stockMap = new Map<number, Stock>();
  (stocks || []).forEach((s: Stock) => stockMap.set(s.id, s));

  const enrich = (preds: Prediction[]) =>
    preds.map((p) => ({ ...p, stock: stockMap.get(p.stock_id) }));

  const calcStats = (preds: Prediction[]) => {
    const withOutcome = preds.filter((p) => p.was_correct !== null);
    const correct = withOutcome.filter((p) => p.was_correct).length;
    return {
      total: withOutcome.length,
      correct,
      accuracy: withOutcome.length > 0 ? correct / withOutcome.length : 0,
    };
  };

  return {
    nightly: enrich(nightlyPreds || []),
    minute: enrich(minutePreds || []),
    nightlyStats: calcStats(nightlyPreds || []),
    minuteStats: calcStats(minutePreds || []),
  };
}

function PredTable({ predictions }: { predictions: (Prediction & { stock?: Stock })[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#2a2e39] text-[#787b86]">
            <th className="text-left py-2 px-3 font-medium">Stock</th>
            <th className="text-center py-2 px-3 font-medium">Direction</th>
            <th className="text-right py-2 px-3 font-medium">Pred %</th>
            <th className="text-right py-2 px-3 font-medium">Confidence</th>
            <th className="text-right py-2 px-3 font-medium">Actual %</th>
            <th className="text-center py-2 px-3 font-medium">Result</th>
            <th className="text-right py-2 px-3 font-medium">Time</th>
          </tr>
        </thead>
        <tbody>
          {predictions.map((p) => (
            <tr key={p.id} className="border-b border-[#1e222d] hover:bg-[#2a2e39]/30">
              <td className="py-1.5 px-3">
                {p.stock ? (
                  <Link href={`/stocks/${encodeURIComponent(p.stock.symbol)}`} className="text-[#5b9cf6] hover:text-[#2962ff] font-medium">
                    {p.stock.symbol.replace(".NS", "")}
                  </Link>
                ) : `#${p.stock_id}`}
              </td>
              <td className="py-1.5 px-3 text-center">
                <span className={`badge-${p.predicted_direction}`}>
                  {p.predicted_direction === "up" ? "▲" : p.predicted_direction === "down" ? "▼" : "—"} {p.predicted_direction.toUpperCase()}
                </span>
              </td>
              <td className={`py-1.5 px-3 text-right font-tabular ${p.predicted_pct_change > 0 ? "text-[#26a69a]" : "text-[#ef5350]"}`}>
                {p.predicted_pct_change > 0 ? "+" : ""}{(p.predicted_pct_change * 100).toFixed(2)}%
              </td>
              <td className="py-1.5 px-3 text-right font-tabular text-[#d1d4dc]">
                {(p.confidence_score * 100).toFixed(1)}%
              </td>
              <td className={`py-1.5 px-3 text-right font-tabular ${p.actual_pct_change !== null ? (p.actual_pct_change > 0 ? "text-[#26a69a]" : "text-[#ef5350]") : "text-[#787b86]"}`}>
                {p.actual_pct_change !== null ? `${p.actual_pct_change > 0 ? "+" : ""}${(p.actual_pct_change * 100).toFixed(2)}%` : "..."}
              </td>
              <td className="py-1.5 px-3 text-center">
                {p.was_correct === null ? "..." : p.was_correct ? <span className="text-[#26a69a]">✓</span> : <span className="text-[#ef5350]">✗</span>}
              </td>
              <td className="py-1.5 px-3 text-right text-[#787b86] font-tabular">
                {new Date(p.prediction_timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {predictions.length === 0 && <p className="text-center py-6 text-xs text-[#787b86]">No predictions yet</p>}
    </div>
  );
}

export default async function PredictionsPage() {
  const data = await getPredictionsData();

  return (
    <div className="space-y-4">
      <h1 className="text-sm font-semibold text-[#e0e3eb] uppercase tracking-wider">Predictions</h1>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="tv-card p-4">
          <p className="text-[10px] text-[#787b86] uppercase tracking-wider">Minute Accuracy</p>
          <p className="text-2xl font-bold text-[#e0e3eb] mt-1 font-tabular">{(data.minuteStats.accuracy * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-[#787b86] mt-1">{data.minuteStats.correct}/{data.minuteStats.total} correct</p>
        </div>
        <div className="tv-card p-4">
          <p className="text-[10px] text-[#787b86] uppercase tracking-wider">Nightly Accuracy</p>
          <p className="text-2xl font-bold text-[#e0e3eb] mt-1 font-tabular">{(data.nightlyStats.accuracy * 100).toFixed(1)}%</p>
          <p className="text-[10px] text-[#787b86] mt-1">{data.nightlyStats.correct}/{data.nightlyStats.total} correct</p>
        </div>
        <div className="tv-card p-4">
          <p className="text-[10px] text-[#787b86] uppercase tracking-wider">Minute Total</p>
          <p className="text-2xl font-bold text-[#e0e3eb] mt-1 font-tabular">{data.minute.length}</p>
        </div>
        <div className="tv-card p-4">
          <p className="text-[10px] text-[#787b86] uppercase tracking-wider">Nightly Total</p>
          <p className="text-2xl font-bold text-[#e0e3eb] mt-1 font-tabular">{data.nightly.length}</p>
        </div>
      </div>

      {/* Minute Predictions */}
      <div className="tv-card">
        <div className="tv-card-header">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#26a69a] animate-pulse-live" />
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">Minute Predictions</span>
          </div>
        </div>
        <PredTable predictions={data.minute} />
      </div>

      {/* Nightly Predictions */}
      <div className="tv-card">
        <div className="tv-card-header">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#2962ff]" />
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">Nightly Predictions</span>
          </div>
        </div>
        <PredTable predictions={data.nightly} />
      </div>
    </div>
  );
}
