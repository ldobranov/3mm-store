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
from three_mm_store.products import ProductService  # noqa: E402


class FixedClock:
    def now(self):
        return datetime(2026, 10, 7, 9, 0, tzinfo=UTC)


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
        self.user_id = 11
        self.idempotency_key = key


def content(
    language_code: str,
    name: str,
    *,
    short_description: str = "",
    description: str = "",
    meta_title: str = "",
    meta_description: str = "",
) -> dict[str, object]:
    return {
        "language_code": language_code,
        "name": name,
        "short_description": short_description,
        "description": description,
        "meta_title": meta_title,
        "meta_description": meta_description,
    }


class ProductServiceTests(unittest.TestCase):
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
        self.service = ProductService(Context(self.storage))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create_category(self, suffix: str) -> str:
        category_id = "cat_" + suffix * 32
        with self.storage.transaction() as connection:
            connection.execute(
                """
                INSERT INTO categories(
                    id, slug, name, description, parent_id, sort_order,
                    status, created_at, updated_at, legacy_language_code
                ) VALUES (?, ?, ?, '', NULL, 0, 'active', ?, ?, 'en')
                """,
                (
                    category_id,
                    f"category-{suffix}",
                    f"Category {suffix}",
                    "2026-10-07T09:00:00+00:00",
                    "2026-10-07T09:00:00+00:00",
                ),
            )
        return category_id

    def create_product(
        self,
        *,
        sku: str = "SKU-1",
        slug: str = "product-one",
        name: str = "Product one",
        language_code: str = "en",
        category_ids: list[str] | None = None,
        key: str = "product-create-0001",
    ):
        return self.service.create(
            {
                "sku": sku,
                "slug": slug,
                "price_minor": 1299,
                "track_inventory": True,
                "category_ids": category_ids or [],
                "content": content(language_code, name),
            },
            Actor(key),
        )["product"]

    def test_create_is_replay_safe_and_initializes_inventory(self) -> None:
        category_id = self.create_category("a")
        payload = {
            "sku": "sku-1",
            "slug": "product-one",
            "price_minor": 1299,
            "track_inventory": True,
            "category_ids": [category_id],
            "content": content("en", "Product one"),
        }

        first = self.service.create(payload, Actor("create-0001"))
        second = self.service.create(payload, Actor("create-0001"))
        self.assertEqual(first, second)
        self.assertEqual(first["product"]["sku"], "SKU-1")
        self.assertEqual(first["product"]["status"], "draft")

        with self.storage.transaction() as connection:
            inventory = connection.execute(
                """
                SELECT stock_on_hand
                FROM inventory
                WHERE product_id = ?
                """,
                (first["product"]["product_id"],),
            ).fetchone()
            categories = connection.execute(
                """
                SELECT category_id
                FROM product_categories
                WHERE product_id = ?
                """,
                (first["product"]["product_id"],),
            ).fetchall()

        self.assertEqual(inventory[0], 0)
        self.assertEqual([row[0] for row in categories], [category_id])

    def test_product_keeps_multiple_language_versions(self) -> None:
        product = self.create_product(
            sku="PAMP-L",
            slug="pampersi-l",
            name="Памперси L",
            language_code="bg",
            key="create-0002",
        )

        self.service.update(
            {
                "product_id": product["product_id"],
                "content": content(
                    "EN",
                    "Adult diapers L",
                    short_description="Large size",
                    description="English description",
                    meta_title="Adult diapers L",
                    meta_description="English SEO",
                ),
            },
            Actor("update-0001"),
        )

        detail = self.service.get_product(
            {"product_id": product["product_id"]},
            None,
        )
        self.assertEqual(detail["legacy_language_code"], "bg")
        self.assertEqual(
            [item["language_code"] for item in detail["translations"]],
            ["bg", "en"],
        )

        english = self.service.list_products(
            {"language_code": "en", "limit": 20, "offset": 0},
            None,
        )
        bulgarian = self.service.list_products(
            {"language_code": "bg", "limit": 20, "offset": 0},
            None,
        )
        self.assertEqual(english["items"][0]["name"], "Adult diapers L")
        self.assertEqual(bulgarian["items"][0]["name"], "Памперси L")

    def test_sku_is_canonical_and_unique(self) -> None:
        first = self.create_product(
            sku="abc.01",
            slug="first",
            key="create-0003",
        )
        self.assertEqual(first["sku"], "ABC.01")

        with self.assertRaisesRegex(ValueError, "SKU is already in use"):
            self.create_product(
                sku="ABC.01",
                slug="second",
                key="create-0004",
            )

    def test_slug_history_is_reserved(self) -> None:
        product = self.create_product(
            sku="SKU-HISTORY",
            slug="old-product",
            key="create-0005",
        )

        updated = self.service.update(
            {
                "product_id": product["product_id"],
                "slug": "new-product",
            },
            Actor("update-0002"),
        )["product"]
        self.assertEqual(updated["slug"], "new-product")

        with self.assertRaisesRegex(ValueError, "reserved by URL history"):
            self.create_product(
                sku="SKU-OTHER",
                slug="old-product",
                key="create-0006",
            )

    def test_categories_can_be_replaced_transactionally(self) -> None:
        first = self.create_category("b")
        second = self.create_category("c")
        product = self.create_product(
            sku="SKU-CATS",
            slug="category-product",
            category_ids=[first],
            key="create-0007",
        )

        self.service.update(
            {
                "product_id": product["product_id"],
                "category_ids": [second, first],
            },
            Actor("update-0003"),
        )

        detail = self.service.get_product(
            {"product_id": product["product_id"]},
            None,
        )
        self.assertEqual(detail["category_ids"], [second, first])

        with self.assertRaisesRegex(ValueError, "were not found"):
            self.service.update(
                {
                    "product_id": product["product_id"],
                    "category_ids": ["cat_" + "f" * 32],
                },
                Actor("update-0004"),
            )

    def test_search_uses_localized_name_sku_and_slug(self) -> None:
        self.create_product(
            sku="PAMP-TEST",
            slug="pampersi-test",
            name="Памперси тест",
            language_code="bg",
            key="create-0008",
        )

        by_name = self.service.list_products(
            {
                "language_code": "bg",
                "search": "ПАМПЕРСИ",
                "limit": 20,
                "offset": 0,
            },
            None,
        )
        by_sku = self.service.list_products(
            {
                "language_code": "en",
                "search": "pamp-test",
                "limit": 20,
                "offset": 0,
            },
            None,
        )
        self.assertEqual(by_name["total"], 1)
        self.assertEqual(by_sku["total"], 1)

    def test_status_and_price_validation(self) -> None:
        product = self.create_product(
            sku="SKU-STATUS",
            slug="status-product",
            key="create-0009",
        )
        active = self.service.set_status(
            {
                "product_id": product["product_id"],
                "status": "active",
            },
            Actor("status-0001"),
        )["product"]
        self.assertEqual(active["status"], "active")

        with self.assertRaisesRegex(ValueError, "price"):
            self.service.update(
                {
                    "product_id": product["product_id"],
                    "price_minor": -1,
                },
                Actor("update-0005"),
            )


if __name__ == "__main__":
    unittest.main()
