import React from 'react';

const Sidebar: React.FC = () => {
  return (
    <nav className="w-64 h-screen bg-gray-800 text-white flex flex-col">
      <div className="p-4 text-lg font-bold border-b border-gray-700">
        Bot Control
      </div>
      <ul className="flex-1 ">
        <li className="border-b border-gray-700">
          <a href="/" className="block p-4  hover:bg-gray-700">🏠 Home</a>
        </li>
        <li className="border-b border-gray-700">
          <a href="/api-keys" className="block p-4  hover:bg-gray-700">🔑 API Keys</a>
        </li>
      </ul>
    </nav>
  );
};

export default Sidebar;