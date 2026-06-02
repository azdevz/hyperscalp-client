// dashboard/components/BotControlsWrapper.tsx
// Self-fetching client component — fetches bot state independently
"use client";

import { useState, useEffect, useCallback } from "react";
import { api, BotState } from "@/lib/api";
import BotControls from "./BotControls";

export default function BotControlsWrapper() {
  const [state, setState] = useState<BotState | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await api.getState();
      setState(s);
    } catch { /* offline */ }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 10000); // poll every 10s
    return () => clearInterval(interval);
  }, [refresh]);

  return <BotControls state={state} onRefresh={refresh} />;
}
