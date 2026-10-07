"""Forward-only Store database migrations."""

from __future__ import annotations

import sqlite3

from three_mm_application_sdk import ApplicationMigration


def _migration_0001(connection: sqlite3.Connection) -> None:
    statements = (
        """
        CREATE TABLE store_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE categories (
            id TEXT PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            parent_id TEXT NULL REFERENCES categories(id) ON DELETE RESTRICT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'archived')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX idx_categories_parent_sort
            ON categories(parent_id, sort_order, name)
        """,
        """
        CREATE TABLE products (
            id TEXT PRIMARY KEY,
            sku TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            short_description TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'active', 'archived')),
            price_minor INTEGER NOT NULL
                CHECK (price_minor >= 0),
            track_inventory INTEGER NOT NULL DEFAULT 1
                CHECK (track_inventory IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX idx_products_status_name
            ON products(status, name)
        """,
        """
        CREATE INDEX idx_products_updated
            ON products(updated_at)
        """,
        """
        CREATE TABLE product_categories (
            product_id TEXT NOT NULL
                REFERENCES products(id) ON DELETE CASCADE,
            category_id TEXT NOT NULL
                REFERENCES categories(id) ON DELETE RESTRICT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (product_id, category_id)
        )
        """,
        """
        CREATE INDEX idx_product_categories_category
            ON product_categories(category_id, sort_order, product_id)
        """,
        """
        CREATE TABLE inventory (
            product_id TEXT PRIMARY KEY
                REFERENCES products(id) ON DELETE CASCADE,
            stock_on_hand INTEGER NOT NULL DEFAULT 0
                CHECK (stock_on_hand >= 0),
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE product_media (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL
                REFERENCES products(id) ON DELETE CASCADE,
            storage_key TEXT NOT NULL UNIQUE,
            media_type TEXT NOT NULL
                CHECK (
                    media_type IN (
                        'image/jpeg',
                        'image/webp',
                        'image/avif',
                        'image/png'
                    )
                ),
            byte_size INTEGER NOT NULL CHECK (byte_size > 0),
            width INTEGER NOT NULL CHECK (width > 0),
            height INTEGER NOT NULL CHECK (height > 0),
            sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
            alt_text TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_primary INTEGER NOT NULL DEFAULT 0
                CHECK (is_primary IN (0, 1)),
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX idx_product_media_product
            ON product_media(product_id, sort_order, id)
        """,
        """
        CREATE TABLE slug_history (
            entity_type TEXT NOT NULL
                CHECK (entity_type IN ('product', 'category')),
            entity_id TEXT NOT NULL,
            old_slug TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (entity_type, old_slug)
        )
        """,
        """
        CREATE INDEX idx_slug_history_entity
            ON slug_history(entity_type, entity_id)
        """,
        """
        CREATE TABLE idempotency_records (
            operation_id TEXT NOT NULL,
            actor_key TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (operation_id, actor_key, idempotency_key)
        )
        """,
    )
    for statement in statements:
        connection.execute(statement)


def _migration_0002(connection: sqlite3.Connection) -> None:
    """Add language-keyed content without guessing legacy text language."""

    statements = (
        "ALTER TABLE categories ADD COLUMN legacy_language_code TEXT NULL",
        "ALTER TABLE products ADD COLUMN legacy_language_code TEXT NULL",
        "ALTER TABLE product_media ADD COLUMN legacy_language_code TEXT NULL",
        """
        CREATE TABLE category_translations (
            category_id TEXT NOT NULL
                REFERENCES categories(id) ON DELETE CASCADE,
            language_code TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            meta_title TEXT NOT NULL DEFAULT '',
            meta_description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (category_id, language_code)
        )
        """,
        """
        CREATE INDEX idx_category_translations_language_name
            ON category_translations(language_code, name, category_id)
        """,
        """
        CREATE TABLE product_translations (
            product_id TEXT NOT NULL
                REFERENCES products(id) ON DELETE CASCADE,
            language_code TEXT NOT NULL,
            name TEXT NOT NULL,
            short_description TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            meta_title TEXT NOT NULL DEFAULT '',
            meta_description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (product_id, language_code)
        )
        """,
        """
        CREATE INDEX idx_product_translations_language_name
            ON product_translations(language_code, name, product_id)
        """,
        """
        CREATE TABLE product_media_translations (
            media_id TEXT NOT NULL
                REFERENCES product_media(id) ON DELETE CASCADE,
            language_code TEXT NOT NULL,
            alt_text TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (media_id, language_code)
        )
        """,
        """
        CREATE TABLE store_translations (
            language_code TEXT PRIMARY KEY,
            store_name TEXT NOT NULL DEFAULT '',
            home_title TEXT NOT NULL DEFAULT '',
            home_description TEXT NOT NULL DEFAULT '',
            meta_title TEXT NOT NULL DEFAULT '',
            meta_description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    )
    for statement in statements:
        connection.execute(statement)


def get_migrations() -> tuple[ApplicationMigration, ...]:
    return (
        ApplicationMigration(
            revision="0001",
            apply=_migration_0001,
        ),
        ApplicationMigration(
            revision="0002",
            apply=_migration_0002,
        ),
    )
