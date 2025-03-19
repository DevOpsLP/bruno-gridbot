// ExchangesButton.tsx
import React, { useState, useEffect } from "react";
import { supportedExchanges } from "../utils/supported_exchanges";

export default function ExchangesButton() {
  const [selectedExchanges, setSelectedExchanges] = useState<string[]>([]);
  const [showList, setShowList] = useState(false);

  useEffect(() => {
    // Load from localStorage
    const saved = localStorage.getItem("selectedExchanges");
    if (saved) {
      setSelectedExchanges(JSON.parse(saved));
    }
  }, []);

  const handleToggleExchange = (exchange: string) => {
    setSelectedExchanges((prev) => {
      let newList = [];
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
    <div className="relative inline-block z-50">
      <button
        onClick={() => setShowList(!showList)}
        className="px-4 py-2 border rounded-xl"
      >
        Exchanges
      </button>
      {showList && (
        <div className="absolute bg-white border rounded shadow p-2 mt-2">
          {supportedExchanges.map((ex) => {
            const active = selectedExchanges.includes(ex);
            return (
              <div
                key={ex}
                className="flex items-center space-x-2 hover:bg-gray-100 p-1 cursor-pointer"
                onClick={() => handleToggleExchange(ex)}
              >
                <input type="checkbox" readOnly checked={active} />
                <span>{ex.toUpperCase()}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}