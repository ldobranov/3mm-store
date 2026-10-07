# S1.5 — Public Catalog Rendering

Status: **implemented; physical acceptance pending**

Version: `0.1.0-dev.9`

Branch: `s1/public-catalog`

## Goal

Expose the first real Store-owned public catalog through the accepted 3mm
Milestone 19 Public Web Runtime, without registering Store routers in Core and
without exposing the administrative SPA.

S1.5 implements exactly three public GET/HEAD routes:

```text
/
/products/{slug}
/categories/{slug}
```

All three dispatch through the declared `render_public` Application Extension
query.

## Public operation contract

`render_public` uses the exact 3mm Application Public HTTP v1 request and
response schemas.

It accepts only the Core-projected public request fields:

```text
method
path
path_params
query
headers
```

and returns the closed public response model.

No Store-specific HTTP endpoint is added to 3mm Core.

## Visibility rules

Public rendering is fail-closed:

- only `active` products are rendered;
- only `active` categories are rendered;
- draft/archived products return 404;
- archived categories return 404;
- old product/category slugs redirect with 301 only while the target entity is
  still active;
- unknown slugs return 404;
- product lists are bounded.

The public renderer never exposes internal SQLite paths, operation errors,
application runtime details or administrator authentication state.

## Localized public content

Public content is selected from Store-owned translation rows.

Selection order is:

1. explicit bounded `?lang=<code>` when that language is available;
2. forwarded `Accept-Language` preferences;
3. English when available;
4. the first available Store content language;
5. legacy S0/S1 fallback content when no translation row exists.

BCP47-like regional codes may fall back to their primary language code.

The renderer does not read Core database tables and does not depend on a
Store-specific Core language API. Store management UI remains responsible for
discovering currently installed 3mm language packs. Persisted translations are
not deleted when a language pack is removed.

Language links use the same public route with `?lang=`, so one canonical Store
entity ID and slug remain language-independent in S1.

Localized slugs and language-prefixed route trees remain deferred.

## Store settings used

S1.5 consumes the Store-owned S1.4 settings:

```text
currency
public_base_url
store_name
home_title
home_description
meta_title
meta_description
```

`public_base_url` is the only source for absolute canonical URLs. The renderer
does not trust or infer the public origin from a Host header.

When no trusted public base origin is configured, the canonical link is omitted.

## HTML safety and transport

All Store-owned text inserted into HTML is escaped.

The page shell is self-contained and uses no external scripts or remote assets.
Product media remains outside S1.5 until the generic extension-media boundary is
accepted.

Responses use:

```text
Content-Type: text/html; charset=utf-8
Cache-Control: public, max-age=60
Content-Language: <selected language>
Vary: Accept-Language
```

HEAD uses the same rendered representation as GET; the 3mm Public Web Runtime
removes the body while retaining the corresponding Content-Length.

## Public pages

### Home

The home page renders:

- localized Store/home title and description;
- active categories;
- a bounded recent active-product set;
- localized names/descriptions;
- Store currency price formatting;
- language links for available Store content languages.

### Category

The category page renders:

- localized category name/description/SEO metadata;
- only active products assigned to that category;
- bounded product output;
- old-slug redirect while the category remains active.

### Product

The product page renders:

- localized product name;
- localized short/full description;
- localized SEO title/description;
- Store currency price;
- old-slug redirect while the product remains active.

No product image is rendered in S1.5 because media ingestion/serving remains the
separate generic G4 platform-gap candidate.

## Storage compatibility

S1.5 adds no database schema.

The accepted migration target remains:

```text
0001
0002
0003
```

Upgrading from S1.4 therefore must not add or re-run a Store migration.

## Automated verification

Tests cover:

- exact public route declaration in the install package;
- public operation declaration and audience;
- explicit language selection;
- Accept-Language selection;
- HTML escaping;
- trusted canonical URL generation;
- draft product exclusion;
- active-only category product listing;
- active old-slug redirects;
- archived-target redirect suppression;
- GET/HEAD representation equality;
- rejection of non-public direct service context.

The built ZIP is still validated by CI against the current real 3mm package
validator.

## Physical acceptance target

Before S1.5 is accepted on Raspberry:

1. upgrade the existing Store installation with `0.1.0-dev.9`;
2. confirm the Store service is active;
3. confirm migration journal remains exactly `0001, 0002, 0003`;
4. confirm the public listener serves `/`;
5. confirm an active product renders at `/products/<slug>`;
6. confirm an active category renders at `/categories/<slug>`;
7. confirm BG/EN content selection through `?lang=` and Accept-Language;
8. confirm draft/archived products and archived categories return 404;
9. change a product/category slug and confirm the old public URL returns 301;
10. archive the redirect target and confirm the historical URL returns 404;
11. confirm HEAD returns no body with the GET representation length;
12. stop only the Store service and confirm Admin/Core remains healthy while
    public Store requests fail closed;
13. restart Store and confirm the public routes recover.

No Store-specific Core change is part of S1.5.
