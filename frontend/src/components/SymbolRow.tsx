import React, { useState } from "react";
import { FaPlay, FaStop, FaTrash, FaSearch } from "react-icons/fa";

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
  onUpdate: (id: string, symbol: string, tp: number, sl: number) => void;
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
  onUpdate,
}: SymbolRowProps) {
  const [selectedSymbol, setSelectedSymbol] = useState(defaultSymbol);
  const [tpPercent, setTpPercent] = useState(defaultTp);
  const [slPercent, setSlPercent] = useState(defaultSl);
  const [searchTerm, setSearchTerm] = useState("");

  const handleSymbolSelect = (newSymbol: string) => {
    setSelectedSymbol(newSymbol);
    setSearchTerm("");
    onUpdate(id, newSymbol, tpPercent, slPercent);
  };

  const handleUpdate = () => {
    onUpdate(id, selectedSymbol, tpPercent, slPercent);
  };

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 mb-3">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
        {/* Symbol Search */}
        <div className="md:col-span-4 relative">
          {editMode ? (
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <FaSearch className="text-gray-400" />
              </div>
              <input
                type="text"
                placeholder="Search Symbol..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={searchTerm || selectedSymbol}
                onChange={(e) => setSearchTerm(e.target.value)}
                onBlur={() => {
                  if (searchTerm.trim() && searchTerm !== selectedSymbol) {
                    setSelectedSymbol(searchTerm.toUpperCase());
                    onUpdate(id, searchTerm.toUpperCase(), tpPercent, slPercent);
                  }
                }}
                disabled={isRunning}
              />
              {searchTerm && (
                <div className="absolute z-[100] w-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-48 overflow-y-auto">
                  {allSymbols
                    .filter((s) => s.includes(searchTerm.toUpperCase()))
                    .map((s) => (
                      <div
                        key={s}
                        className="px-4 py-2 hover:bg-indigo-50 cursor-pointer transition-colors"
                        onClick={() => handleSymbolSelect(s)}
                      >
                        <span className="text-sm text-gray-700">{s}</span>
                      </div>
                    ))}
                </div>
              )}
            </div>
          ) : (
            <span className="text-sm font-medium text-gray-900">{selectedSymbol}</span>
          )}
        </div>

        {/* TP Input */}
        <div className="md:col-span-3">
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">TP%</label>
            <div className="relative flex-1">
              <input
                type="number"
                step="0.1"
                className="w-full pl-3 pr-8 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={tpPercent}
                onChange={(e) => setTpPercent(parseFloat(e.target.value))}
                onBlur={handleUpdate}
                disabled={!editMode || isRunning}
              />
              <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500">%</span>
            </div>
          </div>
        </div>

        {/* SL Input */}
        <div className="md:col-span-3">
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">SL%</label>
            <div className="relative flex-1">
              <input
                type="number"
                step="0.1"
                className="w-full pl-3 pr-8 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={slPercent}
                onChange={(e) => setSlPercent(parseFloat(e.target.value))}
                onBlur={handleUpdate}
                disabled={!editMode || isRunning}
              />
              <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500">%</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="md:col-span-2 flex items-center space-x-2">
          <button
            onClick={() => (isRunning ? onStop(selectedSymbol) : onStart(selectedSymbol))}
            className={`flex items-center justify-center px-4 py-2 rounded-lg text-white transition-colors
              ${isRunning 
                ? "bg-red-500 hover:bg-red-600" 
                : "bg-green-500 hover:bg-green-600"
              }`}
          >
            {isRunning ? (
              <>
                <FaStop className="mr-2" />
                <span className="hidden md:inline">Stop</span>
              </>
            ) : (
              <>
                <FaPlay className="mr-2" />
                <span className="hidden md:inline">Start</span>
              </>
            )}
          </button>

          {editMode && (
            <button
              onClick={onRemove}
              className="p-2 text-gray-500 hover:text-red-500 transition-colors"
              title="Remove"
            >
              <FaTrash />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}