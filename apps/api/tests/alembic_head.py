"""Alembic head revision expected by milestone verify scripts."""

EXPECTED_HEAD = "035"


def is_at_expected_head(alembic_output: str) -> bool:
    return EXPECTED_HEAD in alembic_output and "head" in alembic_output.lower()
