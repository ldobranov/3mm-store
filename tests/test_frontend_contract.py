from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "source" / "frontend"


class FrontendHostContractTests(unittest.TestCase):
    def test_catalog_uses_runtime_backend_transport(self) -> None:
        source = (FRONTEND / "application-api.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("fetch('/runtime-config.json'", source)
        self.assertIn("configuration.backend_url", source)
        self.assertIn("configuration.backend_port", source)
        self.assertIn("backendBase", source)
        self.assertIn("/api/v1/application-extensions/", source)
        self.assertIn("org.3mm.store", source)

        catalog = (FRONTEND / "Catalog.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn("invokeApplicationOperation", catalog)
        self.assertNotIn(
            "fetch(\n    `/api/v1/application-extensions",
            catalog,
        )

    def test_store_ui_follows_host_language(self) -> None:
        language = (FRONTEND / "language.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("preferredLanguage", language)
        self.assertIn("language-changed", language)
        self.assertIn("useStoreLanguage", language)

        for name in ("Catalog.vue", "Inventory.vue", "Settings.vue"):
            source = (FRONTEND / name).read_text(encoding="utf-8")
            self.assertIn("useStoreLanguage", source)
            self.assertIn("t(", source)

    def test_store_ui_uses_platform_theme_tokens(self) -> None:
        catalog = (FRONTEND / "Catalog.vue").read_text(
            encoding="utf-8"
        )
        for token in (
            "--text-primary",
            "--text-secondary",
            "--card-bg",
            "--card-border",
            "--input-bg",
            "--input-border",
            "--button-primary-bg",
            "--button-primary-text",
        ):
            self.assertIn(token, catalog)

        self.assertNotIn("background: var(--surface-color", catalog)
        self.assertNotIn("border-color: var(--border-color", catalog)

        for name in ("Inventory.vue", "Settings.vue"):
            source = (FRONTEND / name).read_text(encoding="utf-8")
            self.assertIn("--card-bg", source)
            self.assertIn("--card-border", source)
            self.assertIn("--text-primary", source)


if __name__ == "__main__":
    unittest.main()
