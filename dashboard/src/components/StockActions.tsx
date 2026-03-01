"use client";

import { useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface PredictionResult {
  symbol: string;
  predicted_direction: string;
  raw_direction: string;
  predicted_pct_change: number;
  confidence_score: number;
  top_features: { feature: string; importance: number }[];
}

interface TrainResult {
  message: string;
  version: string;
  metrics: Record<string, number>;
  samples: { train: number; test: number };
  features: number;
}

export default function StockActions({ symbol }: { symbol: string }) {
  const [predicting, setPredicting] = useState(false);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [training, setTraining] = useState(false);
  const [trainStatus, setTrainStatus] = useState("");
  const [trainResult, setTrainResult] = useState<TrainResult | null>(null);
  const [error, setError] = useState("");

  const cleanSymbol = symbol.replace(".NS", "").replace(".BO", "");

  const handlePredict = useCallback(async () => {
    setPredicting(true);
    setError("");
    setPrediction(null);
    try {
      const res = await fetch(`${API_BASE}/api/predict/${encodeURIComponent(cleanSymbol)}`);
      const data = await res.json();
      if (res.ok) {
        setPrediction(data);
      } else {
        setError(data.error || "Prediction failed");
      }
    } catch (e: any) {
      setError(`API server not reachable. Run 'python app.py serve'. (${e.message})`);
    } finally {
      setPredicting(false);
    }
  }, [cleanSymbol]);

  const handleTrain = useCallback(async () => {
    setTraining(true);
    setError("");
    setTrainResult(null);
    setTrainStatus("Starting training...");
    try {
      const res = await fetch(`${API_BASE}/api/train/stock`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: cleanSymbol, tune: false }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to start training");
        setTraining(false);
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
  }, [cleanSymbol]);

  const dirColor = (dir: string) => {
    if (dir === "up") return "text-[#26a69a]";
    if (dir === "down") return "text-[#ef5350]";
    if (dir === "hold") return "text-[#ff9800]";
    return "text-[#787b86]";
  };

  return (
    <div className="space-y-3">
      {/* Action buttons */}
      <div className="tv-card p-4">
        <div className="flex items-center gap-3">
          <button
            onClick={handlePredict}
            disabled={predicting}
            className={`px-4 py-2 text-xs font-medium rounded transition-colors ${
              predicting
                ? "bg-[#2a2e39] text-[#787b86] cursor-not-allowed"
                : "bg-[#2962ff] text-white hover:bg-[#2962ff]/80"
            }`}
          >
            {predicting ? "Predicting..." : "Run Prediction"}
          </button>
          <button
            onClick={handleTrain}
            disabled={training}
            className={`px-4 py-2 text-xs font-medium rounded transition-colors ${
              training
                ? "bg-[#2a2e39] text-[#787b86] cursor-not-allowed"
                : "bg-[#363a45] text-[#d1d4dc] hover:bg-[#434651]"
            }`}
          >
            {training ? "Training..." : "Train on This Stock"}
          </button>
        </div>
        {trainStatus && (
          <p className="text-xs text-[#787b86] mt-2 animate-pulse">{trainStatus}</p>
        )}
      </div>

      {error && (
        <div className="tv-card p-3 border border-[#ef5350]/30 bg-[#ef5350]/5">
          <p className="text-xs text-[#ef5350]">{error}</p>
        </div>
      )}

      {/* Prediction result */}
      {prediction && (
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
              ML Prediction
            </span>
            <span className="text-xs text-[#787b86]">5-day forward</span>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-[10px] text-[#787b86] uppercase">Direction</p>
                <p className={`text-lg font-bold mt-1 ${dirColor(prediction.predicted_direction)}`}>
                  {prediction.predicted_direction.toUpperCase()}
                </p>
                {prediction.raw_direction !== prediction.predicted_direction && (
                  <p className="text-[10px] text-[#787b86] mt-0.5">
                    raw: {prediction.raw_direction}
                  </p>
                )}
              </div>
              <div>
                <p className="text-[10px] text-[#787b86] uppercase">Expected Change</p>
                <p className={`text-lg font-bold font-tabular mt-1 ${
                  prediction.predicted_pct_change > 0 ? "text-[#26a69a]" : prediction.predicted_pct_change < 0 ? "text-[#ef5350]" : "text-[#787b86]"
                }`}>
                  {prediction.predicted_pct_change > 0 ? "+" : ""}
                  {(prediction.predicted_pct_change * 100).toFixed(2)}%
                </p>
              </div>
              <div>
                <p className="text-[10px] text-[#787b86] uppercase">Confidence</p>
                <p className="text-lg font-bold font-tabular mt-1 text-[#d1d4dc]">
                  {(prediction.confidence_score * 100).toFixed(1)}%
                </p>
              </div>
            </div>

            {prediction.top_features && prediction.top_features.length > 0 && (
              <div className="mt-4 pt-3 border-t border-[#1e222d]">
                <p className="text-[10px] text-[#787b86] uppercase mb-2">Top Feature Drivers</p>
                <div className="space-y-1">
                  {prediction.top_features.map((f) => (
                    <div key={f.feature} className="flex items-center gap-2 text-xs">
                      <span className="text-[#787b86] w-40 truncate">{f.feature}</span>
                      <div className="flex-1 bg-[#1e222d] rounded-full h-1.5">
                        <div
                          className="bg-[#2962ff] h-1.5 rounded-full"
                          style={{
                            width: `${Math.min(100, (f.importance / (prediction.top_features[0]?.importance || 1)) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-[#787b86] font-tabular w-10 text-right">
                        {f.importance}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Train result */}
      {trainResult && (
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#26a69a] uppercase tracking-wider">
              Training Complete
            </span>
            <span className="text-xs text-[#787b86]">{trainResult.version}</span>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(trainResult.metrics).map(([key, val]) => (
                <div key={key} className="text-center">
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
    </div>
  );
}
