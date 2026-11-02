import pytest


@pytest.fixture(autouse=True)
def audit_log(tmp_path, monkeypatch):
    """Keep tests from writing to the real audit log."""
    path = tmp_path / "audit.log"
    monkeypatch.setenv("HOMELAB_MCP_AUDIT_LOG", str(path))
    return path
