"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { createBrowserClient } from "@/lib/supabase";
import {
  createChart,
  ColorType,
  LineStyle,
  CandlestickData,
} from "lightweight-charts";
import type { Stock } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface BacktestPoint {
  date: string;
  actual_price: number;
  model_price: number;
  direction: string;
  confidence: number;
}

interface PredictionResult {
  symbol: string;
  predicted_direction: string;
  raw_direction: string;
  predicted_pct_change: number;
  confidence_score: number;
  top_features: { feature: string; importance: number }[];
  prices: { date: string; open: number; high: number; low: number; close: number; volume: number }[];
  backtest: BacktestPoint[];
  backtest_stats?: {
    directional_accuracy: number;
    total_signals: number;
    correct_signals: number;
  };
}

interface TrainResult {
  status: string;
  message: string;
  version: string;
  metrics: Record<string, number>;
  samples: { train: number; test: number };
  features: number;
  elapsed: number;
}

export default function PredictPage() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [loading, setLoading] = useState(false);
  const [predicting, setPredicting] = useState(false);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [training, setTraining] = useState(false);
  const [trainStatus, setTrainStatus] = useState("");
  const [trainResult, setTrainResult] = useState<TrainResult | null>(null);
  const [error, setError] = useState("");
  const [chartPrices, setChartPrices] = useState<any[]>([]);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  // Corrected pct change: align regressor with classifier direction
  const correctedPct = useMemo(() => {
    if (!prediction) return 0;
    const dir = prediction.raw_direction;
    let pct = prediction.predicted_pct_change;
    if (dir === "down" && pct > 0) pct = -Math.abs(pct);
    if (dir === "up" && pct < 0) pct = Math.abs(pct);
    return pct;
  }, [prediction]);

  // Backtest stats: avg prediction error
  const backtestStats = useMemo(() => {
    if (!prediction?.backtest || prediction.backtest.length === 0) return null;
    const bt = prediction.backtest;
    let totalErr = 0;
    for (const p of bt) {
      totalErr += Math.abs((p.model_price - p.actual_price) / p.actual_price);
    }
    const avgErrPct = (totalErr / bt.length) * 100;
    return {
      points: bt.length,
      avgError: avgErrPct.toFixed(2),
    };
  }, [prediction]);

  // Load stocks from Supabase
  useEffect(() => {
    const supabase = createBrowserClient();
    async function loadStocks() {
      const { data } = await supabase
        .from("stocks")
        .select("*")
        .eq("is_active", true)
        .order("symbol");
      if (data && data.length > 0) {
        setStocks(data);
        setSelectedSymbol(data[0].symbol.replace(".NS", "").replace(".BO", ""));
      }
    }
    loadStocks();
  }, []);

  // Load chart prices when stock changes
  const loadPrices = useCallback(async (sym: string) => {
    if (!sym) return;
    setLoading(true);
    setPrediction(null);
    setTrainResult(null);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/prices/${encodeURIComponent(sym)}?days=180`);
      if (res.ok) {
        const data = await res.json();
        setChartPrices(data.prices || []);
      }
    } catch {
      setChartPrices([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPrices(selectedSymbol);
  }, [selectedSymbol, loadPrices]);

  // Render chart
  useEffect(() => {
    if (!chartContainerRef.current || chartPrices.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#131722" },
        textColor: "#787b86",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "#1e222d" },
        horzLines: { color: "#1e222d" },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: "#2962ff", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#2962ff" },
        horzLine: { color: "#2962ff", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#2962ff" },
      },
      rightPriceScale: {
        borderColor: "#2a2e39",
        scaleMargins: { top: 0.05, bottom: 0.15 },
      },
      timeScale: {
        borderColor: "#2a2e39",
        timeVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: 450,
    });

    chartRef.current = chart;

    // ── Line 1: Actual price (white) ──
    const actualLine = chart.addLineSeries({
      color: "#e0e3eb",
      lineWidth: 2,
      title: "Actual Price",
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
    });
    actualLine.setData(
      chartPrices.map((p) => ({
        time: p.date as any,
        value: Number(p.close),
      }))
    );

    // Volume histogram
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    volumeSeries.setData(
      chartPrices.map((p) => ({
        time: p.date as any,
        value: Number(p.volume),
        color: Number(p.close) >= Number(p.open) ? "#26a69a33" : "#ef535033",
      }))
    );

    // ── Line 2: Model strategy equity (orange) — from backtest ──
    if (prediction?.backtest && prediction.backtest.length > 0) {
      const modelLine = chart.addLineSeries({
        color: "#ff9800",
        lineWidth: 2,
        title: "Model Predicted",
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
      });
      modelLine.setData(
        prediction.backtest.map((p) => ({
          time: p.date as any,
          value: p.model_price,
        }))
      );
    }

    // ── Future prediction overlay ──
    if (prediction) {
      const lastPrice = chartPrices[chartPrices.length - 1];
      const lastClose = Number(lastPrice.close);

      // Use raw_direction to determine forecast direction.
      // If classifier says "down" but regressor says +%, flip the sign.
      const dir = prediction.raw_direction;
      let pctChange = prediction.predicted_pct_change;
      if (dir === "down" && pctChange > 0) pctChange = -Math.abs(pctChange);
      if (dir === "up" && pctChange < 0) pctChange = Math.abs(pctChange);

      const predictedPrice = lastClose * (1 + pctChange);

      const lastDate = new Date(lastPrice.date);
      const futureDate = new Date(lastDate);
      futureDate.setDate(futureDate.getDate() + 7);
      const futureDateStr = futureDate.toISOString().slice(0, 10);

      const predColor =
        dir === "up"
          ? "#26a69a"
          : dir === "down"
            ? "#ef5350"
            : "#ff9800";

      const forecastLine = chart.addLineSeries({
        color: predColor,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        title: `Forecast (${prediction.raw_direction})`,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: false,
      });
      forecastLine.setData([
        { time: lastPrice.date as any, value: lastClose },
        { time: futureDateStr as any, value: predictedPrice },
      ]);

      // Confidence band
      const spread = lastClose * 0.02 * (1 - prediction.confidence_score + 0.3);
      const upperBand = chart.addLineSeries({
        color: predColor, lineWidth: 1, lineStyle: LineStyle.Dotted,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      });
      upperBand.setData([
        { time: lastPrice.date as any, value: lastClose },
        { time: futureDateStr as any, value: predictedPrice + spread },
      ]);
      const lowerBand = chart.addLineSeries({
        color: predColor, lineWidth: 1, lineStyle: LineStyle.Dotted,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      });
      lowerBand.setData([
        { time: lastPrice.date as any, value: lastClose },
        { time: futureDateStr as any, value: predictedPrice - spread },
      ]);
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [chartPrices, prediction]);

  // Run prediction
  const handlePredict = useCallback(async () => {
    if (!selectedSymbol) return;
    setPredicting(true);
    setError("");
    setPrediction(null);
    try {
      const res = await fetch(`${API_BASE}/api/predict/${encodeURIComponent(selectedSymbol)}`);
      const data = await res.json();
      if (res.ok) {
        setPrediction(data);
        if (data.prices && data.prices.length > 0) {
          setChartPrices(data.prices);
        }
      } else {
        setError(data.error || "Prediction failed");
      }
    } catch (e: any) {
      setError(`API server not reachable. Run 'python app.py serve'. (${e.message})`);
    } finally {
      setPredicting(false);
    }
  }, [selectedSymbol]);

  // Train on stock
  const handleTrain = useCallback(async () => {
    if (!selectedSymbol) return;
    setTraining(true);
    setError("");
    setTrainResult(null);
    setTrainStatus("Starting training...");
    try {
      const res = await fetch(`${API_BASE}/api/train/stock`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: selectedSymbol, tune: false }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to start training");
        setTraining(false);
        setTrainStatus("");
        return;
      }

      const jobId = data.job_id;
      setTrainStatus("Training in progress...");

      const poll = async () => {
        try {
          const statusRes = await fetch(`${API_BASE}/api/train/${jobId}`);
          const statusData = await statusRes.json();
          if (statusData.status === "completed") {
            setTrainResult(statusData);
            setTrainStatus("");
            setTraining(false);
          } else if (statusData.status === "failed") {
            setError(statusData.error || "Training failed");
            setTrainStatus("");
            setTraining(false);
          } else {
            const elapsed = statusData.elapsed ? `${Math.round(statusData.elapsed)}s` : "";
            setTrainStatus(`Training${elapsed ? ` (${elapsed})` : ""}...`);
            setTimeout(poll, 3000);
          }
        } catch {
          setTimeout(poll, 5000);
        }
      };
      setTimeout(poll, 2000);
    } catch (e: any) {
      setError(`API server not reachable. (${e.message})`);
      setTraining(false);
      setTrainStatus("");
    }
  }, [selectedSymbol]);

  const dirColor = (dir: string) => {
    if (dir === "up") return "text-[#26a69a]";
    if (dir === "down") return "text-[#ef5350]";
    if (dir === "hold") return "text-[#ff9800]";
    return "text-[#787b86]";
  };

  const dirBg = (dir: string) => {
    if (dir === "up") return "bg-[#26a69a]/10 border-[#26a69a]/30";
    if (dir === "down") return "bg-[#ef5350]/10 border-[#ef5350]/30";
    if (dir === "hold") return "bg-[#ff9800]/10 border-[#ff9800]/30";
    return "bg-[#2a2e39] border-[#2a2e39]";
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold text-[#e0e3eb] uppercase tracking-wider">
          ML Prediction
        </h1>
        <span className="text-[10px] text-[#787b86]">5-day forward forecast</span>
      </div>

      {/* Controls row */}
      <div className="tv-card p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <label className="text-xs text-[#787b86]">Stock</label>
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="bg-[#1e222d] border border-[#2a2e39] text-[#e0e3eb] text-xs rounded px-3 py-2 focus:border-[#2962ff] focus:outline-none min-w-[200px]"
            >
              {stocks.map((s) => {
                const clean = s.symbol.replace(".NS", "").replace(".BO", "");
                return (
                  <option key={s.id} value={clean}>
                    {clean} — {s.company_name}
                  </option>
                );
              })}
            </select>
          </div>

          <button
            onClick={handlePredict}
            disabled={predicting || !selectedSymbol}
            className={`px-5 py-2 text-xs font-semibold rounded transition-colors ${
              predicting
                ? "bg-[#2a2e39] text-[#787b86] cursor-not-allowed"
                : "bg-[#2962ff] text-white hover:bg-[#2962ff]/80"
            }`}
          >
            {predicting ? "Running Model..." : "Run Prediction"}
          </button>

          <button
            onClick={handleTrain}
            disabled={training || !selectedSymbol}
            className={`px-5 py-2 text-xs font-semibold rounded transition-colors ${
              training
                ? "bg-[#2a2e39] text-[#787b86] cursor-not-allowed"
                : "bg-[#363a45] text-[#d1d4dc] hover:bg-[#434651]"
            }`}
          >
            {training ? "Training..." : "Train Model"}
          </button>

          {trainStatus && (
            <span className="text-xs text-[#787b86] animate-pulse">{trainStatus}</span>
          )}

          {/* Backtest stats badges */}
          {backtestStats && (
            <div className="ml-auto flex gap-2">
              {prediction?.backtest_stats && (
                <span className={`px-3 py-1 text-xs font-semibold rounded ${
                  prediction.backtest_stats.directional_accuracy > 0.5
                    ? "bg-[#26a69a]/15 text-[#26a69a]"
                    : "bg-[#ef5350]/15 text-[#ef5350]"
                }`}>
                  Direction: {(prediction.backtest_stats.directional_accuracy * 100).toFixed(1)}% ({prediction.backtest_stats.correct_signals}/{prediction.backtest_stats.total_signals})
                </span>
              )}
              <span className="px-3 py-1 text-xs font-semibold rounded bg-[#2962ff]/15 text-[#2962ff]">
                Avg Error: {backtestStats.avgError}% ({backtestStats.points} pts)
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="tv-card p-3 border border-[#ef5350]/30 bg-[#ef5350]/5">
          <p className="text-xs text-[#ef5350]">{error}</p>
        </div>
      )}

      {/* Prediction result banner */}
      {prediction && (
        <div className={`tv-card border ${dirBg(prediction.predicted_direction)}`}>
          <div className="p-4">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 items-center">
              <div className="text-center">
                <p className="text-[10px] text-[#787b86] uppercase mb-1">Signal</p>
                <p className={`text-2xl font-black ${dirColor(prediction.predicted_direction)}`}>
                  {prediction.predicted_direction === "up" ? "▲" : prediction.predicted_direction === "down" ? "▼" : "●"}{" "}
                  {prediction.predicted_direction.toUpperCase()}
                </p>
                {prediction.raw_direction !== prediction.predicted_direction && (
                  <p className="text-[10px] text-[#787b86] mt-0.5">
                    raw: {prediction.raw_direction}
                  </p>
                )}
              </div>

              <div className="text-center">
                <p className="text-[10px] text-[#787b86] uppercase mb-1">5-Day Return</p>
                <p className={`text-2xl font-bold font-tabular ${
                  correctedPct > 0 ? "text-[#26a69a]" : correctedPct < 0 ? "text-[#ef5350]" : "text-[#787b86]"
                }`}>
                  {correctedPct > 0 ? "+" : ""}
                  {(correctedPct * 100).toFixed(2)}%
                </p>
              </div>

              <div className="text-center">
                <p className="text-[10px] text-[#787b86] uppercase mb-1">Confidence</p>
                <p className="text-2xl font-bold font-tabular text-[#d1d4dc]">
                  {(prediction.confidence_score * 100).toFixed(1)}%
                </p>
                <div className="w-full bg-[#1e222d] rounded-full h-1.5 mt-2 mx-auto max-w-[100px]">
                  <div
                    className="h-1.5 rounded-full transition-all"
                    style={{
                      width: `${prediction.confidence_score * 100}%`,
                      backgroundColor: prediction.confidence_score > 0.5 ? "#26a69a" : prediction.confidence_score > 0.35 ? "#ff9800" : "#ef5350",
                    }}
                  />
                </div>
              </div>

              <div className="text-center">
                <p className="text-[10px] text-[#787b86] uppercase mb-1">Target Price</p>
                {prediction.prices && prediction.prices.length > 0 && (
                  <p className="text-2xl font-bold font-tabular text-[#d1d4dc]">
                    ₹{(Number(prediction.prices[prediction.prices.length - 1].close) * (1 + correctedPct)).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </p>
                )}
              </div>

              <div className="text-center">
                <p className="text-[10px] text-[#787b86] uppercase mb-1">Current</p>
                {prediction.prices && prediction.prices.length > 0 && (
                  <p className="text-2xl font-bold font-tabular text-[#787b86]">
                    ₹{Number(prediction.prices[prediction.prices.length - 1].close).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Chart */}
      <div className="tv-card overflow-hidden">
        <div className="tv-card-header">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
              {selectedSymbol || "—"} — Model vs Actual
            </span>
          </div>
          {/* Chart legend */}
          <div className="flex gap-3 text-[10px]">
            <span className="flex items-center gap-1">
              <span className="w-4 h-0.5 inline-block bg-[#e0e3eb]" />
              <span className="text-[#787b86]">Actual Price</span>
            </span>
            {prediction?.backtest && prediction.backtest.length > 0 && (
              <span className="flex items-center gap-1">
                <span className="w-4 h-0.5 inline-block bg-[#ff9800]" />
                <span className="text-[#787b86]">Model Predicted</span>
              </span>
            )}
            {prediction && (
              <span className="flex items-center gap-1">
                <span className="w-4 h-0.5 inline-block" style={{ borderBottom: "2px dashed #2962ff" }} />
                <span className="text-[#787b86]">Forecast</span>
              </span>
            )}
          </div>
        </div>
        {loading ? (
          <div className="h-[450px] flex items-center justify-center">
            <div className="text-[#787b86] text-sm">Loading chart...</div>
          </div>
        ) : chartPrices.length === 0 ? (
          <div className="h-[450px] flex items-center justify-center flex-col gap-2">
            <p className="text-[#787b86] text-sm">No price data available</p>
            <p className="text-[#787b86] text-xs">Make sure the API server is running: python app.py serve</p>
          </div>
        ) : (
          <div ref={chartContainerRef} />
        )}
      </div>

      {/* Bottom section */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* Feature importance */}
        {prediction && prediction.top_features && prediction.top_features.length > 0 && (
          <div className="tv-card">
            <div className="tv-card-header">
              <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
                Top Feature Drivers
              </span>
            </div>
            <div className="p-4 space-y-2">
              {prediction.top_features.map((f, i) => (
                <div key={f.feature} className="flex items-center gap-3 text-xs">
                  <span className="text-[#787b86] w-4 text-right font-tabular">{i + 1}</span>
                  <span className="text-[#d1d4dc] w-44 truncate">{f.feature}</span>
                  <div className="flex-1 bg-[#1e222d] rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${Math.min(100, (f.importance / (prediction.top_features[0]?.importance || 1)) * 100)}%`,
                        backgroundColor: i === 0 ? "#2962ff" : i < 3 ? "#2962ff99" : "#2962ff55",
                      }}
                    />
                  </div>
                  <span className="text-[#787b86] font-tabular w-12 text-right">{f.importance}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Training results */}
        {trainResult && (
          <div className="tv-card">
            <div className="tv-card-header">
              <span className="text-xs font-medium text-[#26a69a] uppercase tracking-wider">
                Training Complete
              </span>
              <span className="text-xs text-[#787b86]">
                {trainResult.version} — {trainResult.elapsed}s
              </span>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(trainResult.metrics).map(([key, val]) => (
                  <div key={key}>
                    <p className="text-lg font-bold text-[#d1d4dc] font-tabular">
                      {typeof val === "number"
                        ? val < 1
                          ? (val * 100).toFixed(1) + "%"
                          : val.toFixed(4)
                        : val}
                    </p>
                    <p className="text-[10px] text-[#787b86] uppercase">
                      {key.replace(/_/g, " ")}
                    </p>
                  </div>
                ))}
              </div>
              <div className="flex gap-4 mt-3 pt-3 border-t border-[#1e222d] text-xs text-[#787b86]">
                <span>Train: {trainResult.samples.train.toLocaleString()} samples</span>
                <span>Test: {trainResult.samples.test.toLocaleString()} samples</span>
                <span>{trainResult.features} features</span>
              </div>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!prediction && !trainResult && (
          <div className="tv-card lg:col-span-2">
            <div className="p-8 text-center">
              <p className="text-sm text-[#787b86]">
                Select a stock and click <span className="text-[#2962ff] font-medium">Run Prediction</span> to see model vs actual price
              </p>
              <p className="text-xs text-[#787b86] mt-1">
                The chart shows two lines: <span className="text-[#e0e3eb]">white = actual price</span> and <span className="text-[#ff9800]">orange = model predicted price</span> (5-day forecast)
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Backtest comparison table */}
      {prediction?.backtest && prediction.backtest.length > 0 && (
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
              Predicted vs Actual Price ({prediction.backtest.length} points)
            </span>
            {backtestStats && (
              <span className="text-xs font-semibold text-[#2962ff]">
                Avg Error: {backtestStats.avgError}%
              </span>
            )}
          </div>
          <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-[#1e222d]">
                <tr className="border-b border-[#2a2e39]">
                  <th className="text-left px-4 py-2 text-[#787b86] font-medium">Date</th>
                  <th className="text-center px-4 py-2 text-[#787b86] font-medium">Direction</th>
                  <th className="text-right px-4 py-2 text-[#787b86] font-medium">Predicted</th>
                  <th className="text-right px-4 py-2 text-[#787b86] font-medium">Actual Price</th>
                  <th className="text-right px-4 py-2 text-[#787b86] font-medium">Diff</th>
                  <th className="text-center px-4 py-2 text-[#787b86] font-medium">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {prediction.backtest.slice().reverse().slice(0, 50).map((p, i) => {
                  const err = p.model_price - p.actual_price;
                  const errPct = ((err / p.actual_price) * 100);
                  return (
                    <tr key={`${p.date}-${i}`} className="border-b border-[#1e222d]/50 hover:bg-[#1e222d]/30">
                      <td className="px-4 py-2 text-[#d1d4dc] font-tabular">{p.date}</td>
                      <td className="px-4 py-2 text-center">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          p.direction === "up" ? "bg-[#26a69a]/15 text-[#26a69a]"
                            : p.direction === "down" ? "bg-[#ef5350]/15 text-[#ef5350]"
                            : "bg-[#ff9800]/15 text-[#ff9800]"
                        }`}>
                          {p.direction === "up" ? "▲" : p.direction === "down" ? "▼" : "●"} {(p.direction || "").toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right text-[#ff9800] font-tabular">
                        ₹{p.model_price.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                      </td>
                      <td className="px-4 py-2 text-right text-[#e0e3eb] font-tabular">
                        ₹{p.actual_price.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                      </td>
                      <td className={`px-4 py-2 text-right font-tabular ${
                        Math.abs(errPct) < 1 ? "text-[#26a69a]" : Math.abs(errPct) < 3 ? "text-[#ff9800]" : "text-[#ef5350]"
                      }`}>
                        {errPct > 0 ? "+" : ""}{errPct.toFixed(2)}%
                      </td>
                      <td className="px-4 py-2 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <div className="w-12 bg-[#1e222d] rounded-full h-1.5">
                            <div
                              className="h-1.5 rounded-full"
                              style={{
                                width: `${p.confidence * 100}%`,
                                backgroundColor: p.confidence > 0.5 ? "#26a69a" : p.confidence > 0.35 ? "#ff9800" : "#ef5350",
                              }}
                            />
                          </div>
                          <span className="text-[#787b86] font-tabular">{(p.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
