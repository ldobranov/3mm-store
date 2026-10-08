# S1.4 — Store Settings

Status: **implemented; physical acceptance pending**

Version: `0.1.0-dev.8`

Branch: `s1/settings`

## Goal

Complete the Store-owned administrative settings surface without moving Store
configuration into 3mm Core.

S1.4 uses the existing Store SQLite tables introduced by revisions `0001`
and `0002`. No new migration is required, so the accepted storage revision
remains `0003`.

## Settings model

Language-independent settings live in `store_settings`:

```text
currency
public_base_url
```

Localized storefront content lives in `store_translations`:

```text
language_code
store_name
home_title
home_description
meta_title
meta_description
```

There are no `*_bg`, `*_en` or other language-specific columns. New
language packs do not require a Store migration.

The Settings UI discovers active languages through the existing 3mm
`/language/available` API. Removing a language pack hides that language from
the editor but does not delete the Store-owned translation row.

## Operations

S1.4 adds two administrator-only operations:

```text
store_settings_get
store_settings_update
```

`store_settings_get` is a query and forbids idempotency.

`store_settings_update` is a replay-safe command and can atomically update
global settings plus multiple language translations in one Store transaction.
This lets the browser preserve edits while moving between language tabs and
save all pending localized drafts together.

## Validation

Store enforces:

- currency as a canonical uppercase three-letter code;
- `public_base_url` as an optional HTTP(S) origin only;
- no path, query, fragment or credentials in `public_base_url`;
- bounded BCP47-like language codes;
- bounded public text and SEO fields;
- no duplicate language entries in one update;
- no arbitrary Store setting keys from the browser.

The initial effective currency is `EUR` even when no row has been written.
The initial public base URL is empty.

Changing the Store currency does not convert existing product prices.

## UI behavior

`/store/settings` now provides:

- Store currency;
- trusted public base origin;
- dynamically discovered content languages;
- localized Store name;
- localized home title and description;
- localized SEO title and description;
- per-language saved/unsaved indicators;
- preservation of unsaved language drafts while switching languages;
- one save action for all pending language drafts.

The UI follows the current 3mm display language until the administrator
explicitly chooses a different content language.

## Physical acceptance target

Before S1.4 is accepted:

1. upgrade the existing Store installation with `0.1.0-dev.8`;
2. confirm the migration journal remains `0001, 0002, 0003`;
3. save currency and public base URL;
4. edit at least two installed content languages without saving between tab
   switches and confirm both drafts survive;
5. save once and confirm both translations persist after reload;
6. confirm a removed language pack hides its editor without deleting its row;
7. restart the Store service and confirm settings persist;
8. confirm the administrator route remains inaccessible to non-admin users.

No Store-specific Core change is part of S1.4.
