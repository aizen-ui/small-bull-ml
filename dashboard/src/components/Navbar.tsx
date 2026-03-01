"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/stocks", label: "Stocks" },
  { href: "/predict", label: "Predict" },
  { href: "/predictions", label: "Predictions" },
  { href: "/model", label: "Model" },
  { href: "/sentiment", label: "Sentiment" },
  { href: "/upload", label: "Upload" },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-[#2a2e39] bg-[#131722] sticky top-0 z-50">
      <div className="max-w-[1600px] mx-auto px-4">
        <div className="flex items-center justify-between h-12">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-[#2962ff] flex items-center justify-center text-xs font-bold text-white">
                ML
              </div>
              <span className="font-semibold text-[#e0e3eb] text-sm">
                Stock Predictor
              </span>
            </Link>
            <div className="flex">
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors border-b-2 ${
                    pathname === link.href ||
                    (link.href !== "/" && pathname.startsWith(link.href))
                      ? "border-[#2962ff] text-[#e0e3eb]"
                      : "border-transparent text-[#787b86] hover:text-[#d1d4dc]"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#26a69a] animate-pulse-live" />
              <span className="text-[#787b86]">LIVE</span>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
