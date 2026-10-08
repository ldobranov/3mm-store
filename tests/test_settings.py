from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import types
import unittest


SERVICE_SRC = Path(__file__).resolve().parents[1] / "service" / "src"
if str(SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(SERVICE_SRC))


sdk = sys.modules.get("three_mm_application_sdk")
if sdk is None:
    sdk = types.ModuleType("three_mm_application_sdk")

    @dataclass(frozen=True)
    class ApplicationMigration:
        revision: str
        apply: object

    sdk.ApplicationMigration = ApplicationMigration
    sys.modules["three_mm_application_sdk"] = sdk


from three_mm_store.migrations import get_migrations  # noqa: E402
from three_mm_store.settings import StoreSettingsService  # noqa: E402


class FixedClock:
    def now(self):
        return datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


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
        self.user_id = 31
        self.idempotency_key = key


def translation(
    language_code: str,
    store_name: str,
    **overrides: str,
) -> dict[str, object]:
    value: dict[str, object] = {
        "language_code": language_code,
        "store_name": store_name,
        "home_title": "",
        "home_description": "",
        "meta_title": "",
        "meta_description": "",
    }
    value.update(overrides)
    return value


class StoreSettingsServiceTests(unittest.TestCase):
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

        self.settings = StoreSettingsService(Context(self.storage))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_defaults_do_not_require_seed_rows(self) -> None:
        result = self.settings.get_settings({}, None)

        self.assertEqual(result["currency"], "EUR")
        self.assertEqual(result["public_base_url"], "")
        self.assertEqual(result["translations"], [])

    def test_global_and_localized_settings_are_replay_safe(self) -> None:
        payload = {
            "currency": "usd",
            "public_base_url": "https://Shop.Example.com/",
            "translations": [
                translation(
                    "bg",
                    "Моят магазин",
                    home_title="Добре дошли",
                    meta_title="Моят магазин",
                ),
                translation(
                    "en",
                    "My Store",
                    home_title="Welcome",
                    meta_title="My Store",
                ),
            ],
        }

        first = self.settings.update(
            payload,
            Actor("settings-update-0001"),
        )
        second = self.settings.update(
            payload,
            Actor("settings-update-0001"),
        )

        self.assertEqual(first, second)
        self.assertEqual(first["currency"], "USD")
        self.assertEqual(
            first["public_base_url"],
            "https://shop.example.com",
        )
        self.assertEqual(
            [row["language_code"] for row in first["translations"]],
            ["bg", "en"],
        )

        with self.storage.transaction() as connection:
            stored = {
                row["key"]: json.loads(row["value_json"])
                for row in connection.execute(
                    "SELECT key, value_json FROM store_settings"
                )
            }
            idempotency_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM idempotency_records
                WHERE operation_id = 'store_settings_update'
                """
            ).fetchone()[0]

        self.assertEqual(
            stored,
            {
                "currency": "USD",
                "public_base_url": "https://shop.example.com",
            },
        )
        self.assertEqual(idempotency_count, 1)

    def test_partial_translation_update_preserves_other_fields(self) -> None:
        self.settings.update(
            {
                "translations": [
                    translation(
                        "bg",
                        "Магазин",
                        home_title="Начало",
                        home_description="Описание",
                        meta_title="SEO",
                        meta_description="SEO описание",
                    )
                ]
            },
            Actor("settings-update-0002"),
        )

        updated = self.settings.update(
            {
                "translations": [
                    {
                        "language_code": "BG",
                        "home_title": "Ново начало",
                    }
                ]
            },
            Actor("settings-update-0003"),
        )

        row = updated["translations"][0]
        self.assertEqual(row["language_code"], "bg")
        self.assertEqual(row["store_name"], "Магазин")
        self.assertEqual(row["home_title"], "Ново начало")
        self.assertEqual(row["home_description"], "Описание")
        self.assertEqual(row["meta_title"], "SEO")
        self.assertEqual(row["meta_description"], "SEO описание")

    def test_translations_are_independent_by_language(self) -> None:
        self.settings.update(
            {
                "translations": [
                    translation("bg", "Магазин"),
                    translation("de", "Geschäft"),
                ]
            },
            Actor("settings-update-0004"),
        )

        result = self.settings.get_settings({}, None)
        names = {
            row["language_code"]: row["store_name"]
            for row in result["translations"]
        }

        self.assertEqual(
            names,
            {"bg": "Магазин", "de": "Geschäft"},
        )

    def test_currency_and_public_origin_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "Currency"):
            self.settings.update(
                {"currency": "EURO"},
                Actor("settings-invalid-0001"),
            )

        invalid_urls = (
            "ftp://example.com",
            "https://user:pass@example.com",
            "https://example.com/path",
            "https://example.com/?x=1",
            "not-a-url",
        )
        for index, value in enumerate(invalid_urls):
            with self.assertRaisesRegex(ValueError, "Public base URL"):
                self.settings.update(
                    {"public_base_url": value},
                    Actor(f"settings-invalid-url-{index}"),
                )

        cleared = self.settings.update(
            {"public_base_url": ""},
            Actor("settings-clear-url-0001"),
        )
        self.assertEqual(cleared["public_base_url"], "")

    def test_translation_batch_rejects_duplicate_languages(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicated"):
            self.settings.update(
                {
                    "translations": [
                        translation("bg", "A"),
                        translation("BG", "B"),
                    ]
                },
                Actor("settings-duplicate-language"),
            )

    def test_idempotency_key_cannot_change_request(self) -> None:
        self.settings.update(
            {"currency": "EUR"},
            Actor("settings-reuse-0001"),
        )

        with self.assertRaisesRegex(ValueError, "reused"):
            self.settings.update(
                {"currency": "USD"},
                Actor("settings-reuse-0001"),
            )


if __name__ == "__main__":
    unittest.main()
