import { useState, useEffect } from 'react';
import { FaWallet, FaChartBar, FaExchangeAlt, FaChevronDown } from 'react-icons/fa';

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
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  const selectedPortfolio = portfolioData.portfolio.find(item => item.symbol === selectedSymbol);

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 space-y-6">
      <div className="flex items-center space-x-3">
        <FaWallet className="text-2xl text-indigo-600" />
        <h1 className="text-2xl font-bold text-gray-800">Portfolio Overview</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Symbol Selection and Details */}
        <div className="bg-gray-50 p-6 rounded-xl space-y-4">
          <div className="relative">
            <label className="block text-sm font-medium text-gray-700 mb-2">Select Symbol</label>
            <div className="relative">
              <select
                className="block appearance-none w-full bg-white border border-gray-300 hover:border-gray-400 px-4 py-3 pr-8 rounded-lg leading-tight focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
              >
                {portfolioData.portfolio.map((item) => (
                  <option key={item.symbol} value={item.symbol}>
                    {item.symbol}
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-700">
                <FaChevronDown className="fill-current h-4 w-4" />
              </div>
            </div>
          </div>

          {selectedPortfolio && (
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-white rounded-lg shadow-sm">
                <div className="flex items-center space-x-3">
                  <FaChartBar className="text-indigo-600" />
                  <span className="text-gray-600">Total Invested</span>
                </div>
                <span className="font-semibold">{selectedPortfolio.totalInvested.toFixed(2)} USDT</span>
              </div>
              <div className="flex items-center justify-between p-4 bg-white rounded-lg shadow-sm">
                <div className="flex items-center space-x-3">
                  <FaExchangeAlt className="text-indigo-600" />
                  <span className="text-gray-600">Total PnL</span>
                </div>
                <span className={`font-semibold ${selectedPortfolio.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {selectedPortfolio.totalPnl.toFixed(2)} USDT
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Trades Table */}
        <div className="bg-gray-50 p-6 rounded-xl">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Recent Trades</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Buy Price</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {selectedPortfolio?.trades.map((trade, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{trade.buyPrice.toFixed(4)} USDT</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{trade.quantity.toFixed(2)}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{trade.value.toFixed(2)} USDT</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Overall Summary */}
      <div className="bg-gray-50 p-6 rounded-xl">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Portfolio Summary</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {portfolioData.portfolio.map((item) => (
            <div key={item.symbol} className="bg-white p-4 rounded-lg shadow-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-900">{item.symbol}</span>
                <span className={`text-sm ${item.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {item.totalPnl.toFixed(2)} USDT
                </span>
              </div>
              <div className="mt-2 text-sm text-gray-600">
                Invested: {item.totalInvested.toFixed(2)} USDT
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}