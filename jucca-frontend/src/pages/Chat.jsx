import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { chatService } from '../services/api';
import { 
  Send, User, Shield, Settings, LogOut, 
  AlertTriangle, CheckCircle, XCircle, HelpCircle,
  Bot, Menu, X, ChevronDown
} from 'lucide-react';

const statusConfig = {
  'Allowed': { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' },
  'Restricted': { icon: AlertTriangle, color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' },
  'Prohibited': { icon: XCircle, color: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200' },
  'Blocked': { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' }
};

function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const status = message.status || 'Allowed';
  const config = statusConfig[status] || statusConfig.Allowed;
  const StatusIcon = config.icon;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 w-full`}>
      <div className={`max-w-[80%] ${isUser ? 'order-2' : 'order-1'}`}>
        {/* Message bubble */}
        <div className={`rounded-2xl px-4 py-3 ${
          isUser 
            ? 'bg-jumia-orange text-white rounded-br-md' 
            : 'bg-white border border-gray-200 rounded-bl-md shadow-sm'
        }`}>
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.text}</p>
          ) : (
            <div>
              {/* Status badge for bot messages */}
              {message.status && (
                <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium mb-2 ${config.bg} ${config.color} ${config.border} border`}>
                  <StatusIcon className="w-4 h-4" />
                  {status}
                </div>
              )}
              <p className="whitespace-pre-wrap text-gray-700">{message.text}</p>
            </div>
          )}
        </div>
        
        {/* Timestamp */}
        <div className={`text-xs text-gray-400 mt-1 ${isUser ? 'text-right' : 'text-left'}`}>
          {message.time || ''}
        </div>
      </div>
    </div>
  );
}

function Chat() {
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: "Hello! I'm JUCCA, your compliance assistant. You can ask me questions like:\n\n• 'Can I sell Nike shoes in Nigeria?'\n• 'What brands require authorization?'\n• 'Can I list used electronics?'\n\nHow can I help you today?",
      status: null,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const navigate = useNavigate();
  const userRole = localStorage.getItem('role') || 'seller';
  const sessionId = useRef(`session_${Date.now()}`);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleScroll = () => {
    if (messagesContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
      const scrollPercentage = (scrollTop / (scrollHeight - clientHeight)) * 100;
      setShowScrollButton(scrollPercentage < 95 && scrollPercentage > 0);
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    handleScroll();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      role: 'user',
      text: input.trim(),
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await chatService.ask(
        userMessage.text, 
        sessionId.current, 
        userRole
      );

      const botMessage = {
        role: 'bot',
        text: response.answer,
        status: response.decision,
        reason: response.reason,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      const errorMessage = {
        role: 'bot',
        text: "I'm sorry, I encountered an error processing your request. Please try again.",
        status: 'Blocked',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-xl transform transition-transform duration-300 lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-jumia-orange rounded-xl flex items-center justify-center">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="font-bold text-jumia-dark">JUCCA</h1>
                <p className="text-xs text-gray-500">Compliance Assistant</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-2">
            <button className="w-full flex items-center gap-3 px-4 py-3 bg-jumia-orange/10 text-jumia-orange rounded-xl font-medium">
              <Bot className="w-5 h-5" />
              Chat
            </button>
            
            {(userRole === 'admin' || userRole === 'legal') && (
              <button 
                onClick={() => navigate('/admin')}
                className="w-full flex items-center gap-3 px-4 py-3 text-gray-600 hover:bg-gray-100 rounded-xl transition-colors"
              >
                <Settings className="w-5 h-5" />
                Admin Dashboard
              </button>
            )}
          </nav>

          {/* User Info & Logout */}
          <div className="p-4 border-t border-gray-100">
            <div className="flex items-center gap-3 mb-4 px-2">
              <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center">
                <User className="w-5 h-5 text-gray-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-700 truncate">Seller Account</p>
                <p className="text-xs text-gray-400 capitalize">{userRole}</p>
              </div>
            </div>
            <button 
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-red-50 hover:text-red-600 rounded-lg transition-colors text-sm"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </div>
        </div>
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col lg:ml-0 min-h-screen h-screen">
        {/* Mobile Header */}
        <header className="lg:hidden bg-white shadow-sm px-4 py-3 flex items-center gap-3 flex-shrink-0">
          <button 
            onClick={() => setSidebarOpen(true)}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-jumia-orange rounded-lg flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-jumia-dark">JUCCA</span>
          </div>
        </header>

        {/* Chat Area - Full height with fixed input */}
        <div className="flex-1 flex flex-col w-full h-full relative">
          {/* Scroll to bottom button */}
          {showScrollButton && (
            <button
              onClick={scrollToBottom}
              className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-jumia-orange text-white px-4 py-2 rounded-full shadow-lg flex items-center gap-2 hover:bg-orange-600 transition-colors"
            >
              <ChevronDown className="w-4 h-4" />
              Scroll to bottom
            </button>
          )}

          {/* Messages - Scrollable area */}
          <div 
            ref={messagesContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-4 space-y-4 pb-32"
          >
            {messages.map((message, index) => (
              <ChatMessage key={index} message={message} />
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-2 text-gray-500">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area - Fixed at bottom */}
          <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4">
            <div className="max-w-3xl mx-auto">
              <div className="flex gap-3 items-end">
                <div className="flex-1 relative">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Ask a compliance question..."
                    className="w-full px-4 py-3 pr-12 border border-gray-200 rounded-xl focus:ring-2 focus:ring-jumia-orange focus:border-transparent outline-none transition-all"
                    disabled={loading}
                  />
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || loading}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-jumia-orange text-white rounded-lg hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
              
              {/* Quick suggestions */}
              <div className="flex flex-wrap gap-2 mt-3">
                <button 
                  onClick={() => setInput("Can I sell Nike shoes?")}
                  className="px-3 py-1.5 text-sm bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200 transition-colors"
                >
                  Nike shoes?
                </button>
                <button 
                  onClick={() => setInput("What about used electronics?")}
                  className="px-3 py-1.5 text-sm bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200 transition-colors"
                >
                  Used electronics?
                </button>
                <button 
                  onClick={() => setInput("Can I list fake products?")}
                  className="px-3 py-1.5 text-sm bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200 transition-colors"
                >
                  Fake products?
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Chat;
