import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useNote, useUpdateNote, useDeleteNote } from "../hooks/useNotes";

export default function NoteDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const noteId = Number(id);

  const noteQ = useNote(noteId);
  const updateMutation = useUpdateNote();
  const deleteMutation = useDeleteNote();

  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");

  if (noteQ.isLoading) {
    return <div className="p-6 text-muted">Loading...</div>;
  }

  if (!noteQ.data) {
    return (
      <div className="p-6">
        <button
          onClick={() => navigate("/notes")}
          className="text-accent hover:text-accent-hover text-sm mb-4"
        >
          &larr; Back to Notes
        </button>
        <p className="text-danger">Note not found</p>
      </div>
    );
  }

  const note = noteQ.data;

  const startEditing = () => {
    setEditTitle(note.title);
    setEditContent(note.content);
    setEditing(true);
  };

  const saveEdit = async () => {
    await updateMutation.mutateAsync({
      id: noteId,
      data: { title: editTitle, content: editContent },
    });
    setEditing(false);
  };

  const handleDelete = async () => {
    if (confirm("Delete this note permanently?")) {
      await deleteMutation.mutateAsync(noteId);
      navigate("/notes");
    }
  };

  return (
    <div className="p-6 max-w-[900px] mx-auto">
      {/* Back */}
      <button
        onClick={() => navigate("/notes")}
        className="text-accent hover:text-accent-hover text-sm mb-4 flex items-center gap-1"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Notes
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="min-w-0 flex-1">
          {editing ? (
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="w-full bg-surface border border-border rounded-lg px-3 py-2 text-lg font-bold text-gray-100 focus:outline-none focus:border-accent/50"
            />
          ) : (
            <>
              <div className="flex items-center gap-2 mb-1">
                <h1 className="text-xl font-bold text-gray-100">{note.title}</h1>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                    note.note_type === "memo"
                      ? "bg-accent/15 text-accent border border-accent/25"
                      : "bg-border/50 text-muted border border-border"
                  }`}
                >
                  {note.note_type === "memo" ? "Memo" : "Note"}
                </span>
                {note.ticker && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-warning/10 text-warning border border-warning/20">
                    {note.ticker}
                  </span>
                )}
              </div>
              <p className="text-xs text-muted">
                Created {new Date(note.created_at).toLocaleDateString()} &middot;
                Updated {new Date(note.updated_at).toLocaleDateString()} at{" "}
                {new Date(note.updated_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </>
          )}
        </div>

        <div className="flex items-center gap-1 flex-shrink-0 ml-4">
          {editing ? (
            <>
              <button
                onClick={() => setEditing(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-muted hover:text-gray-200 hover:bg-surface transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={saveEdit}
                disabled={updateMutation.isPending}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
              >
                {updateMutation.isPending ? "Saving..." : "Save"}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={startEditing}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-muted hover:text-gray-200 hover:bg-surface transition-colors flex items-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                </svg>
                Edit
              </button>
              <button
                onClick={handleDelete}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-muted hover:text-danger hover:bg-danger/10 transition-colors flex items-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                </svg>
                Delete
              </button>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="bg-surface rounded-lg border border-border p-6">
        {editing ? (
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="w-full bg-panel border border-border rounded-lg p-4 text-sm text-gray-200 font-mono resize-none focus:outline-none focus:border-accent/50 min-h-[400px]"
          />
        ) : (
          <div className="prose prose-invert prose-sm max-w-none [&_table]:text-xs [&_table]:border-collapse [&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-1 [&_th]:bg-panel [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_code]:bg-panel [&_code]:px-1 [&_code]:rounded [&_pre]:bg-panel [&_pre]:border [&_pre]:border-border [&_pre]:rounded-lg [&_a]:text-accent [&_strong]:text-gray-100 [&_h1]:text-gray-100 [&_h2]:text-gray-100 [&_h3]:text-gray-100 [&_hr]:border-border">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {note.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
