import { useState, useEffect } from 'react';

const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000";

// Define the interfaces based on your new response shape
interface Trade {
  buyPrice: number;
  quantity: number;
  value: number;
}

interface SymbolPortfolio {
  symbol: string;
  totalInvested: number;
  totalPnl: number;
  trades: Trade[];
}

interface PortfolioResponse {
  portfolio: SymbolPortfolio[];
}

export default function PortfolioOverview() {
  const [portfolioData, setPortfolioData] = useState<PortfolioResponse | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');

  useEffect(() => {
    const fetchPortfolio = async () => {
      try {
        const response = await fetch(`${API_URL}/portfolio`);
        if (!response.ok) {
          throw new Error(`Failed to fetch portfolio: ${response.statusText}`);
        }
        const data: PortfolioResponse = await response.json();
        setPortfolioData(data);

        // Set default selected symbol from the response
        if (data.portfolio.length > 0 && !selectedSymbol) {
          setSelectedSymbol(data.portfolio[0].symbol);
        }
      } catch (err) {
        console.error(err);
        setPortfolioData(null);
      }
    };

    fetchPortfolio();
  }, [selectedSymbol]);

  if (!portfolioData) {
    return <div>Loading portfolio data...</div>;
  }

  const selectedPortfolio = portfolioData.portfolio.find(item => item.symbol === selectedSymbol);

  return (
    <div className="bg-white p-6 rounded-4xl shadow space-y-6 mt-6">
      <h1 className="text-2xl font-bold">Portfolio Overview</h1>

      {/* Symbol Dropdown populated from the response */}
      <div className="bg-gray-50 p-4 rounded-2xl shadow">
        <label className="block mb-1 font-bold">Select Symbol</label>
        <select
          className="block appearance-none w-48 bg-white border border-gray-300 hover:border-gray-400 px-4 py-2 rounded-xl leading-tight focus:outline-none"
          value={selectedSymbol}
          onChange={(e) => setSelectedSymbol(e.target.value)}
        >
          {portfolioData.portfolio.map((item) => (
            <option key={item.symbol} value={item.symbol}>
              {item.symbol}
            </option>
          ))}
        </select>
      </div>

      {/* Details for Selected Symbol */}
      {selectedPortfolio ? (
        <div className="bg-gray-50 p-4 rounded-2xl shadow space-y-4">
          <h2 className="text-lg font-bold">{selectedPortfolio.symbol} Details</h2>
          <p>Total Invested: {selectedPortfolio.totalInvested.toFixed(2)} USDT</p>
          <p>Total PnL: {selectedPortfolio.totalPnl.toFixed(2)} USDT</p>

          {/* Trades Table */}
          <div className="max-h-80 overflow-y-auto border rounded-xl p-2">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-100">
                <tr>
                  <th className="text-left p-2 font-medium">Buy Price</th>
                  <th className="text-left p-2 font-medium">Quantity</th>
                  <th className="text-left p-2 font-medium">Value</th>
                </tr>
              </thead>
              <tbody>
                {selectedPortfolio.trades.map((trade, index) => (
                  <tr key={index} className="border-b">
                    <td className="p-2">{trade.buyPrice.toFixed(4)} USDT</td>
                    <td className="p-2">{trade.quantity.toFixed(2)}</td>
                    <td className="p-2">{trade.value.toFixed(2)} USDT</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div>No data available for the selected symbol.</div>
      )}

      {/* Overall Summary Section (Optional) */}
      <div className="bg-gray-50 p-4 rounded-2xl shadow">
        <h2 className="text-lg font-bold">Overall Portfolio Summary</h2>
        {portfolioData.portfolio.length > 0 ? (
          <ul>
            {portfolioData.portfolio.map((item) => (
              <li key={item.symbol} className="mb-2">
                <span className="font-bold">{item.symbol}:</span> Invested: {item.totalInvested.toFixed(2)} USDT, PnL: {item.totalPnl.toFixed(2)} USDT
              </li>
            ))}
          </ul>
        ) : (
          <p>No portfolio data available.</p>
        )}
      </div>
    </div>
  );
}