import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, MessageCircle, X, Minimize2, Paperclip, Image, FileText, Mic, MicOff } from 'lucide-react'

interface Message {
  id: string
  text: string
  role: 'user' | 'assistant'
  timestamp: Date
  metadata?: any
  files?: FileAttachment[]
}

interface FileAttachment {
  id: string
  filename: string
  type: string
  url: string
  thumbnail_url?: string
  size: number
}

interface EnhancedChatWidgetProps {
  apiBaseUrl?: string
  brand?: string
  enableFileUpload?: boolean
  enableVoice?: boolean
  enableTypingIndicator?: boolean
}

const EnhancedChatWidget = ({ 
  apiBaseUrl = '/api', 
  brand = 'AI Customer Agent',
  enableFileUpload = true,
  enableVoice = false,
  enableTypingIndicator = true
}: EnhancedChatWidgetProps) => {
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
  const [isTyping, setIsTyping] = useState(false)
  const [sessionId, setSessionId] = useState<string>('')
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number>(0)
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

  useEffect(() => {
    // Generate session ID if not exists
    if (!sessionId) {
      setSessionId(`session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`)
    }
  }, [sessionId])

  useEffect(() => {
    // Initialize WebSocket connection
    if (isOpen && !ws) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}${apiBaseUrl}/ws/chat?session_id=${sessionId}`
      
      const websocket = new WebSocket(wsUrl)
      
      websocket.onopen = () => {
        setIsConnected(true)
        setWs(websocket)
      }
      
      websocket.onmessage = (event) => {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      }
      
      websocket.onclose = () => {
        setIsConnected(false)
        setWs(null)
      }
      
      websocket.onerror = (error) => {
        console.error('WebSocket error:', error)
        setIsConnected(false)
      }
    }
    
    return () => {
      if (ws) {
        ws.close()
        setWs(null)
      }
    }
  }, [isOpen, sessionId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'welcome':
        console.log('Connected to AI Customer Agent')
        break
      case 'response':
        const assistantMessage: Message = {
          id: Date.now().toString(),
          text: data.data.text,
          role: 'assistant',
          timestamp: new Date(),
          metadata: data.data.metadata
        }
        setMessages(prev => [...prev, assistantMessage])
        setIsLoading(false)
        break
      case 'typing':
        setIsTyping(data.is_typing)
        break
      case 'error':
        console.error('WebSocket error:', data.message)
        setIsLoading(false)
        break
      default:
        console.log('Unknown message type:', data.type)
    }
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
      if (ws && isConnected) {
        // Send via WebSocket
        ws.send(JSON.stringify({
          type: 'message',
          text: inputText,
          session_id: sessionId,
          channel: 'web'
        }))
      } else {
        // Fallback to REST API
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
        setIsLoading(false)
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
      setIsLoading(false)
    }
  }

  const handleFileUpload = async (file: File) => {
    if (!enableFileUpload) return

    try {
      setUploadProgress(0)
      
      const formData = new FormData()
      formData.append('file', file)
      formData.append('session_id', sessionId)

      const response = await fetch(`${apiBaseUrl}/files/upload`, {
        method: 'POST',
        body: formData,
      })

      if (response.ok) {
        const data = await response.json()
        const fileAttachment: FileAttachment = {
          id: data.data.id,
          filename: data.data.filename,
          type: data.data.type,
          url: data.data.url,
          thumbnail_url: data.data.thumbnail_url,
          size: data.data.size
        }

        // Add file to last user message or create new message
        setMessages(prev => {
          const newMessages = [...prev]
          const lastMessage = newMessages[newMessages.length - 1]
          
          if (lastMessage && lastMessage.role === 'user') {
            lastMessage.files = [...(lastMessage.files || []), fileAttachment]
          } else {
            const fileMessage: Message = {
              id: Date.now().toString(),
              text: `📎 ${file.name}`,
              role: 'user',
              timestamp: new Date(),
              files: [fileAttachment]
            }
            newMessages.push(fileMessage)
          }
          
          return newMessages
        })

        setUploadProgress(100)
        setTimeout(() => setUploadProgress(0), 2000)
      } else {
        throw new Error('File upload failed')
      }
    } catch (error) {
      console.error('Error uploading file:', error)
      setUploadProgress(0)
    }
  }

  const handleVoiceRecording = async () => {
    if (!enableVoice) return

    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const mediaRecorder = new MediaRecorder(stream)
        mediaRecorderRef.current = mediaRecorder
        audioChunksRef.current = []

        mediaRecorder.ondataavailable = (event) => {
          audioChunksRef.current.push(event.data)
        }

        mediaRecorder.onstop = async () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' })
          // Here you would typically send the audio to a speech-to-text service
          console.log('Audio recorded:', audioBlob)
        }

        mediaRecorder.start()
        setIsRecording(true)
      } catch (error) {
        console.error('Error starting voice recording:', error)
      }
    } else {
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop()
        setIsRecording(false)
      }
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

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const renderFileAttachment = (file: FileAttachment) => {
    if (file.type === 'image') {
      return (
        <div className="mt-2">
          <img 
            src={file.thumbnail_url || file.url} 
            alt={file.filename}
            className="max-w-xs rounded-lg cursor-pointer"
            onClick={() => window.open(file.url, '_blank')}
          />
          <p className="text-xs text-gray-500 mt-1">{file.filename}</p>
        </div>
      )
    } else {
      return (
        <div className="mt-2 p-2 bg-gray-100 rounded-lg flex items-center space-x-2">
          <FileText size={16} />
          <div className="flex-1">
            <p className="text-sm font-medium">{file.filename}</p>
            <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
          </div>
          <button
            onClick={() => window.open(file.url, '_blank')}
            className="text-blue-500 hover:text-blue-700"
          >
            View
          </button>
        </div>
      )
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
          <p className="text-sm text-primary-100">
            AI Assistant {isConnected ? '🟢' : '🔴'}
          </p>
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
              {message.files && message.files.map((file) => (
                <div key={file.id}>
                  {renderFileAttachment(file)}
                </div>
              ))}
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
        
        {isTyping && enableTypingIndicator && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg">
              <p className="text-sm">AI is typing...</p>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Upload Progress */}
      {uploadProgress > 0 && (
        <div className="px-4 py-2 bg-blue-50 border-t border-blue-200">
          <div className="flex items-center space-x-2">
            <div className="flex-1 bg-blue-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
            <span className="text-xs text-blue-600">{uploadProgress}%</span>
          </div>
        </div>
      )}

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
          
          {enableFileUpload && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-gray-500 hover:text-gray-700 p-2"
              disabled={isLoading}
            >
              <Paperclip size={16} />
            </button>
          )}
          
          {enableVoice && (
            <button
              onClick={handleVoiceRecording}
              className={`p-2 ${isRecording ? 'text-red-500' : 'text-gray-500 hover:text-gray-700'}`}
              disabled={isLoading}
            >
              {isRecording ? <MicOff size={16} /> : <Mic size={16} />}
            </button>
          )}
          
          <button
            onClick={handleSendMessage}
            disabled={!inputText.trim() || isLoading}
            className="bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors duration-200"
          >
            <Send size={16} />
          </button>
        </div>
        
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept="image/*,application/pdf,.doc,.docx,.txt"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) {
              handleFileUpload(file)
            }
          }}
        />
      </div>
    </div>
  )
}

export default EnhancedChatWidget
