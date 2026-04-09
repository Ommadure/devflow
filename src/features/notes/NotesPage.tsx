import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../hooks/redux';
import { addNote, updateNote, deleteNote, setActiveNote, fetchNotes, Note } from './notesSlice';
import { useDebounce } from '../../hooks/useDebounce';
import { Plus, Trash2, Edit3, Eye, FileText, Search } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DOMPurify from 'dompurify';
import { format } from 'date-fns';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';

export function NotesPage() {
  const dispatch = useAppDispatch();
  const { notes, activeNoteId, status } = useAppSelector(state => state.notes);
  
  const [searchTerm, setSearchTerm] = useState('');
  const [isPreview, setIsPreview] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<{ isOpen: boolean; id: string }>({
    isOpen: false,
    id: '',
  });

  useEffect(() => {
    if (status === 'idle') {
      // @ts-ignore - thunk typing issue
      dispatch(fetchNotes());
    }
  }, [status, dispatch]);

  const activeNote = notes.find(n => n.id === activeNoteId) || null;
  const [localTitle, setLocalTitle] = useState('');
  const [localContent, setLocalContent] = useState('');

  // Sync local state when active note changes
  useEffect(() => {
    if (activeNote) {
      setLocalTitle(activeNote.title);
      setLocalContent(activeNote.content);
    } else {
      setLocalTitle('');
      setLocalContent('');
    }
  }, [activeNoteId, activeNote?.id]); // Only run when ID changes, not content

  // Auto-save logic
  const debouncedTitle = useDebounce(localTitle, 1000);
  const debouncedContent = useDebounce(localContent, 1000);

  useEffect(() => {
    if (activeNote && (debouncedTitle !== activeNote.title || debouncedContent !== activeNote.content)) {
      // @ts-ignore
      dispatch(updateNote({
        id: activeNote.id,
        title: debouncedTitle,
        content: debouncedContent,
      }));
    }
  }, [debouncedTitle, debouncedContent, activeNote, dispatch]);

  const filteredNotes = notes.filter(n => 
    n.title.toLowerCase().includes(searchTerm.toLowerCase()) || 
    n.content.toLowerCase().includes(searchTerm.toLowerCase())
  ).sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

  const handleCreateNote = () => {
    // @ts-ignore
    dispatch(addNote({ title: 'New Note', content: '# New Note\n\nStart typing here...' }));
    setIsPreview(false);
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteConfirm({ isOpen: true, id });
  };

  const confirmDelete = () => {
    if (deleteConfirm.id) {
      // @ts-ignore
      dispatch(deleteNote(deleteConfirm.id));
      setDeleteConfirm({ isOpen: false, id: '' });
    }
  };

  const sanitizedContent = DOMPurify.sanitize(localContent);

  return (
    <div className="h-[calc(100vh-8rem)] flex gap-6">
      {/* Sidebar - Notes List */}
      <div className="w-1/3 flex flex-col card overflow-hidden">
        <div className="p-4 border-b border-border flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <FileText className="w-5 h-5" /> Notes
            </h2>
            <button onClick={handleCreateNote} className="p-2 bg-accent/10 text-accent rounded hover:bg-accent hover:text-white transition-colors">
              <Plus className="w-5 h-5" />
            </button>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search notes..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-field w-full pl-9 py-2 text-sm"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-hide">
          {filteredNotes.length === 0 ? (
            <p className="text-center text-gray-500 mt-8 text-sm">No notes found.</p>
          ) : (
            filteredNotes.map(note => (
              <div
                key={note.id}
                onClick={() => dispatch(setActiveNote(note.id))}
                className={`p-3 rounded-lg cursor-pointer transition-colors group flex justify-between items-start ${activeNoteId === note.id ? 'bg-accent/20 border border-accent/30' : 'hover:bg-surface border border-transparent'}`}
              >
                <div className="overflow-hidden">
                  <h4 className={`font-medium truncate ${activeNoteId === note.id ? 'text-accent' : 'text-gray-300'}`}>
                    {note.title || 'Untitled Note'}
                  </h4>
                  <p className="text-xs text-gray-500 mt-1">
                    {format(new Date(note.updatedAt), 'MMM d, yyyy HH:mm')}
                  </p>
                </div>
                <button
                  onClick={(e) => handleDelete(note.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-1 text-gray-500 hover:text-red-400 transition-all"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main Editor Area */}
      <div className="flex-1 flex flex-col card overflow-hidden">
        {activeNote ? (
          <>
            <div className="p-4 border-b border-border flex items-center justify-between bg-surface">
              <input
                type="text"
                value={localTitle}
                onChange={(e) => setLocalTitle(e.target.value)}
                className="bg-transparent text-xl font-bold text-white focus:outline-none flex-1 mr-4 placeholder:text-gray-600"
                placeholder="Note Title..."
              />
              <div className="flex gap-2 bg-background p-1 rounded-lg border border-border">
                <button
                  onClick={() => setIsPreview(false)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium flex items-center gap-2 transition-colors ${!isPreview ? 'bg-surface text-white shadow-sm' : 'text-gray-400 hover:text-white'}`}
                >
                  <Edit3 className="w-4 h-4" /> Write
                </button>
                <button
                  onClick={() => setIsPreview(true)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium flex items-center gap-2 transition-colors ${isPreview ? 'bg-surface text-white shadow-sm' : 'text-gray-400 hover:text-white'}`}
                >
                  <Eye className="w-4 h-4" /> Preview
                </button>
              </div>
            </div>
            
            <div className="flex-1 overflow-hidden relative">
              {isPreview ? (
                <div className="absolute inset-0 p-6 overflow-y-auto prose prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {sanitizedContent}
                  </ReactMarkdown>
                </div>
              ) : (
                <textarea
                  value={localContent}
                  onChange={(e) => setLocalContent(e.target.value)}
                  className="absolute inset-0 w-full h-full p-6 bg-transparent text-gray-300 font-mono resize-none focus:outline-none leading-relaxed"
                  placeholder="Write your markdown here..."
                />
              )}
            </div>
            <div className="p-2 border-t border-border bg-surface text-xs text-gray-500 text-right">
              {debouncedTitle !== activeNote.title || debouncedContent !== activeNote.content ? 'Saving...' : 'Saved'}
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
            <FileText className="w-16 h-16 mb-4 opacity-50" />
            <p className="text-lg">Select a note or create a new one</p>
          </div>
        )}
      </div>
      {/* Confirm Dialog */}
      <ConfirmDialog
        isOpen={deleteConfirm.isOpen}
        onClose={() => setDeleteConfirm({ ...deleteConfirm, isOpen: false })}
        onConfirm={confirmDelete}
        title="Delete Note"
        message="Are you sure you want to delete this note? This action cannot be undone."
        confirmLabel="Delete"
      />
    </div>
  );
}
