// DashboardControls.tsx
import React, { useState, useEffect } from "react";
import ExchangesButton from "./ExchangesButton";
import SymbolsManager from "./SymbolsManager";
import { FaRobot, FaExchangeAlt, FaChartLine } from "react-icons/fa";

export default function DashboardControls() {
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

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case "running":
        return "text-green-500";
      case "stopped":
        return "text-red-500";
      default:
        return "text-gray-500";
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0">
        <div className="flex items-center space-x-3">
          <FaRobot className="text-3xl text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Grid Bot Dashboard</h1>
            <div className="flex items-center space-x-2 mt-1">
              <span className="text-sm text-gray-600">Status:</span>
              <span className={`text-sm font-medium ${getStatusColor(globalStatus)}`}>
                {globalStatus.charAt(0).toUpperCase() + globalStatus.slice(1)}
              </span>
            </div>
          </div>
        </div>
        
        <div className="flex items-center space-x-4">
          <ExchangesButton />
        </div>
      </div>

      <div className="mt-6">
        <div className="flex items-center space-x-2 mb-4">
          <FaChartLine className="text-xl text-indigo-600" />
          <h2 className="text-xl font-semibold text-gray-800">Trading Symbols</h2>
        </div>
        <SymbolsManager />
      </div>
    </div>
  );
}