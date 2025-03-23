// Dashboard.tsx
import React, { useState, useEffect } from "react";
import ExchangesButton from "./ExchangesButton";
import SymbolsManager from "./SymbolsManager";

export default function Dashboard() {
  const [globalStatus, setGlobalStatus] = useState("stopped");
  const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    checkGlobalStatus();
  }, []);

  const checkGlobalStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/grid-bot/status`);
      if (res.ok) {
        const data = await res.json();
        setGlobalStatus(data.status);
      }
    } catch (err) {
      console.error("Error checking bot status:", err);
    }
  };

  return (
    <div>
      <div className="flex items-center space-x-4">
        <h1 className="text-2xl font-bold">Grid Bot Dashboard</h1>
        <ExchangesButton />
      </div>

      <p className="mt-2">Global Status: {globalStatus}</p>

      <hr className="my-4" />

      <SymbolsManager />
    </div>
  );
}