import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchNotes,
  fetchNote,
  createNote,
  updateNote,
  deleteNote,
  saveConversationAsNote,
  generateMemoFromConversation,
} from "../api/client";

export function useNotesList(ticker?: string, noteType?: string) {
  return useQuery({
    queryKey: ["notes", ticker, noteType],
    queryFn: () => fetchNotes(ticker, noteType),
  });
}

export function useNote(id: number) {
  return useQuery({
    queryKey: ["note", id],
    queryFn: () => fetchNote(id),
    enabled: id > 0,
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      title: string;
      content: string;
      note_type?: string;
      ticker?: string;
    }) => createNote(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes"] }),
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: { title: string; content: string } }) =>
      updateNote(id, data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      qc.invalidateQueries({ queryKey: ["note", vars.id] });
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteNote(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes"] }),
  });
}

export function useSaveAsNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      conversationId,
      title,
    }: {
      conversationId: number;
      title?: string;
    }) => saveConversationAsNote(conversationId, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes"] }),
  });
}

export function useGenerateMemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      conversationId,
      title,
    }: {
      conversationId: number;
      title?: string;
    }) => generateMemoFromConversation(conversationId, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes"] }),
  });
}
