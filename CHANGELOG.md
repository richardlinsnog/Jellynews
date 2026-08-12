





# Changelog

All notable changes to JellyNews will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Custom logo upload** — upload a custom logo via Server Settings (PNG/JPEG, max 2 MB). Logo is embedded inline in emails via CID.
- **Thumbnail API for email images** — movie/series covers use Jellyfin thumbnail API (`fillHeight=300`) to reduce email size.
- **Image proxy** — backend serves proxied Jellyfin images via `/api/v1/images/proxy/{item_id}` to avoid broken images in email clients.
- **Popcorn emoji favicon** — 🍿 favicon added to the frontend.
- **Clickable server name** — email header server name is now a clickable link to the Jellyfin server.
- **Subscriber tag filtering** — case-insensitive tag matching when sending newsletters.
- **CustomNews integrated with newsletter** — scheduled articles are automatically included in newsletter footer and marked as `sent` after delivery.
- **Template safe globals** — `custom_news` variable allowlisted in Jinja2 sandbox.
- **Newsletter automation** — APScheduler background scheduler with configurable auto-send job (SQLite-compatible)
- **ntfy delivery channel** — push-based notification delivery via [ntfy.sh](https://ntfy.sh)
- **CustomNews status workflow** — Draft → Scheduled → Sent lifecycle with automatic transition
- **Premailer CSS inlining** — email CSS is inlined for better client compatibility
- **List-Unsubscribe header** — email channel sends `List-Unsubscribe` and `List-Unsubscribe-Post` headers
- **i18n infrastructure** — backend gettext with `.mo` preloading + lightweight Vue composable (en/pt-BR)
- **Template zip import** — `POST /api/v1/templates/import` with manifest validation, path traversal protection, 10 MB limit
- **Exponential backoff with jitter** — centralized retry (1s→2s→4s) across all delivery channels
- **Refresh token rotation** — `token_version` column invalidates old refresh tokens on password change; `POST /auth/change-password` endpoint
- **Jellyfin connection test** — Test Connection button in Setup wizard with instant feedback
- **LICENSE (MIT)** and **CONTRIBUTING.md**
- **Backup & restore documentation**

### Fixed

- TemplatesPage reload bug (wrong response property)
- TemplatesPage now includes zip import UI with success/error feedback
- **Security: authentication added to public list endpoints** — `GET /api/v1/subscribers`, `GET /api/v1/subscribers/tags`, and `GET /api/v1/news` now require a valid JWT token.
- **CustomNews HTML escaping** — `custom_news` in email templates is now marked as `Markup`-safe so HTML renders correctly.
- **Premailer CID protection** — `premailer` no longer strips `cid:` image references in email CSS.
- **SVG rejection** — logo upload rejects SVG files (PNG/JPEG only).

