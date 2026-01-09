import axios from 'axios';

const API_BASE = 'https://jucca.onrender.com';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth services
export const authService = {
  login: async (username, password) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await api.post('/token', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    return response.data;
  },
  
  register: async (username, password, role = 'seller') => {
    const response = await api.post('/register', { username, password, role });
    return response.data;
  }
};

// Chat services
export const chatService = {
  ask: async (question, sessionId = 'default', role = 'seller') => {
    const response = await api.post('/ask', {
      question,
      session_id: sessionId,
      role
    });
    return response.data;
  }
};

// Admin services
export const adminService = {
  getStats: async () => {
    const response = await api.get('/admin/policy-stats');
    return response.data;
  },
  
  uploadPolicy: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/admin/upload-policy', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  }
};

// Health check
export const healthService = {
  check: async () => {
    const response = await api.get('/health');
    return response.data;
  }
};

export default api;
