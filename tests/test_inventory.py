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


from three_mm_store.inventory import InventoryService  # noqa: E402
from three_mm_store.migrations import get_migrations  # noqa: E402
from three_mm_store.products import ProductService  # noqa: E402


class FixedClock:
    def now(self):
        return datetime(2026, 10, 7, 10, 0, tzinfo=UTC)


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
        self.user_id = 21
        self.idempotency_key = key


def content(language_code: str, name: str) -> dict[str, object]:
    return {
        "language_code": language_code,
        "name": name,
        "short_description": "",
        "description": "",
        "meta_title": "",
        "meta_description": "",
    }


class InventoryServiceTests(unittest.TestCase):
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

        context = Context(self.storage)
        self.products = ProductService(context)
        self.inventory = InventoryService(context)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create_product(
        self,
        *,
        sku: str,
        slug: str,
        name: str,
        language_code: str = "en",
        track_inventory: bool = True,
        key: str,
    ) -> dict[str, object]:
        return self.products.create(
            {
                "sku": sku,
                "slug": slug,
                "price_minor": 1000,
                "track_inventory": track_inventory,
                "category_ids": [],
                "content": content(language_code, name),
            },
            Actor(key),
        )["product"]

    def test_list_uses_requested_localized_name_and_availability(self) -> None:
        product = self.create_product(
            sku="PAMP-L",
            slug="adult-diapers-l",
            name="Adult diapers L",
            key="product-create-0001",
        )
        self.products.update(
            {
                "product_id": product["product_id"],
                "content": content("bg", "Памперси L"),
            },
            Actor("product-update-0001"),
        )
        self.inventory.adjust(
            {
                "product_id": product["product_id"],
                "delta": 7,
                "reason": "Initial delivery",
            },
            Actor("inventory-adjust-0001"),
        )

        result = self.inventory.list_inventory(
            {
                "language_code": "bg",
                "availability": "in_stock",
                "search": "ПАМПЕРСИ",
                "limit": 20,
                "offset": 0,
            },
            None,
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["name"], "Памперси L")
        self.assertEqual(result["items"][0]["stock_on_hand"], 7)
        self.assertEqual(result["items"][0]["availability"], "in_stock")

    def test_adjustment_is_atomic_replay_safe_and_audited(self) -> None:
        product = self.create_product(
            sku="STOCK-1",
            slug="stock-one",
            name="Stock one",
            key="product-create-0002",
        )
        payload = {
            "product_id": product["product_id"],
            "delta": 12,
            "reason": "Supplier delivery",
        }

        first = self.inventory.adjust(payload, Actor("inventory-adjust-0002"))
        second = self.inventory.adjust(payload, Actor("inventory-adjust-0002"))

        self.assertEqual(first, second)
        self.assertEqual(first["adjustment"]["stock_before"], 0)
        self.assertEqual(first["adjustment"]["stock_after"], 12)

        with self.storage.transaction() as connection:
            stock = connection.execute(
                """
                SELECT stock_on_hand
                FROM inventory
                WHERE product_id = ?
                """,
                (product["product_id"],),
            ).fetchone()[0]
            history = connection.execute(
                """
                SELECT delta, stock_before, stock_after, reason
                FROM inventory_adjustments
                WHERE product_id = ?
                """,
                (product["product_id"],),
            ).fetchall()

        self.assertEqual(stock, 12)
        self.assertEqual(len(history), 1)
        self.assertEqual(
            tuple(history[0]),
            (12, 0, 12, "Supplier delivery"),
        )

    def test_adjustment_rejects_negative_result_without_partial_write(self) -> None:
        product = self.create_product(
            sku="STOCK-2",
            slug="stock-two",
            name="Stock two",
            key="product-create-0003",
        )
        self.inventory.adjust(
            {
                "product_id": product["product_id"],
                "delta": 3,
                "reason": "Delivery",
            },
            Actor("inventory-adjust-0003"),
        )

        with self.assertRaisesRegex(ValueError, "stock negative"):
            self.inventory.adjust(
                {
                    "product_id": product["product_id"],
                    "delta": -4,
                    "reason": "Bad count",
                },
                Actor("inventory-adjust-0004"),
            )

        with self.storage.transaction() as connection:
            stock = connection.execute(
                "SELECT stock_on_hand FROM inventory WHERE product_id = ?",
                (product["product_id"],),
            ).fetchone()[0]
            count = connection.execute(
                """
                SELECT COUNT(*)
                FROM inventory_adjustments
                WHERE product_id = ?
                """,
                (product["product_id"],),
            ).fetchone()[0]

        self.assertEqual(stock, 3)
        self.assertEqual(count, 1)

    def test_untracked_products_are_distinct_from_out_of_stock(self) -> None:
        tracked = self.create_product(
            sku="TRACKED",
            slug="tracked",
            name="Tracked",
            track_inventory=True,
            key="product-create-0004",
        )
        untracked = self.create_product(
            sku="UNTRACKED",
            slug="untracked",
            name="Untracked",
            track_inventory=False,
            key="product-create-0005",
        )

        out_of_stock = self.inventory.list_inventory(
            {
                "availability": "out_of_stock",
                "limit": 20,
                "offset": 0,
            },
            None,
        )
        no_tracking = self.inventory.list_inventory(
            {
                "availability": "untracked",
                "limit": 20,
                "offset": 0,
            },
            None,
        )

        self.assertEqual(
            [item["product_id"] for item in out_of_stock["items"]],
            [tracked["product_id"]],
        )
        self.assertEqual(
            [item["product_id"] for item in no_tracking["items"]],
            [untracked["product_id"]],
        )

    def test_delta_and_reason_are_bounded(self) -> None:
        product = self.create_product(
            sku="BOUNDS",
            slug="bounds",
            name="Bounds",
            key="product-create-0006",
        )

        for delta in (0, 1_000_000_001, -1_000_000_001):
            with self.assertRaisesRegex(ValueError, "delta"):
                self.inventory.adjust(
                    {
                        "product_id": product["product_id"],
                        "delta": delta,
                        "reason": "Reason",
                    },
                    Actor(f"inventory-bound-{delta}"),
                )

        with self.assertRaisesRegex(ValueError, "reason"):
            self.inventory.adjust(
                {
                    "product_id": product["product_id"],
                    "delta": 1,
                    "reason": " ",
                },
                Actor("inventory-bound-reason"),
            )


