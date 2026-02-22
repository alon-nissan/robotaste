# Workflow Guide: React + FastAPI Architecture

This guide covers how to develop with and extend the RoboTaste platform using the new React frontend and FastAPI backend.

---

## 1. Quick Start

### Start Each Service Individually

**API Server** (from project root):
```bash
uvicorn api.main:app --reload --port 8000
```

**Frontend Dev Server**:
```bash
cd frontend && npm run dev
```
Runs on port 5173.

**Pump Service** (optional — only needed with physical NE-4000 pumps):
```bash
python pump_control_service.py --db-path robotaste.db --poll-interval 0.5
```

### All-in-One (Production — for experiments)

```bash
python start_new_ui.py              # Serves everything on port 8000
python start_new_ui.py --with-pump  # Also starts pump service
```
Builds the frontend, starts FastAPI, and serves everything on a single port. The
terminal shows the subject URL and a QR code for the tablet.

### All-in-One (Development — for coding)

```bash
python start_new_ui.py --dev
```
Starts FastAPI (port 8000) and Vite dev server (port 5173) with hot reload.

### API Documentation

Auto-generated Swagger UI is available at [http://localhost:8000/docs](http://localhost:8000/docs) once the API server is running.

---

## 2. Architecture Overview

```
┌─────────────────┐                     ┌──────────────────┐
│  React Frontend │ ◄─── same-origin ──► │  FastAPI Backend  │
│  (served from   │       /api/*        │  (port 8000)      │
│   port 8000)    │                     │                    │
│                 │                     │  Routers:          │
│  Pages:         │                     │  /api/sessions     │
│  /              │                     │  /api/protocols    │
│  /moderator/*   │                     │  /api/pump         │
│  /subject/*     │                     │  /api/docs         │
│  /protocols     │                     │                    │
└─────────────────┘                     └────────┬───────────┘
                                                 │ Python imports
                                                 ▼
                                        ┌──────────────────┐
                                        │  robotaste/       │
                                        │  (Business Logic) │
                                        │                   │
                                        │  data/database.py │
                                        │  core/trials.py   │
                                        │  core/bo_engine.py │
                                        └────────┬──────────┘
                                                 │
                                                 ▼
                                        ┌──────────────────┐
                                        │  robotaste.db     │
                                        │  (SQLite)         │
                                        └──────────────────┘
```

- The **React frontend** handles all UI rendering and user interaction.
- The **FastAPI backend** serves both the API and the React production build on a single port (8000).
- In **development mode** (`--dev`), the frontend runs separately on Vite (port 5173) with hot reload, and proxies `/api` requests to FastAPI.

---

## 3. Page Routing

### Moderator Flow

| Step | Route | Purpose |
|------|-------|---------|
| 1 | `/` | Landing page — create a new session or resume an existing one |
| 2 | `/moderator/setup` | Select protocol, configure pumps, start session |
| 3 | `/moderator/monitoring?session={id}` | Live monitoring dashboard |
| 4 | `/protocols` | Protocol manager (create, edit, delete protocols) |

### Subject Flow

| Step | Route | Purpose |
|------|-------|---------|
| 1 | `/` | Landing page — join by session code or QR scan |
| 2 | `/subject/{sessionId}/consent` | Informed consent form |
| 3 | `/subject/{sessionId}/register` | Demographics registration |
| 4 | `/subject/{sessionId}/instructions` | Read experiment instructions |
| 5 | `/subject/{sessionId}/select` | Sample selection (grid or slider UI) |
| 6 | `/subject/{sessionId}/preparing` | Wait for pump dispensing (if enabled) |
| 7 | `/subject/{sessionId}/questionnaire` | Rate the sample |
| 8 | Steps 5–7 repeat for each cycle | |
| 9 | `/subject/{sessionId}/complete` | Thank you / completion screen |
| 10 | `/subject/{sessionId}/phase/{phaseId}` | Custom protocol-defined phases |

### Logo Visibility

- **Moderator pages**: Logo is always shown.
- **Subject pages**: Logo is shown on consent, registration, and instructions only. It is hidden during the active experiment (selection, questionnaire, preparing, completion, custom phases) to maximize screen real estate for the participant.

---

## 4. State Synchronization

The database is the single source of truth for experiment state. The React frontend uses API polling to stay in sync.

### How It Works

1. The **moderator** advances the experiment phase via the API (e.g., `POST /api/sessions/{id}/advance`).
2. The API updates `sessions.current_phase` in the database.
3. **Subject pages** poll `GET /api/sessions/{id}/status` every ~5 seconds.
4. When the polled phase differs from the local state, the subject UI navigates to the appropriate page automatically.

### Comparison with Legacy Streamlit

| Concern | Streamlit (legacy) | React + FastAPI (current) |
|---------|-------------------|--------------------------|
| State source | `sessions.current_phase` in DB | Same |
| Sync mechanism | `sync_session_state_to_streamlit()` | API polling (`GET /api/sessions/{id}/status`) |
| Local state | `st.session_state` | React component state / context |
| Update flow | DB → Streamlit session state | DB → API response → React state |

---

## 5. How to Add a New Page

1. **Create the page component** at `frontend/src/pages/MyNewPage.tsx`.
2. **Wrap content** with `PageLayout` for consistent layout and optional logo.
3. **Use React Router hooks**: `useParams()` for URL parameters, `useNavigate()` for programmatic navigation.
4. **Add the route** in `frontend/src/App.tsx`.
5. **Follow styling conventions** documented in `docs/DESIGN_GUIDELINES.md`.

### Example Skeleton

```tsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';

export default function MyNewPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Fetch data on mount
    api.get(`/sessions/${sessionId}`)
      .then(res => { /* use res.data */ })
      .catch(err => setError('Failed to load'))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) return <PageLayout><p>Loading...</p></PageLayout>;
  if (error) return <PageLayout><p className="text-red-700">{error}</p></PageLayout>;

  return (
    <PageLayout showLogo={false}>
      {/* Page content */}
    </PageLayout>
  );
}
```

---

## 6. How to Add an API Endpoint

1. **Choose or create a router file** in `api/routers/`.
2. **Define a Pydantic request model** if the endpoint accepts a body.
3. **Create the endpoint function** with the appropriate decorator (`@router.get`, `@router.post`, etc.).
4. **Use existing `robotaste.data.*` functions** for database access — do not write raw SQL.
5. **Register the router** in `api/main.py` if you created a new file.

### Example

```python
from pydantic import BaseModel

class MyRequest(BaseModel):
    field: str

@router.post("/{session_id}/my-action")
def my_action(session_id: str, request: MyRequest):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Business logic here
    return {"message": "Done"}
```

---

## 7. Key Files Reference

| File | Purpose |
|------|---------|
| `frontend/src/App.tsx` | All route definitions |
| `frontend/src/components/PageLayout.tsx` | Page wrapper (logo + layout) |
| `frontend/src/api/client.ts` | Axios HTTP client |
| `frontend/src/types/index.ts` | All TypeScript types |
| `api/main.py` | FastAPI entry point |
| `api/routers/sessions.py` | Session endpoints |
| `api/routers/protocols.py` | Protocol CRUD endpoints |
| `api/routers/pump.py` | Pump monitoring endpoints |
| `docs/DESIGN_GUIDELINES.md` | UI styling reference |

---

## 8. Development Tips

- **Hot reload**: Both Vite (frontend) and uvicorn `--reload` (API) auto-restart on file changes.
- **API docs**: Interactive Swagger UI at [http://localhost:8000/docs](http://localhost:8000/docs).
- **TypeScript errors**: Run `npx tsc --noEmit` to check types without building.
- **Debug API**: Check `logs/uvicorn.log` for request timing and errors.
- **Database**: Use `sqlite3 robotaste.db` for direct DB inspection.
- **Tests**: Run `pytest` from the project root (Python tests only).
