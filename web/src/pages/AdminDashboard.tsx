import { useState, useEffect } from 'react'
import { 
  Users, 
  MessageSquare, 
  ShoppingCart, 
  TrendingUp, 
  Activity, 
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle
} from 'lucide-react'

interface DashboardMetrics {
  messages: {
    total: number
    user: number
    assistant: number
    response_rate: number
  }
  workflows: {
    [key: string]: {
      total: number
      success: number
      failure: number
      success_rate: number
    }
  }
  conversions: {
    [key: string]: {
      count: number
      average_value: number
    }
  }
  performance: {
    average_response_time: number
    uptime_percentage: number
    error_rate: number
  }
  customers: {
    total: number
    new_today: number
    active_week: number
  }
}

interface RealtimeMetrics {
  active_sessions: number
  message_rate_per_minute: number
  average_response_time: number
  system_status: string
}

const AdminDashboard = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [realtimeMetrics, setRealtimeMetrics] = useState<RealtimeMetrics | null>(null)
  const [timeRange, setTimeRange] = useState('24h')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchDashboardMetrics()
    fetchRealtimeMetrics()
    
    // Update real-time metrics every 30 seconds
    const interval = setInterval(fetchRealtimeMetrics, 30000)
    
    return () => clearInterval(interval)
  }, [timeRange])

  const fetchDashboardMetrics = async () => {
    try {
      setIsLoading(true)
      const response = await fetch(`/api/analytics/dashboard?time_range=${timeRange}`)
      const data = await response.json()
      setMetrics(data.data)
    } catch (error) {
      console.error('Failed to fetch dashboard metrics:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const fetchRealtimeMetrics = async () => {
    try {
      const response = await fetch('/api/analytics/realtime')
      const data = await response.json()
      setRealtimeMetrics(data.data)
    } catch (error) {
      console.error('Failed to fetch real-time metrics:', error)
    }
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M'
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K'
    }
    return num.toString()
  }

  const formatPercentage = (num: number) => {
    return num.toFixed(1) + '%'
  }

  const formatTime = (seconds: number) => {
    if (seconds < 60) {
      return seconds.toFixed(1) + 's'
    } else {
      return (seconds / 60).toFixed(1) + 'm'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
        <div className="flex space-x-4">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="1h">Last Hour</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>
          <button
            onClick={fetchDashboardMetrics}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Real-time Status */}
      {realtimeMetrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-6 rounded-lg shadow border">
            <div className="flex items-center">
              <Activity className="h-8 w-8 text-green-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">System Status</p>
                <p className="text-2xl font-semibold text-gray-900 capitalize">
                  {realtimeMetrics.system_status}
                </p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow border">
            <div className="flex items-center">
              <Users className="h-8 w-8 text-blue-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Active Sessions</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {realtimeMetrics.active_sessions}
                </p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow border">
            <div className="flex items-center">
              <MessageSquare className="h-8 w-8 text-purple-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Message Rate</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {realtimeMetrics.message_rate_per_minute.toFixed(1)}/min
                </p>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow border">
            <div className="flex items-center">
              <Clock className="h-8 w-8 text-orange-500" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">Avg Response Time</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {formatTime(realtimeMetrics.average_response_time)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Metrics */}
      {metrics && (
        <>
          {/* Message Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <MessageSquare className="h-8 w-8 text-blue-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Total Messages</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatNumber(metrics.messages.total)}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <Users className="h-8 w-8 text-green-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">User Messages</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatNumber(metrics.messages.user)}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <CheckCircle className="h-8 w-8 text-purple-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Assistant Messages</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatNumber(metrics.messages.assistant)}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <TrendingUp className="h-8 w-8 text-orange-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Response Rate</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatPercentage(metrics.messages.response_rate)}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Workflow Performance */}
          <div className="bg-white p-6 rounded-lg shadow border">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Workflow Performance</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.entries(metrics.workflows).map(([workflow, data]) => (
                <div key={workflow} className="border rounded-lg p-4">
                  <h4 className="font-medium text-gray-900 mb-2">{workflow}</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-500">Total</span>
                      <span className="text-sm font-medium">{data.total}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-500">Success</span>
                      <span className="text-sm font-medium text-green-600">{data.success}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-500">Failure</span>
                      <span className="text-sm font-medium text-red-600">{data.failure}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-500">Success Rate</span>
                      <span className="text-sm font-medium">{formatPercentage(data.success_rate)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Conversions */}
          <div className="bg-white p-6 rounded-lg shadow border">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Conversions</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(metrics.conversions).map(([type, data]) => (
                <div key={type} className="border rounded-lg p-4">
                  <h4 className="font-medium text-gray-900 mb-2 capitalize">{type}</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-500">Count</span>
                      <span className="text-sm font-medium">{data.count}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-500">Avg Value</span>
                      <span className="text-sm font-medium">${data.average_value.toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Performance Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <Clock className="h-8 w-8 text-blue-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Avg Response Time</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatTime(metrics.performance.average_response_time)}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <CheckCircle className="h-8 w-8 text-green-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Uptime</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatPercentage(metrics.performance.uptime_percentage)}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <XCircle className="h-8 w-8 text-red-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Error Rate</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatPercentage(metrics.performance.error_rate)}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Customer Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <Users className="h-8 w-8 text-blue-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Total Customers</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatNumber(metrics.customers.total)}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <TrendingUp className="h-8 w-8 text-green-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">New Today</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatNumber(metrics.customers.new_today)}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center">
                <Activity className="h-8 w-8 text-purple-500" />
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Active This Week</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {formatNumber(metrics.customers.active_week)}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default AdminDashboard