class InventoryMigrationTests(unittest.TestCase):
    def test_0003_backfills_missing_inventory_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                migrations = get_migrations()
                migrations[0].apply(connection)
                migrations[1].apply(connection)
                product_id = "prd_" + "a" * 32
                connection.execute(
                    """
                    INSERT INTO products(
                        id, sku, slug, name, short_description,
                        description, status, price_minor,
                        track_inventory, created_at, updated_at,
                        legacy_language_code
                    ) VALUES (?, 'LEGACY', 'legacy', 'Legacy', '', '',
                              'draft', 100, 1, ?, ?, 'en')
                    """,
                    (
                        product_id,
                        "2026-10-07T10:00:00+00:00",
                        "2026-10-07T10:00:00+00:00",
                    ),
                )
                connection.commit()

                migrations[2].apply(connection)
                connection.commit()

                row = connection.execute(
                    """
                    SELECT stock_on_hand
                    FROM inventory
                    WHERE product_id = ?
                    """,
                    (product_id,),
                ).fetchone()
                adjustment_table = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name = 'inventory_adjustments'
                    """
                ).fetchone()
            finally:
                connection.close()

        self.assertEqual(row[0], 0)
        self.assertEqual(adjustment_table[0], "inventory_adjustments")


if __name__ == "__main__":
    unittest.main()
