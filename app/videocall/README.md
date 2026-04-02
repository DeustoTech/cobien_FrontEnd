# Videocall Module

## Overview

The `videocall` package contains frontend components and helpers required for
video call interactions:

- Contact selection and call request submission.
- User confirmation popup after call request dispatch.
- Standalone PyQt launcher embedding the web videocall portal.

## Files

- `contactScreen.py`: Contact cards and call-request UI flow.
- `request_call.py`: HTTP helper to notify backend/pizarra service.
- `confirmation_popup.py`: Call-sent confirmation modal.
- `videocall_launcher.py`: Full-screen PyQt web launcher for active calls.
- `README_videocall_english.md` / `README_videocall_spanish.md`: legacy docs.

## Runtime Responsibilities

1. User selects a contact from contact screen.
2. A call request notification is sent through backend API.
3. A visual confirmation popup is displayed.
4. Incoming call acceptance launches `videocall_launcher.py`.
5. Launcher opens portal URL, injects room/device prompt values, and logs call end duration.

## Known Technical Debt / Bad Practices

- Split documentation across legacy language-specific READMEs and code comments;
  no single canonical technical document existed before this file.
- Contact UI logic (`contactScreen.py`) remains large and strongly coupled to
  external resources (images, API, translations, logging).
- `videocall_launcher.py` mixes UI setup, backend notification, environment
  configuration, and logging concerns in one file.
- Error handling relies heavily on `print` statements instead of centralized
  structured logging.
- Some flows still depend on mutable global/runtime state and filesystem
  side-effects, making automated tests harder.
