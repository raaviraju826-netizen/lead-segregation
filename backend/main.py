from sqlalchemy import func, select

from app.api import simulate_target_inbox_sync
from app.config import IS_VERCEL
from app.db import SessionLocal, init_db
from app.demo.loader import load_demo
from app.main import app, reviewed_examples, seed_taxonomy
from app.models import Email
from app.services import knowledge_base as kb

if IS_VERCEL:
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
