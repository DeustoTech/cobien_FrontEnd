# Contacts Assets Module

This directory stores static assets and runtime-editable source data used by the
video-call contacts screen.

## Purpose

- Provide local contact images used by the contact cards UI.
- Provide a plain-text contact mapping file consumed by
  `app/videocall/contactScreen.py`.

## Files

- `list_contacts.txt`
  - Contact mapping source in `DisplayName=username` format.
  - Parsed at runtime by `load_contacts_from_file(...)`.

- `default_user.png`
  - Fallback image used when no per-contact image exists.

- `*.png`, `*.jpg`, `*.jpeg`, `*.bmp`, `*.gif`, `*.webp`
  - Optional per-contact image files.
  - Resolution key is based on normalized display name.

## Contact Mapping Format

Each non-empty line should follow:

```text
DisplayName=username
```

Examples:

```text
Jules=jules_pourret
Capucine=capucine
```

Notes:

- `DisplayName` is the UI label.
- `username` is the backend target for call notifications.
- Empty or malformed usernames are now rejected by the frontend loader and the
  contact is hidden from the UI.

## Image Resolution Rules

The loader:

1. Normalizes `DisplayName` (lowercase, no diacritics, alphanumeric only).
2. Searches `app/contacts` with this base name and supported extensions.
3. Falls back to `default_user.png` when no match is found.

Supported extension order:

1. `.png`
2. `.jpg`
3. `.jpeg`
4. `.PNG`
5. `.JPG`
6. `.JPEG`
7. `.bmp`
8. `.gif`
9. `.webp`

## Operational Notes

- This folder intentionally contains no Python logic.
- Runtime contact refresh is triggered by the contact screen lifecycle (`on_pre_enter`).
- Keep image file names aligned with normalized display names to avoid fallback usage.

## Known Technical Debt / Bad Practices

- Contacts source-of-truth is a plain text file (`list_contacts.txt`) without a formal schema.
- Validation now rejects empty or malformed usernames, but the format is still ad-hoc text.
- Contact logic lives in `app/videocall/contactScreen.py`, while assets live here, which increases cross-module coupling.
- Loader diagnostics rely on `print()` instead of structured logging and severity levels.
