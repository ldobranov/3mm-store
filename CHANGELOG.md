# Changelog

All notable changes to 3mm Store will be documented here.

## Unreleased

### Added

- Initial repository and S0 architecture baseline.
- Reviewed Store Application Extension guide.
- Generic platform gap audit.
- S0.1 catalog contract covering IDs/slugs, money, Store settings, SQLite schema, permissions, operation inventory, public routes and lifecycle.
- Confirmed product-media ingestion as a generic platform-gap candidate instead of introducing a Store-specific Core upload path.
- S0.2 deterministic installable package foundation with health service, migration `0001`, compiled UI route placeholders, build tests and local 3mm-validator helper.
- S0 physical Raspberry acceptance for package `0.1.0-dev.0`.
- S1.1 category management operations, replay-safe Store idempotency, category hierarchy/slug-history rules and functional Catalog UI.
- CI validation of the built Store ZIP against the current 3mm package contract.
- Cross-platform byte-identical package archives independent of checkout line endings and zlib implementation.
- GitHub Release workflow that publishes versioned Store ZIP and SHA256SUMS from explicit version tags.
- S1.1 compiled UI now resolves the 3mm backend through runtime configuration, follows the host BG/EN language event, and uses platform theme tokens in light and dark themes.\n- S1.1b localization foundation with schema revision `0002`, language-keyed Store content, dynamic platform language discovery and multilingual category/SEO editing.
