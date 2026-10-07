"""Store-owned category domain and localized content operations."""

from __future__ import annotations

import re
import secrets

from .idempotency import run_idempotent


CATEGORY_ID = re.compile(r"^cat_[0-9a-f]{32}$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LANGUAGE_CODE = re.compile(
    r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$"
)

MAX_NAME = 160
MAX_DESCRIPTION = 5000
MAX_META_TITLE = 160
MAX_META_DESCRIPTION = 320
MAX_SLUG = 120
MAX_SEARCH = 120
MAX_SORT_ORDER = 100_000
MAX_OFFSET = 1_000_000


class CategoryService:
    def __init__(self, application) -> None:
        self.application = application

    @staticmethod
    def _known_fields(
        payload: dict[str, object],
        allowed: set[str],
    ) -> None:
        if set(payload) - allowed:
            raise ValueError("Category request contains unknown fields")

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
    def _slug(cls, value: object) -> str:
        slug = cls._text(value, "Category slug", maximum=MAX_SLUG)
        if SLUG.fullmatch(slug) is None:
            raise ValueError(
                "Category slug must contain lowercase letters, digits and hyphens"
            )
        return slug

    @classmethod
    def _language_code(cls, value: object) -> str:
        code = cls._text(
            value,
            "Language code",
            maximum=35,
        ).lower()
        if LANGUAGE_CODE.fullmatch(code) is None:
            raise ValueError("Language code is invalid")
        return code

    @classmethod
    def _content(cls, value: object) -> dict[str, str]:
        if not isinstance(value, dict):
            raise ValueError("Category content is required")
        cls._known_fields(
            value,
            {
                "language_code",
                "name",
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
                "Category name",
                maximum=MAX_NAME,
            ),
            "description": cls._text(
                value.get("description", ""),
                "Category description",
                maximum=MAX_DESCRIPTION,
                allow_empty=True,
            ),
            "meta_title": cls._text(
                value.get("meta_title", ""),
                "Category meta title",
                maximum=MAX_META_TITLE,
                allow_empty=True,
            ),
            "meta_description": cls._text(
                value.get("meta_description", ""),
                "Category meta description",
                maximum=MAX_META_DESCRIPTION,
                allow_empty=True,
            ),
        }

    @staticmethod
    def _category_id(value: object, *, nullable: bool = False) -> str | None:
        if value is None and nullable:
            return None
        if not isinstance(value, str) or CATEGORY_ID.fullmatch(value) is None:
            raise ValueError("Category ID is invalid")
        return value

    @staticmethod
    def _sort_order(value: object) -> int:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= MAX_SORT_ORDER
        ):
            raise ValueError("Category sort order is invalid")
        return value

    @staticmethod
    def _row_to_category(row) -> dict[str, object]:
        return {
            "category_id": str(row["id"]),
            "slug": str(row["slug"]),
            "name": str(row["name"]),
            "description": str(row["description"]),
            "parent_id": (
                str(row["parent_id"])
                if row["parent_id"] is not None
                else None
            ),
            "sort_order": int(row["sort_order"]),
            "status": str(row["status"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    @staticmethod
    def _translation_to_dict(row) -> dict[str, object]:
        return {
            "language_code": str(row["language_code"]),
            "name": str(row["name"]),
            "description": str(row["description"]),
            "meta_title": str(row["meta_title"]),
            "meta_description": str(row["meta_description"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    @staticmethod
    def _load(connection, category_id: str):
        row = connection.execute(
            """
            SELECT id, slug, name, description, parent_id, sort_order,
                   status, created_at, updated_at, legacy_language_code
            FROM categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Category was not found")
        return row

    @classmethod
    def _load_localized(
        cls,
        connection,
        category_id: str,
        language_code: str,
    ):
        row = connection.execute(
            """
            SELECT
                c.id,
                c.slug,
                COALESCE(t.name, c.name) AS name,
                COALESCE(t.description, c.description) AS description,
                c.parent_id,
                c.sort_order,
                c.status,
                c.created_at,
                c.updated_at
            FROM categories c
            LEFT JOIN category_translations t
              ON t.category_id = c.id
             AND t.language_code = ?
            WHERE c.id = ?
            """,
            (language_code, category_id),
        ).fetchone()
        if row is None:
            raise ValueError("Category was not found")
        return row

    @staticmethod
    def _translation_rows(connection, category_id: str):
        return connection.execute(
            """
            SELECT language_code, name, description, meta_title,
                   meta_description, created_at, updated_at
            FROM category_translations
            WHERE category_id = ?
            ORDER BY language_code
            """,
            (category_id,),
        ).fetchall()

    @staticmethod
    def _upsert_translation(
        connection,
        category_id: str,
        content: dict[str, str],
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO category_translations(
                category_id,
                language_code,
                name,
                description,
                meta_title,
                meta_description,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(category_id, language_code)
            DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                meta_title = excluded.meta_title,
                meta_description = excluded.meta_description,
                updated_at = excluded.updated_at
            """,
            (
                category_id,
                content["language_code"],
                content["name"],
                content["description"],
                content["meta_title"],
                content["meta_description"],
                now,
                now,
            ),
        )

    @staticmethod
    def _assert_slug_available(
        connection,
        slug: str,
        *,
        current_id: str | None = None,
    ) -> None:
        current = connection.execute(
            "SELECT id FROM categories WHERE slug = ?",
            (slug,),
        ).fetchone()
        if current is not None and str(current[0]) != current_id:
            raise ValueError("Category slug is already in use")

        historical = connection.execute(
            """
            SELECT entity_id
            FROM slug_history
            WHERE entity_type = 'category' AND old_slug = ?
            """,
            (slug,),
        ).fetchone()
        if historical is not None and str(historical[0]) != current_id:
            raise ValueError("Category slug is reserved by URL history")

    @classmethod
    def _assert_parent(
        cls,
        connection,
        parent_id: str | None,
        *,
        current_id: str | None,
        child_status: str,
    ) -> None:
        if parent_id is None:
            return

        parent = connection.execute(
            "SELECT id, parent_id, status FROM categories WHERE id = ?",
            (parent_id,),
        ).fetchone()
        if parent is None:
            raise ValueError("Parent category was not found")
        if child_status == "active" and str(parent["status"]) != "active":
            raise ValueError("An active category requires an active parent")

        seen: set[str] = set()
        cursor = parent_id
        while cursor is not None:
            if cursor == current_id:
                raise ValueError("Category hierarchy cannot contain a cycle")
            if cursor in seen:
                raise ValueError("Category hierarchy is invalid")
            seen.add(cursor)
            row = connection.execute(
                "SELECT parent_id FROM categories WHERE id = ?",
                (cursor,),
            ).fetchone()
            if row is None:
                raise ValueError("Category hierarchy is invalid")
            cursor = str(row[0]) if row[0] is not None else None

    def list_categories(
        self,
        payload: dict[str, object],
        _context,
    ) -> dict[str, object]:
        self._known_fields(
            payload,
            {
                "search",
                "status",
                "limit",
                "offset",
                "language_code",
            },
        )

        search = self._text(
            payload.get("search", ""),
            "Category search",
            maximum=MAX_SEARCH,
            allow_empty=True,
        )
        status = payload.get("status")
        if status is not None and status not in {"active", "archived"}:
            raise ValueError("Category status filter is invalid")

        language_code = (
            self._language_code(payload["language_code"])
            if "language_code" in payload
            else None
        )

        limit_value = payload.get("limit", 20)
        offset_value = payload.get("offset", 0)
        if (
            not isinstance(limit_value, int)
            or isinstance(limit_value, bool)
            or not 1 <= limit_value <= 100
        ):
            raise ValueError("Category list limit is invalid")
        if (
            not isinstance(offset_value, int)
            or isinstance(offset_value, bool)
            or not 0 <= offset_value <= MAX_OFFSET
        ):
            raise ValueError("Category list offset is invalid")

        join_sql = ""
        select_name = "c.name"
        select_description = "c.description"
        parameters: list[object] = []
        if language_code is not None:
            join_sql = """
                LEFT JOIN category_translations t
                  ON t.category_id = c.id
                 AND t.language_code = ?
            """
            select_name = "COALESCE(t.name, c.name)"
            select_description = "COALESCE(t.description, c.description)"
            parameters.append(language_code)

        where: list[str] = []
        where_parameters: list[object] = []
        if status is not None:
            where.append("c.status = ?")
            where_parameters.append(status)
        if search:
            where.append(
                f"(store_casefold({select_name}) LIKE ? "
                "OR store_casefold(c.slug) LIKE ?)"
            )
            pattern = f"%{search.casefold()}%"
            where_parameters.extend((pattern, pattern))

        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        select_sql = f"""
            SELECT
                c.id,
                c.slug,
                {select_name} AS name,
                {select_description} AS description,
                c.parent_id,
                c.sort_order,
                c.status,
                c.created_at,
                c.updated_at
            FROM categories c
            {join_sql}
            {where_sql}
            ORDER BY c.sort_order, {select_name}, c.id
            LIMIT ? OFFSET ?
        """
        count_sql = f"""
            SELECT COUNT(*)
            FROM categories c
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
            "items": [self._row_to_category(row) for row in rows],
            "total": total,
            "limit": limit_value,
            "offset": offset_value,
        }

    def get_category(
        self,
        payload: dict[str, object],
        _context,
    ) -> dict[str, object]:
        self._known_fields(payload, {"category_id"})
        category_id = self._category_id(payload.get("category_id"))

        with self.application.storage.transaction() as connection:
            current = self._load(connection, category_id)
            translations = self._translation_rows(
                connection,
                category_id,
            )
            return {
                "category": self._row_to_category(current),
                "legacy_language_code": (
                    str(current["legacy_language_code"])
                    if current["legacy_language_code"] is not None
                    else None
                ),
                "translations": [
                    self._translation_to_dict(row)
                    for row in translations
                ],
            }

    def create(
        self,
        payload: dict[str, object],
        context,
    ) -> dict[str, object]:
        self._known_fields(
            payload,
            {
                "slug",
                "parent_id",
                "sort_order",
                "content",
            },
        )
        slug = self._slug(payload.get("slug"))
        content = self._content(payload.get("content"))
        parent_id = self._category_id(
            payload.get("parent_id"),
            nullable=True,
        )
        sort_order = self._sort_order(payload.get("sort_order", 0))

        normalized_payload: dict[str, object] = {
            "slug": slug,
            "parent_id": parent_id,
            "sort_order": sort_order,
            "content": content,
        }

        def mutation(connection):
            self._assert_slug_available(connection, slug)
            self._assert_parent(
                connection,
                parent_id,
                current_id=None,
                child_status="active",
            )
            category_id = f"cat_{secrets.token_hex(16)}"
            now = self.application.clock.now().isoformat()
            connection.execute(
                """
                INSERT INTO categories(
                    id,
                    slug,
                    name,
                    description,
                    parent_id,
                    sort_order,
                    status,
                    created_at,
                    updated_at,
                    legacy_language_code
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    category_id,
                    slug,
                    content["name"],
                    content["description"],
                    parent_id,
                    sort_order,
                    now,
                    now,
                    content["language_code"],
                ),
            )
            self._upsert_translation(
                connection,
                category_id,
                content,
                now,
            )
            return {
                "category": self._row_to_category(
                    self._load_localized(
                        connection,
                        category_id,
                        content["language_code"],
                    )
                )
            }

        return run_idempotent(
            self.application,
            "category_create",
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
            "slug",
            "parent_id",
            "sort_order",
            "content",
        }
        self._known_fields(payload, {"category_id", *mutable})
        category_id = self._category_id(payload.get("category_id"))
        if not (set(payload) & mutable):
            raise ValueError("Category update contains no changes")

        normalized_payload: dict[str, object] = {
            "category_id": category_id,
        }
        if "slug" in payload:
            normalized_payload["slug"] = self._slug(payload["slug"])
        if "parent_id" in payload:
            normalized_payload["parent_id"] = self._category_id(
                payload["parent_id"],
                nullable=True,
            )
        if "sort_order" in payload:
            normalized_payload["sort_order"] = self._sort_order(
                payload["sort_order"]
            )
        if "content" in payload:
            normalized_payload["content"] = self._content(
                payload["content"]
            )

        def mutation(connection):
            current = self._load(connection, category_id)
            slug = normalized_payload.get(
                "slug",
                str(current["slug"]),
            )
            parent_id = normalized_payload.get(
                "parent_id",
                (
                    str(current["parent_id"])
                    if current["parent_id"] is not None
                    else None
                ),
            )
            sort_order = normalized_payload.get(
                "sort_order",
                int(current["sort_order"]),
            )
            content = normalized_payload.get("content")

            if (
                not isinstance(slug, str)
                or (parent_id is not None and not isinstance(parent_id, str))
                or not isinstance(sort_order, int)
                or (content is not None and not isinstance(content, dict))
            ):
                raise ValueError("Normalized category update is invalid")

            self._assert_slug_available(
                connection,
                slug,
                current_id=category_id,
            )
            self._assert_parent(
                connection,
                parent_id,
                current_id=category_id,
                child_status=str(current["status"]),
            )

            now = self.application.clock.now().isoformat()
            if slug != str(current["slug"]):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO slug_history(
                        entity_type, entity_id, old_slug, created_at
                    ) VALUES ('category', ?, ?, ?)
                    """,
                    (
                        category_id,
                        str(current["slug"]),
                        now,
                    ),
                )

            connection.execute(
                """
                UPDATE categories
                SET slug = ?,
                    parent_id = ?,
                    sort_order = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    slug,
                    parent_id,
                    sort_order,
                    now,
                    category_id,
                ),
            )

            response_language: str | None = None
            if content is not None:
                language_code = str(content["language_code"])
                response_language = language_code
                self._upsert_translation(
                    connection,
                    category_id,
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
                        UPDATE categories
                        SET name = ?,
                            description = ?,
                            legacy_language_code = COALESCE(
                                legacy_language_code,
                                ?
                            )
                        WHERE id = ?
                        """,
                        (
                            str(content["name"]),
                            str(content["description"]),
                            language_code,
                            category_id,
                        ),
                    )

            row = (
                self._load_localized(
                    connection,
                    category_id,
                    response_language,
                )
                if response_language is not None
                else self._load(connection, category_id)
            )
            return {
                "category": self._row_to_category(row)
            }

        return run_idempotent(
            self.application,
            "category_update",
            normalized_payload,
            context,
            mutation,
        )

    def set_status(
        self,
        payload: dict[str, object],
        context,
    ) -> dict[str, object]:
        self._known_fields(payload, {"category_id", "status"})
        category_id = self._category_id(payload.get("category_id"))
        status = payload.get("status")
        if status not in {"active", "archived"}:
            raise ValueError("Category status is invalid")

        normalized_payload = {
            "category_id": category_id,
            "status": status,
        }

        def mutation(connection):
            current = self._load(connection, category_id)
            if status == "active":
                parent_id = (
                    str(current["parent_id"])
                    if current["parent_id"] is not None
                    else None
                )
                self._assert_parent(
                    connection,
                    parent_id,
                    current_id=category_id,
                    child_status="active",
                )
            else:
                active_child = connection.execute(
                    """
                    SELECT 1
                    FROM categories
                    WHERE parent_id = ? AND status = 'active'
                    LIMIT 1
                    """,
                    (category_id,),
                ).fetchone()
                if active_child is not None:
                    raise ValueError(
                        "Archive active child categories first"
                    )

            if str(current["status"]) != status:
                connection.execute(
                    """
                    UPDATE categories
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        self.application.clock.now().isoformat(),
                        category_id,
                    ),
                )

            return {
                "category": self._row_to_category(
                    self._load(connection, category_id)
                )
            }

        return run_idempotent(
            self.application,
            "category_set_status",
            normalized_payload,
            context,
            mutation,
        )
