import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      throw new Error(error.response.data.detail || 'Server error occurred');
    } else if (error.request) {
      throw new Error('Unable to connect to the server. Please check if the API is running.');
    } else {
      throw new Error('An unexpected error occurred');
    }
  }
);

export const askQuestion = async (query, sessionId = null) => {
  try {
    const response = await api.post('/ask', {
      query,
      session_id: sessionId,
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const checkHealth = async () => {
  try {
    const response = await api.get('/healthz');
    return response.data;
  } catch (error) {
    throw error;
  }
};

export default api;


