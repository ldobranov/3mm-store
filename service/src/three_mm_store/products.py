"""Store-owned product catalog and localized content operations."""

from __future__ import annotations

import re
import secrets

from .idempotency import run_idempotent


PRODUCT_ID = re.compile(r"^prd_[0-9a-f]{32}$")
CATEGORY_ID = re.compile(r"^cat_[0-9a-f]{32}$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKU = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,79}$")
LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")

MAX_NAME = 200
MAX_SHORT_DESCRIPTION = 500
MAX_DESCRIPTION = 10_000
MAX_META_TITLE = 160
MAX_META_DESCRIPTION = 320
MAX_SLUG = 120
MAX_SEARCH = 120
MAX_OFFSET = 1_000_000
MAX_PRICE_MINOR = 999_999_999_999
MAX_CATEGORIES = 50


class ProductService:
    def __init__(self, application) -> None:
        self.application = application

    @staticmethod
    def _known_fields(
        payload: dict[str, object],
        allowed: set[str],
    ) -> None:
        if set(payload) - allowed:
            raise ValueError("Product request contains unknown fields")

    @staticmethod
    def _text(
        value: object,
        label: str,
        *,
        maximum: int,
        allow_empty: bool = False,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{label} must be text")
        normalized = value.strip()
        if not allow_empty and not normalized:
            raise ValueError(f"{label} is required")
        if len(normalized) > maximum:
            raise ValueError(f"{label} is too long")
        return normalized

    @classmethod
    def _product_id(cls, value: object) -> str:
        if not isinstance(value, str) or PRODUCT_ID.fullmatch(value) is None:
            raise ValueError("Product ID is invalid")
        return value

    @classmethod
    def _slug(cls, value: object) -> str:
        slug = cls._text(value, "Product slug", maximum=MAX_SLUG)
        if SLUG.fullmatch(slug) is None:
            raise ValueError(
                "Product slug must contain lowercase letters, digits and hyphens"
            )
        return slug

    @classmethod
    def _sku(cls, value: object) -> str:
        sku = cls._text(value, "SKU", maximum=80).upper()
        if SKU.fullmatch(sku) is None:
            raise ValueError("SKU contains unsupported characters")
        return sku

    @classmethod
    def _language_code(cls, value: object) -> str:
        code = cls._text(value, "Language code", maximum=35).lower()
        if LANGUAGE_CODE.fullmatch(code) is None:
            raise ValueError("Language code is invalid")
        return code

    @classmethod
    def _content(cls, value: object) -> dict[str, str]:
        if not isinstance(value, dict):
            raise ValueError("Product content is required")
        cls._known_fields(
            value,
            {
                "language_code",
                "name",
                "short_description",
                "description",
                "meta_title",
                "meta_description",
            },
        )
        return {
            "language_code": cls._language_code(
                value.get("language_code")
            ),
            "name": cls._text(
                value.get("name"),
                "Product name",
                maximum=MAX_NAME,
            ),
            "short_description": cls._text(
                value.get("short_description", ""),
                "Product short description",
                maximum=MAX_SHORT_DESCRIPTION,
                allow_empty=True,
            ),
            "description": cls._text(
                value.get("description", ""),
                "Product description",
                maximum=MAX_DESCRIPTION,
                allow_empty=True,
            ),
            "meta_title": cls._text(
                value.get("meta_title", ""),
                "Product meta title",
                maximum=MAX_META_TITLE,
                allow_empty=True,
            ),
            "meta_description": cls._text(
                value.get("meta_description", ""),
                "Product meta description",
                maximum=MAX_META_DESCRIPTION,
                allow_empty=True,
            ),
        }

    @staticmethod
    def _price_minor(value: object) -> int:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= MAX_PRICE_MINOR
        ):
            raise ValueError("Product price is invalid")
        return value

    @staticmethod
    def _track_inventory(value: object) -> bool:
        if not isinstance(value, bool):
            raise ValueError("track_inventory must be boolean")
        return value

    @classmethod
    def _category_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list) or len(value) > MAX_CATEGORIES:
            raise ValueError("Product categories are invalid")

        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str) or CATEGORY_ID.fullmatch(item) is None:
                raise ValueError("Product category ID is invalid")
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    @staticmethod
    def _row_to_product(row) -> dict[str, object]:
        return {
            "product_id": str(row["id"]),
            "sku": str(row["sku"]),
            "slug": str(row["slug"]),
            "name": str(row["name"]),
            "short_description": str(row["short_description"]),
            "description": str(row["description"]),
            "status": str(row["status"]),
            "price_minor": int(row["price_minor"]),
            "track_inventory": bool(row["track_inventory"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    @staticmethod
    def _translation_to_dict(row) -> dict[str, object]:
        return {
            "language_code": str(row["language_code"]),
            "name": str(row["name"]),
            "short_description": str(row["short_description"]),
            "description": str(row["description"]),
            "meta_title": str(row["meta_title"]),
            "meta_description": str(row["meta_description"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    @staticmethod
    def _load(connection, product_id: str):
        row = connection.execute(
            """
            SELECT id, sku, slug, name, short_description, description,
                   status, price_minor, track_inventory, created_at,
                   updated_at, legacy_language_code
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Product was not found")
        return row

    @classmethod
    def _load_localized(
        cls,
        connection,
        product_id: str,
        language_code: str,
    ):
        row = connection.execute(
            """
            SELECT
                p.id,
                p.sku,
                p.slug,
                COALESCE(t.name, p.name) AS name,
                COALESCE(t.short_description, p.short_description)
                    AS short_description,
                COALESCE(t.description, p.description) AS description,
                p.status,
                p.price_minor,
                p.track_inventory,
                p.created_at,
                p.updated_at
            FROM products p
            LEFT JOIN product_translations t
              ON t.product_id = p.id
             AND t.language_code = ?
            WHERE p.id = ?
            """,
            (language_code, product_id),
        ).fetchone()
        if row is None:
            raise ValueError("Product was not found")
        return row

    @staticmethod
    def _translation_rows(connection, product_id: str):
        return connection.execute(
            """
            SELECT language_code, name, short_description, description,
                   meta_title, meta_description, created_at, updated_at
            FROM product_translations
            WHERE product_id = ?
            ORDER BY language_code
            """,
            (product_id,),
        ).fetchall()

    @staticmethod
    def _upsert_translation(
        connection,
        product_id: str,
        content: dict[str, str],
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO product_translations(
                product_id,
                language_code,
                name,
                short_description,
                description,
                meta_title,
                meta_description,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id, language_code)
            DO UPDATE SET
                name = excluded.name,
                short_description = excluded.short_description,
                description = excluded.description,
                meta_title = excluded.meta_title,
                meta_description = excluded.meta_description,
                updated_at = excluded.updated_at
            """,
            (
                product_id,
                content["language_code"],
                content["name"],
                content["short_description"],
                content["description"],
                content["meta_title"],
                content["meta_description"],
                now,
                now,
            ),
        )

    @staticmethod
    def _category_rows(connection, product_id: str) -> list[str]:
        return [
            str(row[0])
            for row in connection.execute(
                """
                SELECT category_id
                FROM product_categories
                WHERE product_id = ?
                ORDER BY sort_order, category_id
                """,
                (product_id,),
            )
        ]

    @staticmethod
    def _assert_categories(connection, category_ids: list[str]) -> None:
        if not category_ids:
            return
        placeholders = ",".join("?" for _ in category_ids)
        rows = connection.execute(
            f"SELECT id FROM categories WHERE id IN ({placeholders})",
            category_ids,
        ).fetchall()
        found = {str(row[0]) for row in rows}
        if found != set(category_ids):
            raise ValueError("One or more product categories were not found")

    @classmethod
    def _replace_categories(
        cls,
        connection,
        product_id: str,
        category_ids: list[str],
    ) -> None:
        cls._assert_categories(connection, category_ids)
        connection.execute(
            "DELETE FROM product_categories WHERE product_id = ?",
            (product_id,),
        )
        for index, category_id in enumerate(category_ids):
            connection.execute(
                """
                INSERT INTO product_categories(
                    product_id, category_id, sort_order
                ) VALUES (?, ?, ?)
                """,
                (product_id, category_id, index),
            )

    @staticmethod
    def _assert_slug_available(
        connection,
        slug: str,
        *,
        current_id: str | None = None,
    ) -> None:
        current = connection.execute(
            "SELECT id FROM products WHERE slug = ?",
            (slug,),
        ).fetchone()
        if current is not None and str(current[0]) != current_id:
            raise ValueError("Product slug is already in use")

        historical = connection.execute(
            """
            SELECT entity_id
            FROM slug_history
            WHERE entity_type = 'product' AND old_slug = ?
            """,
            (slug,),
        ).fetchone()
        if historical is not None and str(historical[0]) != current_id:
            raise ValueError("Product slug is reserved by URL history")

    @staticmethod
    def _assert_sku_available(
        connection,
        sku: str,
        *,
        current_id: str | None = None,
    ) -> None:
        current = connection.execute(
            "SELECT id FROM products WHERE sku = ?",
            (sku,),
        ).fetchone()
        if current is not None and str(current[0]) != current_id:
            raise ValueError("SKU is already in use")

    def list_products(
        self,
        payload: dict[str, object],
        _context,
    ) -> dict[str, object]:
        self._known_fields(
            payload,
            {
                "search",
                "status",
                "sort",
                "limit",
                "offset",
                "language_code",
            },
        )

        search = self._text(
            payload.get("search", ""),
            "Product search",
            maximum=MAX_SEARCH,
            allow_empty=True,
        )
        status = payload.get("status")
        if status is not None and status not in {
            "draft",
            "active",
            "archived",
        }:
            raise ValueError("Product status filter is invalid")

        language_code = (
            self._language_code(payload["language_code"])
            if "language_code" in payload
            else None
        )
        sort = payload.get("sort", "updated_desc")
        sort_sql = {
            "name_asc": "name_value ASC, p.id ASC",
            "name_desc": "name_value DESC, p.id ASC",
            "updated_desc": "p.updated_at DESC, p.id ASC",
            "sku_asc": "p.sku ASC, p.id ASC",
        }.get(sort)
        if sort_sql is None:
            raise ValueError("Product sort is invalid")

        limit_value = payload.get("limit", 20)
        offset_value = payload.get("offset", 0)
        if (
            not isinstance(limit_value, int)
            or isinstance(limit_value, bool)
            or not 1 <= limit_value <= 100
        ):
            raise ValueError("Product list limit is invalid")
        if (
            not isinstance(offset_value, int)
            or isinstance(offset_value, bool)
            or not 0 <= offset_value <= MAX_OFFSET
        ):
            raise ValueError("Product list offset is invalid")

        join_sql = ""
        select_name = "p.name"
        select_short = "p.short_description"
        select_description = "p.description"
        parameters: list[object] = []
        if language_code is not None:
            join_sql = """
                LEFT JOIN product_translations t
                  ON t.product_id = p.id
                 AND t.language_code = ?
            """
            select_name = "COALESCE(t.name, p.name)"
            select_short = (
                "COALESCE(t.short_description, p.short_description)"
            )
            select_description = "COALESCE(t.description, p.description)"
            parameters.append(language_code)

        where: list[str] = []
        where_parameters: list[object] = []
        if status is not None:
            where.append("p.status = ?")
            where_parameters.append(status)
        if search:
            where.append(
                f"(store_casefold({select_name}) LIKE ? "
                "OR store_casefold(p.sku) LIKE ? "
                "OR store_casefold(p.slug) LIKE ?)"
            )
            pattern = f"%{search.casefold()}%"
            where_parameters.extend((pattern, pattern, pattern))

        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        select_sql = f"""
            SELECT
                p.id,
                p.sku,
                p.slug,
                {select_name} AS name_value,
                {select_name} AS name,
                {select_short} AS short_description,
                {select_description} AS description,
                p.status,
                p.price_minor,
                p.track_inventory,
                p.created_at,
                p.updated_at
            FROM products p
            {join_sql}
            {where_sql}
            ORDER BY {sort_sql}
            LIMIT ? OFFSET ?
        """
        count_sql = f"""
            SELECT COUNT(*)
            FROM products p
            {join_sql}
            {where_sql}
        """
        query_parameters = [*parameters, *where_parameters]

        with self.application.storage.transaction() as connection:
            connection.create_function(
                "store_casefold",
                1,
                lambda value: str(value).casefold(),
                deterministic=True,
            )
            total = int(
                connection.execute(
                    count_sql,
                    query_parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                select_sql,
                [
                    *query_parameters,
                    limit_value,
                    offset_value,
                ],
            ).fetchall()

        return {
            "items": [self._row_to_product(row) for row in rows],
            "total": total,
            "limit": limit_value,
            "offset": offset_value,
        }

    def get_product(
        self,
        payload: dict[str, object],
        _context,
    ) -> dict[str, object]:
        self._known_fields(payload, {"product_id"})
        product_id = self._product_id(payload.get("product_id"))

        with self.application.storage.transaction() as connection:
            current = self._load(connection, product_id)
            translations = self._translation_rows(
                connection,
                product_id,
            )
            return {
                "product": self._row_to_product(current),
                "legacy_language_code": (
                    str(current["legacy_language_code"])
                    if current["legacy_language_code"] is not None
                    else None
                ),
                "translations": [
                    self._translation_to_dict(row)
                    for row in translations
                ],
                "category_ids": self._category_rows(
                    connection,
                    product_id,
                ),
            }

    def create(
        self,
        payload: dict[str, object],
        context,
    ) -> dict[str, object]:
        self._known_fields(
            payload,
            {
                "sku",
                "slug",
                "price_minor",
                "track_inventory",
                "category_ids",
                "content",
            },
        )
        sku = self._sku(payload.get("sku"))
        slug = self._slug(payload.get("slug"))
        price_minor = self._price_minor(payload.get("price_minor"))
        track_inventory = self._track_inventory(
            payload.get("track_inventory", True)
        )
        category_ids = self._category_ids(
            payload.get("category_ids", [])
        )
        content = self._content(payload.get("content"))

        normalized_payload: dict[str, object] = {
            "sku": sku,
            "slug": slug,
            "price_minor": price_minor,
            "track_inventory": track_inventory,
            "category_ids": category_ids,
            "content": content,
        }

        def mutation(connection):
            self._assert_sku_available(connection, sku)
            self._assert_slug_available(connection, slug)
            self._assert_categories(connection, category_ids)

            product_id = f"prd_{secrets.token_hex(16)}"
            now = self.application.clock.now().isoformat()
            connection.execute(
                """
                INSERT INTO products(
                    id, sku, slug, name, short_description, description,
                    status, price_minor, track_inventory,
                    created_at, updated_at, legacy_language_code
                ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    sku,
                    slug,
                    content["name"],
                    content["short_description"],
                    content["description"],
                    price_minor,
                    1 if track_inventory else 0,
                    now,
                    now,
                    content["language_code"],
                ),
            )
            self._upsert_translation(
                connection,
                product_id,
                content,
                now,
            )
            self._replace_categories(
                connection,
                product_id,
                category_ids,
            )
            connection.execute(
                """
                INSERT INTO inventory(
                    product_id, stock_on_hand, updated_at
                ) VALUES (?, 0, ?)
                """,
                (product_id, now),
            )
            return {
                "product": self._row_to_product(
                    self._load_localized(
                        connection,
                        product_id,
                        content["language_code"],
                    )
                )
            }

        return run_idempotent(
            self.application,
            "product_create",
            normalized_payload,
            context,
            mutation,
        )

    def update(
        self,
        payload: dict[str, object],
        context,
    ) -> dict[str, object]:
        mutable = {
            "sku",
            "slug",
            "price_minor",
            "track_inventory",
            "category_ids",
            "content",
        }
        self._known_fields(payload, {"product_id", *mutable})
        product_id = self._product_id(payload.get("product_id"))
        if not (set(payload) & mutable):
            raise ValueError("Product update contains no changes")

        normalized_payload: dict[str, object] = {
            "product_id": product_id,
        }
        if "sku" in payload:
            normalized_payload["sku"] = self._sku(payload["sku"])
        if "slug" in payload:
            normalized_payload["slug"] = self._slug(payload["slug"])
        if "price_minor" in payload:
            normalized_payload["price_minor"] = self._price_minor(
                payload["price_minor"]
            )
        if "track_inventory" in payload:
            normalized_payload["track_inventory"] = self._track_inventory(
                payload["track_inventory"]
            )
        if "category_ids" in payload:
            normalized_payload["category_ids"] = self._category_ids(
                payload["category_ids"]
            )
        if "content" in payload:
            normalized_payload["content"] = self._content(
                payload["content"]
            )

        def mutation(connection):
            current = self._load(connection, product_id)

            sku = normalized_payload.get("sku", str(current["sku"]))
            slug = normalized_payload.get("slug", str(current["slug"]))
            price_minor = normalized_payload.get(
                "price_minor",
                int(current["price_minor"]),
            )
            track_inventory = normalized_payload.get(
                "track_inventory",
                bool(current["track_inventory"]),
            )
            content = normalized_payload.get("content")

            if (
                not isinstance(sku, str)
                or not isinstance(slug, str)
                or not isinstance(price_minor, int)
                or not isinstance(track_inventory, bool)
                or (content is not None and not isinstance(content, dict))
            ):
                raise ValueError("Normalized product update is invalid")

            self._assert_sku_available(
                connection,
                sku,
                current_id=product_id,
            )
            self._assert_slug_available(
                connection,
                slug,
                current_id=product_id,
            )

            category_ids = (
                normalized_payload["category_ids"]
                if "category_ids" in normalized_payload
                else self._category_rows(connection, product_id)
            )
            if not isinstance(category_ids, list):
                raise ValueError("Normalized product categories are invalid")
            self._assert_categories(connection, category_ids)

            now = self.application.clock.now().isoformat()
            if slug != str(current["slug"]):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO slug_history(
                        entity_type, entity_id, old_slug, created_at
                    ) VALUES ('product', ?, ?, ?)
                    """,
                    (
                        product_id,
                        str(current["slug"]),
                        now,
                    ),
                )

            connection.execute(
                """
                UPDATE products
                SET sku = ?,
                    slug = ?,
                    price_minor = ?,
                    track_inventory = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    sku,
                    slug,
                    price_minor,
                    1 if track_inventory else 0,
                    now,
                    product_id,
                ),
            )

            if "category_ids" in normalized_payload:
                self._replace_categories(
                    connection,
                    product_id,
                    category_ids,
                )

            response_language: str | None = None
            if content is not None:
                language_code = str(content["language_code"])
                response_language = language_code
                self._upsert_translation(
                    connection,
                    product_id,
                    content,
                    now,
                )

                legacy_language = current["legacy_language_code"]
                if (
                    legacy_language is None
                    or str(legacy_language) == language_code
                ):
                    connection.execute(
                        """
                        UPDATE products
                        SET name = ?,
                            short_description = ?,
                            description = ?,
                            legacy_language_code = COALESCE(
                                legacy_language_code,
                                ?
                            )
                        WHERE id = ?
                        """,
                        (
                            str(content["name"]),
                            str(content["short_description"]),
                            str(content["description"]),
                            language_code,
                            product_id,
                        ),
                    )

            row = (
                self._load_localized(
                    connection,
                    product_id,
                    response_language,
                )
                if response_language is not None
                else self._load(connection, product_id)
            )
            return {"product": self._row_to_product(row)}

        return run_idempotent(
            self.application,
            "product_update",
            normalized_payload,
            context,
            mutation,
        )

    def set_status(
        self,
        payload: dict[str, object],
        context,
    ) -> dict[str, object]:
        self._known_fields(payload, {"product_id", "status"})
        product_id = self._product_id(payload.get("product_id"))
        status = payload.get("status")
        if status not in {"draft", "active", "archived"}:
            raise ValueError("Product status is invalid")

        normalized_payload = {
            "product_id": product_id,
            "status": status,
        }

        def mutation(connection):
            current = self._load(connection, product_id)
            if str(current["status"]) != status:
                connection.execute(
                    """
                    UPDATE products
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        self.application.clock.now().isoformat(),
                        product_id,
                    ),
                )
            return {
                "product": self._row_to_product(
                    self._load(connection, product_id)
                )
            }

        return run_idempotent(
            self.application,
            "product_set_status",
            normalized_payload,
            context,
            mutation,
        )
