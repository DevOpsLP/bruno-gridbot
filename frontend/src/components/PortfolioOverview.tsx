import { useState, useEffect } from 'react';

const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000";

// List of supported wallets for the dropdown
const supportedWallets = ['Binance', 'Coinbase', 'Kraken'];

interface Order {
  buyPrice: number;
  quantity: number;
  value: number;
}

interface PairData {
  symbol: string;
  totalInvested: number;
  currentPrice: number;
  totalValue: number;
  profitLoss: number;
  profitLossPercent: number;
  orders: Order[];
}

interface PortfolioResponse {
  pairs: PairData[];
  summary: {
    totalInvestedAllPairs: number;
    totalValueAllPairs: number;
    totalPL: number;
    totalPLPercent: number;
    availableBalance: Record<string, number>;
  };
}

export default function PortfolioOverview() {
  const [selectedWallet, setSelectedWallet] = useState<string>('Binance');
  const [portfolioData, setPortfolioData] = useState<PortfolioResponse | null>(null);
  const [selectedPair, setSelectedPair] = useState<string>('');

  useEffect(() => {
    const fetchPortfolio = async () => {
      try {
        const response = await fetch(`${API_URL}/portfolio/${selectedWallet}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch portfolio: ${response.statusText}`);
        }
        const data: PortfolioResponse = await response.json();
        setPortfolioData(data);

        // Set default selected pair if not already set
        if (data.pairs.length > 0 && !selectedPair) {
          setSelectedPair(data.pairs[0].symbol);
        }
      } catch (err) {
        console.error(err);
        setPortfolioData(null);
      }
    };

    fetchPortfolio();
  }, [selectedWallet, selectedPair]);

  if (!portfolioData) {
    return <div>Loading portfolio data...</div>;
  }

  // Destructure the fetched data
  const { pairs, summary } = portfolioData;
  const pairData = pairs.find((p) => p.symbol === selectedPair);

  const {
    totalInvestedAllPairs,
    totalValueAllPairs,
    totalPL,
    totalPLPercent,
    availableBalance,
  } = summary;

  return (
    <div className="bg-white p-6 rounded-4xl shadow space-y-6 mt-6">
      <h1 className="text-2xl font-bold">Portfolio Overview</h1>

      {/* Top Summary Section */}
      <div className="bg-gray-50 p-4 rounded-2xl shadow">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="font-bold text-lg">Total for {selectedWallet} Wallet</h3>
            <p>Total Invested: {totalInvestedAllPairs.toFixed(2)} USDT</p>
            <p>Current Total Value: {totalValueAllPairs.toFixed(2)} USDT</p>
            <p className={totalPL >= 0 ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>
              Total Profit/Loss: {totalPL.toFixed(2)} USDT ({totalPLPercent.toFixed(2)}%)
            </p>
            {/* Available balances by asset */}
            <div className="mt-2">
              <strong>Available Balances:</strong>
              {Object.entries(availableBalance)
                .filter(([_, amount]) => amount > 0)
                .map(([asset, amount]) => (
                  <p key={asset}>
                    {asset}: {amount.toFixed(8)}
                  </p>
              ))}
            </div>
          </div>

          {/* Wallet Selection Dropdown */}
          <div className="mt-4 md:mt-0">
            <label className="block mb-1 font-bold">Select Wallet</label>
            <div className="inline-block relative">
              <select
                className="block appearance-none w-48 bg-white border border-gray-300 hover:border-gray-400 px-4 py-2 pr-8 rounded-xl leading-tight focus:outline-none"
                value={selectedWallet}
                onChange={(e) => {
                  setSelectedWallet(e.target.value);
                  setSelectedPair(''); // reset pair selection on wallet change
                }}
              >
                {supportedWallets.map((wallet) => (
                  <option key={wallet} value={wallet}>
                    {wallet}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Pair Selection & Details Section */}
      <div className="bg-gray-50 p-4 rounded-2xl shadow space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <label className="block font-bold">Select Pair:</label>
          <div className="inline-block relative">
            <select
              className="block appearance-none w-44 bg-white border border-gray-300 hover:border-gray-400 px-3 py-2 pr-8 rounded-xl leading-tight focus:outline-none"
              value={selectedPair}
              onChange={(e) => setSelectedPair(e.target.value)}
            >
              {pairs.map((p) => (
                <option key={p.symbol} value={p.symbol}>
                  {p.symbol}
                </option>
              ))}
            </select>
          </div>
        </div>

        {pairData ? (
          <div className="flex flex-col md:flex-row gap-6">
            {/* Basic Stats Column */}
            <div className="flex-1 space-y-2">
              <h2 className="text-lg font-bold">{pairData.symbol} Overview</h2>
              <p>Total Invested: {pairData.totalInvested.toFixed(2)} USDT</p>
              <p>
                Current Price:{' '}
                <span className="font-semibold">
                  {pairData.currentPrice.toFixed(4)} USDT
                </span>
              </p>
              <p>Total Value: {pairData.totalValue.toFixed(2)} USDT</p>
              <p className={pairData.profitLoss >= 0 ? 'text-green-600' : 'text-red-600'}>
                Profit/Loss: {pairData.profitLoss.toFixed(2)} USDT ({pairData.profitLossPercent.toFixed(2)}%)
              </p>
            </div>

            {/* Orders Table in a Scrollable Box */}
            <div className="flex-1">
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
                    {pairData.orders.map((order, index) => (
                      <tr key={index} className="border-b">
                        <td className="p-2">{order.buyPrice.toFixed(4)} USDT</td>
                        <td className="p-2">{order.quantity.toFixed(2)}</td>
                        <td className="p-2">{order.value.toFixed(2)} USDT</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
          <p>No data available for this pair.</p>
        )}
      </div>

      {/* Overall PnL Display Section */}
      <div className="bg-gray-50 p-4 rounded-2xl shadow">
        <h2 className="text-lg font-bold mb-4">Overall Profit & Loss</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className={totalPL >= 0 ? 'text-green-600 font-bold text-2xl' : 'text-red-600 font-bold text-2xl'}>
              {totalPL.toFixed(2)} USDT
            </p>
            <p className="text-sm">
              {totalPLPercent.toFixed(2)}%
            </p>
          </div>
          <div>
            {/* You can replace this placeholder with an icon or graphic */}
            <span className="text-gray-500">[Icon]</span>
          </div>
        </div>
      </div>

      {/* Performance Chart Placeholder */}
      <div className="bg-gray-50 p-4 rounded-2xl shadow">
        <h2 className="text-lg font-bold mb-4">Performance Chart</h2>
        <div className="w-full h-48 bg-gray-200 rounded flex items-center justify-center">
          <span className="text-gray-500">[Chart Placeholder]</span>
        </div>
      </div>
    </div>
  );
}