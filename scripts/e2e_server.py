"""Start PromptForge with mock dependencies for E2E testing.

Patches the lru_cache'd get_supabase_client so the lifespan
can initialise without real Supabase credentials, then overrides
all FastAPI Depends so that requests also hit the mock.
"""

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Patch the cached client BEFORE importing `app` ──────────────
from prompt_forge.db import client as _db_mod  # noqa: E402
from tests.conftest import MockSupabaseClient  # noqa: E402

mock_db = MockSupabaseClient()

# Clear the lru_cache and replace the function so that the
# lifespan's direct call to get_supabase_client() returns our mock.
_db_mod.get_supabase_client.cache_clear()
_original_get_supabase_client = _db_mod.get_supabase_client
_db_mod.get_supabase_client = lambda: mock_db  # type: ignore[assignment]

# ── Now import the app (triggers module-level code) ─────────────
from prompt_forge.main import app  # noqa: E402
from prompt_forge.core.audit import AuditLogger, get_audit_logger  # noqa: E402
from prompt_forge.core.composer import CompositionEngine, get_composer  # noqa: E402
from prompt_forge.core.registry import PromptRegistry, get_registry  # noqa: E402
from prompt_forge.core.resolver import PromptResolver, get_resolver  # noqa: E402
from prompt_forge.core.vcs import VersionControl, get_vcs  # noqa: E402

# ── Build service instances backed by the mock ──────────────────
registry = PromptRegistry(mock_db)
vcs = VersionControl(mock_db)
resolver = PromptResolver(mock_db)
composer = CompositionEngine(resolver, registry)
audit = AuditLogger(mock_db)

# ── Override FastAPI dependencies ───────────────────────────────
# Note: get_supabase_client is already monkey-patched at module level,
# so Depends(get_supabase_client) in route handlers will call our lambda
# and return mock_db without needing an override here.
app.dependency_overrides[get_registry] = lambda: registry
app.dependency_overrides[get_vcs] = lambda: vcs
app.dependency_overrides[get_resolver] = lambda: resolver
app.dependency_overrides[get_composer] = lambda: composer
app.dependency_overrides[get_audit_logger] = lambda: audit

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8083)
