"use client";

import { useState } from "react";
import type { Stock } from "@/lib/types";

interface Props {
  stocks: Stock[];
  selectedId: number;
  onSelect: (id: number) => void;
}

export default function StockSelector({ stocks, selectedId, onSelect }: Props) {
  const [search, setSearch] = useState("");

  const filtered = stocks.filter(
    (s) =>
      s.symbol.toLowerCase().includes(search.toLowerCase()) ||
      s.company_name.toLowerCase().includes(search.toLowerCase())
  );

  const selected = stocks.find((s) => s.id === selectedId);

  return (
    <div className="relative">
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder={selected ? selected.symbol.replace(".NS", "") : "Search stock..."}
        className="w-full bg-[#1e222d] border border-[#2a2e39] rounded px-3 py-1.5 text-sm text-[#d1d4dc] placeholder-[#787b86] focus:outline-none focus:border-[#2962ff]"
      />
      {search && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[#1e222d] border border-[#2a2e39] rounded max-h-60 overflow-y-auto z-20">
          {filtered.map((stock) => (
            <button
              key={stock.id}
              onClick={() => {
                onSelect(stock.id);
                setSearch("");
              }}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-[#2a2e39] flex justify-between ${
                stock.id === selectedId ? "bg-[#2a2e39]" : ""
              }`}
            >
              <span className="text-[#d1d4dc] font-medium">
                {stock.symbol.replace(".NS", "")}
              </span>
              <span className="text-[#787b86] text-xs">{stock.sector}</span>
            </button>
          ))}
          {filtered.length === 0 && (
            <p className="px-3 py-2 text-sm text-[#787b86]">No results</p>
          )}
        </div>
      )}
    </div>
  );
}
