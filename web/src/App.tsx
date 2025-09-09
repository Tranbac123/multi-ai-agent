import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { useState } from 'react'
import Login from './pages/Login'
import RegisterPage from './pages/RegisterPage'
import Conversations from './pages/Conversations'
import Customers from './pages/Customers'
import Orders from './pages/Orders'
import SubscriptionPage from './pages/SubscriptionPage'
import ChatWidget from './components/ChatWidget'
import Sidebar from './components/Sidebar'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState(null)

  const handleLogin = (userData: any) => {
    setUser(userData)
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    setUser(null)
    setIsAuthenticated(false)
  }

  return (
    <Router>
      <Routes>
        {!isAuthenticated ? (
          <>
            <Route path="/login" element={<Login onLogin={handleLogin} />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="*" element={<Login onLogin={handleLogin} />} />
          </>
        ) : (
          <Route path="*" element={
            <div className="flex h-screen bg-gray-50">
              <Sidebar onLogout={handleLogout} />
              <main className="flex-1 overflow-auto">
                <Routes>
                  <Route path="/" element={<Conversations />} />
                  <Route path="/customers" element={<Customers />} />
                  <Route path="/orders" element={<Orders />} />
                  <Route path="/subscription" element={<SubscriptionPage />} />
                </Routes>
              </main>
              <ChatWidget />
            </div>
          } />
        )}
      </Routes>
    </Router>
  )
}

export default App
