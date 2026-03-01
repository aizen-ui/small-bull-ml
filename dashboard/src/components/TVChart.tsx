"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, LineStyle } from "lightweight-charts";
import { createBrowserClient } from "@/lib/supabase";
import type { Prediction } from "@/lib/types";

interface Props {
  stockId: number;
  symbol: string;
  initialPrices: { time: string; value: number }[];
  initialMinutePreds: { time: string; value: number }[];
  initialNightlyPreds: { time: string; value: number }[];
}

export default function TVChart({
  stockId,
  symbol,
  initialPrices,
  initialMinutePreds,
  initialNightlyPreds,
}: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const priceSeriesRef = useRef<any>(null);
  const minuteSeriesRef = useRef<any>(null);
  const nightlySeriesRef = useRef<any>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#131722" },
        textColor: "#787b86",
        fontSize: 11,
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
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: "#2a2e39",
        timeVisible: true,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: 500,
    });

    chartRef.current = chart;

    // Actual price line (white)
    const priceSeries = chart.addLineSeries({
      color: "#d1d4dc",
      lineWidth: 2,
      title: "Actual Price",
      priceLineVisible: true,
      lastValueVisible: true,
    });
    priceSeries.setData(initialPrices);
    priceSeriesRef.current = priceSeries;

    // Model minute prediction line (green/teal, dotted)
    const minuteSeries = chart.addLineSeries({
      color: "#26a69a",
      lineWidth: 2,
      lineStyle: LineStyle.Dotted,
      title: "Model (1min)",
      priceLineVisible: false,
      lastValueVisible: true,
    });
    minuteSeries.setData(initialMinutePreds);
    minuteSeriesRef.current = minuteSeries;

    // Model nightly prediction line (blue, dashed)
    const nightlySeries = chart.addLineSeries({
      color: "#2962ff",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      title: "Model (Daily)",
      priceLineVisible: false,
      lastValueVisible: true,
    });
    nightlySeries.setData(initialNightlyPreds);
    nightlySeriesRef.current = nightlySeries;

    chart.timeScale().fitContent();

    // Resize handler
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    // Realtime subscription for new predictions
    const supabase = createBrowserClient();
    const channel = supabase
      .channel(`predictions-${stockId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "predictions",
          filter: `stock_id=eq.${stockId}`,
        },
        (payload) => {
          const pred = payload.new as Prediction;
          const ts = Math.floor(new Date(pred.prediction_timestamp).getTime() / 1000);
          // Get latest price to project prediction
          const latestPrices = initialPrices;
          const lastPrice = latestPrices.length > 0
            ? latestPrices[latestPrices.length - 1].value
            : 0;
          const projectedPrice = lastPrice * (1 + pred.predicted_pct_change);

          const point = { time: ts as any, value: projectedPrice };

          if (pred.prediction_type === "minute" && minuteSeriesRef.current) {
            minuteSeriesRef.current.update(point);
          } else if (pred.prediction_type === "nightly" && nightlySeriesRef.current) {
            nightlySeriesRef.current.update(point);
          }
        }
      )
      .subscribe();

    // Realtime subscription for new intraday prices
    const priceChannel = supabase
      .channel(`prices-${stockId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "intraday_prices",
          filter: `stock_id=eq.${stockId}`,
        },
        (payload) => {
          const price = payload.new;
          const ts = Math.floor(new Date(price.timestamp).getTime() / 1000);
          if (priceSeriesRef.current) {
            priceSeriesRef.current.update({
              time: ts as any,
              value: Number(price.close),
            });
          }
        }
      )
      .subscribe();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      supabase.removeChannel(channel);
      supabase.removeChannel(priceChannel);
    };
  }, [stockId, symbol, initialPrices, initialMinutePreds, initialNightlyPreds]);

  return (
    <div className="relative">
      {/* Legend */}
      <div className="absolute top-2 left-2 z-10 flex gap-4 text-[10px] font-medium">
        <span className="flex items-center gap-1">
          <span className="w-4 h-0.5 bg-[#d1d4dc] inline-block" />
          <span className="text-[#787b86]">Actual Price</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-4 h-0.5 inline-block" style={{ borderBottom: "2px dotted #26a69a" }} />
          <span className="text-[#787b86]">Model (1-min)</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-4 h-0.5 inline-block" style={{ borderBottom: "2px dashed #2962ff" }} />
          <span className="text-[#787b86]">Model (Daily)</span>
        </span>
      </div>
      <div ref={chartContainerRef} />
    </div>
  );
}
