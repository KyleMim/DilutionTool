const BASE_URL = import.meta.env.VITE_API_URL || (
  import.meta.env.MODE === "production" ? "" : "http://localhost:8000"
);

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────

export interface CompanyListItem {
  ticker: string;
  name: string;
  sector: string | null;
  market_cap: number | null;
  tracking_tier: string;
  composite_score: number | null;
  share_cagr_score: number | null;
  fcf_burn_score: number | null;
  sbc_revenue_score: number | null;
  offering_freq_score: number | null;
  cash_runway_score: number | null;
  atm_active_score: number | null;
  share_cagr_3y: number | null;
  fcf_burn_rate: number | null;
  sbc_revenue_pct: number | null;
  offering_count_3y: number | null;
  cash_runway_months: number | null;
  atm_program_active: boolean | null;
  price_change_12m: number | null;
}

export interface FinancialsItem {
  fiscal_period: string;
  shares_outstanding_diluted: number | null;
  free_cash_flow: number | null;
  stock_based_compensation: number | null;
  revenue: number | null;
  cash_and_equivalents: number | null;
}

export interface PricePoint {
  date: string;
  close: number | null;
  volume: number | null;
}

export interface FilingItem {
  accession_number: string;
  filing_type: string;
  filed_date: string | null;
  is_dilution_event: boolean;
  dilution_type: string | null;
  offering_amount_dollars: number | null;
}

export interface CompanyDetail {
  ticker: string;
  name: string;
  sector: string | null;
  exchange: string | null;
  market_cap: number | null;
  tracking_tier: string;
  score: CompanyListItem | null;
  financials: FinancialsItem[];
}

export interface StatsResponse {
  critical_count: number;
  watchlist_count: number;
  monitoring_count: number;
  avg_score: number | null;
  sectors: { sector: string; count: number }[];
}

export interface SectorCount {
  sector: string;
  count: number;
}

export interface HistoryResponse {
  financials: FinancialsItem[];
  scores: CompanyListItem[];
}

// ── API calls ──────────────────────────────────────────────────────

export function fetchCompanies(params?: Record<string, string | number>) {
  const qs = params
    ? "?" + new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)])
      ).toString()
    : "";
  return fetchJson<CompanyListItem[]>(`/api/companies${qs}`);
}

export function fetchCompany(ticker: string) {
  return fetchJson<CompanyDetail>(`/api/companies/${ticker}`);
}

export function fetchCompanyHistory(ticker: string) {
  return fetchJson<HistoryResponse>(`/api/companies/${ticker}/history`);
}

export function fetchCompanyFilings(ticker: string) {
  return fetchJson<FilingItem[]>(`/api/companies/${ticker}/filings`);
}

export function fetchCompanyPrices(ticker: string, months: number = 12) {
  return fetchJson<PricePoint[]>(`/api/companies/${ticker}/prices?months=${months}`);
}

export function fetchStats() {
  return fetchJson<StatsResponse>("/api/stats");
}

export function fetchSectors() {
  return fetchJson<SectorCount[]>("/api/screener/sectors");
}

export function fetchThresholds() {
  return fetchJson<Record<string, number>>("/api/config/thresholds");
}

export function updateThresholds(data: Record<string, number>) {
  return fetchJson<Record<string, number>>("/api/config/thresholds", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function fetchWeights() {
  return fetchJson<Record<string, number>>("/api/config/weights");
}

export function updateWeights(data: Record<string, number>) {
  return fetchJson<Record<string, number>>("/api/config/weights", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ── Chat Types ──────────────────────────────────────────────────────

export interface ConversationResponse {
  id: number;
  title: string | null;
  ticker: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface MessageResponse {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConversationDetailResponse {
  id: number;
  title: string | null;
  ticker: string | null;
  created_at: string;
  messages: MessageResponse[];
}

export interface NoteResponse {
  id: number;
  title: string;
  content: string;
  note_type: "note" | "memo";
  ticker: string | null;
  conversation_id: number | null;
  created_at: string;
  updated_at: string;
}

// ── Chat API calls ──────────────────────────────────────────────────

export function createConversation(data: { ticker?: string; title?: string }) {
  return fetchJson<ConversationResponse>("/api/chat/conversations", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function fetchConversations(ticker?: string) {
  const qs = ticker ? `?ticker=${ticker}` : "";
  return fetchJson<ConversationResponse[]>(`/api/chat/conversations${qs}`);
}

export function fetchConversation(id: number) {
  return fetchJson<ConversationDetailResponse>(`/api/chat/conversations/${id}`);
}

export function deleteConversation(id: number) {
  return fetchJson<void>(`/api/chat/conversations/${id}`, { method: "DELETE" });
}

export function sendMessageUrl(conversationId: number): string {
  return `${BASE_URL}/api/chat/conversations/${conversationId}/messages`;
}

export function truncateFromMessage(conversationId: number, messageId: number) {
  return fetchJson<void>(
    `/api/chat/conversations/${conversationId}/messages/${messageId}/truncate`,
    { method: "DELETE" }
  );
}

// ── Notes API calls ─────────────────────────────────────────────────

export function createNote(data: {
  title: string;
  content: string;
  note_type?: string;
  ticker?: string;
}) {
  return fetchJson<NoteResponse>("/api/notes", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function fetchNotes(ticker?: string, noteType?: string) {
  const params = new URLSearchParams();
  if (ticker) params.set("ticker", ticker);
  if (noteType) params.set("note_type", noteType);
  const qs = params.toString() ? `?${params}` : "";
  return fetchJson<NoteResponse[]>(`/api/notes${qs}`);
}

export function fetchNote(id: number) {
  return fetchJson<NoteResponse>(`/api/notes/${id}`);
}

export function updateNote(id: number, data: { title: string; content: string }) {
  return fetchJson<NoteResponse>(`/api/notes/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function deleteNote(id: number) {
  return fetchJson<void>(`/api/notes/${id}`, { method: "DELETE" });
}

export function saveConversationAsNote(conversationId: number, title?: string) {
  return fetchJson<NoteResponse>(
    `/api/notes/from-conversation/${conversationId}`,
    {
      method: "POST",
      body: JSON.stringify({ title }),
    }
  );
}

export function generateMemoFromConversation(
  conversationId: number,
  title?: string
) {
  return fetchJson<NoteResponse>(
    `/api/notes/memo-from-conversation/${conversationId}`,
    {
      method: "POST",
      body: JSON.stringify({ title }),
    }
  );
}
