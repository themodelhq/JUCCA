import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminService, chatService } from '../services/api';
import { 
  Shield, BarChart3, Upload, Users, FileText, 
  AlertTriangle, CheckCircle, XCircle, ArrowLeft,
  RefreshCw, Database, TrendingUp, ClipboardList,
  Plus, Trash2, Edit, Search, Filter, Eye,
  LogOut, Clock, UserCheck, UserX
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const COLORS = ['#F68B1E', '#22C55E', '#EF4444', '#EAB308', '#8B5CF6', '#EC4899'];

function StatCard({ icon: Icon, title, value, subtitle, color, onClick }) {
  return (
    <div 
      className={`bg-white rounded-xl p-6 shadow-sm border border-gray-100 ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-center gap-4">
        <div className={`w-12 h-12 ${color} rounded-xl flex items-center justify-center`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-800">{value}</p>
          <p className="text-sm text-gray-500">{title}</p>
          {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
        </div>
      </div>
    </div>
  );
}

function Modal({ isOpen, onClose, title, children }) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-800">{title}</h3>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <XCircle className="w-5 h-5 text-gray-400" />
          </button>
        </div>
        <div className="p-6">
          {children}
        </div>
      </div>
    </div>
  );
}

function UserModal({ isOpen, onClose, onSubmit, user = null, isLoading }) {
  const [formData, setFormData] = useState({
    username: user?.username || '',
    password: '',
    role: user?.role || 'seller'
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={user ? 'Edit User' : 'Create New User'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
          <input
            type="text"
            value={formData.username}
            onChange={(e) => setFormData({ ...formData, username: e.target.value })}
            className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-jumia-orange focus:border-transparent outline-none"
            required
            disabled={!!user}
          />
        </div>
        {!user && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-jumia-orange focus:border-transparent outline-none"
              required
            />
          </div>
        )}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
          <select
            value={formData.role}
            onChange={(e) => setFormData({ ...formData, role: e.target.value })}
            className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-jumia-orange focus:border-transparent outline-none"
          >
            <option value="admin">Admin</option>
            <option value="seller">Seller</option>
            <option value="legal">Legal</option>
          </select>
        </div>
        <div className="flex gap-3 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="flex-1 px-4 py-2 bg-jumia-orange text-white rounded-lg hover:bg-orange-600 disabled:opacity-50"
          >
            {isLoading ? 'Saving...' : (user ? 'Update' : 'Create')}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function LogsViewer({ logs, onClose }) {
  const getLevelColor = (level) => {
    switch (level) {
      case 'error': return 'text-red-600 bg-red-50';
      case 'warning': return 'text-yellow-600 bg-yellow-50';
      case 'critical': return 'text-purple-600 bg-purple-50';
      default: return 'text-green-600 bg-green-50';
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        <div className="p-6 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
          <h3 className="font-semibold text-gray-800">System Logs</h3>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <XCircle className="w-5 h-5 text-gray-400" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {logs.length === 0 ? (
            <p className="text-center text-gray-500 py-8">No logs found</p>
          ) : (
            <div className="space-y-3">
              {logs.map((log) => (
                <div key={log.id} className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getLevelColor(log.level)}`}>
                      {log.level.toUpperCase()}
                    </span>
                    <span className="text-sm text-gray-500">{log.category}</span>
                    <span className="text-xs text-gray-400 ml-auto">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-gray-700">{log.message}</p>
                  {log.ip_address && (
                    <p className="text-xs text-gray-400 mt-1">IP: {log.ip_address}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AdminDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState({ total_brands: 0, total_keywords: 0, total_products: 0 });
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState(null);
  
  // User management state
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [userFormLoading, setUserFormLoading] = useState(false);
  
  // Logs state
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logStats, setLogStats] = useState(null);
  const [logFilters, setLogFilters] = useState({ level: '', category: '' });
  const [showLogsModal, setShowLogsModal] = useState(false);
  
  const navigate = useNavigate();

  useEffect(() => {
    loadStats();
    if (activeTab === 'users') loadUsers();
    if (activeTab === 'logs') loadLogs();
  }, [activeTab]);

  const loadStats = async () => {
    try {
      const data = await adminService.getStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    setUsersLoading(true);
    try {
      const data = await adminService.getUsers();
      setUsers(data);
    } catch (error) {
      console.error('Failed to load users:', error);
      setMessage({ type: 'error', text: 'Failed to load users' });
    } finally {
      setUsersLoading(false);
    }
  };

  const loadLogs = async () => {
    setLogsLoading(true);
    try {
      const [logsData, statsData] = await Promise.all([
        adminService.getLogs(logFilters),
        adminService.getLogStats()
      ]);
      setLogs(logsData);
      setLogStats(statsData);
    } catch (error) {
      console.error('Failed to load logs:', error);
      setMessage({ type: 'error', text: 'Failed to load logs' });
    } finally {
      setLogsLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setMessage(null);

    try {
      const result = await adminService.uploadPolicy(file);
      setMessage({ type: 'success', text: `Successfully updated policies: ${JSON.stringify(result.results)}` });
      loadStats();
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to upload policy file. Please try again.' });
    } finally {
      setUploading(false);
    }
  };

  const handleCreateUser = async (formData) => {
    setUserFormLoading(true);
    try {
      await adminService.createUser(formData.username, formData.password, formData.role);
      setMessage({ type: 'success', text: 'User created successfully' });
      setUserModalOpen(false);
      loadUsers();
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to create user' });
    } finally {
      setUserFormLoading(false);
    }
  };

  const handleUpdateUser = async (formData) => {
    setUserFormLoading(true);
    try {
      await adminService.updateUser(editingUser.id, formData);
      setMessage({ type: 'success', text: 'User updated successfully' });
      setUserModalOpen(false);
      setEditingUser(null);
      loadUsers();
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to update user' });
    } finally {
      setUserFormLoading(false);
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!window.confirm('Are you sure you want to delete this user?')) return;
    
    try {
      await adminService.deleteUser(userId);
      setMessage({ type: 'success', text: 'User deleted successfully' });
      loadUsers();
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to delete user' });
    }
  };

  const openEditUser = (user) => {
    setEditingUser(user);
    setUserModalOpen(true);
  };

  // Generate chart data from real stats
  const chartData = [
    { name: 'Restricted Brands', value: stats.total_brands },
    { name: 'Blacklisted Keywords', value: stats.total_keywords },
    { name: 'Prohibited Products', value: stats.total_products }
  ];

  const tabs = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'users', label: 'User Management', icon: Users },
    { id: 'logs', label: 'View Logs', icon: FileText }
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/chat')}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-jumia-orange rounded-xl flex items-center justify-center">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="font-bold text-jumia-dark">Admin Dashboard</h1>
                <p className="text-xs text-gray-500">JUCCA Policy Management</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button 
              onClick={() => {
                loadStats();
                if (activeTab === 'users') loadUsers();
                if (activeTab === 'logs') loadLogs();
              }}
              className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                activeTab === tab.id 
                  ? 'bg-jumia-orange text-white' 
                  : 'bg-white text-gray-600 hover:bg-gray-100'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Message display */}
        {message && (
          <div className={`mb-6 p-4 rounded-lg flex items-center gap-3 ${
            message.type === 'success' ? 'bg-green-50 text-green-700' : 
            message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
          }`}>
            {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : 
             message.type === 'error' ? <AlertTriangle className="w-5 h-5" /> : 
             <ClipboardList className="w-5 h-5" />}
            {message.text}
            <button 
              onClick={() => setMessage(null)}
              className="ml-auto p-1 hover:bg-white/50 rounded"
            >
              <XCircle className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <>
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <StatCard 
                icon={Shield} 
                title="Restricted Brands" 
                value={stats.total_brands} 
                color="bg-jumia-orange"
                subtitle="Brands requiring authorization"
              />
              <StatCard 
                icon={AlertTriangle} 
                title="Blacklisted Keywords" 
                value={stats.total_keywords} 
                color="bg-red-500"
                subtitle="Prohibited terms"
              />
              <StatCard 
                icon={XCircle} 
                title="Prohibited Products" 
                value={stats.total_products} 
                color="bg-yellow-500"
                subtitle="Items not allowed"
              />
            </div>

            {/* Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Policy Distribution Chart */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
                <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-jumia-orange" />
                  Policy Distribution
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#F68B1E" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Policy Upload */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
                <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                  <Upload className="w-5 h-5 text-jumia-orange" />
                  Upload Policy File
                </h3>
                <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-jumia-orange transition-colors">
                  <Database className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-600 mb-2">Drag and drop your policy file here</p>
                  <p className="text-sm text-gray-400 mb-4">Supports .xlsx, .xls, .pdf, .doc, .docx files with sheets: Blacklisted Words, Restricted Brands, Prohibited Categories</p>
                  <label className="inline-flex">
                    <input 
                      type="file" 
                      accept=".xlsx,.xls,.pdf,.doc,.docx"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                    <span className="px-4 py-2 bg-jumia-orange text-white rounded-lg cursor-pointer hover:bg-orange-600 transition-colors">
                      {uploading ? 'Uploading...' : 'Select File'}
                    </span>
                  </label>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 lg:col-span-2">
                <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-jumia-orange" />
                  Quick Actions
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <button 
                    onClick={() => navigate('/chat')}
                    className="p-4 border border-gray-200 rounded-xl hover:border-jumia-orange hover:bg-orange-50 transition-all group"
                  >
                    <BarChart3 className="w-8 h-8 text-gray-400 group-hover:text-jumia-orange mb-2" />
                    <p className="font-medium text-gray-700">Test Compliance</p>
                    <p className="text-sm text-gray-400">Try compliance questions</p>
                  </button>
                  
                  <button 
                    onClick={() => setActiveTab('users')}
                    className="p-4 border border-gray-200 rounded-xl hover:border-jumia-orange hover:bg-orange-50 transition-all group cursor-pointer"
                  >
                    <Users className="w-8 h-8 text-gray-400 group-hover:text-jumia-orange mb-2" />
                    <p className="font-medium text-gray-700">User Management</p>
                    <p className="text-sm text-gray-400">Manage user access</p>
                  </button>
                  
                  <button 
                    onClick={() => setActiveTab('logs')}
                    className="p-4 border border-gray-200 rounded-xl hover:border-jumia-orange hover:bg-orange-50 transition-all group cursor-pointer"
                  >
                    <FileText className="w-8 h-8 text-gray-400 group-hover:text-jumia-orange mb-2" />
                    <p className="font-medium text-gray-700">View Logs</p>
                    <p className="text-sm text-gray-400">Audit trail access</p>
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        {/* User Management Tab */}
        {activeTab === 'users' && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100">
            <div className="p-6 border-b border-gray-100 flex items-center justify-between">
              <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                <Users className="w-5 h-5 text-jumia-orange" />
                User Management
              </h3>
              <button
                onClick={() => {
                  setEditingUser(null);
                  setUserModalOpen(true);
                }}
                className="flex items-center gap-2 px-4 py-2 bg-jumia-orange text-white rounded-lg hover:bg-orange-600"
              >
                <Plus className="w-4 h-4" />
                Add User
              </button>
            </div>
            
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created At</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {usersLoading ? (
                    <tr>
                      <td colSpan="5" className="px-6 py-8 text-center text-gray-500">
                        Loading users...
                      </td>
                    </tr>
                  ) : users.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="px-6 py-8 text-center text-gray-500">
                        No users found
                      </td>
                    </tr>
                  ) : (
                    users.map((user) => (
                      <tr key={user.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{user.id}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-800">{user.username}</td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                            user.role === 'admin' ? 'bg-purple-100 text-purple-800' :
                            user.role === 'legal' ? 'bg-blue-100 text-blue-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {user.role}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => openEditUser(user)}
                              className="p-2 text-gray-400 hover:text-jumia-orange hover:bg-orange-50 rounded-lg transition-colors"
                              title="Edit user"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDeleteUser(user.id)}
                              className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                              title="Delete user"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div className="space-y-6">
            {/* Log Stats */}
            {logStats && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <StatCard 
                  icon={Database} 
                  title="Total Logs" 
                  value={logStats.total} 
                  color="bg-blue-500"
                />
                <StatCard 
                  icon={AlertTriangle} 
                  title="Errors (24h)" 
                  value={logStats.recent_errors_24h} 
                  color="bg-red-500"
                />
                <StatCard 
                  icon={Eye} 
                  title="Info Logs" 
                  value={logStats.by_level?.info || 0} 
                  color="bg-green-500"
                />
                <StatCard 
                  icon={Filter} 
                  title="Warning Logs" 
                  value={logStats.by_level?.warning || 0} 
                  color="bg-yellow-500"
                />
              </div>
            )}

            {/* Logs Table */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100">
              <div className="p-6 border-b border-gray-100 flex items-center justify-between">
                <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-jumia-orange" />
                  System Logs
                </h3>
                <div className="flex items-center gap-3">
                  <select
                    value={logFilters.level}
                    onChange={(e) => setLogFilters({ ...logFilters, level: e.target.value })}
                    className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-jumia-orange outline-none"
                  >
                    <option value="">All Levels</option>
                    <option value="info">Info</option>
                    <option value="warning">Warning</option>
                    <option value="error">Error</option>
                    <option value="critical">Critical</option>
                  </select>
                  <select
                    value={logFilters.category}
                    onChange={(e) => setLogFilters({ ...logFilters, category: e.target.value })}
                    className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-jumia-orange outline-none"
                  >
                    <option value="">All Categories</option>
                    <option value="admin">Admin</option>
                    <option value="auth">Auth</option>
                    <option value="compliance">Compliance</option>
                    <option value="system">System</option>
                  </select>
                  <button
                    onClick={loadLogs}
                    className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                  >
                    <RefreshCw className={`w-4 h-4 ${logsLoading ? 'animate-spin' : ''}`} />
                    Refresh
                  </button>
                </div>
              </div>
              
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Level</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Message</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {logsLoading ? (
                      <tr>
                        <td colSpan="6" className="px-6 py-8 text-center text-gray-500">
                          Loading logs...
                        </td>
                      </tr>
                    ) : logs.length === 0 ? (
                      <tr>
                        <td colSpan="6" className="px-6 py-8 text-center text-gray-500">
                          No logs found
                        </td>
                      </tr>
                    ) : (
                      logs.map((log) => (
                        <tr key={log.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{log.id}</td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                              log.level === 'error' ? 'bg-red-100 text-red-800' :
                              log.level === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                              log.level === 'critical' ? 'bg-purple-100 text-purple-800' :
                              'bg-green-100 text-green-800'
                            }`}>
                              {log.level}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{log.category}</td>
                          <td className="px-6 py-4 text-sm text-gray-700 max-w-md truncate">{log.message}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{log.user_id || '-'}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* User Modal */}
        <UserModal
          isOpen={userModalOpen}
          onClose={() => {
            setUserModalOpen(false);
            setEditingUser(null);
          }}
          onSubmit={editingUser ? handleUpdateUser : handleCreateUser}
          user={editingUser}
          isLoading={userFormLoading}
        />
      </main>
    </div>
  );
}

export default AdminDashboard;
