import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("VERCEL", "1")

from sqlalchemy import func, select  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app, reviewed_examples, seed_taxonomy  # noqa: E402
from app.models import Email  # noqa: E402
from app.services import knowledge_base as kb  # noqa: E402
from app.api import simulate_target_inbox_sync  # noqa: E402
from app.demo.loader import load_demo  # noqa: E402

# Ensure tables, taxonomy, vector KB, and initial inbox data are ready on serverless cold start
init_db()
seed_taxonomy()
kb.ensure_knowledge_base(reviewed_examples())

_db = SessionLocal()
try:
    if (_db.scalar(select(func.count()).select_from(Email).where(Email.source == "gmail")) or 0) == 0:
        simulate_target_inbox_sync(_db)
    if (_db.scalar(select(func.count()).select_from(Email).where(Email.source == "demo")) or 0) == 0:
        load_demo(_db)
finally:
    _db.close()

__all__ = ["app"]
