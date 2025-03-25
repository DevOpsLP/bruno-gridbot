// ExchangesButton.tsx
import React, { useState, useEffect } from "react";
import { supportedExchanges } from "../utils/supported_exchanges";

export default function ExchangesButton() {
  const [selectedExchanges, setSelectedExchanges] = useState<string[]>([]);

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
    <div className="flex items-center space-x-2">
      <span className="font-bold">Exchange:</span>
      {supportedExchanges.map((ex) => {
        const active = selectedExchanges.includes(ex);
        return (
          <button
            key={ex}
            onClick={() => handleToggleExchange(ex)}
            className={`px-4 py-1 rounded-full border border-dashed transition
              ${active
                ? "bg-blue-500 text-white border-blue-500 hover:bg-blue-600"
                : "bg-transparent text-gray-700 border-gray-400 hover:bg-gray-100"}
            `}
          >
            {ex.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}