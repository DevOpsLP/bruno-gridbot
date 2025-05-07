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
  exchanges: string[];
  loadingOperations?: { [key: string]: string };
  onStart: (symbol: string) => void;
  onStop: (symbol: string, exchange?: string) => void;
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
  exchanges = [],
  loadingOperations = {},
  onStart,
  onStop,
  onRemove,
  onUpdate,
}: SymbolRowProps) {
  const [selectedSymbol, setSelectedSymbol] = useState(defaultSymbol);
  const [tpPercent, setTpPercent] = useState(defaultTp);
  const [slPercent, setSlPercent] = useState(defaultSl);
  const [searchTerm, setSearchTerm] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);

  const filteredSymbols = allSymbols.filter((symbol) =>
    symbol.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleSymbolChange = (symbol: string) => {
    setSelectedSymbol(symbol);
    onUpdate(id, symbol, tpPercent, slPercent);
  };

  const handleUpdate = () => {
    onUpdate(id, selectedSymbol, tpPercent, slPercent);
  };

  const isStarting = loadingOperations[selectedSymbol] === 'starting';
  const isStopping = loadingOperations[selectedSymbol] === 'stopping';
  const isStoppingExchange = (exchange: string) => loadingOperations[`${selectedSymbol}-${exchange}`] === 'stopping';

  return (
    <div className="flex items-center gap-2 p-2 bg-gray-800 rounded-lg">
      {/* Symbol Selection */}
      <div className="flex-1">
        <div className="relative">
          <input
            type="text"
            value={selectedSymbol}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setShowDropdown(true);
            }}
            onFocus={() => setShowDropdown(true)}
            disabled={isRunning || editMode}
            className="w-full px-3 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Search symbol..."
          />
          {showDropdown && !isRunning && !editMode && (
            <div className="absolute z-10 w-full mt-1 bg-gray-700 rounded-lg shadow-lg max-h-60 overflow-auto">
              {filteredSymbols.map((symbol) => (
                <div
                  key={symbol}
                  className="px-3 py-2 hover:bg-gray-600 cursor-pointer"
                  onClick={() => {
                    handleSymbolChange(symbol);
                    setShowDropdown(false);
                  }}
                >
                  {symbol}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* TP Input */}
      <div className="w-24">
        <input
          type="number"
          value={tpPercent}
          onChange={(e) => setTpPercent(Number(e.target.value))}
          onBlur={handleUpdate}
          disabled={isRunning || editMode}
          className="w-full px-3 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="TP %"
        />
      </div>

      {/* SL Input */}
      <div className="w-24">
        <input
          type="number"
          value={slPercent}
          onChange={(e) => setSlPercent(Number(e.target.value))}
          onBlur={handleUpdate}
          disabled={isRunning || editMode}
          className="w-full px-3 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="SL %"
        />
      </div>

      {/* Start/Stop Buttons */}
      <div className="flex gap-2">
        {!isRunning ? (
          <button
            onClick={() => onStart(selectedSymbol)}
            disabled={isStarting || editMode}
            className={`flex items-center justify-center px-3 py-1.5 rounded-lg text-white transition-colors text-sm
              ${isStarting ? 'bg-gray-400 cursor-not-allowed' : 'bg-green-500 hover:bg-green-600'}`}
          >
            <FaPlay className="w-3 h-3 mr-1.5" />
            <span>{isStarting ? 'Starting...' : 'Start'}</span>
          </button>
        ) : (
          <>
            {exchanges.map((exchange) => (
              <button
                key={exchange}
                onClick={() => onStop(selectedSymbol, exchange)}
                disabled={isStoppingExchange(exchange)}
                className={`px-2 py-1 rounded text-xs text-white transition-colors flex items-center
                  ${isStoppingExchange(exchange) ? 'bg-gray-400 cursor-not-allowed' : 'bg-red-600 hover:bg-red-700'}`}
              >
                <FaStop className="w-2.5 h-2.5 mr-1" />
                {isStoppingExchange(exchange) ? 'Stopping...' : `Stop ${exchange.charAt(0).toUpperCase() + exchange.slice(1)}`}
              </button>
            ))}
            <button
              onClick={() => onStop(selectedSymbol)}
              disabled={isStopping}
              className={`px-2 py-1 rounded text-xs text-white transition-colors flex items-center
                ${isStopping ? 'bg-gray-400 cursor-not-allowed' : 'bg-red-600 hover:bg-red-700'}`}
            >
              <FaStop className="w-2.5 h-2.5 mr-1" />
              {isStopping ? 'Stopping...' : 'Stop All'}
            </button>
          </>
        )}
      </div>

      {editMode && (
        <button
          onClick={onRemove}
          className="p-1.5 text-gray-500 hover:text-red-500 transition-colors"
          title="Remove"
        >
          <FaTrash className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}