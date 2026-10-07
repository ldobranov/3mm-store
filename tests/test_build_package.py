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

            service_source = (
                package_builder.ROOT / "service/src/three_mm_store"
            )
            service_target = root / "service/src/three_mm_store"
            service_target.mkdir(parents=True, exist_ok=True)
            for source in sorted(service_source.glob("*.py")):
                text = source.read_text(encoding="utf-8")
                (service_target / source.name).write_bytes(
                    text.replace("\n", "\r\n").encode("utf-8")
                )

            frontend_source = package_builder.ROOT / "source/frontend"
            frontend_target = root / "source/frontend"
            frontend_target.mkdir(parents=True, exist_ok=True)
            for source in sorted(frontend_source.rglob("*")):
                if not source.is_file():
                    continue
                destination = frontend_target / source.relative_to(
                    frontend_source
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
                "catalog_get_category",
                "category_create",
                "category_update",
                "category_set_status",
                "catalog_list_products",
                "catalog_get_product",
                "product_create",
                "product_update",
                "product_set_status",
                "inventory_list",
                "inventory_adjust",
                "store_settings_get",
                "store_settings_update",
                "render_public",
            ],
        )

        catalog_operations = {
            "catalog_list_categories",
            "catalog_get_category",
            "category_create",
            "category_update",
            "category_set_status",
            "catalog_list_products",
            "catalog_get_product",
            "product_create",
            "product_update",
            "product_set_status",
        }
        inventory_operations = {"inventory_list", "inventory_adjust"}
        settings_operations = {
            "store_settings_get",
            "store_settings_update",
        }
        for operation in application["operations"][1:]:
            if operation["operation_id"] in settings_operations:
                self.assertEqual(
                    operation["audiences"],
                    ["administrator"],
                )
                self.assertNotIn("required_permission", operation)
                continue
            if operation["operation_id"] == "render_public":
                self.assertEqual(operation["audiences"], ["public"])
                self.assertNotIn("required_permission", operation)
                continue

            self.assertIn("operator", operation["audiences"])
            self.assertIn("administrator", operation["audiences"])
            if operation["operation_id"] in catalog_operations:
                self.assertEqual(
                    operation["required_permission"],
                    "catalog_manage",
                )
            if operation["operation_id"] in inventory_operations:
                self.assertEqual(
                    operation["required_permission"],
                    "inventory_manage",
                )
        self.assertEqual(
            [item["entrypoint_id"] for item in compiled_ui["entrypoints"]],
            ["catalog", "inventory", "settings"],
        )
        self.assertEqual(
            application["storage"]["schema_revision"],
            "0003",
        )
        self.assertFalse(
            application["storage"]["contains_personal_data"]
        )
        self.assertEqual(
            [route["path"] for route in application["public_http_routes"]],
            ["/", "/products/{slug}", "/categories/{slug}"],
        )
        public = next(
            operation
            for operation in application["operations"]
            if operation["operation_id"] == "render_public"
        )
        self.assertEqual(public["audiences"], ["public"])
        self.assertEqual(public["kind"], "query")
        self.assertEqual(public["idempotency"], "forbidden")

    def test_zip_metadata_is_platform_neutral(self) -> None:
        payload = build_package()

        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            self.assertTrue(entries)
            for item in entries:
                self.assertEqual(item.create_system, 3)
                self.assertEqual(item.create_version, 20)
                self.assertEqual(item.extract_version, 20)
                self.assertEqual(item.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(item.extra, b"")
                self.assertEqual(item.comment, b"")

            application = json.loads(
                archive.read("application-extension.json")
            )
            wheel = archive.read(application["service"]["artifact"])

        with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
            entries = archive.infolist()
            self.assertTrue(entries)
            for item in entries:
                self.assertEqual(item.create_system, 3)
                self.assertEqual(item.create_version, 20)
                self.assertEqual(item.extract_version, 20)
                self.assertEqual(item.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(item.extra, b"")
                self.assertEqual(item.comment, b"")

    def test_archives_use_stored_entries_for_cross_platform_identity(self) -> None:
        payload = build_package()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertTrue(
                all(
                    item.compress_type == zipfile.ZIP_STORED
                    for item in archive.infolist()
                )
            )

        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            application = json.loads(
                archive.read("application-extension.json")
            )
            wheel = archive.read(application["service"]["artifact"])

        with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
            self.assertTrue(
                all(
                    item.compress_type == zipfile.ZIP_STORED
                    for item in archive.infolist()
                )
            )

    def test_installable_zip_contains_only_expected_runtime_files(self) -> None:
        payload = build_package()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = set(archive.namelist())

        self.assertIn("manifest.json", names)
        self.assertIn("application-extension.json", names)
        self.assertIn("compiled-ui.json", names)
        self.assertIn("source/frontend/Catalog.vue", names)
        self.assertIn("source/frontend/ProductsPanel.vue", names)
        self.assertIn("source/frontend/Inventory.vue", names)
        self.assertIn("source/frontend/Settings.vue", names)
        self.assertIn("source/frontend/application-api.ts", names)
        self.assertIn("source/frontend/language.ts", names)
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
