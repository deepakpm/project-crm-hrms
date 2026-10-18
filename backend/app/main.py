from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, company, customers, invoices, items, payments, quotes, reports, users
from app.config import settings  # noqa: F401  (import triggers fail-fast startup validation)
from app.modules.people.api import attendance as people_attendance
from app.modules.people.api import employees as people_employees
from app.modules.people.api import expenses as people_expenses
from app.modules.people.api import leave as people_leave

app = FastAPI(title="ledgerly")
# Dev-only: the Vite dev server runs on a different origin. Tighten this to the
# real frontend origin(s) before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5190"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(company.router)
app.include_router(customers.router)
app.include_router(items.router)
app.include_router(quotes.router)
app.include_router(invoices.router)
app.include_router(payments.router)
app.include_router(reports.router)
app.include_router(people_employees.router)
app.include_router(people_employees.departments_router)
app.include_router(people_employees.designations_router)
app.include_router(people_leave.router)
app.include_router(people_attendance.router)
app.include_router(people_expenses.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
