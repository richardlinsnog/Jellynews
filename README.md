




# 🐙 JellyNews

<p align="center">
  <strong>Self-hosted newsletter service for Jellyfin</strong><br>
  Keep your users informed about new media, library updates, and custom news — via email, Telegram, Discord, ntfy, or any webhook.
</p>

<p align="center">
  <a href="#quick-start"><strong>Quick Start</strong></a> •
  <a href="#features">Features</a> •
  <a href="docs/API.md">API</a> •
  <a href="docs/CONTRIBUTING.md">Contributing</a>
</p>

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/your-org/jellynews.git
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

- 📰 **Automated newsletters** — new Jellyfin content delivered on a schedule you define
- ✍️ **Custom news** — rich-text editor (TipTap), HTML sanitization via nh3
- 📬 **Multi-channel delivery** — Email (SMTP), Telegram, Discord, ntfy, generic webhooks
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

- **Authentication**: JWT access + refresh tokens, Argon2id password hashing
- **Secrets**: Channel credentials encrypted at rest (AES-256-GCM via cryptography)
- **Templates**: Jinja2 sandbox — no filesystem access, no network calls
- **HTML sanitization**: nh3 (Rust-backed, ~100x faster than bleach)
- **Rate limiting**: SlowAPI on auth and mutation endpoints
- **Audit trail**: Every mutation on Channel/Secret/Template/CustomNews is logged
- **CSP headers**: Content-Security-Policy with strict defaults

Report vulnerabilities privately — see [SECURITY.md](docs/SECURITY.md).

---

## License

AGPL-3.0 — see [LICENSE](LICENSE).

Built for the Jellyfin community. PRs welcome!



