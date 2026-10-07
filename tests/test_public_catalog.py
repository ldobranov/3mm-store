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


from three_mm_store.categories import CategoryService  # noqa: E402
from three_mm_store.migrations import get_migrations  # noqa: E402
from three_mm_store.products import ProductService  # noqa: E402
from three_mm_store.public_catalog import PublicCatalogRenderer  # noqa: E402
from three_mm_store.settings import StoreSettingsService  # noqa: E402


class FixedClock:
    def now(self):
        return datetime(2026, 10, 7, 16, 0, tzinfo=UTC)


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
        self.user_id = 41
        self.idempotency_key = key


class PublicActor:
    audience = "public"
    user_id = None
    idempotency_key = None


def category_content(language: str, name: str, description: str = ""):
    return {
        "language_code": language,
        "name": name,
        "description": description,
        "meta_title": "",
        "meta_description": "",
    }


def product_content(
    language: str,
    name: str,
    *,
    short_description: str = "",
    description: str = "",
    meta_title: str = "",
    meta_description: str = "",
):
    return {
        "language_code": language,
        "name": name,
        "short_description": short_description,
        "description": description,
        "meta_title": meta_title,
        "meta_description": meta_description,
    }


def request(
    path: str,
    *,
    slug: str | None = None,
    lang: str | None = None,
    accept_language: str | None = None,
    method: str = "GET",
):
    query = {"lang": [lang]} if lang is not None else {}
    headers = (
        {"accept-language": accept_language}
        if accept_language is not None
        else {}
    )
    return {
        "method": method,
        "path": path,
        "path_params": {"slug": slug} if slug is not None else {},
        "query": query,
        "headers": headers,
    }


