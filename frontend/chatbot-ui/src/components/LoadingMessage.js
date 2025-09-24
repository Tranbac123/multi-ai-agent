import React from 'react';
import { Bot } from 'lucide-react';

const LoadingMessage = () => {
  return (
    <div className="flex gap-3 justify-start">
      <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-primary-600" />
      </div>
      <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
        <div className="flex space-x-1">
          <div 
            className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"
            style={{ animationDelay: '0ms' }}
          ></div>
          <div 
            className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"
            style={{ animationDelay: '150ms' }}
          ></div>
          <div 
            className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"
            style={{ animationDelay: '300ms' }}
          ></div>
        </div>
      </div>
    </div>
  );
};

export default LoadingMessage;




