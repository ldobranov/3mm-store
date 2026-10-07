#!/usr/bin/env python3
"""Build a deterministic 3mm Store Application Extension package."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def module_version() -> str:
    value = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if SEMVER.fullmatch(value) is None:
        raise ValueError("VERSION must be valid SemVer")
    return value


def wheel_version(version: str) -> str:
    match = SEMVER.fullmatch(version)
    if match is None:
        raise ValueError("version must be valid SemVer")
    base = ".".join(match.group(index) for index in (1, 2, 3))
    prerelease = match.group(4)
    if prerelease is None:
        return base
    if prerelease.startswith("dev."):
        return base + ".dev" + prerelease.removeprefix("dev.")
    return base + ".dev0"


def wheel_name(version: str) -> str:
    return f"three_mm_store-{wheel_version(version)}-py3-none-any.whl"


def _write(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    # Stored entries avoid zlib-version/platform differences in compressed bytes.
    # Package size is small; cross-platform byte identity is more valuable here.
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, payload)


def _text_bytes(path: Path) -> bytes:
    """Return canonical UTF-8/LF bytes independent of checkout line endings."""
    text = path.read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def build_wheel(version: str) -> bytes:
    package_root = ROOT / "service" / "src" / "three_mm_store"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path in sorted(package_root.glob("*.py")):
            _write(
                archive,
                f"three_mm_store/{path.name}",
                _text_bytes(path),
            )

        dist_info = f"three_mm_store-{wheel_version(version)}.dist-info"
        metadata = (
            "Metadata-Version: 2.1\n"
            "Name: three-mm-store\n"
            f"Version: {wheel_version(version)}\n"
        ).encode("utf-8")
        wheel = (
            "Wheel-Version: 1.0\n"
            "Generator: 3mm-store\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode("utf-8")

        _write(archive, f"{dist_info}/METADATA", metadata)
        _write(archive, f"{dist_info}/WHEEL", wheel)
        _write(archive, f"{dist_info}/RECORD", b"")
    return output.getvalue()


def build_package(version: str | None = None) -> bytes:
    selected_version = version or module_version()

    manifest = json.loads(
        (ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    application = json.loads(
        (ROOT / "application-extension.json").read_text(encoding="utf-8")
    )
    compiled_ui = json.loads(
        (ROOT / "compiled-ui.json").read_text(encoding="utf-8")
    )

    manifest["version"] = selected_version
    application["version"] = selected_version
    compiled_ui["version"] = selected_version

    wheel = build_wheel(selected_version)
    artifact = f"service/{wheel_name(selected_version)}"
    application["service"]["artifact"] = artifact
    application["service"]["artifact_sha256"] = hashlib.sha256(
        wheel
    ).hexdigest()

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, value in (
            ("manifest.json", manifest),
            ("application-extension.json", application),
            ("compiled-ui.json", compiled_ui),
        ):
            _write(
                archive,
                name,
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
        _write(archive, artifact, wheel)

        frontend_root = ROOT / "source" / "frontend"
        for path in sorted(frontend_root.rglob("*")):
            if path.is_file():
                _write(
                    archive,
                    path.relative_to(ROOT).as_posix(),
                    _text_bytes(path),
                )

    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "3mm-store.zip",
    )
    parser.add_argument("--version")
    arguments = parser.parse_args()

    payload = build_package(arguments.version)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(payload)

    print(f"package: {arguments.output}")
    print(f"version: {arguments.version or module_version()}")
    print(f"sha256: {hashlib.sha256(payload).hexdigest()}")
    print(f"bytes: {len(payload)}")


if __name__ == "__main__":
    main()
