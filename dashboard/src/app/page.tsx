"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { createBrowserClient } from "@/lib/supabase";
import TVChart from "@/components/TVChart";
import LiveMetrics from "@/components/LiveMetrics";
import StockSelector from "@/components/StockSelector";
import type { Stock, Prediction, DailyPrice, IntradayPrice } from "@/lib/types";

export default function DashboardPage() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [selectedStockId, setSelectedStockId] = useState<number>(0);
  const [prices, setPrices] = useState<{ time: string; value: number }[]>([]);
  const [minutePreds, setMinutePreds] = useState<{ time: string; value: number }[]>([]);
  const [nightlyPreds, setNightlyPreds] = useState<{ time: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [stockInfo, setStockInfo] = useState<Stock | null>(null);
  const [latestPrice, setLatestPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);

  const supabaseRef = useRef(createBrowserClient());
  const supabase = supabaseRef.current;

  // Load stocks list once
  useEffect(() => {
    async function loadStocks() {
      const { data } = await supabase
        .from("stocks")
        .select("*")
        .eq("is_active", true)
        .order("symbol");
      if (data && data.length > 0) {
        setStocks(data);
        setSelectedStockId(data[0].id);
      }
    }
    loadStocks();
  }, []);

  // Load chart data when stock changes
  const loadChartData = useCallback(async (stockId: number) => {
    if (!stockId) return;
    setLoading(true);

    const stock = stocks.find((s) => s.id === stockId);
    setStockInfo(stock || null);

    // Fetch daily prices + intraday + predictions in parallel
    const [
      { data: dailyPrices },
      { data: intradayPrices },
      { data: minutePredictions },
      { data: nightlyPredictions },
    ] = await Promise.all([
      supabase
        .from("daily_prices")
        .select("*")
        .eq("stock_id", stockId)
        .order("date", { ascending: false })
        .limit(90),
      supabase
        .from("intraday_prices")
        .select("*")
        .eq("stock_id", stockId)
        .order("timestamp", { ascending: true })
        .limit(500),
      supabase
        .from("predictions")
        .select("*")
        .eq("stock_id", stockId)
        .eq("prediction_type", "minute")
        .order("prediction_timestamp", { ascending: true })
        .limit(500),
      supabase
        .from("predictions")
        .select("*")
        .eq("stock_id", stockId)
        .eq("prediction_type", "nightly")
        .order("prediction_timestamp", { ascending: true })
        .limit(100),
    ]);

    // Build price series: daily + intraday merged
    const pricePoints: { time: string; value: number }[] = [];

    // dailyPrices came back in desc order, reverse to ascending
    const sortedDaily = [...(dailyPrices || [])].reverse();
    sortedDaily.forEach((p: DailyPrice) => {
      pricePoints.push({
        time: p.date,
        value: Number(p.close),
      });
    });

    // Intraday prices override/extend daily
    (intradayPrices || []).forEach((p: IntradayPrice) => {
      const ts = Math.floor(new Date(p.timestamp).getTime() / 1000);
      pricePoints.push({
        time: ts as any,
        value: Number(p.close),
      });
    });

    // Latest price info
    if (pricePoints.length > 0) {
      const last = pricePoints[pricePoints.length - 1].value;
      setLatestPrice(last);
      if (pricePoints.length > 1) {
        const prev = pricePoints[pricePoints.length - 2].value;
        setPriceChange(prev > 0 ? (last - prev) / prev : 0);
      }
    }

    setPrices(pricePoints);

    // Build a date→price lookup from daily prices for resolving base price per prediction
    const priceByDate: Record<string, number> = {};
    sortedDaily.forEach((p: DailyPrice) => {
      priceByDate[p.date] = Number(p.close);
    });
    const dailyDates = sortedDaily.map((p: DailyPrice) => p.date).sort();

    // Helper: find the closest previous daily close for a given timestamp
    function getBasePrice(timestamp: string): number {
      const predDate = timestamp.slice(0, 10); // "YYYY-MM-DD"
      // Walk backwards to find last known close before this prediction
      for (let i = dailyDates.length - 1; i >= 0; i--) {
        if (dailyDates[i] <= predDate) return priceByDate[dailyDates[i]];
      }
      return pricePoints.length > 0 ? pricePoints[pricePoints.length - 1].value : 0;
    }

    // Build minute prediction series: predicted price = base_price * (1 + predicted_pct_change)
    const mPreds: { time: string; value: number }[] = [];
    (minutePredictions || []).forEach((pred: Prediction) => {
      const ts = Math.floor(new Date(pred.prediction_timestamp).getTime() / 1000);
      const basePrice = getBasePrice(pred.prediction_timestamp);
      mPreds.push({
        time: ts as any,
        value: basePrice * (1 + pred.predicted_pct_change),
      });
    });
    setMinutePreds(mPreds);

    // Build nightly prediction series: each prediction is for next day
    const nPreds: { time: string; value: number }[] = [];
    (nightlyPredictions || []).forEach((pred: Prediction) => {
      const basePrice = getBasePrice(pred.prediction_timestamp);
      // Nightly predictions target the next trading day — plot on the next date
      const predDate = new Date(pred.prediction_timestamp);
      predDate.setDate(predDate.getDate() + 1);
      const nextDay = predDate.toISOString().slice(0, 10);
      nPreds.push({
        time: nextDay,
        value: basePrice * (1 + pred.predicted_pct_change),
      });
    });
    setNightlyPreds(nPreds);

    setLoading(false);
  }, [stocks, supabase]);  // supabase is now stable via useRef

  useEffect(() => {
    loadChartData(selectedStockId);
  }, [selectedStockId, loadChartData]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (selectedStockId) loadChartData(selectedStockId);
    }, 60000);
    return () => clearInterval(interval);
  }, [selectedStockId, loadChartData]);

  const selectedSymbol = stockInfo?.symbol.replace(".NS", "") || "";

  return (
    <div className="space-y-4">
      {/* Top bar: stock selector + price info */}
      <div className="flex items-center gap-4">
        <div className="w-64">
          <StockSelector
            stocks={stocks}
            selectedId={selectedStockId}
            onSelect={setSelectedStockId}
          />
        </div>
        {stockInfo && (
          <div className="flex items-center gap-4">
            <div>
              <span className="text-lg font-bold text-[#e0e3eb]">
                {selectedSymbol}
              </span>
              <span className="text-xs text-[#787b86] ml-2">
                {stockInfo.company_name}
              </span>
            </div>
            <div className="font-tabular">
              <span className="text-lg font-bold text-[#e0e3eb]">
                {latestPrice > 0 ? `₹${latestPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "—"}
              </span>
              {priceChange !== 0 && (
                <span
                  className={`ml-2 text-sm font-medium ${
                    priceChange > 0 ? "text-[#26a69a]" : "text-[#ef5350]"
                  }`}
                >
                  {priceChange > 0 ? "+" : ""}
                  {(priceChange * 100).toFixed(2)}%
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Live Metrics */}
      <LiveMetrics />

      {/* Main Chart */}
      <div className="tv-card overflow-hidden">
        {loading ? (
          <div className="h-[500px] flex items-center justify-center">
            <div className="text-[#787b86] text-sm">Loading chart...</div>
          </div>
        ) : (
          <TVChart
            key={selectedStockId}
            stockId={selectedStockId}
            symbol={selectedSymbol}
            initialPrices={prices}
            initialMinutePreds={minutePreds}
            initialNightlyPreds={nightlyPreds}
          />
        )}
      </div>

      {/* Bottom panels */}
      <div className="grid lg:grid-cols-3 gap-4">
        {/* Recent Minute Predictions */}
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
              Minute Predictions
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-[#26a69a] animate-pulse-live" />
          </div>
          <RecentPredictionsList stockId={selectedStockId} type="minute" />
        </div>

        {/* Nightly Predictions */}
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
              Nightly Predictions
            </span>
            <span className="w-2 h-2 rounded-full bg-[#2962ff]" />
          </div>
          <RecentPredictionsList stockId={selectedStockId} type="nightly" />
        </div>

        {/* Model Info */}
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
              Model Info
            </span>
          </div>
          <ModelInfoPanel />
        </div>
      </div>
    </div>
  );
}

// Sub-components

function RecentPredictionsList({
  stockId,
  type,
}: {
  stockId: number;
  type: "minute" | "nightly";
}) {
  const [preds, setPreds] = useState<Prediction[]>([]);

  useEffect(() => {
    if (!stockId) return;
    const supabase = createBrowserClient();

    async function load() {
      const { data } = await supabase
        .from("predictions")
        .select("*")
        .eq("stock_id", stockId)
        .eq("prediction_type", type)
        .order("prediction_timestamp", { ascending: false })
        .limit(15);
      setPreds(data || []);
    }
    load();

    const channel = supabase
      .channel(`pred-list-${stockId}-${type}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "predictions",
          filter: `stock_id=eq.${stockId}`,
        },
        () => load()
      )
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [stockId, type]);

  return (
    <div className="p-3 space-y-1 max-h-64 overflow-y-auto">
      {preds.length === 0 && (
        <p className="text-xs text-[#787b86] text-center py-4">
          No predictions yet
        </p>
      )}
      {preds.map((p) => (
        <div
          key={p.id}
          className="flex items-center justify-between py-1 text-xs border-b border-[#1e222d] last:border-0"
        >
          <span
            className={
              p.predicted_direction === "up"
                ? "text-[#26a69a]"
                : p.predicted_direction === "down"
                  ? "text-[#ef5350]"
                  : "text-[#787b86]"
            }
          >
            {p.predicted_direction === "up"
              ? "▲"
              : p.predicted_direction === "down"
                ? "▼"
                : "—"}{" "}
            {(p.predicted_pct_change * 100).toFixed(3)}%
          </span>
          <span className="text-[#787b86] font-tabular">
            {(p.confidence_score * 100).toFixed(1)}%
          </span>
          <span className="text-[#787b86]">
            {p.was_correct === null
              ? "..."
              : p.was_correct
                ? "✓"
                : "✗"}
          </span>
          <span className="text-[#787b86] font-tabular">
            {new Date(p.prediction_timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      ))}
    </div>
  );
}

function ModelInfoPanel() {
  const [model, setModel] = useState<any>(null);

  useEffect(() => {
    const supabase = createBrowserClient();
    async function load() {
      const { data } = await supabase
        .from("model_performance")
        .select("*")
        .order("evaluation_date", { ascending: false })
        .limit(1);
      if (data && data.length > 0) setModel(data[0]);
    }
    load();
  }, []);

  if (!model) {
    return (
      <div className="p-4 text-xs text-[#787b86] text-center">
        No model trained yet
      </div>
    );
  }

  const rows = [
    ["Version", model.model_version],
    ["Accuracy", `${(model.accuracy * 100).toFixed(1)}%`],
    ["Dir. Accuracy", `${(model.directional_accuracy * 100).toFixed(1)}%`],
    ["F1 Score", `${(model.f1_up * 100).toFixed(1)}%`],
    ["MAE", model.mae?.toFixed(4)],
    ["RMSE", model.rmse?.toFixed(4)],
  ];

  return (
    <div className="p-3 space-y-2">
      {rows.map(([label, val]) => (
        <div key={label} className="flex justify-between text-xs">
          <span className="text-[#787b86]">{label}</span>
          <span className="text-[#d1d4dc] font-tabular font-medium">
            {val || "—"}
          </span>
        </div>
      ))}
    </div>
  );
}
