import React, { useState } from "react";

interface SymbolRowProps {
  id: string;
  allSymbols: string[];
  defaultSymbol?: string;
  defaultTp?: number;
  defaultSl?: number;
  isRunning?: boolean;
  editMode: boolean;
  onStart: (symbol: string) => void;
  onStop: (symbol: string) => void;
  onRemove: () => void;
  onUpdate: (id: string, symbol: string, tp: number, sl: number) => void; // Updated signature
}

export default function SymbolRow({
  id,
  allSymbols,
  defaultSymbol = "",
  defaultTp = 2.0,
  defaultSl = 1.0,
  isRunning = false,
  editMode,
  onStart,
  onStop,
  onRemove,
  onUpdate, // ✅ Add this function
}: SymbolRowProps) {
  const [selectedSymbol, setSelectedSymbol] = useState(defaultSymbol);
  const [tpPercent, setTpPercent] = useState(defaultTp);
  const [slPercent, setSlPercent] = useState(defaultSl);
  const [searchTerm, setSearchTerm] = useState("");

  // ✅ Handle when user selects a new symbol
  const handleSymbolSelect = (newSymbol: string) => {
    setSelectedSymbol(newSymbol);
    setSearchTerm("");
    // Immediately update the parent after a user picks a symbol
    onUpdate(id, newSymbol, tpPercent, slPercent);
  };

  // ✅ Capture TP/SL updates
  const handleUpdate = () => {
    // Now pass the row's id as well
    onUpdate(id, selectedSymbol, tpPercent, slPercent);
  };
  return (
    <div className="flex items-center space-x-2 border p-2 rounded-xl mb-2 w-full">
      {/* Symbol Dropdown */}
      <div className="relative w-full">
      <input
        type="text"
        placeholder="Search Symbol..."
        className="border border-gray-300 rounded-lg w-full p-2"
        value={searchTerm || selectedSymbol}
        onChange={(e) => setSearchTerm(e.target.value)}
        onBlur={() => {
            // If user typed something but didn't pick from the dropdown
            if (searchTerm.trim() && searchTerm !== selectedSymbol) {
            setSelectedSymbol(searchTerm.toUpperCase());
            onUpdate(id, searchTerm.toUpperCase(), tpPercent, slPercent);
            }
        }}
        disabled={!editMode || isRunning
        }/>
        {searchTerm && (
          <div className="absolute bg-white border rounded-md shadow-md w-full max-h-48 overflow-y-auto z-50">
            {allSymbols
              .filter((s) => s.includes(searchTerm.toUpperCase()))
              .map((s) => (
                <div
                  key={s}
                  className="px-3 py-2 hover:bg-gray-100 cursor-pointer"
                  onClick={() => handleSymbolSelect(s)}
                >
                  {s}
                </div>
              ))}
          </div>
        )}
      </div>

      {/* TP Input */}
      <div className="flex items-center space-x-1">
        <label>TP%</label>
        <input
          type="number"
          step="0.1"
          className="border rounded px-2 py-1 w-16"
          value={tpPercent}
          onChange={(e) => setTpPercent(parseFloat(e.target.value))}
          onBlur={handleUpdate} // ✅ Save when losing focus
          disabled={!editMode || isRunning}
        />
      </div>

      {/* SL Input */}
      <div className="flex items-center space-x-1">
        <label>SL%</label>
        <input
          type="number"
          step="0.1"
          className="border rounded px-2 py-1 w-16"
          value={slPercent}
          onChange={(e) => setSlPercent(parseFloat(e.target.value))}
          onBlur={handleUpdate} // ✅ Save when losing focus
          disabled={!editMode || isRunning}
        />
      </div>

      {/* Start/Stop Button */}
      <button
        onClick={() => (isRunning ? onStop(selectedSymbol) : onStart(selectedSymbol))}
        className={`px-4 py-2 rounded-2xl text-white ${isRunning ? "bg-red-500" : "bg-green-500"}`}
      >
        {isRunning ? "Stop" : "Start"}
      </button>

      {/* Remove Row */}
      {editMode && (
        <button onClick={onRemove} className="px-2 py-1 text-sm bg-gray-300 rounded-xl">
          Remove
        </button>
      )}
    </div>
  );
}