class PublicCatalogTests(unittest.TestCase):
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
        self.categories = CategoryService(context)
        self.products = ProductService(context)
        self.settings = StoreSettingsService(context)
        self.public = PublicCatalogRenderer(context)

        self.settings.update(
            {
                "currency": "EUR",
                "public_base_url": "https://shop.example.com",
                "translations": [
                    {
                        "language_code": "bg",
                        "store_name": "Моят магазин",
                        "home_title": "Начало",
                        "home_description": "Добре дошли",
                        "meta_title": "Моят магазин",
                        "meta_description": "Български магазин",
                    },
                    {
                        "language_code": "en",
                        "store_name": "My Store",
                        "home_title": "Home",
                        "home_description": "Welcome",
                        "meta_title": "My Store",
                        "meta_description": "English store",
                    },
                ],
            },
            Actor("settings-0001"),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create_category(self) -> dict[str, object]:
        category = self.categories.create(
            {
                "slug": "subscriptions",
                "sort_order": 1,
                "content": category_content(
                    "bg",
                    "Абонаменти",
                    "Изберете абонамент",
                ),
            },
            Actor("category-0001"),
        )["category"]
        self.categories.update(
            {
                "category_id": category["category_id"],
                "content": category_content(
                    "en",
                    "Subscriptions",
                    "Choose a subscription",
                ),
            },
            Actor("category-0002"),
        )
        return category

    def create_product(
        self,
        *,
        slug: str = "one-month",
        sku: str = "SUB-1",
        active: bool = True,
        category_ids: list[str] | None = None,
        name_bg: str = "Абонамент за 1 месец",
        name_en: str = "One month subscription",
        key: str = "product-0001",
    ) -> dict[str, object]:
        product = self.products.create(
            {
                "sku": sku,
                "slug": slug,
                "price_minor": 990,
                "track_inventory": False,
                "category_ids": category_ids or [],
                "content": product_content(
                    "bg",
                    name_bg,
                    short_description="Кратко описание",
                    description="Подробно описание",
                    meta_title="Един месец",
                    meta_description="Месечен абонамент",
                ),
            },
            Actor(key),
        )["product"]
        self.products.update(
            {
                "product_id": product["product_id"],
                "content": product_content(
                    "en",
                    name_en,
                    short_description="Short description",
                    description="Long description",
                    meta_title="One month",
                    meta_description="Monthly subscription",
                ),
            },
            Actor(key + "-en"),
        )
        if active:
            self.products.set_status(
                {
                    "product_id": product["product_id"],
                    "status": "active",
                },
                Actor(key + "-active"),
            )
        return product

    def test_home_uses_store_language_and_active_products(self) -> None:
        self.create_product(
            name_bg="<b>Абонамент</b>",
            key="product-home",
        )

        result = self.public.render(
            request("/", lang="bg"),
            PublicActor(),
        )

        self.assertEqual(result["status"], 200)
        self.assertEqual(
            result["headers"]["Content-Language"],
            "bg",
        )
        self.assertIn("<h1>Начало</h1>", result["body"])
        self.assertIn("&lt;b&gt;Абонамент&lt;/b&gt;", result["body"])
        self.assertNotIn("<b>Абонамент</b>", result["body"])
        self.assertIn("EUR 9.90", result["body"])
        self.assertIn(
            'rel="canonical" href="https://shop.example.com/?lang=bg"',
            result["body"],
        )

    def test_accept_language_selects_localized_product_content(self) -> None:
        self.create_product(key="product-language")

        english = self.public.render(
            request(
                "/products/one-month",
                slug="one-month",
                accept_language="en-US,en;q=0.9,bg;q=0.5",
            ),
            PublicActor(),
        )
        bulgarian = self.public.render(
            request(
                "/products/one-month",
                slug="one-month",
                accept_language="bg-BG,bg;q=0.9",
            ),
            PublicActor(),
        )

        self.assertEqual(
            english["headers"]["Content-Language"],
            "en",
        )
        self.assertIn("One month subscription", english["body"])
        self.assertEqual(
            bulgarian["headers"]["Content-Language"],
            "bg",
        )
        self.assertIn("Абонамент за 1 месец", bulgarian["body"])

    def test_draft_product_is_not_public(self) -> None:
        self.create_product(
            slug="draft-product",
            sku="DRAFT-1",
            active=False,
            key="product-draft",
        )

        result = self.public.render(
            request(
                "/products/draft-product",
                slug="draft-product",
                lang="bg",
            ),
            PublicActor(),
        )

        self.assertEqual(result["status"], 404)
        self.assertNotIn("Абонамент", result["body"])

    def test_historical_slug_redirects_only_for_active_entity(self) -> None:
        product = self.create_product(key="product-history")
        self.products.update(
            {
                "product_id": product["product_id"],
                "slug": "one-month-new",
            },
            Actor("product-history-slug"),
        )

        result = self.public.render(
            request(
                "/products/one-month",
                slug="one-month",
                lang="bg",
            ),
            PublicActor(),
        )

        self.assertEqual(result["status"], 301)
        self.assertEqual(
            result["location"],
            "/products/one-month-new?lang=bg",
        )

        self.products.set_status(
            {
                "product_id": product["product_id"],
                "status": "archived",
            },
            Actor("product-history-archive"),
        )
        hidden = self.public.render(
            request(
                "/products/one-month",
                slug="one-month",
                lang="bg",
            ),
            PublicActor(),
        )
        self.assertEqual(hidden["status"], 404)

    def test_category_page_lists_only_active_assigned_products(self) -> None:
        category = self.create_category()
        self.create_product(
            category_ids=[category["category_id"]],
            key="product-category-active",
        )
        self.create_product(
            slug="hidden-product",
            sku="HIDDEN-1",
            active=False,
            category_ids=[category["category_id"]],
            name_bg="Скрит продукт",
            name_en="Hidden product",
            key="product-category-hidden",
        )

        result = self.public.render(
            request(
                "/categories/subscriptions",
                slug="subscriptions",
                lang="bg",
            ),
            PublicActor(),
        )

        self.assertEqual(result["status"], 200)
        self.assertIn("Абонаменти", result["body"])
        self.assertIn("Абонамент за 1 месец", result["body"])
        self.assertNotIn("Скрит продукт", result["body"])

    def test_head_uses_same_rendered_representation(self) -> None:
        self.create_product(key="product-head")

        get_result = self.public.render(
            request(
                "/products/one-month",
                slug="one-month",
                lang="en",
                method="GET",
            ),
            PublicActor(),
        )
        head_result = self.public.render(
            request(
                "/products/one-month",
                slug="one-month",
                lang="en",
                method="HEAD",
            ),
            PublicActor(),
        )

        self.assertEqual(get_result, head_result)

    def test_non_public_audience_is_rejected(self) -> None:
        class AdminActor:
            audience = "administrator"

        with self.assertRaisesRegex(ValueError, "public audience"):
            self.public.render(
                request("/"),
                AdminActor(),
            )


if __name__ == "__main__":
    unittest.main()
