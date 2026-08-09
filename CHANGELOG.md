





# Changelog

All notable changes to JellyNews will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Newsletter automation** — APScheduler background scheduler with configurable auto-send job (SQLite-compatible)
- **ntfy delivery channel** — push-based notification delivery via [ntfy.sh](https://ntfy.sh)
- **CustomNews status workflow** — Draft → Scheduled → Sent lifecycle with automatic transition
- **Premailer CSS inlining** — email CSS is inlined for better client compatibility
- **List-Unsubscribe header** — email channel sends `List-Unsubscribe` and `List-Unsubscribe-Post` headers
- **i18n infrastructure** — backend gettext with `.mo` preloading + lightweight Vue composable (en/pt-BR)
- **Template zip import** — `POST /api/v1/templates/import` with manifest validation, path traversal protection, 10 MB limit
- **Exponential backoff with jitter** — centralized retry (1s→2s→4s) across all delivery channels
- **Refresh token rotation** — `token_version` column invalidates old refresh tokens on password change; `POST /auth/change-password` endpoint
- **Jellyfin connection test** — Test Connection button in Setup wizard with instant feedback
- **LICENSE (MIT)** and **CONTRIBUTING.md**
- **Backup & restore documentation**

### Fixed

- TemplatesPage reload bug (wrong response property)
- TemplatesPage now includes zip import UI with success/error feedback

