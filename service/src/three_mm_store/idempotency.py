"""Replay-safe Store command helper."""

from __future__ import annotations

import hashlib
import json
from typing import Callable


def _canonical(value: dict[str, object]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def run_idempotent(
    application,
    operation_id: str,
    payload: dict[str, object],
    context,
    callback: Callable,
) -> dict[str, object]:
    key = context.idempotency_key
    user_id = context.user_id
    if not isinstance(key, str) or len(key) < 8:
        raise ValueError("A valid idempotency key is required")
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise ValueError("An authenticated Store actor is required")

    actor_key = f"user:{user_id}"
    request_hash = hashlib.sha256(
        _canonical(payload).encode("utf-8")
    ).hexdigest()

    with application.storage.transaction() as connection:
        previous = connection.execute(
            """
            SELECT request_hash, response_json
            FROM idempotency_records
            WHERE operation_id = ?
              AND actor_key = ?
              AND idempotency_key = ?
            """,
            (operation_id, actor_key, key),
        ).fetchone()
        if previous is not None:
            if str(previous[0]) != request_hash:
                raise ValueError(
                    "Idempotency key was reused with another request"
                )
            result = json.loads(str(previous[1]))
            if not isinstance(result, dict):
                raise ValueError("Stored idempotency result is invalid")
            return result

        result = callback(connection)
        if not isinstance(result, dict):
            raise ValueError("Store command returned an invalid result")
        connection.execute(
            """
            INSERT INTO idempotency_records(
                operation_id,
                actor_key,
                idempotency_key,
                request_hash,
                response_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                operation_id,
                actor_key,
                key,
                request_hash,
                _canonical(result),
                application.clock.now().isoformat(),
            ),
        )
        return result
