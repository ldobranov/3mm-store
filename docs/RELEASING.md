# Releasing 3mm Store

3mm Store publishes installable versions through GitHub Releases, following the
same tagged-build model used by the other 3mm extensions.

## Release trigger

A release is created only from a pushed version tag:

```text
v<contents-of-VERSION>
```

Example:

```text
VERSION = 0.1.0-dev.1
tag     = v0.1.0-dev.1
```

The release workflow fails closed if the tag and `VERSION` differ.

## What the workflow does

The tagged workflow:

1. checks out the exact tagged Store commit;
2. checks out current 3mm contracts;
3. runs Store tests;
4. builds the installable ZIP twice and requires byte-for-byte equality;
5. validates the built package through the real 3mm package validator;
6. creates `SHA256SUMS`;
7. publishes both files as GitHub Release assets.

Published assets are:

```text
3mm-store-<version>.zip
SHA256SUMS
```

If `RELEASE_NOTES_<version>.md` exists, it is used as release notes.
Otherwise GitHub-generated notes are used.

## Important

Creating the workflow does not publish a release by itself.

Merging a branch also does not publish a release. Publication requires an
explicit version/tag decision and a pushed tag after the target commit is
accepted.
