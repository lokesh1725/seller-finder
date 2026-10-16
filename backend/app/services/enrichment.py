"""Optional enrichment (Hunter)."""
from __future__ import annotations

from typing import Any, Dict

def get_config():
    from ..config import Config
    return Config





def enrich_with_hunter(domain: str, founder_name: str) -> Dict[str, Any]:
    cfg = get_config()
    if not cfg.HUNTER_API_KEY or not domain:
        return {"enriched": False}
    # stub: do not call external API
    return {"enriched": False, "domain": domain, "founder_name": founder_name}
