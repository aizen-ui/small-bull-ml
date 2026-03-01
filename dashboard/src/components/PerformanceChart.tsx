"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface DataPoint {
  date: string;
  accuracy: number;
  directional_accuracy?: number;
}

interface Props {
  data: DataPoint[];
  title?: string;
}

export default function PerformanceChart({ data, title }: Props) {
  return (
    <div>
      {title && (
        <h3 className="text-sm font-medium text-[#a0a0a0] mb-3">{title}</h3>
      )}
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#a0a0a0", fontSize: 11 }}
            tickFormatter={(v) => v.slice(5)}
          />
          <YAxis
            tick={{ fill: "#a0a0a0", fontSize: 11 }}
            domain={[0, 1]}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          />
          <Tooltip
            contentStyle={{
              background: "#1a1a1a",
              border: "1px solid #2a2a2a",
              borderRadius: 8,
            }}
            labelStyle={{ color: "#a0a0a0" }}
            formatter={(value: number) => `${(value * 100).toFixed(1)}%`}
          />
          <Line
            type="monotone"
            dataKey="accuracy"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Overall Accuracy"
          />
          {data.some((d) => d.directional_accuracy !== undefined) && (
            <Line
              type="monotone"
              dataKey="directional_accuracy"
              stroke="#22c55e"
              strokeWidth={2}
              dot={false}
              name="Directional Accuracy"
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
