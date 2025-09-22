import { useState, useRef, useEffect } from 'react'
import { Send, MessageCircle, X, Minimize2 } from 'lucide-react'

interface Message {
  id: string
  text: string
  role: 'user' | 'assistant'
  timestamp: Date
}

interface ChatWidgetProps {
  apiBaseUrl?: string
  brand?: string
}

const ChatWidget = ({ apiBaseUrl = '/api', brand = 'AI Customer Agent' }: ChatWidgetProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Hello! I\'m your AI customer assistant. How can I help you today?',
      role: 'assistant',
      timestamp: new Date()
    }
  ])
  const [inputText, setInputText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Generate session ID if not exists
    if (!sessionId) {
      setSessionId(`session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`)
    }
  }, [sessionId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSendMessage = async () => {
    if (!inputText.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputText,
      role: 'user',
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInputText('')
    setIsLoading(true)

    try {
      const response = await fetch(`${apiBaseUrl}/chat/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: inputText,
          session_id: sessionId,
          channel: 'web'
        }),
      })

      if (response.ok) {
        const data = await response.json()
        const assistantMessage: Message = {
          id: Date.now().toString(),
          text: data.data.answer,
          role: 'assistant',
          timestamp: new Date()
        }
        setMessages(prev => [...prev, assistantMessage])
      } else {
        throw new Error('Failed to send message')
      }
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: Message = {
        id: Date.now().toString(),
        text: 'Sorry, I\'m having trouble processing your request. Please try again.',
        role: 'assistant',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const toggleChat = () => {
    if (isMinimized) {
      setIsMinimized(false)
    } else if (isOpen) {
      setIsOpen(false)
    } else {
      setIsOpen(true)
    }
  }

  if (!isOpen && !isMinimized) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <button
          onClick={toggleChat}
          className="bg-primary-600 hover:bg-primary-700 text-white rounded-full p-4 shadow-lg transition-all duration-200 hover:scale-110"
        >
          <MessageCircle size={24} />
        </button>
      </div>
    )
  }

  if (isMinimized) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <button
          onClick={toggleChat}
          className="bg-primary-600 hover:bg-primary-700 text-white rounded-full p-4 shadow-lg transition-all duration-200"
        >
          <MessageCircle size={24} />
        </button>
      </div>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 w-96 h-[500px] bg-white rounded-lg shadow-xl border border-gray-200 flex flex-col">
      {/* Header */}
      <div className="bg-primary-600 text-white p-4 rounded-t-lg flex items-center justify-between">
        <div>
          <h3 className="font-semibold">{brand}</h3>
          <p className="text-sm text-primary-100">AI Assistant</p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => setIsMinimized(true)}
            className="text-white hover:text-primary-100 transition-colors"
          >
            <Minimize2 size={16} />
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="text-white hover:text-primary-100 transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-xs px-4 py-2 rounded-lg ${
                message.role === 'user'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              <p className="text-sm">{message.text}</p>
              <p className="text-xs opacity-70 mt-1">
                {message.timestamp.toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex space-x-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            disabled={isLoading}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputText.trim() || isLoading}
            className="bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors duration-200"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatWidget
