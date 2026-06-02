// dashboard/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import MobileMenu from "@/components/MobileMenu";
import Header from "@/components/Header";
import { api } from "@/lib/api";

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export const metadata: Metadata = {
  title: "HYPER-SCALP-AI Dashboard",
  description: "Autonomous crypto scalping bot — Hyperliquid Perps + Solana Meme DEX",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  let activeStrategyName = "Alpha-V1-Momentum";
  let activeMode = "testnet";
  try {
    const state = await api.getState();
    const s = state.active_strategy;
    if (s && typeof s === "object" && s.name) activeStrategyName = s.name;
    if (state.mode) activeMode = state.mode === "live" ? "mainnet" : "testnet";
  } catch {}

  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased">
        <div className="layout">
          <MobileMenu />
          <Sidebar mode={activeMode} activeStrategy={activeStrategyName} />
          <main className="main-content fade-in">
            <Header />
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
