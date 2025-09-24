import React from 'react';
import { Bot, AlertCircle } from 'lucide-react';
import { useChat } from './hooks/useChat';
import MessageBubble from './components/MessageBubble';
import ChatInput from './components/ChatInput';
import WelcomeScreen from './components/WelcomeScreen';
import LoadingMessage from './components/LoadingMessage';

function App() {
  const { messages, isLoading, error, sendMessage, clearChat, messagesEndRef } = useChat();

  return (
    <div className="chat-container">
      <header className="flex items-center justify-between p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">AI Search Agent</h1>
            <p className="text-sm text-gray-500">Intelligent search and research assistant</p>
          </div>
        </div>
        <button
          onClick={clearChat}
          className="px-3 py-1 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
        >
          Clear Chat
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && <WelcomeScreen />}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && <LoadingMessage />}

        {error && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
              <AlertCircle className="w-4 h-4 text-red-600" />
            </div>
            <div className="bg-red-50 border border-red-200 rounded-2xl rounded-bl-md px-4 py-3 max-w-2xl">
              <div className="text-red-800">{error}</div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}

export default App;
