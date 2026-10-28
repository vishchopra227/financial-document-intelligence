import { useEffect, useState, useRef } from 'react';
import { 
  Building2, 
  FileText, 
  MessageSquare, 
  GitCompare, 
  Settings as SettingsIcon, 
  Layers, 
  AlertCircle, 
  RefreshCw, 
  Database,
  Cpu,
  ShieldCheck,
  UploadCloud,
  Search,
  FileCode,
  FileCheck2,
  ChevronLeft,
  ChevronRight,
  Send,
  Sparkles,
  BookOpen,
  X,
  Clock,
  FileDown
} from 'lucide-react';
import { 
  checkHealth, 
  getSettings, 
  listDocuments, 
  uploadDocument, 
  deleteDocument, 
  getDocumentPreview,
  askQuestion,
  compareDocuments,
  compareMetricsTable,
  downloadComparisonExport,
  type SystemHealth, 
  type SystemSettings, 
  type DocumentListResponse,
  type ChatMessage,
  type Citation,
  type ComparisonResult,
  type MetricComparisonRow
} from './api/client';

type TabType = 'dashboard' | 'documents' | 'workspace' | 'assistant' | 'comparison' | 'settings';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [docData, setDocData] = useState<DocumentListResponse>({ documents: [], total_count: 0, indexed_count: 0 });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date>(new Date());

  // Document Management States
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Workspace States
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewPage, setPreviewPage] = useState<number>(1);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);

  // Chat / RAG States
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [queryInput, setQueryInput] = useState<string>('');
  const [chatLoading, setChatLoading] = useState<boolean>(false);
  const [chatDocFilter, setChatDocFilter] = useState<string>('all');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Cross-document comparison
  const [comparisonDocumentIds, setComparisonDocumentIds] = useState<string[]>([]);
  const [comparisonQuery, setComparisonQuery] = useState('Compare the reported revenue, net income, and reporting periods.');
  const [comparisonResult, setComparisonResult] = useState<ComparisonResult | null>(null);
  const [comparisonMetrics, setComparisonMetrics] = useState<MetricComparisonRow[]>([]);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  const fetchStatusAndDocs = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, settingsRes, docsRes] = await Promise.all([
        checkHealth(),
        getSettings(),
        listDocuments('default', searchQuery)
      ]);
      setHealth(healthRes);
      setSettings(settingsRes);
      setDocData(docsRes);
      setLastChecked(new Date());

      if (selectedDocId) {
        loadDocumentPreview(selectedDocId, previewPage);
      } else if (docsRes.documents.length > 0 && !selectedDocId) {
        setSelectedDocId(docsRes.documents[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Unable to communicate with FinSight backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatusAndDocs();
  }, [searchQuery]);

  useEffect(() => {
    if (activeTab === 'assistant') {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, activeTab]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    setUploadProgress(`Reading, chunking, and indexing ${file.name}...`);

    try {
      await uploadDocument(file);
      setUploadProgress('Document indexed successfully into vector store!');
      setTimeout(() => setUploadProgress(null), 3000);
      await fetchStatusAndDocs();
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload document');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = async (docId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"? All vectors and metadata will be permanently cleaned up.`)) {
      return;
    }

    try {
      await deleteDocument(docId);
      if (selectedDocId === docId) {
        setSelectedDocId(null);
        setPreviewData(null);
      }
      await fetchStatusAndDocs();
    } catch (err: any) {
      alert(`Deletion error: ${err.message}`);
    }
  };

  const loadDocumentPreview = async (docId: string, pageNum: number = 1) => {
    setPreviewLoading(true);
    try {
      const data = await getDocumentPreview(docId, pageNum);
      setPreviewData(data);
      setPreviewPage(pageNum);
      setSelectedDocId(docId);
    } catch (err: any) {
      console.error('Failed to load preview:', err);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSendQuery = async (queryToSend?: string) => {
    const query = (queryToSend || queryInput).trim();
    if (!query || chatLoading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      created_at: new Date().toLocaleTimeString(),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setQueryInput('');
    setChatLoading(true);

    try {
      const docIds = chatDocFilter === 'all' ? undefined : [chatDocFilter];
      const res = await askQuestion(query, docIds, conversationId || undefined);

      if (!conversationId) {
        setConversationId(res.conversation_id);
      }

      const assistantMsg: ChatMessage = {
        id: res.message_id,
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        created_at: new Date().toLocaleTimeString(),
        latency: `Retrieval: ${res.retrieval_latency_ms}ms | Generation: ${res.generation_latency_ms}ms (${res.model_name})`,
      };

      setChatMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Error generating response: ${err.message || 'Backend communication failure.'}`,
        created_at: new Date().toLocaleTimeString(),
      };
      setChatMessages((prev) => [...prev, errorMsg]);
    } finally {
      setChatLoading(false);
    }
  };

  const clearChat = () => {
    setChatMessages([]);
    setConversationId(null);
  };

  const runComparison = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (comparisonDocumentIds.length < 2 || !comparisonQuery.trim() || comparisonLoading) return;
    setComparisonLoading(true);
    setComparisonError(null);
    try {
      const [result, metrics] = await Promise.all([
        compareDocuments(comparisonDocumentIds, comparisonQuery.trim()),
        compareMetricsTable(comparisonDocumentIds),
      ]);
      setComparisonResult(result);
      setComparisonMetrics(metrics.metrics_table);
    } catch (err: any) {
      setComparisonError(err.message || 'Unable to compare the selected documents.');
    } finally {
      setComparisonLoading(false);
    }
  };

  const exportComparison = async (format: 'json' | 'csv') => {
    if (!comparisonResult) return;
    try {
      const blob = await downloadComparisonExport(comparisonDocumentIds, comparisonQuery.trim(), format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `finsight-comparison.${format}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err: any) {
      setComparisonError(err.message || 'Unable to export comparison results.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-800">
      {/* Top Navbar */}
      <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-md">
                <Building2 className="w-6 h-6 text-white" />
              </div>
              <div>
                <span className="font-bold text-lg tracking-tight text-white flex items-center gap-1.5">
                  FinSight <span className="text-blue-400 font-semibold text-sm px-1.5 py-0.5 rounded bg-blue-950/80 border border-blue-800">INTELLIGENCE</span>
                </span>
                <p className="text-xs text-slate-400">Financial Document Intelligence & Advanced RAG</p>
              </div>
            </div>

            {/* System Status Indicator */}
            <div className="flex items-center gap-3">
              {loading ? (
                <div className="flex items-center gap-2 text-xs bg-slate-800 px-3 py-1.5 rounded-full text-slate-300 border border-slate-700">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-400" />
                  <span>Connecting...</span>
                </div>
              ) : error ? (
                <div className="flex items-center gap-2 text-xs bg-rose-950/80 text-rose-300 border border-rose-800 px-3 py-1.5 rounded-full">
                  <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
                  <span>Backend Offline</span>
                  <button onClick={fetchStatusAndDocs} className="ml-1 underline cursor-pointer">Retry</button>
                </div>
              ) : (
                <div className="flex items-center gap-2.5 text-xs bg-slate-800/80 px-3 py-1.5 rounded-full border border-slate-700">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span className="text-slate-200 font-medium">Backend Ready</span>
                  <span className="text-slate-500">|</span>
                  <span className="text-blue-400 uppercase tracking-wider text-[11px] font-semibold">
                    {health?.database.type}
                  </span>
                  <span className="text-slate-500">|</span>
                  <span className="text-indigo-300 text-[11px] font-medium">
                    {health?.ai_providers.llm_provider.toUpperCase()}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex space-x-1 border-t border-slate-800/80 pt-1 -mb-px overflow-x-auto">
            {[
              { id: 'dashboard', label: 'Dashboard', icon: Layers },
              { id: 'documents', label: 'Document Library', icon: FileText, badge: docData.total_count },
              { id: 'workspace', label: 'Document Workspace', icon: Building2 },
              { id: 'assistant', label: 'AI Research Assistant', icon: MessageSquare },
              { id: 'comparison', label: 'Cross-Doc Analysis', icon: GitCompare },
              { id: 'settings', label: 'Settings', icon: SettingsIcon },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors cursor-pointer whitespace-nowrap ${
                    isActive
                      ? 'border-blue-400 text-blue-400 bg-slate-800/40'
                      : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                  {tab.badge !== undefined && tab.badge > 0 && (
                    <span className="ml-1 px-1.5 py-0.2 bg-slate-700 text-slate-300 rounded-full text-[10px]">
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileUpload} 
          accept=".pdf,.txt,.docx" 
          className="hidden" 
        />

        {/* ================= TAB 1: DASHBOARD ================= */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-slate-900">
                  Financial Intelligence Dashboard
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                  Upload SEC filings, 10-K/10-Q reports, earnings releases, and inspect grounded AI insights with verifiable citations.
                </p>
              </div>
              <div className="flex gap-3">
                <button 
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                >
                  <UploadCloud className="w-4 h-4" />
                  {uploading ? 'Indexing...' : 'Upload Document'}
                </button>
                <button 
                  onClick={() => setActiveTab('assistant')}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-medium shadow-xs transition-colors cursor-pointer"
                >
                  <MessageSquare className="w-4 h-4" />
                  Ask AI Assistant
                </button>
              </div>
            </div>

            {uploadProgress && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-800 flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-blue-600 animate-spin" />
                <span>{uploadProgress}</span>
              </div>
            )}
            {uploadError && (
              <div className="bg-rose-50 border border-rose-200 rounded-lg p-3 text-xs text-rose-800 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600" />
                <span>{uploadError}</span>
              </div>
            )}

            {/* Metrics Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase">Total Documents</span>
                  <FileText className="w-5 h-5 text-blue-600" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-slate-900">{docData.total_count}</span>
                  <span className="text-xs text-slate-500">files</span>
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase">Indexed Documents</span>
                  <FileCheck2 className="w-5 h-5 text-emerald-600" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-slate-900">{docData.indexed_count}</span>
                  <span className="text-xs text-emerald-600 font-medium">ready for RAG</span>
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase">Database Engine</span>
                  <Database className="w-5 h-5 text-indigo-600" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-xl font-bold text-slate-900 uppercase">{health?.database.type || 'N/A'}</span>
                  <span className="text-xs text-slate-500">{health?.database.status}</span>
                </div>
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase">LLM & Vector Engine</span>
                  <Cpu className="w-5 h-5 text-purple-600" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-base font-bold text-slate-900 truncate">{health?.ai_providers.llm_provider}</span>
                  <span className="text-xs text-slate-500 font-mono">Hybrid RRF</span>
                </div>
              </div>
            </div>

            {/* Recent Activity Table */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="p-5 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-slate-900">Recent Document Activity</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Documents indexed and available for semantic search</p>
                </div>
                <button 
                  onClick={() => setActiveTab('documents')}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium cursor-pointer"
                >
                  View All ({docData.total_count}) →
                </button>
              </div>

              {docData.documents.length === 0 ? (
                <div className="p-8 text-center">
                  <FileCode className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-700">No documents indexed yet</p>
                  <p className="text-xs text-slate-400 mt-1 mb-4">Upload a 10-K, 10-Q or financial document to get started.</p>
                  <button 
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium cursor-pointer"
                  >
                    <UploadCloud className="w-3.5 h-3.5" />
                    Upload Financial Report
                  </button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider text-[11px] border-b border-slate-200">
                      <tr>
                        <th className="px-5 py-3">Document Name</th>
                        <th className="px-5 py-3">Format</th>
                        <th className="px-5 py-3">Pages</th>
                        <th className="px-5 py-3">Chunks</th>
                        <th className="px-5 py-3">Status</th>
                        <th className="px-5 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      {docData.documents.slice(0, 5).map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                          <td className="px-5 py-3.5 font-medium text-slate-900 flex items-center gap-2">
                            <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                            <span className="truncate max-w-[280px]">{doc.original_filename}</span>
                          </td>
                          <td className="px-5 py-3.5 uppercase font-semibold text-slate-500">{doc.file_type}</td>
                          <td className="px-5 py-3.5">{doc.page_count}</td>
                          <td className="px-5 py-3.5 font-mono">{doc.chunk_count}</td>
                          <td className="px-5 py-3.5">
                            <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100 text-emerald-800">
                              {doc.status}
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-right space-x-2">
                            <button
                              onClick={() => {
                                setChatDocFilter(doc.id);
                                setActiveTab('assistant');
                              }}
                              className="text-blue-600 hover:text-blue-800 font-medium cursor-pointer"
                            >
                              Query
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ================= TAB 2: DOCUMENT LIBRARY ================= */}
        {activeTab === 'documents' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-slate-900">Document Library</h1>
                <p className="text-sm text-slate-500 mt-0.5">
                  Manage indexed financial filings, check extraction progress, and preview source pages.
                </p>
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-xs transition-colors cursor-pointer self-start sm:self-auto disabled:opacity-50"
              >
                <UploadCloud className="w-4 h-4" />
                {uploading ? 'Processing File...' : 'Upload Document'}
              </button>
            </div>

            {/* Drag & Drop Upload Zone */}
            <div 
              onClick={() => fileInputRef.current?.click()}
              className="p-8 border-2 border-dashed border-slate-300 rounded-xl text-center bg-white hover:border-blue-500 hover:bg-blue-50/20 transition-all cursor-pointer"
            >
              <UploadCloud className="w-10 h-10 text-blue-500 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-800">Click to upload or drag and drop financial documents</p>
              <p className="text-xs text-slate-400 mt-1">Supports PDF (with page preservation), TXT, and DOCX up to {settings?.max_upload_size_mb || 30}MB</p>
              {uploadProgress && (
                <div className="mt-4 inline-flex items-center gap-2 text-xs font-medium text-blue-700 bg-blue-100 px-3 py-1 rounded-full">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  {uploadProgress}
                </div>
              )}
              {uploadError && (
                <div className="mt-4 inline-flex items-center gap-2 text-xs font-medium text-rose-700 bg-rose-100 px-3 py-1 rounded-full">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {uploadError}
                </div>
              )}
            </div>

            {/* Filter Bar */}
            <div className="flex items-center justify-between gap-4">
              <div className="relative max-w-sm w-full">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search documents by name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-xs bg-white border border-slate-200 rounded-lg text-slate-800 focus:outline-hidden focus:border-blue-500"
                />
              </div>
              <span className="text-xs text-slate-500 font-medium">
                {docData.total_count} documents ({docData.indexed_count} indexed)
              </span>
            </div>

            {/* Library Table */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
              {docData.documents.length === 0 ? (
                <div className="p-12 text-center">
                  <FileText className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-700">No documents found</p>
                  <p className="text-xs text-slate-400 mt-1">Upload files to begin indexing.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider text-[11px] border-b border-slate-200">
                      <tr>
                        <th className="px-5 py-3">File Name</th>
                        <th className="px-5 py-3">Type</th>
                        <th className="px-5 py-3">Size</th>
                        <th className="px-5 py-3">Pages</th>
                        <th className="px-5 py-3">Chunks</th>
                        <th className="px-5 py-3">Status</th>
                        <th className="px-5 py-3">Uploaded</th>
                        <th className="px-5 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      {docData.documents.map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                          <td className="px-5 py-3.5 font-medium text-slate-900 flex items-center gap-2">
                            <FileText className="w-4 h-4 text-blue-600 shrink-0" />
                            <span className="truncate max-w-[280px]">{doc.original_filename}</span>
                          </td>
                          <td className="px-5 py-3.5 uppercase font-semibold text-slate-500">{doc.file_type}</td>
                          <td className="px-5 py-3.5 text-slate-500">{(doc.file_size_bytes / 1024).toFixed(1)} KB</td>
                          <td className="px-5 py-3.5">{doc.page_count}</td>
                          <td className="px-5 py-3.5 font-mono text-blue-600 font-semibold">{doc.chunk_count}</td>
                          <td className="px-5 py-3.5">
                            <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100 text-emerald-800">
                              {doc.status}
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-slate-400">
                            {new Date(doc.created_at).toLocaleDateString()}
                          </td>
                          <td className="px-5 py-3.5 text-right space-x-3">
                            <button
                              onClick={() => {
                                setSelectedDocId(doc.id);
                                loadDocumentPreview(doc.id, 1);
                                setActiveTab('workspace');
                              }}
                              className="text-blue-600 hover:text-blue-800 font-medium cursor-pointer"
                            >
                              Preview
                            </button>
                            <button
                              onClick={() => {
                                setChatDocFilter(doc.id);
                                setActiveTab('assistant');
                              }}
                              className="text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer"
                            >
                              Chat
                            </button>
                            <button
                              onClick={() => handleDelete(doc.id, doc.original_filename)}
                              className="text-rose-600 hover:text-rose-800 font-medium cursor-pointer"
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ================= TAB 3: DOCUMENT WORKSPACE ================= */}
        {activeTab === 'workspace' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-slate-900">Document Workspace</h1>
                <p className="text-sm text-slate-500 mt-0.5">
                  Inspect page-by-page extracted text, verify page numbers, and examine source context.
                </p>
              </div>

              {docData.documents.length > 0 && (
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500">Select Document:</span>
                  <select
                    value={selectedDocId || ''}
                    onChange={(e) => loadDocumentPreview(e.target.value, 1)}
                    className="text-xs bg-white border border-slate-200 rounded-lg px-3 py-2 text-slate-800 font-medium focus:outline-hidden focus:border-blue-500"
                  >
                    {docData.documents.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.original_filename} ({d.page_count} pages, {d.chunk_count} chunks)
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {previewLoading ? (
              <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
                <RefreshCw className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-700">Loading document pages...</p>
              </div>
            ) : previewData ? (
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4 h-fit">
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-blue-600" />
                    Document Metadata
                  </h3>
                  <div className="text-xs text-slate-600 space-y-2 border-t border-slate-100 pt-3">
                    <div>
                      <span className="text-slate-400 block">Filename:</span>
                      <span className="font-semibold text-slate-800 break-all">{previewData.filename}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block">Total Pages:</span>
                      <span className="font-semibold text-slate-800">{previewData.total_pages}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block">Current Page:</span>
                      <span className="font-semibold text-slate-800">Page {previewPage} of {previewData.total_pages}</span>
                    </div>
                    {previewData.page && (
                      <div>
                        <span className="text-slate-400 block">Characters on Page:</span>
                        <span className="font-semibold text-slate-800">{previewData.page.char_count} chars</span>
                      </div>
                    )}
                  </div>

                  <div className="pt-3 border-t border-slate-100">
                    <button
                      onClick={() => {
                        setChatDocFilter(selectedDocId!);
                        setActiveTab('assistant');
                      }}
                      className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-medium cursor-pointer transition-colors"
                    >
                      <MessageSquare className="w-3.5 h-3.5" />
                      Chat About This Doc
                    </button>
                  </div>
                </div>

                <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 flex flex-col shadow-xs">
                  <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 rounded-t-xl">
                    <span className="text-xs font-semibold text-slate-700">
                      Page {previewPage} / {previewData.total_pages}
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        disabled={previewPage <= 1}
                        onClick={() => loadDocumentPreview(selectedDocId!, previewPage - 1)}
                        className="p-1 rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-100 disabled:opacity-40 cursor-pointer"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <button
                        disabled={previewPage >= previewData.total_pages}
                        onClick={() => loadDocumentPreview(selectedDocId!, previewPage + 1)}
                        className="p-1 rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-100 disabled:opacity-40 cursor-pointer"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="p-6 font-mono text-xs text-slate-800 bg-slate-900/5 rounded-b-xl overflow-y-auto max-h-[600px] whitespace-pre-wrap leading-relaxed select-text">
                    {previewData.page?.text || (
                      <span className="text-slate-400 italic">No text extracted on this page.</span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
                <Building2 className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-700">No document selected</p>
                <p className="text-xs text-slate-400 mt-1">Select an uploaded document above to inspect its pages.</p>
              </div>
            )}
          </div>
        )}

        {/* ================= TAB 4: AI RESEARCH ASSISTANT (PHASE 4 RAG) ================= */}
        {activeTab === 'assistant' && (
          <div className="space-y-4">
            {/* Header / Filter Toolbar */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-slate-900">AI Research Assistant</h2>
                  <p className="text-xs text-slate-500">Answers are strictly grounded in retrieved evidence with verifiable page citations.</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500 font-medium">Scope:</span>
                <select
                  value={chatDocFilter}
                  onChange={(e) => setChatDocFilter(e.target.value)}
                  className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-800 font-medium focus:outline-hidden focus:border-blue-500"
                >
                  <option value="all">All Documents ({docData.total_count})</option>
                  {docData.documents.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.original_filename}
                    </option>
                  ))}
                </select>

                {chatMessages.length > 0 && (
                  <button
                    onClick={clearChat}
                    className="text-xs px-2.5 py-1.5 text-slate-600 hover:text-slate-900 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors cursor-pointer"
                  >
                    Clear Chat
                  </button>
                )}
              </div>
            </div>

            {/* Chat Thread Container */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col h-[560px]">
              {/* Message List */}
              <div className="flex-1 p-6 overflow-y-auto space-y-6">
                {chatMessages.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-6">
                    <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mb-3">
                      <MessageSquare className="w-6 h-6" />
                    </div>
                    <h3 className="text-base font-bold text-slate-900">What would you like to analyze?</h3>
                    <p className="text-xs text-slate-500 max-w-md mt-1 mb-6">
                      Ask questions about reported revenue, operational risks, margins, or balance sheet figures.
                    </p>

                    {/* Pre-canned Financial Queries */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-lg w-full text-left">
                      {[
                        "What were the major sources of revenue and sales growth?",
                        "What key risks or uncertainties did the company disclose?",
                        "Summarize operating performance and net margins.",
                        "What are the reported debt levels and cash balances?",
                      ].map((prompt, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleSendQuery(prompt)}
                          disabled={docData.total_count === 0}
                          className="p-3 text-xs bg-slate-50 hover:bg-blue-50/70 border border-slate-200 hover:border-blue-300 rounded-lg text-slate-700 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          "{prompt}"
                        </button>
                      ))}
                    </div>

                    {docData.total_count === 0 && (
                      <p className="text-xs text-amber-600 mt-4 bg-amber-50 px-3 py-1.5 rounded-md border border-amber-200">
                        Please upload financial documents in the Document Library before asking questions.
                      </p>
                    )}
                  </div>
                ) : (
                  chatMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                    >
                      <div
                        className={`max-w-3xl rounded-xl p-4 text-xs sm:text-sm leading-relaxed ${
                          msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-br-none shadow-xs'
                            : 'bg-slate-50 text-slate-800 border border-slate-200 rounded-bl-none shadow-xs'
                        }`}
                      >
                        {/* Message Header */}
                        <div className="flex items-center justify-between gap-4 mb-1.5 text-[11px] opacity-75">
                          <span className="font-semibold uppercase tracking-wider">
                            {msg.role === 'user' ? 'You' : 'FinSight Assistant'}
                          </span>
                          {msg.created_at && <span>{msg.created_at}</span>}
                        </div>

                        {/* Message Content */}
                        <div className="whitespace-pre-wrap">{msg.content}</div>

                        {/* Citations Grid (For Assistant Messages) */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-4 pt-3 border-t border-slate-200/60">
                            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block mb-2">
                              Supporting Source Citations ({msg.citations.length}):
                            </span>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {msg.citations.map((c, i) => (
                                <div
                                  key={i}
                                  onClick={() => setSelectedCitation(c)}
                                  className="p-2.5 rounded-lg border border-slate-200 bg-white hover:border-blue-400 hover:shadow-xs transition-all cursor-pointer text-left"
                                >
                                  <div className="flex items-center justify-between text-[11px] font-semibold text-blue-600">
                                    <span className="flex items-center gap-1">
                                      <BookOpen className="w-3.5 h-3.5" />
                                      Page {c.page_number || 'N/A'}
                                    </span>
                                    {c.similarity_score !== undefined && (
                                      <span className="text-slate-400 font-mono text-[10px]">
                                        Score: {c.similarity_score}
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-[11px] text-slate-500 truncate mt-0.5">{c.filename}</p>
                                  <p className="text-[11px] text-slate-700 italic line-clamp-2 mt-1 font-mono bg-slate-50 p-1 rounded">
                                    "{c.excerpt}"
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Observability Latency Badge */}
                        {msg.latency && (
                          <div className="mt-3 pt-2 text-[10px] text-slate-400 flex items-center gap-1 font-mono">
                            <Clock className="w-3 h-3" />
                            <span>{msg.latency}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}

                {chatLoading && (
                  <div className="flex items-start gap-2 text-xs text-slate-500 bg-slate-50 p-3.5 rounded-xl border border-slate-200 max-w-sm animate-pulse">
                    <RefreshCw className="w-4 h-4 text-blue-600 animate-spin shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-slate-800">Retrieving & Synthesizing...</p>
                      <p className="text-[11px] text-slate-500">Searching vector index and evaluating evidence.</p>
                    </div>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>

              {/* Chat Input Bar */}
              <div className="p-4 border-t border-slate-100 bg-white rounded-b-xl">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendQuery();
                  }}
                  className="flex items-center gap-2"
                >
                  <input
                    type="text"
                    value={queryInput}
                    onChange={(e) => setQueryInput(e.target.value)}
                    placeholder={
                      docData.total_count === 0
                        ? "Upload a financial document first to enable Q&A..."
                        : "Ask a grounded financial question (e.g., 'What was the reported revenue?')..."
                    }
                    disabled={chatLoading || docData.total_count === 0}
                    className="flex-1 px-4 py-2.5 text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-lg text-slate-800 focus:outline-hidden focus:border-blue-500 focus:bg-white transition-all disabled:opacity-50"
                  />
                  <button
                    type="submit"
                    disabled={!queryInput.trim() || chatLoading || docData.total_count === 0}
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs sm:text-sm font-medium shadow-xs transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Send className="w-4 h-4" />
                    <span>Send</span>
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* ================= TAB 5: CROSS-DOCUMENT ANALYSIS ================= */}
        {activeTab === 'comparison' && (
          <div className="space-y-6">
            <section className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Cross-Document Analysis</h2>
                <p className="text-sm text-slate-500 mt-1">Select indexed reports to compare evidence and extracted metrics across their reporting periods.</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {docData.documents.filter((doc) => doc.status === 'indexed').map((doc) => (
                  <label key={doc.id} className="flex items-start gap-3 rounded-lg border border-slate-200 p-3 text-sm cursor-pointer hover:bg-slate-50">
                    <input
                      type="checkbox"
                      checked={comparisonDocumentIds.includes(doc.id)}
                      onChange={(event) => setComparisonDocumentIds((current) =>
                        event.target.checked
                          ? [...current, doc.id]
                          : current.filter((id) => id !== doc.id)
                      )}
                      onClick={() => {
                        setComparisonResult(null);
                        setComparisonMetrics([]);
                        setComparisonError(null);
                      }}
                      className="mt-1 accent-indigo-600"
                    />
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-slate-800">{doc.original_filename}</span>
                      <span className="block text-xs text-slate-500">
                        {doc.company_name || 'Company not identified'}{doc.reporting_period ? ` · ${doc.reporting_period}` : ''}
                      </span>
                    </span>
                  </label>
                ))}
                {docData.documents.filter((doc) => doc.status === 'indexed').length === 0 && (
                  <p className="text-sm text-slate-500">Upload and index at least two documents to compare them.</p>
                )}
              </div>
              <form onSubmit={runComparison} className="space-y-3">
                <label htmlFor="comparison-query" className="block text-xs font-semibold text-slate-700">Comparison question</label>
                <textarea
                  id="comparison-query"
                  value={comparisonQuery}
                  onChange={(event) => {
                    setComparisonQuery(event.target.value);
                    setComparisonResult(null);
                    setComparisonMetrics([]);
                    setComparisonError(null);
                  }}
                  rows={3}
                  maxLength={2000}
                  className="w-full rounded-lg border border-slate-200 p-3 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none"
                />
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="submit"
                    disabled={comparisonDocumentIds.length < 2 || comparisonLoading}
                    className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {comparisonLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <GitCompare className="h-4 w-4" />}
                    {comparisonLoading ? 'Comparing...' : `Compare ${comparisonDocumentIds.length} documents`}
                  </button>
                  {comparisonResult && (
                    <>
                      <button type="button" onClick={() => exportComparison('csv')} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                        <FileDown className="h-4 w-4" /> CSV
                      </button>
                      <button type="button" onClick={() => exportComparison('json')} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                        <FileDown className="h-4 w-4" /> JSON
                      </button>
                    </>
                  )}
                  <span className="text-xs text-slate-500">Metric rows retain each source period, unit, currency, page and excerpt.</span>
                </div>
              </form>
              {comparisonError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{comparisonError}</p>}
            </section>

            {comparisonResult && (
              <>
                <section className="rounded-xl border border-slate-200 bg-white p-6 space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="font-bold text-slate-900">Grounded comparison</h3>
                      <p className="mt-1 text-xs text-slate-500">Model: {comparisonResult.model_name}</p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${comparisonResult.has_sufficient_evidence ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                      {comparisonResult.has_sufficient_evidence ? 'Evidence retrieved' : 'Insufficient evidence'}
                    </span>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {comparisonResult.documents.map((doc) => (
                      <div key={doc.document_id} className="rounded-lg bg-slate-50 p-3">
                        <p className="text-sm font-semibold text-slate-800">{doc.filename}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {[doc.company_name, doc.reporting_period, `${doc.page_count} pages`].filter(Boolean).join(' · ')}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">Evidence pages: {doc.pages_cited.length ? doc.pages_cited.join(', ') : 'None retrieved'}</p>
                      </div>
                    ))}
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">{comparisonResult.analysis}</p>
                  <div className="border-t border-slate-100 pt-4">
                    <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Source citations</h4>
                    {comparisonResult.citations.length ? (
                      <div className="flex flex-wrap gap-2">
                        {comparisonResult.citations.map((citation, index) => (
                          <button key={`${citation.chunk_id}-${index}`} onClick={() => setSelectedCitation(citation)} className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-left text-xs text-blue-800 hover:bg-blue-100">
                            {citation.filename} · Page {citation.page_number ?? 'unknown'}
                          </button>
                        ))}
                      </div>
                    ) : <p className="text-xs text-slate-500">No source passages were retrieved.</p>}
                  </div>
                </section>

                <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                  <div className="border-b border-slate-100 p-5">
                    <h3 className="font-bold text-slate-900">Extracted financial metrics</h3>
                    <p className="mt-1 text-xs text-slate-500">Rows are separated by reported period; missing values remain blank rather than inferred.</p>
                  </div>
                  {comparisonMetrics.length === 0 ? (
                    <p className="p-5 text-sm text-slate-500">No extractable metrics were found in the selected documents.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[760px] text-left text-xs">
                        <thead className="bg-slate-50 text-slate-500">
                          <tr>
                            <th className="p-3">Metric / Period</th>
                            {comparisonDocumentIds.map((id) => <th key={id} className="p-3">{docData.documents.find((doc) => doc.id === id)?.original_filename || id}</th>)}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {comparisonMetrics.map((row, index) => (
                            <tr key={`${row.metric_name}-${row.reporting_period}-${index}`} className="align-top">
                              <td className="p-3 font-semibold text-slate-800">{row.metric_name}<span className="block mt-1 font-normal text-slate-500">{row.reporting_period || 'Period not identified'}</span></td>
                              {comparisonDocumentIds.map((id) => {
                                const value = row.values[id];
                                return (
                                  <td key={id} className="max-w-sm p-3 text-slate-700">
                                    {value?.evidence.length ? value.evidence.map((evidence, evidenceIndex) => (
                                      <div key={`${evidence.page_number}-${evidenceIndex}`} className="mb-2 last:mb-0">
                                        <p className="font-semibold">{evidence.raw_value}{evidence.currency ? ` ${evidence.currency}` : ''}{evidence.unit ? ` · ${evidence.unit}` : ''}</p>
                                        <p className="mt-0.5 text-slate-500">Page {evidence.page_number ?? 'unknown'}{evidence.period ? ` · ${evidence.period}` : ''}</p>
                                        {evidence.source_excerpt && <p className="mt-1 text-slate-500">{evidence.source_excerpt}</p>}
                                      </div>
                                    )) : <span className="text-slate-400">Not reported</span>}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </>
            )}
          </div>
        )}

        {/* ================= TAB 6: SETTINGS ================= */}
        {activeTab === 'settings' && (
          <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-6">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Platform Configuration</h2>
              <p className="text-sm text-slate-500 mt-1">
                Inspect active AI models, vector storage, and security settings.
              </p>
            </div>

            {settings && (
              <div className="space-y-4 max-w-3xl">
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 space-y-2 text-sm">
                  <div className="flex justify-between py-1 border-b border-slate-200">
                    <span className="text-slate-600">Application:</span>
                    <span className="font-semibold text-slate-900">{settings.project_name}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-200">
                    <span className="text-slate-600">Environment:</span>
                    <span className="font-semibold text-slate-900">{settings.environment}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-200">
                    <span className="text-slate-600">Vector Store Backend:</span>
                    <span className="font-semibold text-slate-900">{settings.vector_store_backend}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-200">
                    <span className="text-slate-600">LLM Provider:</span>
                    <span className="font-semibold text-slate-900">{settings.providers.llm.name}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-200">
                    <span className="text-slate-600">Active Model:</span>
                    <span className="font-semibold text-slate-900 font-mono text-xs">{settings.providers.llm.model}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-slate-600">Embedding Engine:</span>
                    <span className="font-semibold text-slate-900">{settings.providers.embedding.name}</span>
                  </div>
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-xs text-blue-900 flex items-start gap-2.5">
                  <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold">Security & Credentials Isolation</p>
                    <p className="mt-0.5 text-blue-800">{settings.security_note}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Citation Inspection Modal */}
      {selectedCitation && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-xl w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2 text-blue-600 font-bold text-sm">
                <BookOpen className="w-4 h-4" />
                <span>Citation Evidence Inspector</span>
              </div>
              <button
                onClick={() => setSelectedCitation(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs space-y-2 bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div className="flex justify-between">
                <span className="text-slate-500">Source Document:</span>
                <span className="font-semibold text-slate-800">{selectedCitation.filename}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Page Number:</span>
                <span className="font-semibold text-slate-800">Page {selectedCitation.page_number}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Chunk Identifier:</span>
                <span className="font-mono text-slate-600 text-[10px]">{selectedCitation.chunk_id}</span>
              </div>
              {selectedCitation.similarity_score !== undefined && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Cosine Similarity:</span>
                  <span className="font-mono text-blue-600 font-semibold">{selectedCitation.similarity_score}</span>
                </div>
              )}
            </div>

            <div>
              <span className="text-xs font-bold text-slate-700 block mb-1">Verifiable Excerpt:</span>
              <div className="p-4 bg-slate-900/5 font-mono text-xs text-slate-800 rounded-lg max-h-60 overflow-y-auto whitespace-pre-wrap leading-relaxed select-text border border-slate-200">
                {selectedCitation.excerpt}
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedCitation(null)}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-medium cursor-pointer"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
          <p>© 2026 FinSight Intelligence. Financial Document Intelligence Platform.</p>
          <div className="flex items-center gap-4">
            <span>Grounding: Strictly Cited</span>
            <span>•</span>
            <span>Vector Engine: Persistent Index</span>
            <span>•</span>
            <button onClick={fetchStatusAndDocs} className="text-blue-600 hover:underline cursor-pointer">
              Refresh Diagnostics ({lastChecked.toLocaleTimeString()})
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
