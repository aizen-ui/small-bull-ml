"use client";

import { useState, useRef, useCallback, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface UploadResult {
  message: string;
  filename: string;
  features_extracted: number;
  features: Record<string, number | null>;
}

interface UploadedFile {
  filename: string;
  size_kb: number;
}

interface TrainResult {
  message: string;
  version: string;
  metrics: Record<string, number>;
  samples: { train: number; test: number };
  features: number;
}

export default function UploadPage() {
  const [uploading, setUploading] = useState(false);
  const [training, setTraining] = useState(false);
  const [trainStatus, setTrainStatus] = useState<string>("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [trainResult, setTrainResult] = useState<TrainResult | null>(null);
  const [error, setError] = useState<string>("");
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadFiles = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/uploads`);
      if (res.ok) {
        const data = await res.json();
        setFiles(data.files || []);
      }
    } catch {
      // API server might not be running
    }
  }, []);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setResult(data);
        loadFiles();
      } else {
        setError(data.error || "Upload failed");
      }
    } catch (e: any) {
      setError(
        `Failed to connect to API server. Make sure 'python app.py serve' is running. (${e.message})`
      );
    } finally {
      setUploading(false);
    }
  };

  const handleTrain = async () => {
    setTraining(true);
    setError("");
    setTrainResult(null);
    setTrainStatus("Starting training...");

    try {
      // Start training (returns immediately with job_id)
      const res = await fetch(`${API_BASE}/api/train`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tune: false }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to start training");
        setTraining(false);
        return;
      }

      const jobId = data.job_id;
      setTrainStatus("Training in progress... This may take a few minutes.");

      // Poll for completion
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
            // Still running, poll again
            const elapsed = statusData.elapsed
              ? `${Math.round(statusData.elapsed)}s`
              : "";
            setTrainStatus(
              `Training in progress${elapsed ? ` (${elapsed})` : ""}...`
            );
            setTimeout(poll, 3000);
          }
        } catch {
          // Server might be busy, retry
          setTimeout(poll, 5000);
        }
      };

      // Start polling after 2 seconds
      setTimeout(poll, 2000);
    } catch (e: any) {
      setError(
        `Failed to connect to API server. Make sure 'python app.py serve' is running. (${e.message})`
      );
      setTraining(false);
      setTrainStatus("");
    }
  };

  const handleDelete = async (filename: string) => {
    try {
      await fetch(`${API_BASE}/api/uploads/${encodeURIComponent(filename)}`, {
        method: "DELETE",
      });
      loadFiles();
    } catch {
      // ignore
    }
  };

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const file = e.dataTransfer.files[0];
      if (file && (file.name.endsWith(".xlsx") || file.name.endsWith(".xls"))) {
        handleUpload(file);
      } else {
        setError("Please upload an .xlsx or .xls file");
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  };

  const formatFeatureValue = (val: number | null) => {
    if (val === null || val === undefined) return "N/A";
    if (Math.abs(val) < 1) return (val * 100).toFixed(2) + "%";
    return val.toFixed(2);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold text-[#e0e3eb]">
          Upload Financial Data
        </h1>
        <p className="text-xs text-[#787b86] mt-1">
          Upload Screener.in Excel exports to add company fundamentals to the ML
          model. After uploading, retrain the model to include the new data.
        </p>
      </div>

      {/* Upload zone */}
      <div
        className={`tv-card border-2 border-dashed transition-colors cursor-pointer ${
          dragActive
            ? "border-[#2962ff] bg-[#2962ff]/5"
            : "border-[#2a2e39] hover:border-[#787b86]"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="p-8 text-center">
          <div className="text-3xl mb-2 text-[#787b86]">
            {uploading ? "..." : "+"}
          </div>
          <p className="text-sm text-[#d1d4dc]">
            {uploading
              ? "Uploading & extracting features..."
              : "Drop xlsx file here or click to browse"}
          </p>
          <p className="text-xs text-[#787b86] mt-1">
            Supports Screener.in exports (.xlsx, .xls)
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={onFileSelect}
        />
      </div>

      {error && (
        <div className="tv-card p-3 border border-[#ef5350]/30 bg-[#ef5350]/5">
          <p className="text-xs text-[#ef5350]">{error}</p>
        </div>
      )}

      {/* Upload result */}
      {result && (
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#26a69a] uppercase tracking-wider">
              Upload Successful
            </span>
            <span className="text-xs text-[#787b86]">
              {result.features_extracted} features extracted
            </span>
          </div>
          <div className="p-3">
            <p className="text-sm text-[#d1d4dc] mb-3">{result.filename}</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.entries(result.features).map(([key, val]) => (
                <div
                  key={key}
                  className="flex justify-between text-xs py-1 border-b border-[#1e222d]"
                >
                  <span className="text-[#787b86]">
                    {key.replace("f_", "").replace(/_/g, " ")}
                  </span>
                  <span className="text-[#d1d4dc] font-tabular font-medium">
                    {formatFeatureValue(val)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Uploaded files list */}
      {files.length > 0 && (
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">
              Uploaded Files
            </span>
            <span className="text-xs text-[#787b86]">
              {files.length} file(s)
            </span>
          </div>
          <div className="p-3 space-y-1">
            {files.map((f) => (
              <div
                key={f.filename}
                className="flex items-center justify-between py-1.5 text-xs border-b border-[#1e222d] last:border-0"
              >
                <span className="text-[#d1d4dc]">{f.filename}</span>
                <div className="flex items-center gap-3">
                  <span className="text-[#787b86] font-tabular">
                    {f.size_kb} KB
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(f.filename);
                    }}
                    className="text-[#ef5350] hover:text-[#ef5350]/80"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Train button */}
      <div className="tv-card p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-[#d1d4dc] font-medium">
              Retrain Model
            </p>
            <p className="text-xs text-[#787b86] mt-0.5">
              Retrain with all uploaded fundamentals + latest market data
            </p>
          </div>
          <button
            onClick={handleTrain}
            disabled={training}
            className={`px-4 py-2 text-xs font-medium rounded transition-colors ${
              training
                ? "bg-[#2a2e39] text-[#787b86] cursor-not-allowed"
                : "bg-[#2962ff] text-white hover:bg-[#2962ff]/80"
            }`}
          >
            {training ? "Training..." : "Train Now"}
          </button>
        </div>
        {trainStatus && (
          <p className="text-xs text-[#787b86] mt-2 animate-pulse">
            {trainStatus}
          </p>
        )}
      </div>

      {/* Train result */}
      {trainResult && (
        <div className="tv-card">
          <div className="tv-card-header">
            <span className="text-xs font-medium text-[#26a69a] uppercase tracking-wider">
              Training Complete
            </span>
            <span className="text-xs text-[#787b86]">
              {trainResult.version}
            </span>
          </div>
          <div className="p-3">
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
              <span>
                Train: {trainResult.samples.train.toLocaleString()} samples
              </span>
              <span>
                Test: {trainResult.samples.test.toLocaleString()} samples
              </span>
              <span>{trainResult.features} features</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
