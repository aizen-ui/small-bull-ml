"use client";

import { useEffect, useState } from "react";
import { createBrowserClient } from "@/lib/supabase";
import type { Prediction } from "@/lib/types";

interface Metrics {
  totalMinute: number;
  totalNightly: number;
  minuteAccuracy: number;
  nightlyAccuracy: number;
  lastPrediction: Prediction | null;
  recentPreds: Prediction[];
}

export default function LiveMetrics() {
  const [metrics, setMetrics] = useState<Metrics>({
    totalMinute: 0,
    totalNightly: 0,
    minuteAccuracy: 0,
    nightlyAccuracy: 0,
    lastPrediction: null,
    recentPreds: [],
  });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const supabase = createBrowserClient();

    async function fetchMetrics() {
      const [{ data: minutePreds }, { data: nightlyPreds }, { data: recent }] =
        await Promise.all([
          supabase
            .from("predictions")
            .select("*")
            .eq("prediction_type", "minute")
            .not("was_correct", "is", null)
            .order("prediction_timestamp", { ascending: false })
            .limit(100),
          supabase
            .from("predictions")
            .select("*")
            .eq("prediction_type", "nightly")
            .not("was_correct", "is", null)
            .order("prediction_timestamp", { ascending: false })
            .limit(50),
          supabase
            .from("predictions")
            .select("*")
            .order("prediction_timestamp", { ascending: false })
            .limit(20),
        ]);

      const mCorrect = (minutePreds || []).filter((p) => p.was_correct).length;
      const nCorrect = (nightlyPreds || []).filter((p) => p.was_correct).length;

      setMetrics({
        totalMinute: (minutePreds || []).length,
        totalNightly: (nightlyPreds || []).length,
        minuteAccuracy:
          (minutePreds || []).length > 0
            ? mCorrect / (minutePreds || []).length
            : 0,
        nightlyAccuracy:
          (nightlyPreds || []).length > 0
            ? nCorrect / (nightlyPreds || []).length
            : 0,
        lastPrediction: (recent || [])[0] || null,
        recentPreds: recent || [],
      });
    }

    fetchMetrics();

    // Subscribe to new predictions
    const channel = supabase
      .channel("live-metrics")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "predictions" },
        () => {
          setTick((t) => t + 1);
          fetchMetrics();
        }
      )
      .subscribe();

    // Also poll every 30s as backup
    const interval = setInterval(fetchMetrics, 30000);

    return () => {
      supabase.removeChannel(channel);
      clearInterval(interval);
    };
  }, [tick]);

  const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {/* Minute Accuracy */}
      <div className="tv-card p-4">
        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-[#787b86]">
            Minute Accuracy
          </span>
          <span className="w-1.5 h-1.5 rounded-full bg-[#26a69a] animate-pulse-live" />
        </div>
        <p className="text-2xl font-bold text-[#e0e3eb] mt-2 font-tabular">
          {fmtPct(metrics.minuteAccuracy)}
        </p>
        <p className="text-[10px] text-[#787b86] mt-1">
          {metrics.totalMinute} evaluated
        </p>
      </div>

      {/* Nightly Accuracy */}
      <div className="tv-card p-4">
        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-[#787b86]">
            Nightly Accuracy
          </span>
          <span className="w-2 h-2 rounded-full bg-[#2962ff]" />
        </div>
        <p className="text-2xl font-bold text-[#e0e3eb] mt-2 font-tabular">
          {fmtPct(metrics.nightlyAccuracy)}
        </p>
        <p className="text-[10px] text-[#787b86] mt-1">
          {metrics.totalNightly} evaluated
        </p>
      </div>

      {/* Last Prediction */}
      <div className="tv-card p-4">
        <span className="text-[10px] uppercase tracking-wider text-[#787b86]">
          Last Prediction
        </span>
        {metrics.lastPrediction ? (
          <div className="mt-2">
            <span
              className={
                metrics.lastPrediction.predicted_direction === "up"
                  ? "badge-up"
                  : metrics.lastPrediction.predicted_direction === "down"
                    ? "badge-down"
                    : "badge-neutral"
              }
            >
              {metrics.lastPrediction.predicted_direction.toUpperCase()}{" "}
              {metrics.lastPrediction.predicted_pct_change > 0 ? "+" : ""}
              {(metrics.lastPrediction.predicted_pct_change * 100).toFixed(2)}%
            </span>
            <p className="text-[10px] text-[#787b86] mt-2">
              {metrics.lastPrediction.prediction_type} &middot;{" "}
              {new Date(
                metrics.lastPrediction.prediction_timestamp
              ).toLocaleTimeString()}
            </p>
          </div>
        ) : (
          <p className="text-sm text-[#787b86] mt-2">No predictions yet</p>
        )}
      </div>

      {/* Prediction Feed */}
      <div className="tv-card p-4">
        <span className="text-[10px] uppercase tracking-wider text-[#787b86]">
          Live Feed
        </span>
        <div className="mt-2 space-y-1 max-h-20 overflow-hidden">
          {metrics.recentPreds.slice(0, 4).map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between text-[10px]"
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
                {p.predicted_direction === "up" ? "▲" : p.predicted_direction === "down" ? "▼" : "—"}{" "}
                {(p.predicted_pct_change * 100).toFixed(2)}%
              </span>
              <span className="text-[#787b86]">
                {new Date(p.prediction_timestamp).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
