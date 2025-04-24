import { useState, useEffect } from 'react';
import { supportedExchanges } from '../utils/supported_exchanges';
import { FaPlus, FaEdit, FaTrash, FaCheck, FaTimes, FaExchangeAlt } from 'react-icons/fa';

interface ExchangeKey {
  exchange: string;
  apiKey: string;
  apiSecret: string;
  balance: number;
  leverage: number;
}

export default function ExchangesForm() {
  const [showForm, setShowForm] = useState<boolean>(false);
  const [selectedExchange, setSelectedExchange] = useState<string>(supportedExchanges[0]);
  const [apiKey, setApiKey] = useState<string>('');
  const [apiSecret, setApiSecret] = useState<string>('');
  const [balance, setBalance] = useState<string>('');
  const [leverage, setLeverage] = useState<string>('');
  const [exchangesList, setExchangesList] = useState<ExchangeKey[]>([]);
  const [savedMessage, setSavedMessage] = useState<string>('');
  const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000";

  // Editing state for updating an existing key
  const [editingExchange, setEditingExchange] = useState<string | null>(null);
  const [editApiKey, setEditApiKey] = useState<string>('');
  const [editApiSecret, setEditApiSecret] = useState<string>('');
  const [editBalance, setEditBalance] = useState<string>('');
  const [editLeverage, setEditLeverage] = useState<string>('');

  // Delete modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState<boolean>(false);
  const [exchangeToDelete, setExchangeToDelete] = useState<string | null>(null);

  // Fetch keys for each supported exchange on mount
  useEffect(() => {
    async function fetchKeys() {
      const fetchedKeys: ExchangeKey[] = [];
      for (const exch of supportedExchanges) {
        try {
          const response = await fetch(`${API_URL}/api-keys/${exch}`);
          if (response.ok) {
            const data = await response.json();
            fetchedKeys.push({
              exchange: exch,
              apiKey: data.api_key,
              apiSecret: data.api_secret,
              balance: data.balance || 0,
              leverage: data.leverage || 0
            });
          }
          // If not found (404), simply skip that exchange.
        } catch (error) {
          console.error(`Error fetching key for ${exch}:`, error);
        }
      }
      setExchangesList(fetchedKeys);
    }
    fetchKeys();
  }, [API_URL]);

  // Remove exchanges already saved from the dropdown options
  const availableExchanges = supportedExchanges.filter(
    (exch) => !exchangesList.some(
      (saved) => saved.exchange.toLowerCase() === exch.toLowerCase()
    )
  );

  // Ensure the selected exchange is valid when availableExchanges changes
  useEffect(() => {
    if (!availableExchanges.includes(selectedExchange) && availableExchanges.length > 0) {
      setSelectedExchange(availableExchanges[0]);
    }
  }, [availableExchanges, selectedExchange]);

  // Add a new key
  const handleAddKey = async () => {
    try {
      const formattedSecret = apiSecret.replace(/\\n/g, "\n");
      const response = await fetch(`${API_URL}/api-keys/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exchange: selectedExchange,
          api_key: apiKey,
          api_secret: formattedSecret,
          balance: parseFloat(balance),
          leverage: parseFloat(leverage)
        })
      });
      if (!response.ok) {
        console.error('Error adding API key');
      } else {
        const newKey: ExchangeKey = {
          exchange: selectedExchange,
          apiKey,
          apiSecret: formattedSecret,
          balance: parseFloat(balance),
          leverage: parseFloat(leverage)
        };
        setExchangesList([...exchangesList, newKey]);
        setSavedMessage('Successfully saved your credentials');
        setApiKey('');
        setApiSecret('');
        setBalance('');
        setLeverage('');
        setShowForm(false);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Edit functionality: When Save is clicked in edit mode, this function is called.
  // It makes a PUT request to update the API key data on the backend.
  const handleUpdateKey = async () => {
    if (!editingExchange) return;
    try {
      // Replace all literal "\n" strings with actual newline characters
      const formattedSecret = editApiSecret.replace(/\\n/g, "\n");

      const response = await fetch(`${API_URL}/api-keys/${editingExchange}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exchange: editingExchange,
          api_key: editApiKey,
          api_secret: formattedSecret,
          balance: parseFloat(editBalance),
          leverage: parseFloat(editLeverage)
        })
      });

      if (response.ok) {
        const updatedKey = await response.json();
        setExchangesList(exchangesList.map((key) => {
          if (key.exchange.toLowerCase() === editingExchange.toLowerCase()) {
            return {
              exchange: key.exchange,
              apiKey: updatedKey.api_key,
              apiSecret: updatedKey.api_secret,
              balance: updatedKey.balance,
              leverage: updatedKey.leverage
            };
          }
          return key;
        }));
        setEditingExchange(null);
      } else {
        const errorData = await response.json();
        console.error('Error updating API key:', errorData);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Delete an existing key
  const handleDeleteKey = async (exchange: string) => {
    try {
      const response = await fetch(`${API_URL}/api-keys/${exchange}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        setExchangesList(exchangesList.filter(
          (key) => key.exchange.toLowerCase() !== exchange.toLowerCase()
        ));
        setSavedMessage(`API key for ${exchange.toUpperCase()} deleted successfully.`);
      } else {
        console.error('Error deleting API key');
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Mask function for keys (first 4 and last 4 characters, with 6 asterisks in the middle)
  function maskKey(key: string): string {
    if (key.length <= 8) return key;
    return key.slice(0, 4) + '******' + key.slice(-4);
  }

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6">
        <div className="flex items-center space-x-3 mb-4 md:mb-0">
          <FaExchangeAlt className="text-2xl text-indigo-600" />
          <h2 className="text-xl font-bold text-gray-800">Exchange Configuration</h2>
        </div>
        {availableExchanges.length > 0 && (
          <button
            className="flex items-center space-x-2 bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
            onClick={() => setShowForm(true)}
          >
            <FaPlus />
            <span>Add New Exchange</span>
          </button>
        )}
      </div>

      {savedMessage && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 rounded-lg">
          {savedMessage}
        </div>
      )}

      {showForm && availableExchanges.length > 0 && (
        <div className="mb-6 bg-gray-50 p-6 rounded-xl space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Select Exchange</label>
              <select
                className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={selectedExchange}
                onChange={(e) => setSelectedExchange(e.target.value)}
              >
                {availableExchanges.map((exch) => (
                  <option key={exch} value={exch}>
                    {exch.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">API Key</label>
              <input
                className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">API Secret</label>
              <input
                className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Balance</label>
              <input
                type="number"
                className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={balance}
                onChange={(e) => setBalance(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Leverage</label>
              <input
                type="number"
                className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={leverage}
                onChange={(e) => setLeverage(e.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-end space-x-3">
            <button
              onClick={() => setShowForm(false)}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleAddKey}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Save Credentials
            </button>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        {exchangesList.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No exchanges configured yet. Add your first exchange to get started.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Exchange</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">API Key</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">API Secret</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Balance</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Leverage</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {exchangesList.map((exch, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {exch.exchange.toUpperCase()}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                    {editingExchange === exch.exchange ? (
                      <input
                        className="w-full border border-gray-300 rounded-lg p-1 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        value={editApiKey}
                        onChange={(e) => setEditApiKey(e.target.value)}
                      />
                    ) : (
                      maskKey(exch.apiKey)
                    )}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                    {editingExchange === exch.exchange ? (
                      <input
                        className="w-full border border-gray-300 rounded-lg p-1 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        value={editApiSecret}
                        onChange={(e) => setEditApiSecret(e.target.value)}
                      />
                    ) : (
                      maskKey(exch.apiSecret)
                    )}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                    {editingExchange === exch.exchange ? (
                      <input
                        type="number"
                        className="w-full border border-gray-300 rounded-lg p-1 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        value={editBalance}
                        onChange={(e) => setEditBalance(e.target.value)}
                      />
                    ) : (
                      exch.balance
                    )}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                    {editingExchange === exch.exchange ? (
                      <input
                        type="number"
                        className="w-full border border-gray-300 rounded-lg p-1 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        value={editLeverage}
                        onChange={(e) => setEditLeverage(e.target.value)}
                      />
                    ) : (
                      exch.leverage
                    )}
                  </td>
                  <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div className="flex items-center space-x-2">
                      {editingExchange === exch.exchange ? (
                        <>
                          <button
                            onClick={handleUpdateKey}
                            className="text-green-600 hover:text-green-800 p-1"
                            title="Save"
                          >
                            <FaCheck />
                          </button>
                          <button
                            onClick={() => setEditingExchange(null)}
                            className="text-red-600 hover:text-red-800 p-1"
                            title="Cancel"
                          >
                            <FaTimes />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => {
                              setEditingExchange(exch.exchange);
                              setEditApiKey(exch.apiKey);
                              setEditApiSecret(exch.apiSecret);
                              setEditBalance(String(exch.balance));
                              setEditLeverage(String(exch.leverage));
                            }}
                            className="text-indigo-600 hover:text-indigo-800 p-1"
                            title="Edit"
                          >
                            <FaEdit />
                          </button>
                          <button
                            onClick={() => {
                              setExchangeToDelete(exch.exchange);
                              setDeleteModalOpen(true);
                            }}
                            className="text-red-600 hover:text-red-800 p-1"
                            title="Delete"
                          >
                            <FaTrash />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {deleteModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-xl shadow-lg max-w-sm w-full mx-4">
            <h2 className="text-xl font-bold text-gray-800 mb-4">Confirm Deletion</h2>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete the API key for <strong>{exchangeToDelete?.toUpperCase()}</strong>?
            </p>
            <div className="flex justify-end space-x-3">
              <button
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                onClick={() => {
                  setDeleteModalOpen(false);
                  setExchangeToDelete(null);
                }}
              >
                Cancel
              </button>
              <button
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
                onClick={async () => {
                  if (exchangeToDelete) {
                    await handleDeleteKey(exchangeToDelete);
                    setDeleteModalOpen(false);
                    setExchangeToDelete(null);
                  }
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}