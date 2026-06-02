// dashboard/components/Sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/",          label: "Overview",       icon: "📊" },
  { href: "/positions", label: "Positions",      icon: "📋" },
  { href: "/meme",      label: "Meme Bot",       icon: "🚀" },
  { href: "/log",       label: "Trade Log",      icon: "📜" },
  { href: "/signals",   label: "Signals",        icon: "📡" },
];

export default function Sidebar({ mode = "testnet", activeStrategy = "Unknown" }: { mode?: string, activeStrategy?: string }) {
  const pathname = usePathname();
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-text">HYPER-SCALP-AI</div>
        <div className="logo-sub">$100 → $10,000</div>
      </div>

      <nav className="sidebar-nav">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={`nav-link${pathname === n.href ? " active" : ""}`}
          >
            <span className="nav-icon">{n.icon}</span>
            {n.label}
          </Link>
        ))}
      </nav>

      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "12px", padding: "0 12px", marginBottom: "12px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
           <div style={{ fontSize: "10px", color: "var(--text-muted)", letterSpacing: "0.05em", textTransform: "uppercase", paddingLeft: "4px" }}>Active Strategy</div>
           <div style={{ fontSize: "12px", color: "#818cf8", fontWeight: 700, fontFamily: "var(--font-mono)", paddingLeft: "8px", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", borderRadius: "6px", padding: "6px 8px" }}>
             {activeStrategy}
           </div>
        </div>

        <div className={`mode-badge ${mode}`} style={{ margin: 0 }}>
          {mode === "mainnet" ? "🟢 MAINNET" : "🟡 TESTNET"}
        </div>
      </div>
    </aside>
  );
}
