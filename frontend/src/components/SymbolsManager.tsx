import React, { useState, useEffect } from "react";
import SymbolRow from "./SymbolRow";
import { FaPlus, FaSave, FaEdit, FaTimes } from "react-icons/fa";

interface BotSymbol {
  id: string; // Unique identifier from the backend
  symbol: string;
  tp: number;
  sl: number;
  running: boolean;
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
            running: false // We'll update this from the /status endpoint below
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
      // The new route returns { global_status: ..., active_symbols: { [symbol]: 'running'|'stopped' } }
      if (data.active_symbols) {
        setSymbolRows((prev) =>
          prev.map((row) => {
            const status = data.active_symbols[row.symbol];
            return {
              ...row,
              running: status === "running"
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
      { id: `new-${Date.now()}`, symbol: "", tp: 2.0, sl: 1.0, running: false },
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
  async function handleStop(symbol: string) {
    try {
      await fetch(`${API_URL}/grid-bot/stop-symbol`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol }),
      });

      setSymbolRows((prev) =>
        prev.map((row) => (row.symbol === symbol ? { ...row, running: false } : row))
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
    <div className="bg-white rounded-xl shadow-sm p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center space-x-3">
          <h2 className="text-xl font-bold text-gray-800">Symbols Manager</h2>
          {isLoading && (
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
          )}
        </div>
        <button
          onClick={() => setEditMode(!editMode)}
          className={`flex items-center justify-center space-x-2 px-4 py-2 rounded-lg transition-colors
            ${editMode 
              ? 'bg-red-50 text-red-600 hover:bg-red-100' 
              : 'bg-indigo-50 text-indigo-600 hover:bg-indigo-100'
            }`}
        >
          {editMode ? (
            <>
              <FaTimes className="text-sm" />
              <span>Exit Edit Mode</span>
            </>
          ) : (
            <>
              <FaEdit className="text-sm" />
              <span>Edit Symbols</span>
            </>
          )}
        </button>
      </div>

      {/* Symbol Rows */}
      <div className="space-y-3">
        {symbolRows.map((row) => (
          <SymbolRow
            key={row.id}
            id={row.id}                     // Pass the unique id
            allSymbols={allSymbols}
            defaultSymbol={row.symbol}
            defaultTp={row.tp}
            defaultSl={row.sl}
            isRunning={row.running}
            editMode={editMode}
            onStart={() => handleStart(row.symbol)}
            onStop={() => handleStop(row.symbol)}
            onUpdate={updateSymbolRow}       // Updated to receive id too
            onRemove={() => removeRow(row.id)}
          />
        ))}
      </div>

      {/* Edit Mode Actions */}
      {editMode && (
        <div className="flex flex-col md:flex-row gap-3">
          <button
            onClick={addNewRow}
            className="flex items-center justify-center space-x-2 px-4 py-2 border-2 border-dashed border-indigo-200 text-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors"
          >
            <FaPlus className="text-sm" />
            <span>Add Symbol</span>
          </button>

          <button
            onClick={handleSave}
            className="flex items-center justify-center space-x-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <FaSave className="text-sm" />
            <span>Save Changes</span>
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && symbolRows.length === 0 && (
        <div className="text-center py-8">
          <p className="text-gray-500">No symbols configured yet</p>
          {!editMode && (
            <button
              onClick={() => setEditMode(true)}
              className="mt-4 text-indigo-600 hover:text-indigo-700"
            >
              Click here to add your first symbol
            </button>
          )}
        </div>
      )}
    </div>
  );
}