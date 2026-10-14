# UniSync — AI Timetable Generator

The main module is the **admin AI Timetable Generator**: academic data, faculty availability, constraints, CP-SAT generation, optimization, manual review, publication and analytics. Friends, meetups and common free time are a **student add-on** built on the academic schedule.

New features and workflows: [Feature guide](docs/features.md). React + Vite + Tailwind; FastAPI + SQLAlchemy; JWT + Argon2 passwords; Google OR-Tools CP-SAT; SQLite locally or PostgreSQL.

## Run locally

Requires Python **3.11–3.13** and Node **20.19+ or 22+**. Use Python 3.13 rather than 3.14 with these pinned OR-Tools wheels.

Terminal 1, from this folder:

```sh
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
python -m app.seed
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```sh
cd frontend
npm ci
npm run dev
```

After installing once, you can also run `./start.sh` from this folder to start both servers together.

Open http://localhost:5173. API docs: http://127.0.0.1:8000/docs. The Vite dev server proxies `/api` to the backend. Run backend commands from `backend` so SQLite and `.env` paths resolve correctly.

Demo accounts (password set locally with **DEMO_PASSWORD**):

| Role | Email |
|---|---|
| Coordinator | admin@unisync.local |
| Student | krishna@unisync.local |
| Student | aanya@unisync.local |
| Student | rohan@unisync.local |
| Faculty | meera@unisync.local |

Seeding is explicit and idempotent: existing users are preserved; missing v2 demo configuration is added. Startup applies the additive v1→v2 schema migration and initializes scheduling defaults once, without creating demo users. Replace `JWT_SECRET` in `backend/.env` with a randomly generated secret. With no secret configured, an ephemeral random secret is used and tokens expire on restart. Tokens otherwise expire after eight hours. Tokens are kept in browser session storage.

## Core admin workflow

Sign in as `admin@unisync.local` (the default demo login). Start at **Dashboard**, open **AI timetable generator** to generate and compare schedules, maintain inputs in **Academic data**, then review/edit and publish in **College timetable**. Faculty and students consume the published timetable; social tools appear separately under **Student add-on**.

## Student add-on and other workflows

1. Sign in as Krishna. Open **My schedule**, select theory codes and individual lab codes, and save. A1 maps to both Monday and Wednesday. Theory A1 and lab L1 are different selections.
2. Open **Friends**. Demo Krishna already has Aanya and Rohan as accepted friends. New requests must be accepted by the recipient. Availability sharing can be disabled.
3. Open **Find time together**, choose friends, a weekday, time range and minimum duration. Results use clock intervals, including events, meetups and active published section schedules. Click **Make a plan** to reserve the chosen minimum duration at the start of an interval. The backend checks everyone is still free. All selected members see the meetup.
4. Switch to the coordinator. **Academic data** contains create/edit/delete tables for departments, faculty, subjects, sections, rooms/labs, slot templates, faculty availability, teaching assignments, users/roles, timetable versions and entries. Foreign-key IDs are shown in those tables. The complete typed API is also available in `/docs`.
5. Generate a timetable. Open **College timetable**, inspect by section or faculty and publish. The latest published version becomes the active college schedule. Students can select their course, semester and section in College timetable. Administrators can also edit `section_id` in the user table. Demo students intentionally start without a section so manual slot imports can be explored separately.
6. Faculty can view their own classes and workload in **Teaching desk**, submit change requests, and mark available/preferred/unavailable hours.
7. In **AI timetable generator**, generate and compare multiple solutions, preview plain-language rules, review faculty requests and find free rooms.
8. In **College timetable**, switch section/faculty/room views, download PDF/Excel, inspect quality and utilization, and move classes by selecting or dragging cards in drafts.
9. In **Academic data**, configure working days, workload caps, subject credits/difficulty and hard/soft constraint weights. **Find free rooms** is also available to students and faculty.

## Authoritative slot template

Original image: [`docs/slot-template.png`](docs/slot-template.png). Exact transcription: [`backend/app/slots.py`](backend/app/slots.py). No external VIT timetable was substituted.

- Monday–Friday: 55 theory occurrences + 60 lab occurrences (L1–L60).
- Preserve paired cell labels such as `A1/L1`, `F1/L2`, `D1/L3`, `TB1/L4`, `TG1/L5`, `L6`, `A2/L31`, through Friday `TDD2/L59`, `L60`, `V7`.
- Theory morning: 08:00–08:50, 09:00–09:50, 10:00–10:50, 11:00–11:50, 12:00–12:50. The next theory header cell is blank: **no invented 13:00 theory period**.
- Theory afternoon: 14:00–14:50, 15:00–15:50, 16:00–16:50, 17:00–17:50, 18:00–18:50. The displayed 18:51–19:00 header has no theory code underneath and is recorded as a boundary, not a schedulable class. V3–V7 use **19:01–19:50**.
- Lab morning: 08:00–08:50, 08:51–09:40, 09:51–10:40, 10:41–11:30, 11:40–12:30, 12:31–13:20.
- Lab afternoon: 14:00–14:50, 14:51–15:40, 15:51–16:40, 16:41–17:30, 17:40–18:30, 18:31–19:20. No lab slot under V3–V7.
- Lunch boundary is **13:20–14:00**. Theory morning classes finish earlier. Breaks and lunch remain available for social plans unless explicitly marked busy by an event.
- Exact shown clock boundaries are stored as minutes after midnight with half-open `[start,end)` comparisons. Two intervals touching at an endpoint do not clash. Labels are display metadata; import sends the distinct system and code, never a composite A1/L1 code.

## Solver behavior

The solver selects exactly `weekly_sessions` candidates per teaching assignment. Each candidate must match room type/capacity and fit entirely inside a declared faculty availability window. **No availability rows means unavailable.** Theory sessions have exactly one period. Labs can use 1–6 consecutive lab periods within the same morning/afternoon block. The image's short internal breaks (up to 11 minutes) remain inside the occupied lab-session interval, preventing another class from being inserted between its periods. Lunch and missing periods cannot be crossed.

Faculty, room and section clashes are checked using real start/end times across both slot systems. A sweep over interval boundaries enforces those resource constraints in CP-SAT. The objective uses configurable preferences for subject spread, faculty/student idle gaps, daily workload balance, consecutive lectures, difficult-subject distribution, late hours and preferred faculty windows. An early-start tie-break cost also applies. A 15-second solve limit returns a feasible or optimal schedule, or a clear error; it never returns partial schedules. Another validator checks the selected result before saving.

Manual entry writes use the same candidate and clash validator. Publication also requires exact weekly totals. Scheduling input changes are checked against all published versions; changes that invalidate a published version are rejected and rolled back. Unpublish the affected version before changing hard requirements. Drafts can become invalid after input changes and must pass validation before publication. Unpublish a timetable before editing its entries. Foreign keys prevent deletion of referenced records.

## PostgreSQL

```sh
docker compose up -d db
```

Change `DATABASE_URL` in `backend/.env` to:

```dotenv
DATABASE_URL=postgresql+psycopg://unisync:<your-local-password>@localhost:5432/unisync
```

Then run seed and the backend normally. PostgreSQL uses its own database; SQLite data is not migrated automatically. The local schema has an additive v1→v2 migration that preserves existing data. Future production schema evolution needs additional versioned migrations.

## Tests and production build

```sh
cd backend
source .venv/bin/activate
pytest -q
cd ../frontend
npm run build
```

Tests cover exact slot mapping, distinct clock systems, weekly totals, mixed theory/lab clashes, infeasible availability, room capacity/type, lab/lunch boundaries, intersection and duration filtering, JWT roles, CRUD validation, atomic import, friendship consent, event/meetup busy time and publication guards. Additional tests cover preferences, workload caps, working days, actual infeasibility cores, distinct alternatives, scoring, atomic manual moves, course/semester selection, faculty requests, exports, parsed-rule safety and preserved data during upgrades.

For a local compiled preview, `npm run preview` serves the build; configure a reverse proxy for `/api` or use the dev server. Vite's development API proxy does not automatically apply to a production host.

## API overview

- `/auth/register`, `/auth/login`, `/auth/me`: student registration, JWT and sharing preferences.
- `/admin/{resource}` and `/admin/{resource}/{id}`: typed CRUD, administrator only.
- `/admin/generate`, `/timetables`, `/timetables/{id}`: solve, view, publish via admin timetable PATCH.
- `/slots`, `/schedule`: template and current user's code import/free-busy.
- `/people`, `/friends`, `/friends/{id}/accept`: requests and consent.
- `/common-free`: authenticated self plus accepted sharing friends, actual interval intersection.
- `/events`, `/events/{id}`: owner-scoped recurring weekly personal events.
- `/meetups`, `/meetups/{id}`: member-scoped weekly plans and creator cancellation.
- `/faculty/availability`: linked faculty read/replace available/preferred/unavailable windows.
- `/academic-options`, `/student/section`: course/semester/section selection.
- `/admin/alternatives`, `/admin/diagnostics`: alternative schedules and failure preflight.
- `/admin/constraints/parse`, `/admin/constraints/batch`: local plain-language preview and reviewed writes.
- `/admin/validate-change`, `/admin/entries/{id}/move`: validated draft moves.
- `/timetables/{id}/view`, `/analytics`, `/export/{pdf|xlsx}`: views, analytics and exports (analytics/export paths follow `/timetables/{id}`).
- `/faculty/workload`, `/change-requests`: teaching workloads and coordinator review.
- `/free-rooms`: full-clock interval room lookup.

## MVP boundaries

The app models a recurring Monday–Friday week, not dated semesters, holidays or date-specific exceptions. Meetups reserve members immediately as authorized by the creator's selected sharing friends; there is no separate RSVP workflow. Generation is synchronous and intended for small local datasets. Concurrent writes are not serialized for multi-admin production workloads. PostgreSQL configuration is included; the automated test suite runs against SQLite. Password reset, refresh/revocation tokens, rate limiting, audit logs and future-version migrations are production work. The optional plain-language constraint feature uses documented local patterns, not an external LLM. No OCR is needed: the supplied image is transcribed once and slot codes drive imports thereafter.

Implementation references: [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) and [Google CP-SAT](https://developers.google.com/optimization/cp/cp_solver).

Set `DEMO_PASSWORD` in your local environment before seeding, for example with `read -s DEMO_PASSWORD` followed by `export DEMO_PASSWORD`. No demo password is shipped in the source.

Before starting PostgreSQL, set `POSTGRES_PASSWORD` locally. Use the same value in your local database URL; URL-encode special characters.
