// dashboard/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import MobileMenu from "@/components/MobileMenu";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import { cookies } from "next/headers";

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

  const cookieStore = await cookies();
  const session = cookieStore.get("session")?.value;
  const adminPassword = process.env.ADMIN_PASSWORD || "admin123";
  const isAuthenticated = session === adminPassword;


  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased">
        {isAuthenticated ? (
          <div className="layout">
            <MobileMenu />
            <Sidebar mode={activeMode} activeStrategy={activeStrategyName} />
            <main className="main-content fade-in">
              <Header />
              {children}
            </main>
          </div>
        ) : (
          <div className="flex items-center justify-center min-h-screen bg-slate-950 w-full">
            {children}
          </div>
        )}
      </body>
    </html>
  );
}
