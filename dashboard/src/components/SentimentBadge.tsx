interface Props {
  score: number;
  size?: "sm" | "md";
}

export default function SentimentBadge({ score, size = "sm" }: Props) {
  const color =
    score > 0.1
      ? "bg-green-500/20 text-green-400"
      : score < -0.1
        ? "bg-red-500/20 text-red-400"
        : "bg-yellow-500/20 text-yellow-400";

  const label =
    score > 0.1 ? "Positive" : score < -0.1 ? "Negative" : "Neutral";

  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";

  return (
    <span className={`rounded-full font-medium ${color} ${padding}`}>
      {label} ({score > 0 ? "+" : ""}
      {score.toFixed(2)})
    </span>
  );
}
