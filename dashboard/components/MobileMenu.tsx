// dashboard/components/MobileMenu.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/",          label: "Overview",       icon: "📊" },
  { href: "/positions", label: "Positions",      icon: "📋" },
  { href: "/meme",      label: "Meme Bot",       icon: "🚀" },
  { href: "/log",       label: "Trade Log",      icon: "📜" },
  { href: "/signals",   label: "Signals",        icon: "📡" },
];

export default function MobileMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();

  return (
    <>
      <div className="mobile-header">
        <div className="logo-text">HYPER-SCALP-AI</div>
        <button className="hamburger" onClick={() => setIsOpen(true)}>
          ☰
        </button>
      </div>

      {isOpen && (
        <div className="mobile-drawer-overlay" onClick={() => setIsOpen(false)}>
          <div className="mobile-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="logo-text">HYPER-SCALP-AI</div>
              <button className="close-btn" onClick={() => setIsOpen(false)}>✕</button>
            </div>
            <nav className="sidebar-nav">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  onClick={() => setIsOpen(false)}
                  className={`nav-link${pathname === n.href ? " active" : ""}`}
                >
                  <span className="nav-icon">{n.icon}</span>
                  {n.label}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      )}
    </>
  );
}
