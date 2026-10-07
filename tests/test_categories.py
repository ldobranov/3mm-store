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
        return datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


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


def content(
    language_code: str,
    name: str,
    *,
    description: str = "",
    meta_title: str = "",
    meta_description: str = "",
) -> dict[str, object]:
    return {
        "language_code": language_code,
        "name": name,
        "description": description,
        "meta_title": meta_title,
        "meta_description": meta_description,
    }


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
        language_code: str = "en",
        parent_id: str | None = None,
    ):
        return self.service.create(
            {
                "slug": slug,
                "parent_id": parent_id,
                "sort_order": 0,
                "content": content(language_code, name),
            },
            Actor(key),
        )["category"]

    def test_create_is_replay_safe(self) -> None:
        payload = {
            "slug": "adults",
            "parent_id": None,
            "sort_order": 0,
            "content": content("en", "Adults"),
        }
        first = self.service.create(payload, Actor("create-0001"))
        second = self.service.create(payload, Actor("create-0001"))
        self.assertEqual(first, second)

        changed = dict(payload)
        changed["content"] = content("en", "Different")
        with self.assertRaisesRegex(
            ValueError,
            "Idempotency key was reused",
        ):
            self.service.create(changed, Actor("create-0001"))

        listed = self.service.list_categories(
            {"language_code": "en", "limit": 100, "offset": 0},
            None,
        )
        self.assertEqual(listed["total"], 1)

    def test_category_keeps_multiple_language_versions(self) -> None:
        category = self.create(
            name="Памперси",
            slug="pampersi",
            language_code="bg",
            key="create-0002",
        )

        self.service.update(
            {
                "category_id": category["category_id"],
                "content": content(
                    "EN",
                    "Adult diapers",
                    description="English description",
                    meta_title="Adult diapers",
                    meta_description="English SEO description",
                ),
            },
            Actor("update-0001"),
        )

        detail = self.service.get_category(
            {"category_id": category["category_id"]},
            None,
        )
        self.assertEqual(detail["legacy_language_code"], "bg")
        self.assertEqual(
            [item["language_code"] for item in detail["translations"]],
            ["bg", "en"],
        )

        english = self.service.list_categories(
            {"language_code": "en", "limit": 20, "offset": 0},
            None,
        )
        bulgarian = self.service.list_categories(
            {"language_code": "bg", "limit": 20, "offset": 0},
            None,
        )
        self.assertEqual(english["items"][0]["name"], "Adult diapers")
        self.assertEqual(bulgarian["items"][0]["name"], "Памперси")

    def test_search_uses_requested_translation_and_unicode_casefold(self) -> None:
        category = self.create(
            name="Памперси за възрастни",
            slug="pampersi",
            language_code="bg",
            key="create-0003",
        )
        self.service.update(
            {
                "category_id": category["category_id"],
                "content": content("en", "Adult diapers"),
            },
            Actor("update-0002"),
        )

        bg_result = self.service.list_categories(
            {
                "language_code": "bg",
                "search": "ПАМПЕРСИ",
                "limit": 20,
                "offset": 0,
            },
            None,
        )
        en_result = self.service.list_categories(
            {
                "language_code": "en",
                "search": "ADULT",
                "limit": 20,
                "offset": 0,
            },
            None,
        )
        self.assertEqual(bg_result["total"], 1)
        self.assertEqual(en_result["total"], 1)

    def test_missing_translation_falls_back_to_legacy_content(self) -> None:
        self.create(
            name="Абонаменти",
            slug="subscriptions",
            language_code="bg",
            key="create-0004",
        )

        german = self.service.list_categories(
            {"language_code": "de", "limit": 20, "offset": 0},
            None,
        )
        self.assertEqual(german["items"][0]["name"], "Абонаменти")

    def test_slug_history_cannot_be_reassigned(self) -> None:
        category = self.create(
            name="Adults",
            slug="adults",
            key="create-0005",
        )
        updated = self.service.update(
            {
                "category_id": category["category_id"],
                "slug": "adult-care",
            },
            Actor("update-0003"),
        )["category"]
        self.assertEqual(updated["slug"], "adult-care")

        with self.assertRaisesRegex(ValueError, "reserved by URL history"):
            self.create(
                name="Another",
                slug="adults",
                key="create-0006",
            )

    def test_hierarchy_rejects_cycles_and_archived_parent(self) -> None:
        parent = self.create(
            name="Parent",
            slug="parent",
            key="create-0007",
        )
        child = self.create(
            name="Child",
            slug="child",
            parent_id=parent["category_id"],
            key="create-0008",
        )

        with self.assertRaisesRegex(ValueError, "cycle"):
            self.service.update(
                {
                    "category_id": parent["category_id"],
                    "parent_id": child["category_id"],
                },
                Actor("update-0004"),
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

    def test_pagination_and_status_filter_are_bounded(self) -> None:
        first = self.create(
            name="A",
            slug="a",
            key="create-0009",
        )
        self.create(
            name="B",
            slug="b",
            key="create-0010",
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
                "language_code": "en",
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

    def test_language_code_is_normalized_and_bounded(self) -> None:
        category = self.create(
            name="Portuguese",
            slug="portuguese",
            language_code="PT-BR",
            key="create-0011",
        )
        detail = self.service.get_category(
            {"category_id": category["category_id"]},
            None,
        )
        self.assertEqual(
            detail["translations"][0]["language_code"],
            "pt-br",
        )

        with self.assertRaisesRegex(ValueError, "Language code is invalid"):
            self.service.update(
                {
                    "category_id": category["category_id"],
                    "content": content("../bad", "Bad"),
                },
                Actor("update-0005"),
            )


class LocalizationMigrationTests(unittest.TestCase):
    def test_0002_preserves_legacy_rows_without_guessing_language(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state.sqlite3"
            connection = sqlite3.connect(database)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            migrations = get_migrations()

            migrations[0].apply(connection)
            connection.execute(
                """
                INSERT INTO categories(
                    id, slug, name, description, parent_id, sort_order,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, NULL, 0, 'active', ?, ?)
                """,
                (
                    "cat_" + "a" * 32,
                    "abonamenti",
                    "Абонаменти",
                    "Старо описание",
                    "2026-10-07T08:00:00+00:00",
                    "2026-10-07T08:00:00+00:00",
                ),
            )
            connection.commit()

            migrations[1].apply(connection)
            connection.commit()

            row = connection.execute(
                """
                SELECT name, description, legacy_language_code
                FROM categories
                WHERE slug = 'abonamenti'
                """
            ).fetchone()
            self.assertEqual(row["name"], "Абонаменти")
            self.assertEqual(row["description"], "Старо описание")
            self.assertIsNone(row["legacy_language_code"])
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM category_translations"
                ).fetchone()[0],
                0,
            )

            expected_tables = {
                "category_translations",
                "product_translations",
                "product_media_translations",
                "store_translations",
            }
            actual_tables = {
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }
            self.assertTrue(expected_tables.issubset(actual_tables))
            connection.close()


if __name__ == "__main__":
    unittest.main()
