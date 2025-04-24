import React, { useState } from 'react';
import { FaHome, FaKey, FaBars, FaTimes } from 'react-icons/fa';

const Sidebar: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Mobile menu button */}
      <div className="md:hidden fixed top-4 right-4 z-50">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="p-3 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors shadow-lg"
        >
          {isOpen ? <FaTimes size={24} /> : <FaBars size={24} />}
        </button>
      </div>

      {/* Sidebar */}
      <nav
        className={`fixed top-0 left-0 h-screen bg-white shadow-lg transform transition-transform duration-300 ease-in-out z-40
          ${isOpen ? 'translate-x-0 w-64' : '-translate-x-full w-64'} 
          md:translate-x-0 md:relative md:w-64`}
      >
        <div className="h-full flex flex-col">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-bold text-gray-800 flex items-center space-x-2">
              <FaBars className="text-indigo-600" />
              <span>Bot Control</span>
            </h2>
          </div>
          
          <ul className="flex-1 py-4">
            <li>
              <a
                href="/"
                className="flex items-center space-x-3 px-6 py-3 text-gray-700 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
              >
                <FaHome className="text-indigo-600" />
                <span>Home</span>
              </a>
            </li>
            <li>
              <a
                href="/api-keys"
                className="flex items-center space-x-3 px-6 py-3 text-gray-700 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
              >
                <FaKey className="text-indigo-600" />
                <span>API Keys</span>
              </a>
            </li>
          </ul>
        </div>
      </nav>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
          onClick={() => setIsOpen(false)}
        />
      )}
    </>
  );
};

export default Sidebar;