import { useState, useEffect } from "react";
import { supportedExchanges } from "../utils/supported_exchanges";
import { FaTimes, FaSearch, FaCheck, FaPlus, FaMinus } from "react-icons/fa";

interface SettingsModalProps {
  tpPercent: string;
  slPercent: string;
  setTpPercent: (value: string) => void;
  setSlPercent: (value: string) => void;
  onClose: () => void;
}

export default function SettingsModal({
  tpPercent,
  slPercent,
  setTpPercent,
  setSlPercent,
  onClose,
}: SettingsModalProps) {
  const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000";

  const [selectedExchanges, setSelectedExchanges] = useState<string[]>([]);
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([]);
  const [binanceSymbols, setBinanceSymbols] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    fetchStoredSymbols();
    fetchBinanceSymbols();

    // Load exchanges from localStorage
    const savedExchanges = localStorage.getItem("selectedExchanges");
    if (savedExchanges) {
      setSelectedExchanges(JSON.parse(savedExchanges));
    }
  }, []);

  const fetchStoredSymbols = async () => {
    try {
      const response = await fetch(`${API_URL}/symbols/`);
      if (response.ok) {
        const data = await response.json();
        setSelectedSymbols(data.symbols || []);
      }
    } catch (error) {
      console.error("Error fetching stored symbols:", error);
    }
  };

  const fetchBinanceSymbols = async () => {
    try {
      const response = await fetch(`${API_URL}/list/symbols/`);
      if (response.ok) {
        const data = await response.json();
        setBinanceSymbols(data.symbols || []);
      }
    } catch (error) {
      console.error("Error fetching Binance symbols:", error);
    }
  };

  const handleExchangeToggle = (exchange: string) => {
    setSelectedExchanges((prevExchanges) => {
      const updatedExchanges = prevExchanges.includes(exchange)
        ? prevExchanges.filter((ex) => ex !== exchange)
        : [...prevExchanges, exchange];
  
      localStorage.setItem("selectedExchanges", JSON.stringify(updatedExchanges)); // This remains
  
      return updatedExchanges; // Ensures the correct state is set
    });
  };

  const handleSymbolToggle = (symbol: string) => {
    setSelectedSymbols((prev) =>
      prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol]
    );
    setSearchTerm("");
  };

  const handleSave = async () => {
    
    try {
      await fetch(`${API_URL}/symbols/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(selectedSymbols),
      });
    } catch (error) {
      console.error("Error updating symbols:", error);
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-gray-800">Bot Settings</h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 transition-colors"
            >
              <FaTimes size={20} />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* TP% and SL% inputs */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Take Profit %
              </label>
              <div className="relative">
                <input
                  type="number"
                  step="0.1"
                  className="w-full border border-gray-300 rounded-lg p-2 pl-3 pr-8 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  value={tpPercent}
                  onChange={(e) => setTpPercent(e.target.value)}
                />
                <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500">%</span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Stop Loss %
              </label>
              <div className="relative">
                <input
                  type="number"
                  step="0.1"
                  className="w-full border border-gray-300 rounded-lg p-2 pl-3 pr-8 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  value={slPercent}
                  onChange={(e) => setSlPercent(e.target.value)}
                />
                <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500">%</span>
              </div>
            </div>
          </div>

          {/* Exchange Selection */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Select Exchanges</h3>
            <div className="flex flex-wrap gap-2">
              {supportedExchanges.map((exchange) => (
                <button
                  key={exchange}
                  onClick={() => handleExchangeToggle(exchange)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors
                    ${selectedExchanges.includes(exchange)
                      ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                      : 'border border-indigo-600 text-indigo-600 hover:bg-indigo-50'
                    }`}
                >
                  {selectedExchanges.includes(exchange) ? (
                    <>
                      <FaMinus size={14} />
                      <span>{exchange.toUpperCase()}</span>
                    </>
                  ) : (
                    <>
                      <FaPlus size={14} />
                      <span>{exchange.toUpperCase()}</span>
                    </>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Symbol Selection */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Manage Symbols</h3>
            <div className="relative mb-4">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <FaSearch className="text-gray-400" />
              </div>
              <input
                type="text"
                placeholder="Search Binance Symbols..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="bg-white border border-gray-200 rounded-lg shadow-sm max-h-48 overflow-y-auto">
              {binanceSymbols
                .filter((s) => s.includes(searchTerm.toUpperCase()))
                .map((s) => (
                  <div
                    key={s}
                    className={`flex items-center justify-between px-4 py-2 hover:bg-gray-50 cursor-pointer transition-colors
                      ${selectedSymbols.includes(s) ? 'bg-indigo-50' : ''}`}
                    onClick={() => handleSymbolToggle(s)}
                  >
                    <span className="text-sm text-gray-700">{s}</span>
                    {selectedSymbols.includes(s) && (
                      <FaCheck className="text-indigo-600" size={14} />
                    )}
                  </div>
                ))}
            </div>
          </div>

          {/* Selected Symbols */}
          {selectedSymbols.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Selected Symbols</h3>
              <div className="flex flex-wrap gap-2">
                {selectedSymbols.map((symbol) => (
                  <div
                    key={symbol}
                    className="flex items-center space-x-2 bg-indigo-100 text-indigo-700 px-3 py-1 rounded-lg text-sm"
                  >
                    <span>{symbol}</span>
                    <button
                      onClick={() => handleSymbolToggle(symbol)}
                      className="text-indigo-600 hover:text-indigo-800"
                    >
                      <FaTimes size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50 rounded-b-xl">
          <div className="flex justify-end space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Save Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}