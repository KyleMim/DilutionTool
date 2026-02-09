# AI Agent Chat & Notes/Memos Feature

## Context

The Dilution Tool currently has no AI or chat capabilities. The user wants to be able to click into a company profile and ask an AI agent questions about that company's dilution data, then save those conversations as quick notes or polished memos. Additionally, a global agent sidebar should be accessible at all times for general questions.

**Key decisions from user:**
- LLM: Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) via Anthropic Python SDK
- Company chat: Both a side panel AND a full-page tab view
- Markdown rendering via `react-markdown`
- Two save modes: **Notes** (raw conversation save) and **Memos** (AI-generated structured document with exec summary, company details, aggregated insights)

---

## Architecture Overview

```
[Left Nav 64px] [Main Content flex-1] [Global Agent Sidebar 48px/384px]

CompanyDetail page (when chat is open as side panel):
[Company Data flex-1] [Chat Panel 420px]

CompanyDetail page (when chat is full-page tab):
[Chat Full View with company context header]
```

---

## Phase 1: Backend Foundation

### 1.1 New Dependencies
- **File:** `monitor/requirements.txt` — add `anthropic>=0.39.0`
- **File:** `monitor/.env.example` — add `ANTHROPIC_API_KEY=`
- **File:** `monitor/backend/config.py` — add `anthropic_api_key` and `llm_model` fields to `AppConfig`

### 1.2 New Database Models
- **File:** `monitor/backend/models.py` — add 3 new SQLAlchemy models:

| Table | Key Fields | Purpose |
|-------|-----------|---------|
| `conversations` | id, title, ticker (nullable), created_at, updated_at | Chat sessions. ticker=NULL means global chat |
| `messages` | id, conversation_id (FK), role (user/assistant), content, created_at | Individual messages |
| `notes` | id, title, content, ticker (nullable), conversation_id (nullable), note_type ("note"/"memo"), created_at, updated_at | Saved notes & memos |

### 1.3 LLM Service
- **New file:** `monitor/backend/services/llm_client.py`
- `LLMClient` class wrapping `anthropic.Anthropic` with streaming
- `build_company_context(db, ticker)` — queries Company, DilutionScore, FundamentalsQuarterly, SecFiling from existing tables and formats into a system prompt with all data as markdown tables
- Two system prompts: `SYSTEM_PROMPT_COMPANY` (with full data injection) and `SYSTEM_PROMPT_GLOBAL` (general dilution knowledge)
- Model: `claude-sonnet-4-5-20250929`

### 1.4 Chat API Router
- **New file:** `monitor/backend/api/chat.py`

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/chat/conversations` | Create new conversation `{ticker?, title?}` |
| GET | `/api/chat/conversations` | List conversations `?ticker=` filter |
| GET | `/api/chat/conversations/{id}` | Get conversation with all messages |
| DELETE | `/api/chat/conversations/{id}` | Delete conversation |
| POST | `/api/chat/conversations/{id}/messages` | Send message → SSE stream back AI response |
| PATCH | `/api/chat/conversations/{id}` | Rename conversation |

The message endpoint uses `StreamingResponse` with `text/event-stream` — each Claude chunk sent as `data: {"type":"chunk","content":"..."}`, final event `data: {"type":"done","message_id":N}`. Assistant message saved to DB after stream completes.

### 1.5 Notes API Router
- **New file:** `monitor/backend/api/notes.py`

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/notes` | Create note `{title, content, ticker?, note_type}` |
| GET | `/api/notes` | List notes `?ticker=&type=` filter |
| GET | `/api/notes/{id}` | Get single note |
| PUT | `/api/notes/{id}` | Update note |
| DELETE | `/api/notes/{id}` | Delete note |
| POST | `/api/notes/from-conversation/{id}` | Save conversation as note (raw) |
| POST | `/api/notes/memo-from-conversation/{id}` | Generate memo via AI (structured) |

The memo endpoint sends the full conversation to Claude with a "generate executive memo" system prompt and saves the result as a note with `note_type="memo"`.

### 1.6 Register Routers
- **File:** `monitor/backend/main.py` — add `app.include_router(chat_router)` and `app.include_router(notes_router)`

---

## Phase 2: Frontend Chat Core

### 2.1 API Client Extensions
- **File:** `monitor/frontend/src/api/client.ts` — add TypeScript types and fetch functions for all chat + notes endpoints

### 2.2 New Dependencies
- `react-markdown` + `remark-gfm` for markdown rendering in chat

### 2.3 Chat Hook
- **New file:** `monitor/frontend/src/hooks/useChat.ts`
- Manages: current conversation, messages array, streaming state, SSE consumption
- Uses `fetch` + `ReadableStream` reader for SSE (not EventSource, since we need POST)
- Auto-creates conversation on first message send

