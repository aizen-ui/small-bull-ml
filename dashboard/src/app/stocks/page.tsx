import { supabase } from "@/lib/supabase";
import Link from "next/link";
import type { Stock, Prediction, SentimentScore } from "@/lib/types";

export const revalidate = 60;

async function getStocksData() {
  const [{ data: stocks }, { data: predictions }, { data: sentiments }] =
    await Promise.all([
      supabase.from("stocks").select("*").eq("is_active", true).order("symbol"),
      supabase
        .from("predictions")
        .select("*")
        .eq("prediction_type", "nightly")
        .order("prediction_timestamp", { ascending: false })
        .limit(200),
      supabase
        .from("sentiment_scores")
        .select("*")
        .order("date", { ascending: false })
        .limit(200),
    ]);

  const latestPred = new Map<number, Prediction>();
  (predictions || []).forEach((p: Prediction) => {
    if (!latestPred.has(p.stock_id)) latestPred.set(p.stock_id, p);
  });

  const latestSent = new Map<number, SentimentScore>();
  (sentiments || []).forEach((s: SentimentScore) => {
    if (!latestSent.has(s.stock_id)) latestSent.set(s.stock_id, s);
  });

  return { stocks: stocks || [], latestPred, latestSent };
}

export default async function StocksPage() {
  const { stocks, latestPred, latestSent } = await getStocksData();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold text-[#e0e3eb] uppercase tracking-wider">
          All Stocks
        </h1>
        <span className="text-xs text-[#787b86]">
          {stocks.length} tracked
        </span>
      </div>

      <div className="tv-card overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#2a2e39] text-[#787b86]">
              <th className="text-left py-2.5 px-4 font-medium">Symbol</th>
              <th className="text-left py-2.5 px-4 font-medium">Company</th>
              <th className="text-left py-2.5 px-4 font-medium">Sector</th>
              <th className="text-center py-2.5 px-4 font-medium">Type</th>
              <th className="text-center py-2.5 px-4 font-medium">
                Nightly Prediction
              </th>
              <th className="text-right py-2.5 px-4 font-medium">
                Confidence
              </th>
              <th className="text-right py-2.5 px-4 font-medium">
                Sentiment
              </th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((stock: Stock) => {
              const pred = latestPred.get(stock.id);
              const sent = latestSent.get(stock.id);
              const sentScore = sent?.score ?? 0;

              return (
                <tr
                  key={stock.id}
                  className="border-b border-[#1e222d] hover:bg-[#2a2e39]/50 transition-colors"
                >
                  <td className="py-2 px-4">
                    <Link
                      href={`/stocks/${encodeURIComponent(stock.symbol)}`}
                      className="text-[#5b9cf6] hover:text-[#2962ff] font-medium"
                    >
                      {stock.symbol.replace(".NS", "")}
                    </Link>
                  </td>
                  <td className="py-2 px-4 text-[#787b86] max-w-[200px] truncate">
                    {stock.company_name}
                  </td>
                  <td className="py-2 px-4 text-[#787b86]">{stock.sector}</td>
                  <td className="py-2 px-4 text-center">
                    {stock.is_nifty50 ? (
                      <span className="text-[#2962ff] text-[10px] font-semibold bg-[#2962ff]/10 px-1.5 py-0.5 rounded">
                        N50
                      </span>
                    ) : (
                      <span className="text-[#787b86] text-[10px]">
                        {stock.market_cap_category?.slice(0, 3).toUpperCase()}
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-4 text-center">
                    {pred ? (
                      <span
                        className={`badge-${pred.predicted_direction}`}
                      >
                        {pred.predicted_direction === "up"
                          ? "▲"
                          : pred.predicted_direction === "down"
                            ? "▼"
                            : "—"}{" "}
                        {pred.predicted_direction.toUpperCase()}
                      </span>
                    ) : (
                      <span className="text-[#787b86]">—</span>
                    )}
                  </td>
                  <td className="py-2 px-4 text-right font-tabular">
                    {pred ? (
                      <span className="text-[#d1d4dc]">
                        {(pred.confidence_score * 100).toFixed(1)}%
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2 px-4 text-right">
                    {sent ? (
                      <span
                        className={`font-tabular ${
                          sentScore > 0.05
                            ? "text-[#26a69a]"
                            : sentScore < -0.05
                              ? "text-[#ef5350]"
                              : "text-[#787b86]"
                        }`}
                      >
                        {sentScore > 0 ? "+" : ""}
                        {sentScore.toFixed(3)}
                      </span>
                    ) : (
                      <span className="text-[#787b86]">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
