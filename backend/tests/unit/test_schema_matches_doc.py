"""The migration is generated from ARCHITECTURE.md. Guard against drift.

If someone edits the design document without regenerating the migration, or
edits the migration without updating the document, this test fails and says so.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
DOC = ROOT / "docs" / "ARCHITECTURE.md"
MIGRATION = ROOT / "backend" / "kernote" / "db" / "migrations" / "0001_init.sql"

BEGIN = "-- ===== BEGIN GENERATED FROM docs/ARCHITECTURE.md ====="
END = "-- ===== END GENERATED FROM docs/ARCHITECTURE.md ====="


def _doc_sql() -> str:
    blocks = re.findall(r"```sql\n(.*?)```", DOC.read_text(), re.S)
    assert blocks, "no sql block found in ARCHITECTURE.md"
    return "\n".join(blocks).strip()


def _migration_generated_part() -> str:
    text = MIGRATION.read_text()
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END)
    return text[start:end].strip()


def test_migration_matches_architecture_doc():
    assert _migration_generated_part() == _doc_sql(), (
        "0001_init.sql has drifted from docs/ARCHITECTURE.md §4. "
        "Regenerate the generated section or update the document."
    )


def test_schema_version_seeded():
    assert (
        "INSERT INTO schema_meta(key, value) VALUES ('schema_version', '1')"
        in MIGRATION.read_text()
    )