### 2.4 Notes Hook
- **New file:** `monitor/frontend/src/hooks/useNotes.ts`
- React Query mutations for CRUD + save-from-conversation + generate-memo

### 2.5 Chat Components
All in `monitor/frontend/src/components/chat/`:

| Component | Purpose |
|-----------|---------|
| `ChatPanel.tsx` | Reusable composed panel (used by company chat + global sidebar) |
| `MessageList.tsx` | Scrollable message list with auto-scroll-to-bottom |
| `MessageBubble.tsx` | Single message — user: right-aligned accent, assistant: left-aligned surface with markdown |
| `ChatInput.tsx` | Auto-resizing textarea, Enter to send, Shift+Enter newline, disabled during stream |
| `ChatHeader.tsx` | Title, close button, view toggle (panel/full), save-as-note, generate-memo, conversation history |

---

## Phase 3: Page Integration

### 3.1 CompanyDetail Page
- **File:** `monitor/frontend/src/pages/CompanyDetail.tsx`
- Add state: `chatOpen` (boolean), `chatView` ("panel" | "full")
- **Panel mode**: Wrap existing content in flex container. When chat is open, add `<ChatPanel ticker={ticker} className="w-[420px]" />` alongside
- **Full-page mode**: Show a tab bar at top ["Data", "Chat"]. When "Chat" tab selected, render `<ChatPanel>` at full width instead of company data
- Floating action button (bottom-right) to toggle chat open

### 3.2 Global Agent Sidebar
- **New file:** `monitor/frontend/src/components/GlobalAgentSidebar.tsx`
- Collapsed: 48px strip with sparkle icon
- Expanded: 384px panel with `<ChatPanel />` (no ticker = global mode)
- Lives in `App.tsx` as flex sibling to `<main>`

### 3.3 App Layout Update
- **File:** `monitor/frontend/src/App.tsx`
- Add `<GlobalAgentSidebar />` after `<main>`
- Add nav icon for Notes page in left sidebar
- Add routes: `/notes` and `/notes/:id`

---

## Phase 4: Notes & Memos UI

### 4.1 Notes List Page
- **New file:** `monitor/frontend/src/pages/Notes.tsx`
- Route: `/notes`
- Grid of note cards with: title, ticker badge, note_type badge (Note/Memo), date, content preview
- Filter tabs: All / Notes / Memos, optional ticker filter
- Click card → navigate to `/notes/:id`

### 4.2 Note Detail Page
- **New file:** `monitor/frontend/src/pages/NoteDetail.tsx`
- Route: `/notes/:id`
- Full markdown rendering of note content
- Edit mode toggle (textarea for editing)
- Delete with confirmation
- Back button to `/notes`

---

## New Files Summary (13 files)

**Backend (3):**
1. `monitor/backend/services/llm_client.py`
2. `monitor/backend/api/chat.py`
3. `monitor/backend/api/notes.py`

**Frontend (10):**
4. `monitor/frontend/src/hooks/useChat.ts`
5. `monitor/frontend/src/hooks/useNotes.ts`
6. `monitor/frontend/src/components/chat/ChatPanel.tsx`
7. `monitor/frontend/src/components/chat/MessageList.tsx`
8. `monitor/frontend/src/components/chat/MessageBubble.tsx`
9. `monitor/frontend/src/components/chat/ChatInput.tsx`
10. `monitor/frontend/src/components/chat/ChatHeader.tsx`
11. `monitor/frontend/src/components/GlobalAgentSidebar.tsx`
12. `monitor/frontend/src/pages/Notes.tsx`
13. `monitor/frontend/src/pages/NoteDetail.tsx`

## Modified Files (6)
1. `monitor/requirements.txt` — add anthropic SDK
2. `monitor/backend/config.py` — add anthropic config fields
3. `monitor/backend/models.py` — add 3 new model classes
4. `monitor/backend/main.py` — register 2 new routers
5. `monitor/frontend/src/api/client.ts` — add chat + notes types & API functions
6. `monitor/frontend/src/pages/CompanyDetail.tsx` — add chat panel/tab integration
7. `monitor/frontend/src/App.tsx` — add global sidebar, notes routes, nav icon

---

## Implementation Order
1. Backend models + config → 2. LLM service → 3. Chat API → 4. Notes API → 5. Frontend API client → 6. Chat hook → 7. Chat components → 8. CompanyDetail integration → 9. Global sidebar → 10. Notes pages

## Verification
1. Start backend: `python run.py` — verify new tables created, `/docs` shows new endpoints
2. Test chat: Create conversation via API, send message, verify SSE stream
3. Test frontend: Open company detail, click chat FAB, send message, see streaming response
4. Test notes: Save conversation as note, generate memo, view on /notes page
5. Test global sidebar: Expand, ask general question, verify response
