import { supabase } from "@/lib/supabase";
import PerformanceChart from "@/components/PerformanceChart";
import type { ModelPerformance } from "@/lib/types";

export const revalidate = 60;

async function getModelData() {
  const { data: performance } = await supabase
    .from("model_performance")
    .select("*")
    .order("evaluation_date", { ascending: true });
  return { performance: performance || [] };
}

export default async function ModelPage() {
  const { performance } = await getModelData();
  const latest = performance.length > 0 ? performance[performance.length - 1] : null;

  return (
    <div className="space-y-4">
      <h1 className="text-sm font-semibold text-[#e0e3eb] uppercase tracking-wider">Model Performance</h1>

      {latest && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ["Version", latest.model_version, ""],
            ["Accuracy", `${(latest.accuracy * 100).toFixed(1)}%`, "Overall"],
            ["Dir. Accuracy", `${(latest.directional_accuracy * 100).toFixed(1)}%`, "Up/Down only"],
            ["F1 Score", `${(latest.f1_up * 100).toFixed(1)}%`, "Weighted"],
            ["MAE", latest.mae?.toFixed(4) || "—", "Mean Absolute Error"],
            ["RMSE", latest.rmse?.toFixed(4) || "—", "Root Mean Sq Error"],
            ["Precision", `${(latest.precision_up * 100).toFixed(1)}%`, "Weighted"],
            ["Recall", `${(latest.recall_up * 100).toFixed(1)}%`, "Weighted"],
          ].map(([label, val, sub]) => (
            <div key={label as string} className="tv-card p-4">
              <p className="text-[10px] text-[#787b86] uppercase tracking-wider">{label as string}</p>
              <p className="text-xl font-bold text-[#e0e3eb] mt-1 font-tabular">{val}</p>
              {sub && <p className="text-[10px] text-[#787b86] mt-0.5">{sub as string}</p>}
            </div>
          ))}
        </div>
      )}

      {performance.length > 0 && (
        <div className="tv-card p-4">
          <PerformanceChart
            data={performance.map((p: ModelPerformance) => ({
              date: p.evaluation_date,
              accuracy: p.accuracy,
              directional_accuracy: p.directional_accuracy,
            }))}
            title="Accuracy Over Time"
          />
        </div>
      )}

      <div className="tv-card">
        <div className="tv-card-header">
          <span className="text-xs font-medium text-[#787b86] uppercase tracking-wider">Version History</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#2a2e39] text-[#787b86]">
                <th className="text-left py-2 px-4 font-medium">Version</th>
                <th className="text-left py-2 px-4 font-medium">Date</th>
                <th className="text-right py-2 px-4 font-medium">Accuracy</th>
                <th className="text-right py-2 px-4 font-medium">Dir. Acc</th>
                <th className="text-right py-2 px-4 font-medium">F1</th>
                <th className="text-right py-2 px-4 font-medium">MAE</th>
                <th className="text-right py-2 px-4 font-medium">RMSE</th>
              </tr>
            </thead>
            <tbody>
              {[...performance].reverse().map((p: ModelPerformance) => (
                <tr key={p.id} className="border-b border-[#1e222d] hover:bg-[#2a2e39]/30">
                  <td className="py-1.5 px-4 font-mono text-[10px] text-[#5b9cf6]">{p.model_version}</td>
                  <td className="py-1.5 px-4 text-[#787b86]">{p.evaluation_date}</td>
                  <td className="py-1.5 px-4 text-right font-tabular text-[#d1d4dc]">{(p.accuracy * 100).toFixed(1)}%</td>
                  <td className="py-1.5 px-4 text-right font-tabular text-[#d1d4dc]">{(p.directional_accuracy * 100).toFixed(1)}%</td>
                  <td className="py-1.5 px-4 text-right font-tabular text-[#d1d4dc]">{(p.f1_up * 100).toFixed(1)}%</td>
                  <td className="py-1.5 px-4 text-right font-tabular text-[#d1d4dc]">{p.mae?.toFixed(4)}</td>
                  <td className="py-1.5 px-4 text-right font-tabular text-[#d1d4dc]">{p.rmse?.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {performance.length === 0 && <p className="text-center py-6 text-xs text-[#787b86]">No models trained yet</p>}
        </div>
      </div>
    </div>
  );
}
