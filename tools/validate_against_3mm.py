#!/usr/bin/env python3
"""Validate a built Store ZIP against a local checkout of current 3mm."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--core-root",
        type=Path,
        default=Path("../3mm"),
        help="Path to a 3mm source checkout.",
    )
    parser.add_argument(
        "--package",
        type=Path,
        default=Path("dist/3mm-store.zip"),
    )
    parser.add_argument(
        "--core-version",
        default="0.3.0",
    )
    arguments = parser.parse_args()

    core_root = arguments.core_root.resolve()
    package = arguments.package.resolve()
    if not core_root.is_dir():
        raise SystemExit(f"3mm checkout not found: {core_root}")
    if not package.is_file():
        raise SystemExit(f"Store package not found: {package}")

    sys.path.insert(0, str(core_root))
    from backend.services.module_packages import validate_module_package

    validated = validate_module_package(
        package.read_bytes(),
        architecture="aarch64",
        protocol_version="1.0",
        core_version=arguments.core_version,
    )
    definition = validated.application_extension
    if definition is None:
        raise SystemExit("package is not an Application Extension")

    print("VALID")
    print(f"module_id: {validated.manifest.module_id}")
    print(f"version: {validated.manifest.version}")
    print(f"sha256: {validated.sha256}")
    print(f"operations: {len(definition.operations)}")
    print(f"routes: {len(definition.routes)}")
    print(f"storage_revision: {definition.storage.schema_revision}")


if __name__ == "__main__":
    main()
