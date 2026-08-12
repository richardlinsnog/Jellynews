# JellyNews — Agente de Desenvolvimento

## Visão Geral
**JellyNews** é um serviço de newsletter self-hosted para Jellyfin. Stack: **FastAPI + SQLite + Vue 3 + Tailwind + Docker**.  
Branch atual: `feat/week-8-hardening-final` — Release candidate, pronto para publicação.

## Estrutura do Projeto
```
Jellynews/
├── backend/          # FastAPI (Python 3.12) — async, SQLAlchemy 2.0 + Alembic + SQLite WAL
│   ├── api/          # Rotas: auth, setup, channels, templates, news, subscribers, jellyfin, newsletter, settings, logs, audit
│   ├── core/         # config, database, security, logging, i18n, audit, sanitize (nh3)
│   ├── models/       # User, AppSettings, Channel, Template, Secret, CustomNews, DeliveryLog, MediaLog, Subscriber, AuditLog
│   ├── services/     # vault (Fernet), auth (Argon2+JWT), jellyfin (httpx), channel_registry, template_registry, newsletter_sender, idempotency
│   │   └── channels/ # Email, Telegram, Discord, ntfy, Webhook (todos implementam NotificationChannel ABC)
│   ├── jobs/         # APScheduler — newsletter automática + cleanup de logs (90 dias)
│   ├── templates/    # 3 built-in: minimal-light, cinema-dark, retro-vhs
│   ├── schemas/      # Pydantic schemas para API
│   └── tests/        # Testes com pytest + httpx AsyncClient
├── frontend/         # Vue 3 + Vite + Tailwind + Pinia + TipTap
│   └── src/
│       ├── views/    # SetupPage, LoginPage, DashboardPage, TemplatesPage, ChannelsPage, NewsPage, SubscribersPage, ServerSettingsPage, LogsPage
│       ├── stores/   # auth.js (Pinia)
│       ├── services/ # api.js (axios com interceptor de refresh token)
│       └── router/   # Vue Router com guard de auth
└── docs/             # Specs, API docs, backup/restore guide
```

## Estado Atual da Implementação
O projeto está **muito avançado** — bem além do plano original de 6 semanas (está na semana 8 de hardening final).

### ✅ O que já está implementado:
- **Infra Docker**: multi-stage, non-root, Alembic auto-migration no boot
- **Auth**: JWT access/refresh tokens, Argon2id, rate limiting (slowapi), refresh token rotation (`token_version`)
- **Setup Wizard**: 3 passos (admin, Jellyfin, confirmação) com teste de conexão em tempo real
- **Models completos**: Todos os 10 models da spec implementados
- **SecretsVault**: Criptografia Fernet com PBKDF2 key derivation
- **JellyfinService**: Cliente async httpx, resolução de UserId, fetch de items/libraries, usuários
- **TemplateRegistry**: Sandbox Jinja2, 3 templates built-in, preview render, zip import com validação
- **ChannelRegistry**: 5 canais (email, telegram, discord, ntfy, webhook), Strategy Pattern, exponential backoff com jitter
- **NewsletterSender**: Pipeline completo — fetch → idempotency (MediaLog) → render → dispatch → DeliveryLog
- **Scheduler**: APScheduler com CronTrigger dinâmico, lock via SQLite advisory, job de cleanup
- **Subscribers**: CRUD, CSV import, bulk delete, Jellyfin sync, unsubscribe público com token criptografado
- **CustomNews**: CRUD com sanitização nh3, workflow Draft→Scheduled→Sent
- **Frontend completo**: 9 views, Tiptap editor, auth store com refresh automático, SPA routing
- **i18n**: Backend gettext + Vue composable (en/pt-BR)
- **Imagens inline**: capas embedadas via CID, logo customizado via Server Settings, thumbnail API (fillHeight=300)
- **Image proxy**: `/api/v1/images/proxy/{item_id}` — evita imagens quebradas em clientes de e-mail
- **Favicon**: 🍿 emoji como favicon
- **Server name clicável**: link para o Jellyfin no header do e-mail
- **Subscriber tag filtering**: case-insensitive matching no envio de newsletters
- **CustomNews integrado**: artigos scheduled entram no footer da newsletter e são marcados como sent
- **Segurança reforçada**: todos endpoints de leitura agora exigem autenticação
- **Premailer CID protection**: `premailer` não remove referências `cid:` em CSS inline
- **SVG rejection**: upload de logo rejeita SVG (apenas PNG/JPEG)
- **Segurança**: CSP headers, CORS, rate limiting, audit trail, secrets criptografados, List-Unsubscribe
- **Testes**: Testes de auth, setup, channels, templates, jellyfin, idempotency

### 🔧 Últimos commits (branch `feat/week-8-hardening-final`):
1. Segurança: auth em endpoints públicos (`/subscribers`, `/news`)
2. CustomNews HTML escaping com `Markup()`
3. Premailer CID protection
4. Logo inline via CID em e-mails
5. Image proxy para imagens do Jellyfin
6. Thumbnail API (fillHeight=300)
7. Favicon 🍿
8. Server name clicável no e-mail
9. Subscriber tag case-insensitive matching
10. SVGs rejeitados no upload de logo

## Environment Atual
- **Repositório**: `/home/ubuntu/workspace/Jellynews` (sync com `Jellynews-deploy`)
- **Branch**: `feat/week-8-hardening-final`
- **Database**: SQLite em `backend/data/jellynews.db`
- **Docker**: `docker compose up -d` em `:8000`
