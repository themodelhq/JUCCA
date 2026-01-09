import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminService, chatService } from '../services/api';
import { 
  Shield, BarChart3, Upload, Users, FileText, 
  AlertTriangle, CheckCircle, XCircle, ArrowLeft,
  RefreshCw, Database, TrendingUp
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const COLORS = ['#F68B1E', '#22C55E', '#EF4444', '#EAB308'];

function StatCard({ icon: Icon, title, value, subtitle, color }) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
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

function AdminDashboard() {
  const [stats, setStats] = useState({ total_brands: 0, total_keywords: 0, total_products: 0 });
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadStats();
  }, []);

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

  const chartData = [
    { name: 'Restricted Brands', value: stats.total_brands },
    { name: 'Blacklisted Keywords', value: stats.total_keywords },
    { name: 'Prohibited Products', value: stats.total_products }
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
          <button 
            onClick={loadStats}
            className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* Message display */}
        {message && (
          <div className={`mb-6 p-4 rounded-lg flex items-center gap-3 ${
            message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}>
            {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
            {message.text}
          </div>
        )}

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
              <p className="text-gray-600 mb-2">Drag and drop your Excel policy file here</p>
              <p className="text-sm text-gray-400 mb-4">Supports .xlsx files with sheets: Blacklisted Words, Restricted Brands, Prohibited Categories</p>
              <label className="inline-flex">
                <input 
                  type="file" 
                  accept=".xlsx" 
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
              
              <div className="p-4 border border-gray-200 rounded-xl">
                <Users className="w-8 h-8 text-gray-400 mb-2" />
                <p className="font-medium text-gray-700">User Management</p>
                <p className="text-sm text-gray-400">Manage user access</p>
              </div>
              
              <div className="p-4 border border-gray-200 rounded-xl">
                <FileText className="w-8 h-8 text-gray-400 mb-2" />
                <p className="font-medium text-gray-700">View Logs</p>
                <p className="text-sm text-gray-400">Audit trail access</p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default AdminDashboard;
