import { useState, useEffect } from "react";
import { supportedExchanges } from "../utils/supported_exchanges";

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
    <div className="fixed inset-0 flex items-center justify-center backdrop-brightness-50 bg-opacity-50 z-50">
      <div className="bg-white p-6 rounded-4xl shadow-lg w-full max-w-md">
        <h2 className="text-xl font-bold mb-4">Bot Settings</h2>

        {/* TP% and SL% inputs */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block mb-1 font-bold">Take Profit %</label>
            <input
              type="number"
              step="0.1"
              className="border border-gray-300 rounded-4xl w-full p-2"
              value={tpPercent}
              onChange={(e) => setTpPercent(e.target.value)}
            />
          </div>
          <div>
            <label className="block mb-1 font-bold">Stop Loss %</label>
            <input
              type="number"
              step="0.1"
              className="border border-gray-300 rounded-4xl w-full p-2"
              value={slPercent}
              onChange={(e) => setSlPercent(e.target.value)}
            />
          </div>
        </div>

        {/* Exchange Selection */}
        <div className="mb-4">
          <p className="font-bold mb-2">Select Exchanges:</p>
          <div className="flex flex-wrap gap-2">
            {supportedExchanges.map((exchange) => (
              <button
                key={exchange}
                onClick={() => handleExchangeToggle(exchange)}
                className={`px-3 py-1 transition rounded-4xl text-sm ${
                  selectedExchanges.includes(exchange) ? "bg-blue-500 text-white" : "border border-dashed border-blue-500 text-blue-500"
                }`}
              >
                {selectedExchanges.includes(exchange) ? `- ${exchange.toUpperCase()}` : `+ ${exchange.toUpperCase()}`}
              </button>
            ))}
          </div>
        </div>

        {/* Symbol Selection */}
        <div className="mb-4">
          <p className="font-bold mb-2">Manage Symbols:</p>
          <input
            type="text"
            placeholder="Search Binance Symbols..."
            className="border border-gray-300 rounded-4xl w-full p-2 mb-2"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <div className="bg-white border rounded-md shadow max-h-32 overflow-y-auto">
            {binanceSymbols
              .filter((s) => s.includes(searchTerm.toUpperCase()))
              .map((s) => (
                <div
                  key={s}
                  className="px-3 py-2 hover:bg-gray-100 cursor-pointer"
                  onClick={() => handleSymbolToggle(s)}
                >
                  {selectedSymbols.includes(s) ? `✓ ${s}` : s}
                </div>
              ))}
          </div>
        </div>

        {/* Selected Symbols (as pills) */}
        <div className="flex flex-wrap gap-2 mt-2">
          {selectedSymbols.map((symbol) => (
            <div
              key={symbol}
              className="flex items-center bg-blue-500 text-white px-3 py-1 rounded-4xl text-sm"
            >
              {symbol}
              <button
                className="ml-2 text-lg"
                onClick={() => handleSymbolToggle(symbol)}
              >
                &times;
              </button>
            </div>
          ))}
        </div>

        {/* Buttons */}
        <div className="flex justify-end gap-2 mt-4">
          <button className="bg-gray-300 px-4 py-2 rounded-4xl" onClick={onClose}>
            Cancel
          </button>
          <button className="bg-blue-500 px-4 py-2 text-white rounded-4xl" onClick={handleSave}>
            Save
          </button>
        </div>
      </div>
    </div>
  );
}