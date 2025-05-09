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
    <div className="bg-white rounded-xl shadow-sm p-4 mb-3">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
        {/* Symbol Display/Input */}
        <div className="md:col-span-4 relative">
          {editMode ? (
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <FaSearch className="text-gray-400 w-3.5 h-3.5" />
              </div>
              <input
                type="text"
                placeholder="Search Symbol..."
                className="w-56 pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
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
                <div className="absolute z-[100] w-48 mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-48 overflow-y-auto">
                  {allSymbols
                    .filter((s) => s.includes(searchTerm.toUpperCase()))
                    .map((s) => (
                      <div
                        key={s}
                        className="px-4 py-2 hover:bg-indigo-50 cursor-pointer transition-colors"
                        onClick={() => handleSymbolChange(s)}
                      >
                        <span className="text-sm text-gray-700">{s}</span>
                      </div>
                    ))}
                </div>
              )}
            </div>
          ) : (
            <div className="text-gray-900 font-medium">{selectedSymbol}</div>
          )}
        </div>

        {/* TP Display/Input */}
        <div className="md:col-span-3">
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">TP%</label>
            {editMode ? (
              <div className="relative w-40">
                <input
                  type="number"
                  step="0.1"
                  className="w-full pl-3 pr-8 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  value={tpPercent}
                  onChange={(e) => setTpPercent(Number(e.target.value))}
                  onBlur={handleUpdate}
                  disabled={isRunning}
                  placeholder="TP %"
                />
                <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500">%</span>
              </div>
            ) : (
              <div className="text-gray-900">{tpPercent}%</div>
            )}
          </div>
        </div>

        {/* SL Display/Input */}
        <div className="md:col-span-3">
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-gray-700">SL%</label>
            {editMode ? (
              <div className="relative w-40">
                <input
                  type="number"
                  step="0.1"
                  className="w-full pl-3 pr-8 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  value={slPercent}
                  onChange={(e) => setSlPercent(Number(e.target.value))}
                  onBlur={handleUpdate}
                  disabled={isRunning}
                  placeholder="SL %"
                />
                <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500">%</span>
              </div>
            ) : (
              <div className="text-gray-900">{slPercent}%</div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="md:col-span-2 flex items-center space-x-2">
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
            <div className="flex flex-wrap gap-1.5">
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
            </div>
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
    </div>
  );
}