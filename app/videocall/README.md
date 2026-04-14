# Videocall Module

## Overview

The `videocall` package contains frontend components and helpers required for
video call interactions:

- Contact selection and call request submission.
- Progress, success, and failure popups for outgoing call requests.
- Standalone PyQt launcher embedding the web videocall portal.

## Files

- `contactScreen.py`: Contact cards and call-request UI flow.
- `request_call.py`: HTTP helper to notify backend/pizarra service and classify failures.
- `confirmation_popup.py`: Progress/success/failure modals for outgoing requests.
- `videocall_launcher.py`: Full-screen PyQt web launcher for active calls.
- `README_videocall_spanish.md` / `README_videocall_french.md`: user-facing flow docs.

## Runtime Responsibilities

1. User selects a contact from contact screen.
2. A call request notification is sent through backend API.
3. A blocking progress popup is displayed while the request is in flight.
4. A success or error popup is displayed.
5. Incoming call acceptance launches `videocall_launcher.py`.
6. Launcher opens portal URL, injects room/device prompt values, and logs call end duration.

## Error Codes

Outgoing call requests now classify failures and expose short codes in the UI details panel:

- `VC-CONFIG`: missing `notify_api_key`
- `VC-DEVICE`: missing `device_id`
- `VC-USER`: invalid or empty contact destination
- `VC-TIMEOUT`: backend timeout
- `VC-NET`: connection failure
- `VC-REQ`: generic request-layer failure
- `VC-<HTTP_STATUS>`: backend HTTP rejection
- `VC-UNK`: unclassified exception

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
