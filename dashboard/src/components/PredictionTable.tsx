"use client";

import { Prediction, Stock } from "@/lib/types";
import Link from "next/link";

interface Props {
  predictions: (Prediction & { stock?: Stock })[];
  showStock?: boolean;
}

export default function PredictionTable({
  predictions,
  showStock = true,
}: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#2a2a2a] text-[#a0a0a0]">
            {showStock && <th className="text-left py-2 px-3">Stock</th>}
            <th className="text-left py-2 px-3">Direction</th>
            <th className="text-right py-2 px-3">Predicted %</th>
            <th className="text-right py-2 px-3">Confidence</th>
            <th className="text-right py-2 px-3">Actual %</th>
            <th className="text-center py-2 px-3">Correct</th>
          </tr>
        </thead>
        <tbody>
          {predictions.map((p) => (
            <tr
              key={p.id}
              className="border-b border-[#1a1a1a] hover:bg-[#1a1a1a]"
            >
              {showStock && (
                <td className="py-2 px-3">
                  {p.stock ? (
                    <Link
                      href={`/stocks/${p.stock.symbol}`}
                      className="text-blue-400 hover:underline"
                    >
                      {p.stock.symbol.replace(".NS", "")}
                    </Link>
                  ) : (
                    `#${p.stock_id}`
                  )}
                </td>
              )}
              <td className="py-2 px-3">
                <span
                  className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    p.predicted_direction === "up"
                      ? "bg-green-500/20 text-green-400"
                      : p.predicted_direction === "down"
                        ? "bg-red-500/20 text-red-400"
                        : "bg-yellow-500/20 text-yellow-400"
                  }`}
                >
                  {p.predicted_direction.toUpperCase()}
                </span>
              </td>
              <td
                className={`py-2 px-3 text-right ${
                  p.predicted_pct_change > 0
                    ? "text-green-400"
                    : p.predicted_pct_change < 0
                      ? "text-red-400"
                      : ""
                }`}
              >
                {p.predicted_pct_change > 0 ? "+" : ""}
                {(p.predicted_pct_change * 100).toFixed(2)}%
              </td>
              <td className="py-2 px-3 text-right">
                {(p.confidence_score * 100).toFixed(1)}%
              </td>
              <td
                className={`py-2 px-3 text-right ${
                  p.actual_pct_change !== null
                    ? p.actual_pct_change > 0
                      ? "text-green-400"
                      : "text-red-400"
                    : "text-[#a0a0a0]"
                }`}
              >
                {p.actual_pct_change !== null
                  ? `${p.actual_pct_change > 0 ? "+" : ""}${(p.actual_pct_change * 100).toFixed(2)}%`
                  : "—"}
              </td>
              <td className="py-2 px-3 text-center">
                {p.was_correct === null
                  ? "—"
                  : p.was_correct
                    ? "✓"
                    : "✗"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {predictions.length === 0 && (
        <p className="text-center py-8 text-[#a0a0a0]">No predictions yet</p>
      )}
    </div>
  );
}
