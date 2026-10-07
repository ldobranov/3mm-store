from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest


SERVICE_SRC = Path(__file__).resolve().parents[1] / "service" / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))


sdk = types.ModuleType("three_mm_application_sdk")


@dataclass(frozen=True)
class ApplicationMigration:
    revision: str
    apply: object


sdk.ApplicationMigration = ApplicationMigration
sys.modules.setdefault("three_mm_application_sdk", sdk)


from three_mm_store.categories import CategoryService  # noqa: E402
from three_mm_store.migrations import get_migrations  # noqa: E402


class FixedClock:
    def now(self):
        return datetime(2026, 10, 7, 7, 0, tzinfo=UTC)


class Storage:
    def __init__(self, root: Path) -> None:
        self.database_path = root / "state.sqlite3"

    @contextmanager
    def transaction(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class Context:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self.clock = FixedClock()


class Actor:
    def __init__(self, key: str) -> None:
        self.user_id = 7
        self.idempotency_key = key


class CategoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.storage = Storage(self.root)
        connection = sqlite3.connect(self.storage.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            for migration in get_migrations():
                migration.apply(connection)
            connection.commit()
        finally:
            connection.close()
        self.service = CategoryService(Context(self.storage))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create(
        self,
        *,
        name: str,
        slug: str,
        key: str,
        parent_id: str | None = None,
    ):
        return self.service.create(
            {
                "name": name,
                "slug": slug,
                "parent_id": parent_id,
                "sort_order": 0,
            },
            Actor(key),
        )["category"]

    def test_create_is_replay_safe(self) -> None:
        payload = {
            "name": "Adults",
            "slug": "adults",
            "description": "",
            "parent_id": None,
            "sort_order": 0,
        }
        first = self.service.create(payload, Actor("create-0001"))
        second = self.service.create(payload, Actor("create-0001"))
        self.assertEqual(first, second)

        changed = dict(payload)
        changed["name"] = "Different"
        with self.assertRaisesRegex(
            ValueError,
            "Idempotency key was reused",
        ):
            self.service.create(changed, Actor("create-0001"))

        listed = self.service.list_categories(
            {"limit": 100, "offset": 0},
            None,
        )
        self.assertEqual(listed["total"], 1)

    def test_slug_history_cannot_be_reassigned(self) -> None:
        category = self.create(
            name="Adults",
            slug="adults",
            key="create-0002",
        )
        updated = self.service.update(
            {
                "category_id": category["category_id"],
                "slug": "adult-care",
            },
            Actor("update-0001"),
        )["category"]
        self.assertEqual(updated["slug"], "adult-care")

        with self.assertRaisesRegex(ValueError, "reserved by URL history"):
            self.create(
                name="Another",
                slug="adults",
                key="create-0003",
            )

    def test_hierarchy_rejects_cycles_and_archived_parent(self) -> None:
        parent = self.create(
            name="Parent",
            slug="parent",
            key="create-0004",
        )
        child = self.create(
            name="Child",
            slug="child",
            parent_id=parent["category_id"],
            key="create-0005",
        )

        with self.assertRaisesRegex(ValueError, "cycle"):
            self.service.update(
                {
                    "category_id": parent["category_id"],
                    "parent_id": child["category_id"],
                },
                Actor("update-0002"),
            )

        with self.assertRaisesRegex(ValueError, "active child"):
            self.service.set_status(
                {
                    "category_id": parent["category_id"],
                    "status": "archived",
                },
                Actor("status-0001"),
            )

        self.service.set_status(
            {
                "category_id": child["category_id"],
                "status": "archived",
            },
            Actor("status-0002"),
        )
        self.service.set_status(
            {
                "category_id": parent["category_id"],
                "status": "archived",
            },
            Actor("status-0003"),
        )

        with self.assertRaisesRegex(ValueError, "active parent"):
            self.service.set_status(
                {
                    "category_id": child["category_id"],
                    "status": "active",
                },
                Actor("status-0004"),
            )

    def test_unicode_search_is_case_insensitive(self) -> None:
        self.create(
            name="Памперси за възрастни",
            slug="pampersi",
            key="create-0006",
        )
        self.create(
            name="Чаршафи",
            slug="charshafi",
            key="create-0007",
        )

        result = self.service.list_categories(
            {
                "search": "ПАМПЕРСИ",
                "limit": 20,
                "offset": 0,
            },
            None,
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["slug"], "pampersi")

    def test_pagination_and_status_filter_are_bounded(self) -> None:
        first = self.create(
            name="A",
            slug="a",
            key="create-0008",
        )
        self.create(
            name="B",
            slug="b",
            key="create-0009",
        )
        self.service.set_status(
            {
                "category_id": first["category_id"],
                "status": "archived",
            },
            Actor("status-0005"),
        )

        active = self.service.list_categories(
            {
                "status": "active",
                "limit": 1,
                "offset": 0,
            },
            None,
        )
        self.assertEqual(active["total"], 1)
        self.assertEqual(len(active["items"]), 1)
        self.assertEqual(active["items"][0]["status"], "active")

        with self.assertRaisesRegex(ValueError, "limit"):
            self.service.list_categories(
                {"limit": 101, "offset": 0},
                None,
            )


if __name__ == "__main__":
    unittest.main()
