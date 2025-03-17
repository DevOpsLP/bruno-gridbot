import { useState } from 'react';

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

// Example data for demonstration
const mockPairs: PairData[] = [
  {
    symbol: 'FET-USDC',
    totalInvested: 40,
    currentPrice: 0.41,
    totalValue: 37.73,
    profitLoss: -2.27,
    profitLossPercent: -5.68,
    orders: [
      { buyPrice: 0.45, quantity: 22.22, value: 10 },
      { buyPrice: 0.44, quantity: 22.73, value: 10 },
      { buyPrice: 0.43, quantity: 23.26, value: 10 },
      { buyPrice: 0.42, quantity: 23.81, value: 10 },
    ],
  },
  {
    symbol: 'INJ-USDC',
    totalInvested: 30,
    currentPrice: 16.8,
    totalValue: 28.01,
    profitLoss: -1.99,
    profitLossPercent: -6.62,
    orders: [
      { buyPrice: 18.5, quantity: 0.54, value: 10 },
      { buyPrice: 18.0, quantity: 0.56, value: 10 },
      { buyPrice: 17.5, quantity: 0.57, value: 10 },
    ],
  },
  {
    symbol: 'RENDER-USDC',
    totalInvested: 40,
    currentPrice: 5.5,
    totalValue: 37.34,
    profitLoss: -2.66,
    profitLossPercent: -6.65,
    orders: [
      { buyPrice: 6.2, quantity: 1.61, value: 10 },
      { buyPrice: 6.0, quantity: 1.67, value: 10 },
      { buyPrice: 5.8, quantity: 1.72, value: 10 },
      { buyPrice: 5.6, quantity: 1.79, value: 10 },
    ],
  },
];

const supportedWallets = ['Binance', 'Coinbase', 'Kraken'];

export default function PortfolioOverview() {
  const [selectedWallet, setSelectedWallet] = useState<string>('Binance');
  const [selectedPair, setSelectedPair] = useState<string>('FET-USDC');

  // In a real scenario, you’d fetch or compute these from an API
  // Here, just using the mock data from above:
  const pairData = mockPairs.find((p) => p.symbol === selectedPair);

  const totalInvestedAllPairs = mockPairs.reduce((sum, p) => sum + p.totalInvested, 0);
  const totalValueAllPairs = mockPairs.reduce((sum, p) => sum + p.totalValue, 0);
  const totalPL = totalValueAllPairs - totalInvestedAllPairs;
  const totalPLPercent = (totalPL / totalInvestedAllPairs) * 100;

  return (
    <div className="bg-white p-6 rounded-4xl shadow space-y-6 mt-6">
      <h1 className="text-2xl font-bold">Portfolio Overview</h1>

      {/* Top summary: total across wallet (placeholder logic) */}
      <div className="bg-gray-50 p-4 rounded-2xl shadow">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="font-bold text-lg">Total for {selectedWallet} Wallet</h3>
            <p>Total Invested: {totalInvestedAllPairs.toFixed(2)} USDT</p>
            <p>Current Total Value: {totalValueAllPairs.toFixed(2)} USDT</p>
            <p
              className={
                totalPL >= 0 ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'
              }
            >
              Total Profit/Loss: {totalPL.toFixed(2)} USDT ({totalPLPercent.toFixed(2)}%)
            </p>
          </div>

          {/* Wallet selection */}
          <div className="mt-4 md:mt-0">
            <label className="block mb-1 font-bold">Select Wallet</label>
            <div className="inline-block relative">
              <select
                className="block appearance-none w-48 bg-white border border-gray-300 hover:border-gray-400 px-4 py-2 pr-8 rounded-xl leading-tight focus:outline-none"
                value={selectedWallet}
                onChange={(e) => setSelectedWallet(e.target.value)}
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

      {/* Pair selection & details */}
      <div className="bg-gray-50 p-4 rounded-2xl shadow space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <label className="block font-bold">Select Pair:</label>
          <div className="inline-block relative">
            <select
              className="block appearance-none w-44 bg-white border border-gray-300 hover:border-gray-400 px-3 py-2 pr-8 rounded-xl leading-tight focus:outline-none"
              value={selectedPair}
              onChange={(e) => setSelectedPair(e.target.value)}
            >
              {mockPairs.map((p) => (
                <option key={p.symbol} value={p.symbol}>
                  {p.symbol}
                </option>
              ))}
            </select>
          </div>
        </div>

        {pairData ? (
          <div className="flex flex-col md:flex-row gap-6 ">
            {/* Left column: Basic stats */}
            <div className="flex-1 space-y-2">
              <h2 className="text-lg font-bold">
                {pairData.symbol} Overview
              </h2>
              <p>Total Invested: {pairData.totalInvested.toFixed(2)} USDT</p>
              <p>
                Current Price:{' '}
                <span className="font-semibold">
                  {pairData.currentPrice.toFixed(4)} USDT
                </span>
              </p>
              <p>Total Value: {pairData.totalValue.toFixed(2)} USDT</p>
              <p
                className={
                  pairData.profitLoss >= 0 ? 'text-green-600' : 'text-red-600'
                }
              >
                Profit/Loss: {pairData.profitLoss.toFixed(2)} USDT (
                {pairData.profitLossPercent.toFixed(2)}%)
              </p>
            </div>

            {/* Right column: Orders table in a scrollable box */}
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

      {/* Chart placeholder (optional) */}
      <div className="bg-gray-50 p-4 rounded-2xl shadow">
        <h2 className="text-lg font-bold mb-4">Performance Chart</h2>
        <div className="w-full h-48 bg-gray-200 rounded flex items-center justify-center">
          <span className="text-gray-500">[Chart Placeholder]</span>
        </div>
      </div>
    </div>
  );
}