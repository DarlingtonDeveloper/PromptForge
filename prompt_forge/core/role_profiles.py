"""Role-based section profiles for SOUL variants."""

ROLE_PROFILES: dict[str, list[str] | None] = {
    "king": None,  # None = full SOUL
    "developer": ["voice", "identity", "boundaries", "thinking_mode", "anti_patterns", "communication_rules"],
    "reviewer": ["voice", "identity", "boundaries", "communication_rules"],
    "tester": ["voice", "identity", "boundaries", "communication_rules"],
    "security": ["voice", "identity", "boundaries", "communication_rules"],
}


def get_sections_for_role(role: str) -> list[str] | None:
    """Return the section keys for a role, or None for full content."""
    return ROLE_PROFILES.get(role)
