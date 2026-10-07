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

    def test_store_ui_follows_host_language(self) -> None:
        language = (FRONTEND / "language.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("preferredLanguage", language)
        self.assertIn("language-changed", language)
        self.assertIn("normalizeLanguageCode", language)
        self.assertIn("useStoreLanguage", language)

        for name in ("Catalog.vue", "Inventory.vue", "Settings.vue"):
            source = (FRONTEND / name).read_text(encoding="utf-8")
            self.assertIn("useStoreLanguage", source)
            self.assertIn("t(", source)

    def test_catalog_discovers_content_languages_from_3mm(self) -> None:
        api = (FRONTEND / "application-api.ts").read_text(
            encoding="utf-8"
        )
        catalog = (FRONTEND / "Catalog.vue").read_text(
            encoding="utf-8"
        )

        self.assertIn("/language/available", api)
        self.assertIn("readInstalledLanguages", api)
        self.assertIn("installedLanguages", catalog)
        self.assertIn("contentLanguage", catalog)
        self.assertIn("catalog_get_category", catalog)
        self.assertIn("meta_title", catalog)
        self.assertIn("meta_description", catalog)
        self.assertIn("language_code", catalog)
        self.assertNotIn(
            "installedLanguages = ref<string[]>(['bg', 'en'])",
            catalog,
        )

    def test_catalog_follows_host_language_until_content_language_is_pinned(self) -> None:
        catalog = (FRONTEND / "Catalog.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn("watch(uiLanguage", catalog)
        self.assertIn("contentLanguageFollowsUi", catalog)
        self.assertIn("contentLanguageFollowsUi.value = false", catalog)
        self.assertIn(
            "contentLanguage.value = newLanguage",
            catalog,
        )
        self.assertIn(
            "await Promise.all([loadCategories(), loadAllCategories()])",
            catalog,
        )

    def test_localized_editor_preserves_unsaved_language_drafts(self) -> None:
        catalog = (FRONTEND / "Catalog.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn("localizedDrafts", catalog)
        self.assertIn("snapshotLocalizedDraft", catalog)
        self.assertIn("baselineForLanguage", catalog)
        self.assertIn("hasUnsavedDraft", catalog)
        self.assertIn(
            "snapshotLocalizedDraft(contentLanguage.value)",
            catalog,
        )
        self.assertIn(
            "const draft = localizedDrafts.value[code]",
            catalog,
        )
        self.assertIn(
            "delete remainingDrafts[savedLanguage]",
            catalog,
        )

    def test_products_use_localized_catalog_contract(self) -> None:
        catalog = (FRONTEND / "Catalog.vue").read_text(
            encoding="utf-8"
        )
        products = (FRONTEND / "ProductsPanel.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn("ProductsPanel", catalog)
        for operation in (
            "catalog_list_products",
            "catalog_get_product",
            "product_create",
            "product_update",
            "product_set_status",
        ):
            self.assertIn(operation, products)
        self.assertIn("readInstalledLanguages", products)
        self.assertIn("localizedDrafts", products)
        self.assertIn("snapshotLocalizedDraft", products)
        self.assertIn("category_ids", products)
        self.assertIn("price_minor", products)
        self.assertIn("track_inventory", products)

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
