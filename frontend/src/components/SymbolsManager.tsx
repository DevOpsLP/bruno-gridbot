import React, { useState, useEffect } from "react";
import SymbolRow from "./SymbolRow";

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
            id: `${s.symbol}`, // Unique identifier for frontend (avoid duplicates)
            symbol: s.symbol,
            tp: s.configs.length > 0 ? s.configs[0].tp_percent : 2.0, // Use the first config
            sl: s.configs.length > 0 ? s.configs[0].sl_percent : 1.0,
            running: false, // Will be updated dynamically later
          }))
        );
      }
    } catch (err) {
      console.error("Error fetching stored symbols:", err);
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

  // ✅ Fetch active symbols to mark them as running
  async function fetchRunningStatus() {
    try {
      const resp = await fetch(`${API_URL}/grid-bot/status`);
      const data = await resp.json();
      if (data.running_symbols) {
        setSymbolRows((prev) =>
          prev.map((row) => ({
            ...row,
            running: data.running_symbols.includes(row.symbol),
          }))
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
    <div className="p-4 border rounded-xl space-y-4 w-full">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-bold">Symbols Manager</h2>
        <button
          onClick={() => setEditMode(!editMode)}
          className="px-3 py-1 rounded-lg border bg-gray-200"
        >
          {editMode ? "Exit Edit Mode" : "Edit Symbols"}
        </button>
      </div>

      <div className="space-y-2">
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

      {editMode && (
        <>
          <button
            onClick={addNewRow}
            className="w-full px-4 py-2 border-2 border-dashed rounded-lg"
          >
            + Add Symbol
          </button>

          <button
            onClick={handleSave}
            className="w-full px-4 py-2 mt-2 bg-blue-500 text-white rounded-lg"
          >
            Save Changes
          </button>
        </>
      )}
    </div>
  );
}