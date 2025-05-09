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
  const [loadingOperations, setLoadingOperations] = useState<{[key: string]: string}>({}); // Track loading operations

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
    setSymbolRows((prev) => [
      ...prev,
      { id: `new-${Date.now()}`, symbol: "", tp: 2.0, sl: 1.0, running: false, exchanges: [] },
    ]);
    setEditMode(true); // Automatically enter edit mode when adding a new symbol
  }

  // ✅ Remove a symbol row
  function removeRow(rowId: string) {
    setSymbolRows((prev) => prev.filter((row) => row.id !== rowId));
  }

  // ✅ Handle starting a bot for a symbol
  async function handleStart(symbol: string) {
    try {
      setLoadingOperations(prev => ({ ...prev, [symbol]: 'starting' }));
      const storedExchangesJson = localStorage.getItem("selectedExchanges");
      const storedExchanges = storedExchangesJson ? JSON.parse(storedExchangesJson) : [];
  
      // ✅ Return an error if no exchanges are selected
      if (storedExchanges.length === 0) {
        alert("Error: No exchanges selected. Please select at least one exchange.");
        setLoadingOperations(prev => {
          const newState = { ...prev };
          delete newState[symbol];
          return newState;
        });
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
    } finally {
      setLoadingOperations(prev => {
        const newState = { ...prev };
        delete newState[symbol];
        return newState;
      });
    }
  }
  // ✅ Handle stopping a bot for a symbol
  async function handleStop(symbol: string, exchange?: string) {
    try {
      const operationKey = exchange ? `${symbol}-${exchange}` : symbol;
      setLoadingOperations(prev => ({ ...prev, [operationKey]: 'stopping' }));
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
    } finally {
      setLoadingOperations(prev => {
        const operationKey = exchange ? `${symbol}-${exchange}` : symbol;
        const newState = { ...prev };
        delete newState[operationKey];
        return newState;
      });
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
          onClick={addNewRow}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 mr-4"
        >
          <FaPlus className="w-4 h-4" />
          Add Symbol
        </button>
        <div className="flex space-x-2">
          <button
            onClick={() => setEditMode(!editMode)}
            className={`px-4 py-2 ${editMode ? 'bg-gray-600' : 'bg-indigo-600'} text-white rounded-lg ${editMode ? 'hover:bg-gray-700' : 'hover:bg-indigo-700'} transition-colors`}
          >
            {editMode ? (
              <>
                <FaTimes className="w-4 h-4 inline mr-1" />
                Cancel
              </>
            ) : (
              <>
                <FaEdit className="w-4 h-4 inline mr-1" />
                Edit Symbols
              </>
            )}
          </button>
          {editMode && (
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
            >
              <FaSave className="w-4 h-4" />
              Save Changes
            </button>
          )}
        </div>
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
                <td colSpan={6} className="p-0">
                  <SymbolRow
                    id={row.id}
                    allSymbols={allSymbols}
                    defaultSymbol={row.symbol}
                    defaultTp={row.tp}
                    defaultSl={row.sl}
                    isRunning={row.running}
                    editMode={editMode}
                    exchanges={row.exchanges}
                    loadingOperations={loadingOperations}
                    onStart={handleStart}
                    onStop={handleStop}
                    onRemove={() => removeRow(row.id)}
                    onUpdate={updateSymbolRow}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}