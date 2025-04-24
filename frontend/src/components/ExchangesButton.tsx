// ExchangesButton.tsx
import React, { useState, useEffect } from "react";
import { supportedExchanges } from "../utils/supported_exchanges";
import { FaExchangeAlt } from "react-icons/fa";

export default function ExchangesButton() {
  const [selectedExchanges, setSelectedExchanges] = useState<string[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    // Load saved selection from localStorage
    const saved = localStorage.getItem("selectedExchanges");
    if (saved) {
      setSelectedExchanges(JSON.parse(saved));
    }
  }, []);

  const handleToggleExchange = (exchange: string) => {
    setSelectedExchanges((prev) => {
      let newList: string[] = [];
      if (prev.includes(exchange)) {
        newList = prev.filter((ex) => ex !== exchange);
      } else {
        newList = [...prev, exchange];
      }
      localStorage.setItem("selectedExchanges", JSON.stringify(newList));
      return newList;
    });
  };

  return (
    <div className="relative">
      {/* Mobile Toggle Button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="md:hidden flex items-center space-x-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
      >
        <FaExchangeAlt />
        <span>Exchanges ({selectedExchanges.length})</span>
      </button>

      {/* Exchange Buttons */}
      <div
        className={`flex flex-wrap items-center gap-2 transition-all duration-300 ease-in-out
          ${isExpanded ? 'opacity-100 visible' : 'opacity-0 invisible md:opacity-100 md:visible'}
          ${isExpanded ? 'mt-2' : 'mt-0'}
          md:mt-0`}
      >
        <span className="hidden md:inline text-sm font-medium text-gray-700">Exchange:</span>
        {supportedExchanges.map((ex) => {
          const active = selectedExchanges.includes(ex);
          return (
            <button
              key={ex}
              onClick={() => handleToggleExchange(ex)}
              className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
                ${active
                  ? "bg-indigo-600 text-white hover:bg-indigo-700"
                  : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"}
                ${isExpanded ? 'w-full md:w-auto' : 'w-auto'}
              `}
            >
              <span>{ex.toUpperCase()}</span>
              {active && (
                <span className="text-xs bg-white/20 px-1.5 py-0.5 rounded">
                  ✓
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}