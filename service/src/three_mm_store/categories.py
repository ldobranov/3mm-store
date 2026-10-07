"""Store-owned category domain and operations."""

from __future__ import annotations

import re
import secrets

from .idempotency import run_idempotent


CATEGORY_ID = re.compile(r"^cat_[0-9a-f]{32}$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MAX_NAME = 160
MAX_DESCRIPTION = 5000
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
    def _load(connection, category_id: str):
        row = connection.execute(
            """
            SELECT id, slug, name, description, parent_id, sort_order,
                   status, created_at, updated_at
            FROM categories
            WHERE id = ?
            """,
            (category_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Category was not found")
        return row

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
            {"search", "status", "limit", "offset"},
        )

        search_value = payload.get("search", "")
        search = self._text(
            search_value,
            "Category search",
            maximum=MAX_SEARCH,
            allow_empty=True,
        )
        status = payload.get("status")
        if status is not None and status not in {"active", "archived"}:
            raise ValueError("Category status filter is invalid")

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

        where: list[str] = []
        parameters: list[object] = []
        if status is not None:
            where.append("status = ?")
            parameters.append(status)
        if search:
            where.append(
                "(store_casefold(name) LIKE ? OR store_casefold(slug) LIKE ?)"
            )
            pattern = f"%{search.casefold()}%"
            parameters.extend((pattern, pattern))

        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        select_sql = f"""
            SELECT id, slug, name, description, parent_id, sort_order,
                   status, created_at, updated_at
            FROM categories
            {where_sql}
            ORDER BY sort_order, name, id
            LIMIT ? OFFSET ?
        """
        count_sql = f"SELECT COUNT(*) FROM categories{where_sql}"

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
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                select_sql,
                [*parameters, limit_value, offset_value],
            ).fetchall()

        return {
            "items": [self._row_to_category(row) for row in rows],
            "total": total,
            "limit": limit_value,
            "offset": offset_value,
        }

    def create(
        self,
        payload: dict[str, object],
        context,
    ) -> dict[str, object]:
        self._known_fields(
            payload,
            {"name", "slug", "description", "parent_id", "sort_order"},
        )
        name = self._text(
            payload.get("name"),
            "Category name",
            maximum=MAX_NAME,
        )
        slug = self._slug(payload.get("slug"))
        description = self._text(
            payload.get("description", ""),
            "Category description",
            maximum=MAX_DESCRIPTION,
            allow_empty=True,
        )
        parent_id = self._category_id(
            payload.get("parent_id"),
            nullable=True,
        )
        sort_order = self._sort_order(payload.get("sort_order", 0))

        normalized_payload = {
            "name": name,
            "slug": slug,
            "description": description,
            "parent_id": parent_id,
            "sort_order": sort_order,
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
                    id, slug, name, description, parent_id, sort_order,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    category_id,
                    slug,
                    name,
                    description,
                    parent_id,
                    sort_order,
                    now,
                    now,
                ),
            )
            return {
                "category": self._row_to_category(
                    self._load(connection, category_id)
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
            "name",
            "slug",
            "description",
            "parent_id",
            "sort_order",
        }
        self._known_fields(payload, {"category_id", *mutable})
        category_id = self._category_id(payload.get("category_id"))
        if not (set(payload) & mutable):
            raise ValueError("Category update contains no changes")

        normalized_payload: dict[str, object] = {
            "category_id": category_id,
        }
        if "name" in payload:
            normalized_payload["name"] = self._text(
                payload["name"],
                "Category name",
                maximum=MAX_NAME,
            )
        if "slug" in payload:
            normalized_payload["slug"] = self._slug(payload["slug"])
        if "description" in payload:
            normalized_payload["description"] = self._text(
                payload["description"],
                "Category description",
                maximum=MAX_DESCRIPTION,
                allow_empty=True,
            )
        if "parent_id" in payload:
            normalized_payload["parent_id"] = self._category_id(
                payload["parent_id"],
                nullable=True,
            )
        if "sort_order" in payload:
            normalized_payload["sort_order"] = self._sort_order(
                payload["sort_order"]
            )

        def mutation(connection):
            current = self._load(connection, category_id)
            name = normalized_payload.get("name", str(current["name"]))
            slug = normalized_payload.get("slug", str(current["slug"]))
            description = normalized_payload.get(
                "description",
                str(current["description"]),
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

            if (
                not isinstance(name, str)
                or not isinstance(slug, str)
                or not isinstance(description, str)
                or (parent_id is not None and not isinstance(parent_id, str))
                or not isinstance(sort_order, int)
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
                        self.application.clock.now().isoformat(),
                    ),
                )

            connection.execute(
                """
                UPDATE categories
                SET slug = ?,
                    name = ?,
                    description = ?,
                    parent_id = ?,
                    sort_order = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    slug,
                    name,
                    description,
                    parent_id,
                    sort_order,
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
