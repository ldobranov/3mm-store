"""Store-owned global and localized storefront settings."""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit, urlunsplit

from .idempotency import run_idempotent


LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")
CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")

MAX_STORE_NAME = 160
MAX_HOME_TITLE = 200
MAX_HOME_DESCRIPTION = 5000
MAX_META_TITLE = 160
MAX_META_DESCRIPTION = 320
MAX_PUBLIC_BASE_URL = 2048
MAX_TRANSLATIONS_PER_UPDATE = 64


class StoreSettingsService:
    def __init__(self, application) -> None:
        self.application = application

    @staticmethod
    def _known_fields(
        payload: dict[str, object],
        allowed: set[str],
    ) -> None:
        if set(payload) - allowed:
            raise ValueError("Store settings request contains unknown fields")

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
    def _currency(cls, value: object) -> str:
        currency = cls._text(
            value,
            "Currency",
            maximum=3,
        ).upper()
        if CURRENCY_CODE.fullmatch(currency) is None:
            raise ValueError("Currency must be a three-letter ISO code")
        return currency

    @classmethod
    def _public_base_url(cls, value: object) -> str:
        source = cls._text(
            value,
            "Public base URL",
            maximum=MAX_PUBLIC_BASE_URL,
            allow_empty=True,
        )
        if not source:
            return ""
        if any(character.isspace() for character in source):
            raise ValueError("Public base URL is invalid")

        try:
            parsed = urlsplit(source)
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("Public base URL is invalid") from exc

        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Public base URL must be an HTTP(S) origin without path, query or credentials"
            )

        return urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                "",
                "",
                "",
            )
        )

    @classmethod
    def _translation(cls, value: object) -> dict[str, str]:
        if not isinstance(value, dict):
            raise ValueError("Store translation is invalid")
        allowed = {
            "language_code",
            "store_name",
            "home_title",
            "home_description",
            "meta_title",
            "meta_description",
        }
        cls._known_fields(value, allowed)
        if "language_code" not in value:
            raise ValueError("Store translation language is required")

        translated_fields = allowed - {"language_code"}
        if not (set(value) & translated_fields):
            raise ValueError("Store translation contains no changes")

        normalized: dict[str, str] = {
            "language_code": cls._language_code(
                value["language_code"]
            ),
        }
        limits = {
            "store_name": ("Store name", MAX_STORE_NAME),
            "home_title": ("Home title", MAX_HOME_TITLE),
            "home_description": (
                "Home description",
                MAX_HOME_DESCRIPTION,
            ),
            "meta_title": ("Store meta title", MAX_META_TITLE),
            "meta_description": (
                "Store meta description",
                MAX_META_DESCRIPTION,
            ),
        }
        for field, (label, maximum) in limits.items():
            if field in value:
                normalized[field] = cls._text(
                    value[field],
                    label,
                    maximum=maximum,
                    allow_empty=True,
                )
        return normalized

    @classmethod
    def _translations(cls, value: object) -> list[dict[str, str]]:
        if not isinstance(value, list):
            raise ValueError("Store translations must be a list")
        if not 1 <= len(value) <= MAX_TRANSLATIONS_PER_UPDATE:
            raise ValueError("Store translations list is invalid")

        translations = [cls._translation(item) for item in value]
        codes = [item["language_code"] for item in translations]
        if len(codes) != len(set(codes)):
            raise ValueError("Store translation language is duplicated")
        return translations

    @staticmethod
    def _read_setting(
        connection,
        key: str,
        default: str,
    ) -> str:
        row = connection.execute(
            "SELECT value_json FROM store_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        try:
            value = json.loads(str(row[0]))
        except (TypeError, ValueError) as exc:
            raise ValueError("Stored Store setting is invalid") from exc
        if not isinstance(value, str):
            raise ValueError("Stored Store setting is invalid")
        return value

    @staticmethod
    def _write_setting(
        connection,
        key: str,
        value: str,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO store_settings(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key)
            DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (
                key,
                json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                now,
            ),
        )

    @staticmethod
    def _translation_to_dict(row) -> dict[str, object]:
        return {
            "language_code": str(row["language_code"]),
            "store_name": str(row["store_name"]),
            "home_title": str(row["home_title"]),
            "home_description": str(row["home_description"]),
            "meta_title": str(row["meta_title"]),
            "meta_description": str(row["meta_description"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    @classmethod
    def _snapshot(cls, connection) -> dict[str, object]:
        rows = connection.execute(
            """
            SELECT language_code, store_name, home_title,
                   home_description, meta_title, meta_description,
                   created_at, updated_at
            FROM store_translations
            ORDER BY language_code
            """
        ).fetchall()
        return {
            "currency": cls._read_setting(
                connection,
                "currency",
                "EUR",
            ),
            "public_base_url": cls._read_setting(
                connection,
                "public_base_url",
                "",
            ),
            "translations": [
                cls._translation_to_dict(row)
                for row in rows
            ],
        }

    @staticmethod
    def _upsert_translation(
        connection,
        content: dict[str, str],
        now: str,
    ) -> None:
        current = connection.execute(
            """
            SELECT store_name, home_title, home_description,
                   meta_title, meta_description
            FROM store_translations
            WHERE language_code = ?
            """,
            (content["language_code"],),
        ).fetchone()
        values = {
            "store_name": str(current["store_name"]) if current else "",
            "home_title": str(current["home_title"]) if current else "",
            "home_description": (
                str(current["home_description"]) if current else ""
            ),
            "meta_title": str(current["meta_title"]) if current else "",
            "meta_description": (
                str(current["meta_description"]) if current else ""
            ),
        }
        values.update(
            {
                key: value
                for key, value in content.items()
                if key != "language_code"
            }
        )

        connection.execute(
            """
            INSERT INTO store_translations(
                language_code,
                store_name,
                home_title,
                home_description,
                meta_title,
                meta_description,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(language_code)
            DO UPDATE SET
                store_name = excluded.store_name,
                home_title = excluded.home_title,
                home_description = excluded.home_description,
                meta_title = excluded.meta_title,
                meta_description = excluded.meta_description,
                updated_at = excluded.updated_at
            """,
            (
                content["language_code"],
                values["store_name"],
                values["home_title"],
                values["home_description"],
                values["meta_title"],
                values["meta_description"],
                now,
                now,
            ),
        )

    def get_settings(
        self,
        payload: dict[str, object],
        _context,
    ) -> dict[str, object]:
        self._known_fields(payload, set())
        with self.application.storage.transaction() as connection:
            return self._snapshot(connection)

    def update(
        self,
        payload: dict[str, object],
        context,
    ) -> dict[str, object]:
        self._known_fields(
            payload,
            {"currency", "public_base_url", "translations"},
        )
        if not payload:
            raise ValueError("Store settings update contains no changes")

        normalized: dict[str, object] = {}
        if "currency" in payload:
            normalized["currency"] = self._currency(payload["currency"])
        if "public_base_url" in payload:
            normalized["public_base_url"] = self._public_base_url(
                payload["public_base_url"]
            )
        if "translations" in payload:
            normalized["translations"] = self._translations(
                payload["translations"]
            )

        def mutation(connection):
            now = self.application.clock.now().isoformat()
            currency = normalized.get("currency")
            if isinstance(currency, str):
                self._write_setting(
                    connection,
                    "currency",
                    currency,
                    now,
                )
            public_base_url = normalized.get("public_base_url")
            if isinstance(public_base_url, str):
                self._write_setting(
                    connection,
                    "public_base_url",
                    public_base_url,
                    now,
                )
            translations = normalized.get("translations")
            if isinstance(translations, list):
                for translation in translations:
                    if not isinstance(translation, dict):
                        raise ValueError("Normalized Store translation is invalid")
                    self._upsert_translation(
                        connection,
                        translation,
                        now,
                    )
            return self._snapshot(connection)

        return run_idempotent(
            self.application,
            "store_settings_update",
            normalized,
            context,
            mutation,
        )
