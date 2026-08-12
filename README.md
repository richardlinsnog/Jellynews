




# 🐙 JellyNews

<p align="center">
  <strong>Self-hosted newsletter service for Jellyfin</strong><br>
  Keep your users informed about new media, library updates, and custom news — via email, Telegram, and more.
</p>

<p align="center">
  <a href="#quick-start"><strong>Quick Start</strong></a> •
  <a href="#features">Features</a> •
  <a href="#security-warning">⚠️ Security</a> •
  <a href="docs/API.md">API</a> •
  <a href="docs/CONTRIBUTING.md">Contributing</a>
</p>

---

> ⚠️ **Security Warning — Please Read**
>
> JellyNews is in early development and has **not been through a formal community security audit**. While development-level tests have been performed (SQL injection, auth bypass, XSS, JWT validation, rate limiting), undiscovered vulnerabilities may exist.
>
> **We currently recommend local-only use** (e.g. behind a VPN or on your home network). All features work fully in local mode — the only exception is the **email unsubscribe link**, which requires public access for recipients to opt out.
>
> Once the codebase receives more community scrutiny and testing, this warning will be removed. If you discover a vulnerability, please report it privately via GitHub.

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/richardlinsnog/Jellynews.git
cd jellynews
cp .env.example .env
# Edit .env — set APP_SECRET_KEY (optionally also SECRETS_ENCRYPTION_KEY for production)

# 2. Start
docker compose up -d

# 3. Open http://localhost:8000 and complete the setup wizard
```

**That's it.** No manual database creation, no admin password in environment variables, no external services required.

---

## Features

- 📊 **Jellyfin content sync** — automatically queries Jellyfin API to discover new media (movies, series, audio). Manual send via Dashboard button. *(Automated scheduling coming in a future release.)*
- ✍️ **Custom news** — rich-text editor (TipTap), HTML sanitization via nh3, Draft→Scheduled→Sent workflow
- 🖼️ **Inline images** — movie/series covers embedded via CID, custom logo upload, thumbnail API for smaller emails
- 🖥️ **Image proxy** — backend proxies Jellyfin images so they never break in email clients
- 📬 **Multi-channel delivery** — Email (SMTP) and Telegram are well tested. Discord, ntfy, and webhook channels are implemented but have not been thoroughly tested — your feedback is greatly appreciated!
- 🎨 **Plugin-based templates** — Jinja2 with sandbox; community-contributed templates via `templates/` directory
- 🔐 **Security-first** — Argon2 password hashing, encrypted secrets vault, CSP headers, rate limiting, audit trail
- 🐳 **Single `docker compose up`** — multi-stage image, non-root user, SQLite (no external DB needed)
- 🧩 **Extensible** — add channels and templates without touching core code

---

## Architecture

```
jellynews/
├── backend/          # FastAPI (Python 3.12) — async, SQLAlchemy + SQLite
├── frontend/         # Vue 3 + Tailwind + TipTap
├── docs/             # Specifications, API docs, contributing guide
└── data/             # SQLite database + media cache (the only persistent volume)
```

See [`docs/jellynews-spec-tecnica.md`](docs/jellynews-spec-tecnica.md) for the full technical specification.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_SECRET_KEY` | **Yes** | — | 64+ char random string for JWT signing |
| `SECRETS_ENCRYPTION_KEY` | No | — | 32-byte base64 key for encrypting stored credentials (derived from APP_SECRET_KEY if unset; set a static key in production) |
| `APP_ENV` | No | `production` | `development` or `production` |
| `PORT` | No | `8000` | HTTP port |
| `DATABASE_PATH` | No | `data/jellynews.db` | SQLite path |
| `HEALTHCHECK_ENABLED` | No | `true` | Enable `/healthz` endpoint |

See `.env.example` for the full list.

---

## Minimum Requirements

- **Docker** 24+ and **Docker Compose** v2
- 256 MB RAM, 1 CPU core
- Jellyfin 10.8+ (with API key)

Non-Docker deployments: Python 3.12 + Node 22 — see [Contributing](docs/CONTRIBUTING.md).

---

## Security

> ⚠️ See the [security warning](#-security-warning---please-read) at the top of this README.

- **Authentication**: JWT access + refresh tokens, Argon2id password hashing
- **Secrets**: Channel credentials encrypted at rest (AES-256-GCM via cryptography)
- **Templates**: Jinja2 sandbox — no filesystem access, no network calls
- **HTML sanitization**: nh3 (Rust-backed, ~100x faster than bleach)
- **Rate limiting**: SlowAPI on auth and mutation endpoints
- **Audit trail**: Every mutation on Channel/Secret/Template/CustomNews is logged
- **CSP headers**: Content-Security-Policy with strict defaults

Report vulnerabilities privately via GitHub.

---

## License

MIT — see [LICENSE](LICENSE).

Built for the Jellyfin community. PRs welcome!



