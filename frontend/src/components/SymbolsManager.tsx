import React, { useState, useEffect } from "react";
import SymbolRow from "./SymbolRow";
import { FaPlus, FaSave, FaEdit, FaTimes } from "react-icons/fa";

interface BotSymbol {
  id: string; // Unique identifier from the backend
  symbol: string;
  tp: number;
  sl: number;
  running: boolean;
  exchanges: string[];
}

const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000";

export default function SymbolsManager() {
  const [allSymbols, setAllSymbols] = useState<string[]>([]);
  const [symbolRows, setSymbolRows] = useState<BotSymbol[]>([]);
  const [editMode, setEditMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchStoredSymbols();
    fetchAvailableSymbols();
  }, []);

  // ✅ Fetch stored symbols (including TP/SL from backend)
  async function fetchStoredSymbols() {
    try {
      const resp = await fetch(`${API_URL}/symbols/`);
      const data = await resp.json();
      if (data.symbols) {
        setSymbolRows(
          data.symbols.map((s: any) => ({
            id: s.symbol,
            symbol: s.symbol,
            tp: s.configs.length > 0 ? s.configs[0].tp_percent : 2.0,
            sl: s.configs.length > 0 ? s.configs[0].sl_percent : 1.0,
            running: false, // We'll update this from the /status endpoint below
            exchanges: []
          }))
        );
        // Now fetch the running/stopped status for each symbol
        fetchRunningStatus();
      }
    } catch (err) {
      console.error("Error fetching stored symbols:", err);
    } finally {
      setIsLoading(false);
    }
  }

  // ✅ Fetch available symbols from Binance API
  async function fetchAvailableSymbols() {
    try {
      const resp = await fetch(`${API_URL}/list/symbols/`);
      const data = await resp.json();
      if (data.symbols) setAllSymbols(data.symbols);
    } catch (err) {
      console.error("Error fetching symbols:", err);
    }
  }

  async function fetchRunningStatus() {
    try {
      const resp = await fetch(`${API_URL}/grid-bot/status`);
      const data = await resp.json();
      if (data.active_symbols) {
        setSymbolRows((prev) =>
          prev.map((row) => {
            const symbolStatus = data.active_symbols[row.symbol];
            return {
              ...row,
              running: symbolStatus?.status === "running",
              exchanges: symbolStatus?.exchanges || []
            };
          })
        );
      }
    } catch (err) {
      console.error("Error fetching running symbols:", err);
    }
  }
  // ✅ Add a new row (only in edit mode)
  function addNewRow() {
    if (!editMode) return;
    setSymbolRows((prev) => [
      ...prev,
      { id: `new-${Date.now()}`, symbol: "", tp: 2.0, sl: 1.0, running: false, exchanges: [] },
    ]);
  }

  // ✅ Remove a symbol row
  function removeRow(rowId: string) {
    setSymbolRows((prev) => prev.filter((row) => row.id !== rowId));
  }

  // ✅ Handle starting a bot for a symbol
  async function handleStart(symbol: string) {
    try {
      const storedExchangesJson = localStorage.getItem("selectedExchanges");
      const storedExchanges = storedExchangesJson ? JSON.parse(storedExchangesJson) : [];
  
      // ✅ Return an error if no exchanges are selected
      if (storedExchanges.length === 0) {
        alert("Error: No exchanges selected. Please select at least one exchange.");
        return;
      }
  
      await Promise.all(
        storedExchanges.map(async (exchange: string) => {
          return fetch(`${API_URL}/grid-bot/start-symbol`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ exchange, symbol }),
          });
        })
      );
  
      setSymbolRows((prev) =>
        prev.map((row) =>
          row.symbol === symbol ? { ...row, running: true } : row
        )
      );
    } catch (err) {
      console.error("Error starting symbol", err);
    }
  }
  // ✅ Handle stopping a bot for a symbol
  async function handleStop(symbol: string, exchange?: string) {
    try {
      await fetch(`${API_URL}/stop_symbol`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, exchange }),
      });

      setSymbolRows((prev) =>
        prev.map((row) => {
          if (row.symbol === symbol) {
            if (exchange) {
              // Remove specific exchange from the list
              const updatedExchanges = row.exchanges.filter(e => e !== exchange);
              return {
                ...row,
                exchanges: updatedExchanges,
                running: updatedExchanges.length > 0
              };
            } else {
              // Remove all exchanges
              return { ...row, exchanges: [], running: false };
            }
          }
          return row;
        })
      );
    } catch (err) {
      console.error("Error stopping symbol", err);
    }
  }

    // ✅ Handle updates from SymbolRow
    function updateSymbolRow(id: string, symbol: string, tp: number, sl: number) {
      setSymbolRows((prev) =>
        prev.map((row) =>
          row.id === id ? { ...row, symbol, tp, sl } : row
        )
      );
    }
    
  // ✅ Save new configurations (TP/SL updates)
  async function handleSave() {
    try {
      const validRows = symbolRows.filter(({ symbol }) => symbol.trim().length > 0);
      const payload = {
        symbols: validRows.map(({ symbol, tp, sl }) => ({
          symbol,
          tp_percent: tp,
          sl_percent: sl,
        })),
      };
      await fetch(`${API_URL}/symbols/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setEditMode(false);
    } catch (error) {
      console.error("Error updating symbols:", error);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <button
          onClick={() => setEditMode(!editMode)}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          {editMode ? "Cancel" : "Edit Symbols"}
        </button>
        {editMode && (
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            Save Changes
          </button>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Symbol
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Exchanges
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                TP %
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                SL %
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {symbolRows.map((row) => (
              <tr key={row.id}>
                <td className="px-6 py-4 whitespace-nowrap">
                  {editMode ? (
                    <input
                      type="text"
                      value={row.symbol}
                      onChange={(e) => updateSymbolRow(row.id, e.target.value, row.tp, row.sl)}
                      className="border rounded px-2 py-1"
                    />
                  ) : (
                    <span className="text-sm font-medium text-gray-900">{row.symbol}</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="text-sm text-gray-500">
                    {row.exchanges.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {row.exchanges.map((exchange, index) => (
                          <span 
                            key={index}
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                          >
                            {exchange.charAt(0).toUpperCase() + exchange.slice(1)}
                          </span>
                        ))}
                      </div>
                    ) : (
                      '-'
                    )}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {editMode ? (
                    <input
                      type="number"
                      value={row.tp}
                      onChange={(e) => updateSymbolRow(row.id, row.symbol, parseFloat(e.target.value), row.sl)}
                      className="border rounded px-2 py-1 w-20"
                      step="0.1"
                    />
                  ) : (
                    <span className="text-sm text-gray-500">{row.tp}%</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {editMode ? (
                    <input
                      type="number"
                      value={row.sl}
                      onChange={(e) => updateSymbolRow(row.id, row.symbol, row.tp, parseFloat(e.target.value))}
                      className="border rounded px-2 py-1 w-20"
                      step="0.1"
                    />
                  ) : (
                    <span className="text-sm text-gray-500">{row.sl}%</span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    row.running ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {row.running ? 'Running' : 'Stopped'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  {editMode ? (
                    <button
                      onClick={() => removeRow(row.id)}
                      className="text-red-600 hover:text-red-900"
                    >
                      Remove
                    </button>
                  ) : (
                    <div className="space-x-2">
                      <button
                        onClick={() => handleStart(row.symbol)}
                        disabled={row.running}
                        className={`px-3 py-1 rounded ${
                          row.running
                            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                            : 'bg-green-600 text-white hover:bg-green-700'
                        }`}
                      >
                        Start
                      </button>
                      {row.exchanges.length > 0 && (
                        <div className="inline-flex space-x-1">
                          {row.exchanges.map((exchange) => (
                            <button
                              key={exchange}
                              onClick={() => handleStop(row.symbol, exchange)}
                              className="px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 text-xs"
                            >
                              Stop {exchange.charAt(0).toUpperCase() + exchange.slice(1)}
                            </button>
                          ))}
                          <button
                            onClick={() => handleStop(row.symbol)}
                            className="px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700 text-xs"
                          >
                            Stop All
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}