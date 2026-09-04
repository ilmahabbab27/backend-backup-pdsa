# Smart City Management System – Backend

Backend for the **Smart City Intelligent Decision Support System (IDSS)**.

**Technology:** Python + FastAPI  
**Database:** Supabase  
**Python Version:** Python 3.13.x

---

# ⚠️ Important Rules

- Do not push directly to the `main` branch.
- Create your own branch from the latest `main` branch.
- Work only inside your assigned task folder.
- Follow the given project structure.
- Each task must have its own `.venv`.
- Use **Python 3.13.x**.
- Do not push `.venv` to GitHub.
- Do not push `.env` to GitHub.
- Push `.env.example` and `requirements.txt`.
- Add comments/docstrings for important functions.
- Keep database operations inside `repositories/`.
- Keep algorithms inside `algorithms/`.
- Keep application logic inside `services/`.
- Keep API endpoints inside `api/`.
- Test your work before pushing.
- Push your code to your own branch.
- Create a Pull Request to merge your work into `main`.
- Discuss with the team before changing anything inside `shared/`.
- Discuss with the team before changing shared Supabase tables.

---

# Tasks and Ports

| Task | Service | Port |
| --- | --- | --- |
| Task 1 | Route Optimization | `8001` |
| Task 2 | Resource Allocation | `8002` |
| Task 3 | Network Analysis | `8003` |
| Task 4 | Intelligent Decision | `8004` |
| Task 5 | Waste Route Optimization | `8005` |

---

# Project Structure

# Project Structure

```text
smart-city-backend/
│
├── README.md
├── .gitignore
├── .python-version
│
├── shared/
│   ├── __init__.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── supabase.py
│   │
│   ├── models/
│   │   ├── location.py
│   │   └── road.py
│   │
│   ├── repositories/
│   │   ├── location_repository.py
│   │   └── road_repository.py
│   │
│   └── utils/
│       ├── timing.py
│       └── response.py
│
├── task1-route-service/
│   ├── .venv/
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   │
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── config/
│   │   │   └── settings.py
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── algorithms/
│   │   └── utils/
│   │
│   └── tests/
│
├── task2-resource-service/
│   ├── .venv/
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   │
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── config/
│   │   │   └── settings.py
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── services/
│   │   └── algorithms/
│   │
│   └── tests/
│
├── task3-network-service/
│   ├── .venv/
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   │
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── config/
│   │   │   └── settings.py
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── services/
│   │   └── algorithms/
│   │
│   └── tests/
│
├── task4-decision-service/
│   ├── .venv/
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   │
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── config/
│   │   │   └── settings.py
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── services/
│   │   └── algorithms/
│   │
│   └── tests/
│
└── task5-optimization-service/
    ├── .venv/
    ├── .env
    ├── .env.example
    ├── requirements.txt
    │
    ├── app/
    │   ├── main.py
    │   ├── api/
    │   ├── config/
    │   │   └── settings.py
    │   ├── models/
    │   ├── repositories/
    │   ├── services/
    │   ├── algorithms/
    │   └── utils/
    │
    └── tests/
```

---

# Folder Purpose

| Folder | Purpose |
| --- | --- |
| `api/` | FastAPI endpoints |
| `config/` | Application and Supabase configuration |
| `models/` | Request, response and data models |
| `repositories/` | Supabase/database operations |
| `services/` | Application logic |
| `algorithms/` | Algorithm implementations |
| `utils/` | Helper functions |
| `tests/` | Testing |
| `shared/` | Common code shared between tasks |

---

# How to Run

## 1. Configure Supabase

Create a `.env` file in the backend root with:

```env
SUPABASE_URL=https://baprktxsesgogiwiuvzy.supabase.co
SUPABASE_KEY=your_supabase_key_here
```

If you need a database script, run:

```sql
sql/all_in_one.sql
```

in the Supabase SQL editor.

## 2. Start the backend services

Run all five services from a single command at the backend root:

```powershell
python run_all_services.py
```

This starts:

- Task 1 on `8001`
- Task 2 on `8002`
- Task 3 on `8003`
- Task 4 on `8004`
- Task 5 on `8005`

## 3. Start the frontend

In the frontend project folder:

```powershell
npm install
npm run dev
```

Then open:

```text
http://localhost:5173
```

## 4. Verify the backend

Check these health endpoints in the browser:

- `http://localhost:8001/health`
- `http://localhost:8002/health`
- `http://localhost:8003/health`
- `http://localhost:8004/health`
- `http://localhost:8005/health`

## 5. Shared SQL files

If you want to load the full schema and sample data in one run, use:

- `sql/all_in_one.sql`

If you prefer smaller files, use:

- `sql/schema.sql`
- `sql/seed.sql`
- `sql/route_queries.sql`
- `sql/resource_queries.sql`
- `sql/network_queries.sql`
- `sql/decision_queries.sql`
- `sql/optimization_queries.sql`
