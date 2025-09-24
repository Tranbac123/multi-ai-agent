import React from 'react';
import { Bot, User, ExternalLink, AlertCircle } from 'lucide-react';

const MessageBubble = ({ message, isLoading = false }) => {
  const isUser = message.type === 'user';
  const isError = message.type === 'error';

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          isError ? 'bg-red-100' : 'bg-primary-100'
        }`}>
          {isError ? (
            <AlertCircle className="w-4 h-4 text-red-600" />
          ) : (
            <Bot className="w-4 h-4 text-primary-600" />
          )}
        </div>
      )}
      
      <div className={`max-w-2xl ${isUser ? 'order-first' : ''}`}>
        <div className={`${
          isUser 
            ? 'bg-primary-500 text-white rounded-2xl rounded-br-md px-4 py-3 max-w-xs ml-auto'
            : isError
            ? 'bg-red-100 text-red-800 rounded-2xl rounded-bl-md px-4 py-3 max-w-2xl'
            : 'bg-gray-100 text-gray-900 rounded-2xl rounded-bl-md px-4 py-3 max-w-2xl'
        }`}>
          <div className="whitespace-pre-wrap">{message.content}</div>
          
          {message.citations && message.citations.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Sources:</h4>
              <div className="space-y-1">
                {message.citations.map((citation, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">[{index + 1}]</span>
                    <a
                      href={citation.replace(/^\[.*?\]\s*/, '')}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary-600 hover:text-primary-700 underline text-sm"
                    >
                      {citation}
                      <ExternalLink className="w-3 h-3 inline ml-1" />
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {message.trace && message.trace.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Process:</h4>
              <div className="space-y-1">
                {message.trace.map((item, index) => (
                  <div key={index} className="text-xs text-gray-500 bg-gray-50 rounded px-2 py-1">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        
        <div className="text-xs text-gray-400 mt-1">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
      
      {isUser && (
        <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center flex-shrink-0">
          <User className="w-4 h-4 text-gray-600" />
        </div>
      )}
    </div>
  );
};

export default MessageBubble;


