import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="leadsense_test_")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db", "CHROMA_DIR": f"{_tmp}/chroma", "OPENAI_API_KEY": "",
    "TARGET_GMAIL_ADDRESS": "target@gmail.com", "GOOGLE_CLIENT_SECRETS_FILE": f"{_tmp}/missing.json", "API_ACCESS_KEY": "",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app
    from app.services import gmail_imap
    gmail_imap.IMAP_TOKEN_FILE = Path(_tmp) / "gmail_imap.enc"
    with TestClient(app) as c:
        r = c.post("/api/demo/load")
        assert r.status_code == 200
        yield c
