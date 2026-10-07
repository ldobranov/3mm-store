# S1.1b — Localization Foundation

Status: **implemented; physical acceptance pending**

Version: `0.1.0-dev.4`

Branch: `s1/categories`

## Goal

Make Store business content multilingual before Products are implemented.

UI language and Store content language are separate concerns:

- UI language controls buttons, labels and messages in the management screen;
- content language controls category/product/store text persisted by Store.

Store does not hardcode a fixed list such as BG/EN for business content.
The compiled UI reads the platform's current available-language registry from:

```text
GET /language/available
```

and presents those language codes as content tabs.

No Store-specific Core endpoint or Core database table is introduced.

## Storage revision 0002

Migration `0002` adds language-keyed Store-owned content while preserving the
accepted `0001` rows.

It creates:

```text
category_translations
product_translations
product_media_translations
store_translations
```

and adds nullable `legacy_language_code` markers to:

```text
categories
products
product_media
```

The translation tables use stable entity ID plus language code as identity.
Installing another language therefore does not require a Store schema migration.

### Category translations

```text
(category_id, language_code)
name
description
meta_title
meta_description
created_at
updated_at
```

### Product translations

Reserved now for S1.2:

```text
(product_id, language_code)
name
short_description
description
meta_title
meta_description
created_at
updated_at
```

### Product-media translations

Reserved for the accepted future media path:

```text
(media_id, language_code)
alt_text
created_at
updated_at
```

### Store translations

Reserved for Store settings/public home rendering:

```text
language_code
store_name
home_title
home_description
meta_title
meta_description
created_at
updated_at
```

## Language-code contract

Store persists normalized lower-case BCP-47-like language codes, for example:

```text
bg
en
de
pt-br
zh-hans
```

The service validates the language-code shape but does not ask Core whether a
language is currently installed.

That separation is intentional:

- the UI offers currently available 3mm languages;
- Store preserves translations when a language pack is disabled/uninstalled;
- reinstalling the language makes the preserved Store content available again;
- a Core language-pack lifecycle does not delete Store business data.

## Legacy 0001 content

Migration `0002` does **not** guess the language of existing untagged text.

For example an existing category:

```text
name = Абонаменти
legacy_language_code = NULL
```

is preserved exactly and no translation row is fabricated.

The Catalog editor presents the legacy value as a temporary fallback. The first
explicit save under a chosen language assigns that legacy content to the chosen
language and creates the real translation row.

New categories created after `0002` always create an explicit translation and
record that language as their legacy fallback language.

Legacy columns stay during S1 for safe backward compatibility. Translation
tables are authoritative for language-specific content.

## Category operation contract

S1.1b adds:

```text
catalog_get_category
```

and extends the existing category operations.

`catalog_list_categories` accepts optional `language_code`. It resolves the
requested translation and falls back to the preserved legacy text when a
translation is missing.

`category_create` now receives language-specific content explicitly:

```json
{
  "slug": "pampersi",
  "parent_id": null,
  "sort_order": 0,
  "content": {
    "language_code": "bg",
    "name": "Памперси",
    "description": "...",
    "meta_title": "...",
    "meta_description": "..."
  }
}
```

`category_update` can update structural fields and one explicit language in
the same replay-safe transaction.

Slug, parent, sort order and lifecycle status remain language-independent.

## Catalog UI

The Catalog screen now:

- discovers available content languages from 3mm dynamically;
- selects the current host language initially when available;
- shows one content tab per available language;
- marks persisted translations;
- keeps slug/parent/order shared across languages;
- edits name, description, SEO title and SEO description per language;
- lists/searches categories in the chosen content language;
- retains platform theme behavior and host UI-language behavior.

## Live display-language switching

The Catalog list follows the current 3mm UI language while the content-language selector has not been changed manually. Changing the host language therefore reloads category names/descriptions immediately without a browser refresh.

Once an operator explicitly selects another content language or editor tab, that choice is pinned for the current page session so a later UI-language change does not unexpectedly switch the record being edited.

This keeps UI language and content language separate while still making the normal display path feel native to 3mm.

## Slugs

Localized slugs are intentionally **not** part of S1.1b.

S1 keeps one canonical language-independent slug per category/product.
Localized URL paths, localized slug history, canonical/hreflang rules and
language-prefixed public routes belong to the later public SEO milestone.

This avoids coupling the first product implementation to an unfinished public
URL strategy.

## Upgrade acceptance

Physical acceptance for `0.1.0-dev.3` must prove:

1. upgrade from the existing `0001` database succeeds;
2. migration journal becomes exactly `0001, 0002`;
3. the existing category data is unchanged after migration;
4. no automatic language is assigned to legacy text;
5. available content tabs match the platform language registry;
6. saving the existing legacy category under BG creates a BG translation;
7. adding EN creates a second row without overwriting BG;
8. switching the 3mm display language changes the management list text immediately without refresh while content language is unpinned;
9. removing a language from the available-language registry does not delete its
   stored Store translation;
10. restart preserves all translations;
11. Core requires no Store-specific change.
