import { useState, useMemo, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../hooks/redux';
import { addSnippet, updateSnippet, deleteSnippet, fetchSnippets, Snippet } from './snippetsSlice';
import { useDebounce } from '../../hooks/useDebounce';
import { Search, Plus, Trash2, Edit2, Copy, Check, Tag, Code2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';

export function SnippetsPage() {
  const dispatch = useAppDispatch();
  const { snippets, status } = useAppSelector(state => state.snippets);

  const [deleteConfirm, setDeleteConfirm] = useState<{ isOpen: boolean; id: string }>({
    isOpen: false,
    id: '',
  });

  useEffect(() => {
    if (status === 'idle') {
      // @ts-ignore
      dispatch(fetchSnippets());
    }
  }, [status, dispatch]);

  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearch = useDebounce(searchTerm, 300);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSnippet, setEditingSnippet] = useState<Snippet | null>(null);

  const [formData, setFormData] = useState({ title: '', code: '', language: '', tags: '' });
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const allTags = useMemo(() => {
    const tags = new Set<string>();
    snippets.forEach(s => s.tags.forEach(t => tags.add(t)));
    return Array.from(tags).sort();
  }, [snippets]);

  const filteredSnippets = useMemo(() => {
    return snippets.filter(s => {
      const matchesSearch = s.title.toLowerCase().includes(debouncedSearch.toLowerCase()) || 
                            s.code.toLowerCase().includes(debouncedSearch.toLowerCase());
      const matchesTag = selectedTag ? s.tags.includes(selectedTag) : true;
      return matchesSearch && matchesTag;
    });
  }, [snippets, debouncedSearch, selectedTag]);

  const handleOpenModal = (snippet?: Snippet) => {
    if (snippet) {
      setEditingSnippet(snippet);
      setFormData({
        title: snippet.title,
        code: snippet.code,
        language: snippet.language,
        tags: snippet.tags.join(', '),
      });
    } else {
      setEditingSnippet(null);
      setFormData({ title: '', code: '', language: '', tags: '' });
    }
    setIsModalOpen(true);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    const tagsArray = formData.tags.split(',').map(t => t.trim()).filter(Boolean);
    
    if (editingSnippet) {
      // @ts-ignore
      dispatch(updateSnippet({
        ...editingSnippet,
        title: formData.title,
        code: formData.code,
        language: formData.language,
        tags: tagsArray,
      }));
    } else {
      // @ts-ignore
      dispatch(addSnippet({
        title: formData.title,
        code: formData.code,
        language: formData.language,
        tags: tagsArray,
      }));
    }
    setIsModalOpen(false);
  };

  const handleCopy = (id: string, code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Snippet Manager</h1>
          <p className="text-gray-400 mt-1">Store and manage your reusable code snippets.</p>
        </div>
        <button onClick={() => handleOpenModal()} className="btn-primary flex items-center gap-2">
          <Plus className="w-5 h-5" /> Add Snippet
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Search snippets..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="input-field w-full pl-10"
          />
        </div>
        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
          <button
            onClick={() => setSelectedTag(null)}
            className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${!selectedTag ? 'bg-accent text-white' : 'bg-surface text-gray-400 hover:text-white'}`}
          >
            All
          </button>
          {allTags.map(tag => (
            <button
              key={tag}
              onClick={() => setSelectedTag(tag)}
              className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${selectedTag === tag ? 'bg-accent text-white' : 'bg-surface text-gray-400 hover:text-white'}`}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      {/* Snippets Grid */}
      {filteredSnippets.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <Code2 className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No snippets found.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <AnimatePresence>
            {filteredSnippets.map(snippet => (
              <motion.div
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                key={snippet.id}
                className="card p-5 flex flex-col group"
              >
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-white">{snippet.title}</h3>
                    <div className="text-xs text-gray-500 mt-1">{snippet.language || 'Plain text'}</div>
                  </div>
                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => handleCopy(snippet.id, snippet.code)}
                      className="p-2 hover:bg-border rounded text-gray-400 hover:text-white transition-colors"
                      title="Copy to clipboard"
                    >
                      {copiedId === snippet.id ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => handleOpenModal(snippet)}
                      className="p-2 hover:bg-border rounded text-gray-400 hover:text-accent transition-colors"
                      title="Edit snippet"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        setDeleteConfirm({ isOpen: true, id: snippet.id });
                      }}
                      className="p-2 hover:bg-border rounded text-gray-400 hover:text-red-400 transition-colors"
                      title="Delete snippet"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <pre className="bg-background p-4 rounded-lg text-sm text-gray-300 font-mono overflow-x-auto flex-1 border border-border/50">
                  <code>{snippet.code}</code>
                </pre>
                {snippet.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-border/50">
                    {snippet.tags.map(tag => (
                      <span key={tag} className="flex items-center gap-1 text-xs px-2 py-1 bg-surface border border-border rounded text-gray-400">
                        <Tag className="w-3 h-3" /> {tag}
                      </span>
                    ))}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-surface border border-border rounded-xl p-6 w-full max-w-2xl shadow-2xl"
          >
            <h2 className="text-xl font-bold text-white mb-6">
              {editingSnippet ? 'Edit Snippet' : 'New Snippet'}
            </h2>
            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Title</label>
                <input
                  required
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="input-field w-full"
                  placeholder="e.g., Fetch API wrapper"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Language</label>
                  <input
                    type="text"
                    value={formData.language}
                    onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                    className="input-field w-full"
                    placeholder="e.g., TypeScript"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Tags (comma separated)</label>
                  <input
                    type="text"
                    value={formData.tags}
                    onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                    className="input-field w-full"
                    placeholder="e.g., react, hooks, api"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Code</label>
                <textarea
                  required
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                  className="input-field w-full h-64 font-mono text-sm"
                  placeholder="// Paste your code here..."
                />
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Snippet
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}

      {/* Confirm Dialog */}
      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        onClose={() => setDeleteConfirm({ ...deleteConfirm, isOpen: false })}
        onConfirm={() => {
          if (deleteConfirm.id) {
            // @ts-ignore
            dispatch(deleteSnippet(deleteConfirm.id));
            setDeleteConfirm({ isOpen: false, id: '' });
          }
        }}
        title="Delete Snippet"
        message="Are you sure you want to delete this snippet? This action cannot be undone."
        confirmLabel="Delete"
      />
    </div>
  );
}
