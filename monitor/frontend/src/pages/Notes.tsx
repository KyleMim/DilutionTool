import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useNotesList, useDeleteNote } from "../hooks/useNotes";

export default function Notes() {
  const navigate = useNavigate();
  const [filterType, setFilterType] = useState<string | undefined>();
  const [filterTicker, setFilterTicker] = useState("");

  const notesQ = useNotesList(
    filterTicker || undefined,
    filterType
  );
  const deleteMutation = useDeleteNote();

  const notes = notesQ.data ?? [];

  return (
    <div className="p-6 max-w-[1000px] mx-auto">
      <h1 className="text-xl font-bold text-gray-100 mb-1">Notes & Memos</h1>
      <p className="text-sm text-muted mb-6">
        Saved conversations, notes, and AI-generated memos
      </p>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-center bg-surface rounded-lg p-0.5">
          {(["all", "note", "memo"] as const).map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type === "all" ? undefined : type)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                (type === "all" && !filterType) || filterType === type
                  ? "bg-accent text-white"
                  : "text-muted hover:text-gray-200"
              }`}
            >
              {type === "all" ? "All" : type === "note" ? "Notes" : "Memos"}
            </button>
          ))}
        </div>

        <input
          type="text"
          value={filterTicker}
          onChange={(e) => setFilterTicker(e.target.value.toUpperCase())}
          placeholder="Filter by ticker..."
          className="bg-surface border border-border rounded-lg px-3 py-1.5 text-sm text-gray-100 placeholder-muted w-40 focus:outline-none focus:border-accent/50"
        />
      </div>

      {/* Notes grid */}
      {notesQ.isLoading ? (
        <p className="text-muted text-sm">Loading...</p>
      ) : notes.length === 0 ? (
        <div className="bg-surface rounded-lg border border-border p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          </div>
          <p className="text-muted text-sm">No notes yet</p>
          <p className="text-muted text-xs mt-1">
            Start a chat with a company and save it as a note or memo
          </p>
        </div>
      ) : (
        <div className="grid gap-3">
          {notes.map((note) => (
            <button
              key={note.id}
              onClick={() => navigate(`/notes/${note.id}`)}
              className="group bg-surface rounded-lg border border-border p-4 text-left hover:border-accent/30 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-medium text-gray-100 truncate">
                      {note.title}
                    </h3>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium flex-shrink-0 ${
                        note.note_type === "memo"
                          ? "bg-accent/15 text-accent border border-accent/25"
                          : "bg-border/50 text-muted border border-border"
                      }`}
                    >
                      {note.note_type === "memo" ? "Memo" : "Note"}
                    </span>
                    {note.ticker && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-warning/10 text-warning border border-warning/20 flex-shrink-0">
                        {note.ticker}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted line-clamp-2">
                    {note.content.slice(0, 200).replace(/[#*_\-|]/g, "")}
                  </p>
                  <p className="text-[10px] text-muted mt-2">
                    {new Date(note.updated_at).toLocaleDateString()} at{" "}
                    {new Date(note.updated_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm("Delete this note?")) {
                      deleteMutation.mutate(note.id);
                    }
                  }}
                  className="opacity-0 group-hover:opacity-100 w-7 h-7 rounded flex items-center justify-center text-muted hover:text-danger transition-all flex-shrink-0"
                  title="Delete"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                </button>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
