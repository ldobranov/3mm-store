from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

import tools.build_package as package_builder
from tools.build_package import build_package, module_version, wheel_name


class PackageBuildTests(unittest.TestCase):
    def test_build_is_deterministic(self) -> None:
        self.assertEqual(build_package(), build_package())


    def test_build_is_identical_with_crlf_checkout(self) -> None:
        expected = build_package()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "VERSION",
                "manifest.json",
                "application-extension.json",
                "compiled-ui.json",
            ):
                shutil.copy2(package_builder.ROOT / name, root / name)

            for relative in (
                Path("service/src/three_mm_store"),
                Path("source/frontend"),
            ):
                target = root / relative
                target.mkdir(parents=True, exist_ok=True)
                for source in (package_builder.ROOT / relative).rglob("*"):
                    if not source.is_file():
                        continue
                    destination = target / source.relative_to(
                        package_builder.ROOT / relative
                    )
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    text = source.read_text(encoding="utf-8")
                    destination.write_bytes(
                        text.replace("\n", "\r\n").encode("utf-8")
                    )

            original_root = package_builder.ROOT
            package_builder.ROOT = root
            try:
                actual = package_builder.build_package()
            finally:
                package_builder.ROOT = original_root

        self.assertEqual(expected, actual)

    def test_package_identity_and_wheel_checksum_match(self) -> None:
        payload = build_package()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            application = json.loads(
                archive.read("application-extension.json")
            )
            compiled_ui = json.loads(archive.read("compiled-ui.json"))

            self.assertEqual(manifest["module_id"], "org.3mm.store")
            self.assertEqual(application["module_id"], "org.3mm.store")
            self.assertEqual(compiled_ui["module_id"], "org.3mm.store")
            self.assertEqual(manifest["version"], module_version())
            self.assertEqual(application["version"], module_version())
            self.assertEqual(compiled_ui["version"], module_version())

            artifact = application["service"]["artifact"]
            self.assertEqual(
                artifact,
                f"service/{wheel_name(module_version())}",
            )
            wheel = archive.read(artifact)
            self.assertEqual(
                hashlib.sha256(wheel).hexdigest(),
                application["service"]["artifact_sha256"],
            )

    def test_s11_category_contract_is_declared(self) -> None:
        payload = build_package()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            application = json.loads(
                archive.read("application-extension.json")
            )
            compiled_ui = json.loads(archive.read("compiled-ui.json"))

        self.assertEqual(
            manifest["permissions"],
            ["data.read", "data.write", "process.spawn"],
        )
        self.assertEqual(
            [item["operation_id"] for item in application["operations"]],
            [
                "health",
                "catalog_list_categories",
                "category_create",
                "category_update",
                "category_set_status",
            ],
        )
        for operation in application["operations"][1:]:
            self.assertIn("operator", operation["audiences"])
            self.assertIn("administrator", operation["audiences"])
            self.assertEqual(
                operation["required_permission"],
                "catalog_manage",
            )
        self.assertEqual(
            [item["entrypoint_id"] for item in compiled_ui["entrypoints"]],
            ["catalog", "inventory", "settings"],
        )
        self.assertEqual(
            application["storage"]["schema_revision"],
            "0001",
        )
        self.assertFalse(
            application["storage"]["contains_personal_data"]
        )

    def test_installable_zip_contains_only_expected_runtime_files(self) -> None:
        payload = build_package()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = set(archive.namelist())

        self.assertIn("manifest.json", names)
        self.assertIn("application-extension.json", names)
        self.assertIn("compiled-ui.json", names)
        self.assertIn("source/frontend/Catalog.vue", names)
        self.assertIn("source/frontend/Inventory.vue", names)
        self.assertIn("source/frontend/Settings.vue", names)
        self.assertTrue(
            any(
                name.startswith("service/three_mm_store-")
                for name in names
            )
        )
        self.assertFalse(any(name.startswith("tests/") for name in names))
        self.assertFalse(any(name.startswith("tools/") for name in names))


if __name__ == "__main__":
    unittest.main()
