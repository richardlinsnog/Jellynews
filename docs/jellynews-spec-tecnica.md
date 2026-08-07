# 📄 Especificação Técnica — JellyNews
### Serviço de Newsletter Autohospedado para a Comunidade Jellyfin

**Versão:** 2.0 (revisão "community-ready")
**Status:** Draft para ingestão em OpenSpec / Qwen
**Herda de:** especificação original (Gemini/DeepSeek) — ver seção 0 para o que mudou

---

## 0. O que muda ao ir de "ferramenta pessoal" para "projeto de comunidade"

A primeira especificação (anexada) resolvia bem o caso de uso de **um único admin, rodando para si mesmo**. Para virar algo que qualquer pessoa da comunidade Jellyfin possa clonar, subir com `docker compose up` e confiar, cinco eixos precisam de reforço — são o fio condutor de tudo abaixo:

| Eixo | Spec original | Proposta community-ready |
|---|---|---|
| **Templates** | Editor único de HTML/Jinja2 embutido | Sistema de **templates como plugins** (galeria + preview + import de terceiros) |
| **Canais** | Email + Telegram fixos no código | **Strategy Pattern real**: Email, Telegram, Discord, ntfy, Webhook genérico — novos canais sem tocar no core |
| **Segurança** | JWT + bcrypt básico | Segredos criptografados em repouso, rate limiting, sandboxing de templates (SSTI), imagem Docker non-root, CSP |
| **Onboarding** | Assume usuário técnico | Wizard de primeiro uso, validação de conexão em tempo real, sem credenciais hardcoded no `.env.example` |
| **Distribuição** | Projeto único | Pensado para fork/self-host em massa: versionamento semântico, migrations automáticas, healthcheck, docs públicas |

O nome do projeto e a base tecnológica (FastAPI + SQLite + Vue) são mantidos — são escolhas corretas para self-hosting leve. O que muda é a **arquitetura interna**, para que ela seja extensível sem virar um monólito acoplado.

---

## 1. Visão Geral da Arquitetura

Monolito modular, mas com três limites internos tratados como **interfaces plugáveis**, não como implementações diretas:

```
┌─────────────────────────────────────────────────────────┐
│                     JellyNews Container                  │
│                                                            │
│  ┌──────────┐   ┌───────────────┐   ┌──────────────────┐ │
│  │ Admin UI │──▶│  FastAPI Core  │──▶│  Scheduler (bg)   │ │
│  │ (Vue 3)  │   │  (REST + Auth) │   │  APScheduler       │ │
│  └──────────┘   └───────┬────────┘   └─────────┬─────────┘ │
│                          │                       │           │
│              ┌───────────┴───────────┐          │           │
│              │   Domain Services      │◀─────────┘           │
│              │ Jellyfin / Newsletter  │                       │
│              └───────────┬───────────┘                       │
│         ┌─────────────────┼─────────────────┐                │
│         ▼                 ▼                 ▼                │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────┐        │
│  │ Template     │   │ Channel      │   │ Secrets       │        │
│  │ Registry     │   │ Registry     │   │ Vault         │        │
│  │ (plugável)   │   │ (plugável)   │   │ (Fernet/age)  │        │
│  └─────────────┘   └─────────────┘   └──────────────┘        │
└─────────────────────────────────────────────────────────┘
             │                    │
             ▼                    ▼
      Jellyfin API         Email/Telegram/Discord/ntfy/Webhook
```

- **Template Registry**: carrega templates de `/backend/templates/*/manifest.json`, cada um isolado, com sandbox Jinja2 (sem acesso a builtins perigosos).
- **Channel Registry**: cada canal implementa a interface `NotificationChannel` (`validate_config`, `send`, `test_connection`). Adicionar um canal novo = criar uma classe + registrar, sem tocar no resto.
- **Secrets Vault**: nenhuma API key/token/senha SMTP fica em texto puro no SQLite — tudo passa por uma camada de criptografia simétrica com chave derivada de `APP_SECRET_KEY`.

---

## 2. Stack Tecnológico Completo

| Camada | Tecnologia | Motivo |
|---|---|---|
| Backend | Python 3.12 + **FastAPI** | Async nativo, validação com Pydantic v2, ecossistema maduro |
| ORM / Migrations | **SQLAlchemy 2.0** + **Alembic** | Migrações versionadas — essencial quando múltiplas instâncias da comunidade vão atualizar de versão em versão |
| Banco | **SQLite (modo WAL)** | Zero-dependência de infra externa; portável para backup em 1 arquivo |
| Scheduler | **APScheduler** (AsyncIOScheduler, timezone-aware) | Cron dinâmico configurável pela UI |
| Templates de e-mail | **Jinja2 (sandboxed)** + `premailer` (inline de CSS automático) | Compatibilidade com clientes de e-mail (Outlook etc.) |
| Frontend | **Vue 3 (Composition API)** + Vite + **Tailwind CSS** + Pinia | Leve, sem build pesado |
| HTTP client | `httpx` (async) | Chamadas a Jellyfin/Telegram/Discord/webhooks |
| E-mail | `aiosmtplib` (SMTP) — opcional: adapters para Resend/SendGrid/Mailgun | Suporte a SMTP genérico cobre 90% dos casos de self-hosters |
| Segredos | `cryptography` (Fernet) | Criptografia simétrica dos tokens/API keys no banco |
| Autenticação | **JWT** (`pyjwt`) + **Argon2** (`argon2-cffi`) para hash de senha | Argon2 é o padrão atual recomendado (mais resistente que bcrypt puro a GPU cracking) |
| Rate limiting | `slowapi` | Protege `/auth/login` e endpoints de teste de conexão contra brute-force |
| Editor rich text | **Tiptap** (baseado em ProseMirror) | Sanitização de output mais previsível que Quill/TinyMCE para HTML injetado em e-mail |
| Sanitização HTML | `nh3` (binding Rust do Ammonia) | Sanitiza o HTML do editor antes de persistir — mitiga XSS/HTML injection |
| Infra | Docker + Docker Compose, imagem **multi-stage**, usuário **non-root** | Padrão de segurança esperado em projeto de comunidade |
| CI | GitHub Actions (lint, testes, build de imagem, scan de vulnerabilidade com Trivy) | Necessário para aceitar contribuições externas com confiança |
| Observabilidade | `/healthz` (liveness/readiness) + logs estruturados (JSON, `structlog`) | Facilita integração com Netdata/Uptime Kuma, comum em homelabs |

---

## 3. Sistema de Templates (o diferencial "para a comunidade")

Este é o módulo que transforma o projeto de "meu script" em algo que a comunidade Jellyfin realmente adotaria.

### 3.1 Estrutura de um template
```
/backend/templates/
├── minimal-light/
│   ├── manifest.json      # nome, autor, versão, canais suportados, screenshot
│   ├── email.html.j2
│   ├── email.txt.j2       # fallback plain-text (obrigatório p/ deliverability)
│   └── telegram.md.j2
├── cinema-dark/
│   └── ...
└── retro-vhs/
    └── ...
```

`manifest.json` de exemplo:
```json
{
  "id": "cinema-dark",
  "name": "Cinema Dark",
  "author": "community",
  "version": "1.2.0",
  "supports_channels": ["email", "telegram"],
  "preview_image": "preview.png",
  "variables_required": ["items_added", "custom_news", "server_name"]
}
```

### 3.2 Funcionalidades expostas ao admin
- **Galeria de templates**: grid com preview renderizado (dados fake) direto na UI, sem precisar disparar e-mail de teste.
- **Import de template de terceiros**: upload de um `.zip` seguindo o manifest — validado e sandboxed antes de ativar.
- **Editor com preview ao vivo**: split-screen (código Jinja2 ↔ render), reaproveitando o mesmo motor de sandbox usado em produção (o que se vê no preview é exatamente o que será enviado).
- **Templates por canal**: um mesmo "pacote" pode ter variantes por canal (o e-mail é rico, o Telegram é enxuto) — selecionáveis independentemente.

### 3.3 Sandboxing (crítico para segurança)
Templates de terceiros rodando Jinja2 sem restrição = risco de **Server-Side Template Injection (SSTI)**. Mitigação:
- Uso de `jinja2.sandbox.SandboxedEnvironment`, sem acesso a `__class__`, `__globals__` etc.
- Contexto de renderização é uma allowlist fixa de variáveis (nunca o objeto Python bruto do Jellyfin).
- Templates importados de terceiros ficam com uma flag `unverified=True` até o admin confirmar explicitamente que confia na fonte.

---

## 4. Sistema de Canais (extensibilidade de envio)

Interface comum (pseudocódigo):
```python
class NotificationChannel(ABC):
    @abstractmethod
    async def validate_config(self, config: dict) -> bool: ...
    @abstractmethod
    async def send(self, rendered_content: RenderedContent) -> SendResult: ...
    @abstractmethod
    async def test_connection(self) -> ConnectionStatus: ...
```

Canais no MVP:
| Canal | Observação |
|---|---|
| E-mail (SMTP) | Multipart/alternative, headers de deliverability |
| Telegram | Bot API, chunking automático (limite 4096 chars) |
| Discord | Webhook nativo do Discord (embeds ricos, sem precisar de bot) — muito pedido em comunidades self-hosted |
| ntfy.sh / self-hosted ntfy | Push simples, ótimo para quem já usa ntfy no homelab |
| Webhook genérico | POST de JSON assinado (HMAC) — permite integrar com Home Assistant, n8n, Matrix via bridge, etc., **sem** o core precisar conhecer cada serviço |

Cada instância pode ativar múltiplos canais simultaneamente, cada um com seu próprio template.

---

## 5. Variáveis de Ambiente

```env
# --- APP ---
APP_ENV=production
APP_SECRET_KEY=                 # obrigatório, sem default — app recusa subir se vazio
DEBUG=False
PORT=8000
TZ=America/Sao_Paulo
LOG_LEVEL=INFO
LOG_FORMAT=json

# --- DATABASE ---
DATABASE_URL=sqlite:///./data/jellynews.db

# --- SEGURANÇA ---
JWT_EXPIRATION_MINUTES=60
JWT_REFRESH_EXPIRATION_DAYS=7
RATE_LIMIT_LOGIN=5/minute
SECRETS_ENCRYPTION_KEY=         # se ausente, é derivada de APP_SECRET_KEY via PBKDF2 (com aviso no log)
ALLOW_UNVERIFIED_TEMPLATES=false

# --- SETUP INICIAL (apenas 1ª execução, via wizard — não fica salvo em texto puro depois) ---
FIRST_RUN_SETUP=true

# --- OBSERVABILIDADE ---
HEALTHCHECK_ENABLED=true
```

Diferença deliberada em relação à spec original: **não existe `ADMIN_PASSWORD` fixo no `.env`**. No primeiro boot, a aplicação expõe um wizard (`/setup`) que gera a conta admin com senha definida na hora — evita o antipadrão de milhares de instâncias públicas com `admin/changeme123`.

Credenciais de Jellyfin, SMTP, Telegram, Discord etc. continuam fora do `.env`, salvas no banco — mas agora **criptografadas** via Secrets Vault (seção 2).

---

## 6. Estrutura de Diretórios

```text
/jellynews
├── Dockerfile                  # multi-stage, non-root final stage
├── docker-compose.yml
├── docker-compose.example.yml  # versão comentada para novos usuários
├── .env.example
├── LICENSE                     # AGPL-3.0 ou MIT — decisão de projeto (ver seção 9)
├── CONTRIBUTING.md             # como submeter um template/canal novo
├── /docs                       # mkdocs ou docusaurus — instalação, FAQ, troubleshooting
├── /backend
│   ├── main.py
│   ├── /api                    # rotas versionadas: /api/v1/...
│   ├── /core                   # config, security, secrets vault, sandbox
│   ├── /models                 # SQLAlchemy
│   ├── /schemas                # Pydantic DTOs
│   ├── /services
│   │   ├── jellyfin_service.py
│   │   ├── newsletter_service.py
│   │   ├── channels/            # um arquivo por canal, implementando NotificationChannel
│   │   └── template_registry.py
│   ├── /jobs                   # APScheduler jobs
│   ├── /templates              # templates built-in (seção 3)
│   ├── /alembic
│   └── /tests
├── /frontend
│   ├── /src
│   │   ├── /components
│   │   ├── /views               # Setup, Dashboard, Templates, Canais, Notícias, Logs
│   │   ├── /services
│   │   └── /stores
└── /data                        # volume: sqlite + cache de imagens + logs
```

---

## 7. Modelos, Serviços e Jobs

### Models (SQLAlchemy)

**Semana 1 (implementados):**
- `User` — conta(s) de admin do painel, com roles `owner`/`editor`. Na v1, apenas um `owner` criado via Setup Wizard. Campo `role` com enum `owner`/`editor` já existe, mas API de CRUD de usuários adicionais só na v1.x.
- `AppSettings` — chave/valor não sensível. Chaves concretas da v1: `send_empty_newsletter` (bool, default false), `cron_expression` (string), `server_name` (string), `language` (string, default "en"). Modelado como `key: str` (unique indexed) + `value: str` (JSON-serializado para tipos não-string).

**Semanas 2-6 (a implementar conforme o pipeline):**
- `Subscriber` — assinantes da newsletter. Campos: `email` (unique), `active: bool`, `unsubscribed_at: datetime` (nullable), `unsubscribe_token: str` (nullable). Token de opt-out via SecretsVault: `encrypt("unsub:{id}:{email}")`. Admin gerencia lista via upload de CSV na UI.
- `Secret` — chave/valor **criptografado** (API keys, tokens, senha SMTP) — nunca serializado cru em nenhum response.
- `MediaLog` — itens já notificados (idempotência). Campos: `jellyfin_item_id: str` (indexed, unique), `item_name: str`, `item_type: str` ("Movie", "Series", "Audio"), `library_name: str`, `production_year: int` (nullable), `jellyfin_date_created: datetime`, `first_seen_at: datetime`, `last_notified_at: datetime`.
- `CustomNews` — notícias manuais (`Draft` → `Scheduled` → `Sent`).
- `Template` — metadados de templates instalados (built-in + importados), incluindo `verified: bool`.
- `Channel` — canais configurados, cada um com `type`, `config_ref` (aponta para `Secret`), `active: bool`, `template_id`, `language: str` (default "en").
- `DeliveryLog` — histórico de envios por canal (sucesso/falha). Campo `payload_summary` armazena JSON com `{total_items, movies_count, series_count, audio_count, has_custom_news, custom_news_title, item_ids_sample}`.
- `AuditLog` — alterações de `Channel`/`Secret`/`Template` (quem, quando, o quê — sem valor sensível).

### Serviços
- `JellyfinService` — resolve `UserId` automaticamente, busca itens novos por tipo, tolera múltiplas bibliotecas.
- `TemplateRegistry` — descobre, valida (`manifest.json`), sandboxa e renderiza templates.
- `ChannelRegistry` — descobre e instancia canais via Factory Method.
- `NewsletterService` (Facade) — orquestra: busca novidades → aplica template do canal → chama `channel.send()` → grava `DeliveryLog`.
- `SecretsVaultService` — encrypt/decrypt via Fernet, chave derivada de `APP_SECRET_KEY`.
- `SetupWizardService` — fluxo de primeira execução (cria admin, testa Jellyfin, escolhe template padrão).

### Jobs (APScheduler)
- `job_sync_and_notify` — cron configurável pela UI (não fixo em `.env`).
- `job_clean_logs` — expurga `DeliveryLog`/`MediaLog` antigos (configurável, default 90 dias).
- `job_check_updates` — (opcional, off por padrão) verifica se há nova versão do JellyNews no GitHub Releases e mostra um badge na UI — sem telemetria, só uma checagem pull.

---

## 8. Segurança — seção dedicada (era o ponto mais fraco da spec original)

1. **Segredos em repouso**: toda credencial de terceiro (Jellyfin API key, SMTP, tokens de Telegram/Discord) passa pelo `SecretsVaultService` antes de tocar o SQLite.
2. **Sem credenciais default**: build falha/recusa subir se `APP_SECRET_KEY` não for definido; conta admin é criada via wizard, não via `.env`.
3. **Rate limiting**: login e endpoints de "testar conexão" limitados via `slowapi`, com backoff progressivo.
4. **Sanitização de rich text**: HTML do editor de notícias passa por `nh3` antes de persistir — mitiga XSS armazenado que se propagaria para o e-mail de todos os assinantes.
5. **Sandbox de templates**: `SandboxedEnvironment` do Jinja2 + allowlist de variáveis — mitiga SSTI em templates importados.
6. **Assinatura de Webhooks**: payloads enviados ao canal "Webhook genérico" carregam header `X-JellyNews-Signature` (HMAC-SHA256) para o receptor validar autenticidade.
7. **Docker hardening**: imagem final roda como usuário non-root, filesystem majoritariamente read-only exceto `/data`, sem `latest` implícito (tags semânticas).
8. **Dependências**: scan automático (Trivy/`pip-audit`) no CI a cada PR — importante porque projeto de comunidade recebe contribuições externas.
9. **CORS/CSP**: headers restritivos por padrão; CORS liberado só para o próprio host em produção.
10. **Backups**: `/data` é um único volume — documentação explícita de estratégia 3-2-1 (linha com o que você já usa no seu homelab com Restic/Borg).
11. **Compliance de e-mail**: `List-Unsubscribe` obrigatório nos templates built-in de e-mail — mesmo sendo newsletter "privada" de um servidor pessoal, evita cair em spam.
12. **Auditoria**: toda alteração de `Channel`/`Secret`/`Template` grava um `AuditLog` simples (quem, quando, o quê — sem valor sensível).

---

## 9. Considerações de Projeto Open Source

Como o objetivo é servir a comunidade e não só você:
- **Licença**: AGPL-3.0 é a escolha mais comum em projetos self-hosted de comunidade (Jellyfin em si usa GPL-2.0) — evita que alguém rode como SaaS fechado sem contribuir de volta. MIT é a alternativa mais permissiva, se a prioridade for adoção ampla. Vale decidir isso antes do primeiro commit público.
- **`CONTRIBUTING.md`** com foco em como submeter um novo template ou canal (a estrutura plugável da seção 3–4 existe justamente para baixar a barreira de contribuição).
- **Documentação pública** (mkdocs/Docusaurus) com: instalação em 5 minutos, troubleshooting (baseado nos "hurdles" abaixo), FAQ, comparação com Tautulli (referência que a própria spec original já citou).
- **Versionamento semântico** + changelog automatizado (`release-please` ou similar), já que instâncias de terceiros vão atualizar via `docker compose pull`.

---

## 10. 12 "Common Hurdles" Atualizados

1. **Imagens quebradas no e-mail** — Jellyfin exige auth para baixar capas → cache local + embed `cid:` inline.
2. **Limite de caracteres no Telegram (4096)** — chunking automático no `TelegramChannel`.
3. **Falso-positivos de "novo item"** — validar por ID no `MediaLog`, nunca só por `DateCreated`.
4. **SSTI em templates de terceiros** — mitigado pela sandbox (seção 3.3); testar com payloads conhecidos no CI.
5. **Scheduler duplicado** — lock via SQLite ou thread dedicada no startup do FastAPI.
6. **Perda de estado em updates** — `/data` como volume Docker obrigatório; Alembic roda migrations automaticamente no boot.
7. **Rate limiting de canais externos** (Telegram 429, Discord 429) — backoff exponencial genérico no `ChannelRegistry`, não reimplementado por canal.
8. **UserID do Jellyfin ausente** — resolvido automaticamente via `/Users` na primeira config.
9. **Timezone mismatch** — `TZ` forçado no container + timezone explícito no APScheduler.
10. **Instâncias públicas com credenciais default** — eliminado pelo wizard de setup (sem `ADMIN_PASSWORD` no `.env`).
11. **Template malicioso importado por engano** — flag `unverified`, aviso visual na UI antes de ativar.
12. **Concorrência no SQLite** — modo WAL + `NullPool` + `check_same_thread=False`.

---

## 11. Pipeline de Desenvolvimento (para o Qwen/OpenSpec)

### Estrutura de branches
- `main` — protegida, tag `v0.1.0` no final da Semana 1
- `develop` — branch de integração
- `feat/week-N-*` — branches de feature por semana

### Semana 1 — Infra base e Setup Wizard (escopo ajustado)
**Branch:** `feat/week-1-infra-base`

**Models implementados:** Apenas `User` e `AppSettings`. Os demais models (`Secret`, `MediaLog`, `CustomNews`, `Template`, `Channel`, `DeliveryLog`, `AuditLog`, `Subscriber`) entram nas semanas correspondentes aos seus serviços.

**Sequência de commits (cada um atômico e testável):**

| # | Commit | Descrição |
|---|--------|-----------|
| 01 | `chore: scaffold project structure and Docker multi-stage non-root setup` | Dockerfile, docker-compose.yml, .env.example, .gitignore, estrutura de diretórios |
| 02 | `feat: add FastAPI app skeleton with /healthz and structlog` | main.py, core/config.py (pydantic-settings), core/logging.py, lifespan com healthcheck |
| 03 | `feat: add SQLAlchemy base, User+AppSettings models, Alembic migration` | models/user.py, models/app_settings.py, database session factory WAL+NullPool, alembic init + primeira migration |
| 04 | `feat: implement SecretsVaultService with Fernet encryption` | core/secrets_vault.py, encrypt/decrypt, chave derivada de APP_SECRET_KEY via PBKDF2, testes unitários |
| 05 | `feat: implement JWT + Argon2 authentication with rate limiting` | core/security.py, api/v1/auth.py (/login, /refresh), dependência get_current_user, slowapi em /auth/login |
| 06 | `feat: add Setup Wizard API (admin creation only)` | api/v1/setup.py, services/setup_wizard.py, FIRST_RUN_SETUP flag, bloqueio de acesso se não concluído |
| 07 | `feat: add CORS/CSP/security headers middleware` | CORS allow_origins=["*"], CSP headers, validação SECRETS_ENCRYPTION_KEY no startup |
| 08 | `test: add integration tests for auth, secrets vault, and setup wizard` | tests/test_auth.py, tests/test_secrets_vault.py, tests/test_setup_wizard.py |
| 09 | `chore: add CI pipeline (lint, test, build, Trivy scan)` | .github/workflows/ci.yml, pyproject.toml com ruff, mypy, pytest |

- **Semana 2** — `JellyfinService` + `MediaLog` + testes de idempotência.
- **Semana 3** — `TemplateRegistry` com sandbox + 3 templates built-in (Minimal, Cinema Dark, Retro) + preview ao vivo na UI.
- **Semana 4** — `ChannelRegistry`: Email, Telegram, Discord, Webhook genérico + `DeliveryLog`.
- **Semana 5** — Frontend completo (Setup, Dashboard, Templates, Canais, Notícias, Logs) + editor Tiptap com sanitização.
- **Semana 6** — Hardening de segurança (seção 8), CI (lint/test/build/scan), docs públicas, empacotamento final.

---

## 12. Checklist Pós-Implementação

- [ ] App recusa subir sem `APP_SECRET_KEY`?
- [ ] Nenhuma credencial de terceiro aparece em texto puro no SQLite ou em nenhum response de API?
- [ ] Templates importados exigem confirmação explícita antes de ativar?
- [ ] Rate limiting ativo em `/auth/login` e `/*/test-connection`?
- [ ] Preview de template usa exatamente o mesmo motor de render de produção?
- [ ] Imagem Docker roda non-root e passou no scan Trivy?
- [ ] `docker compose up -d` sobe do zero sem intervenção manual, terminando no wizard de setup?
- [ ] Migrations Alembic rodam automaticamente em upgrade sem perda de dados?
- [ ] E-mails têm `List-Unsubscribe` e fallback plain-text?
- [ ] Documentação pública cobre instalação, troubleshooting e como contribuir um template?

---

### 💡 Como usar
Este documento pode ser colado integralmente no OpenSpec/Qwen com o mesmo tipo de prompt sugerido na conversa original — pedindo para confirmar entendimento do escopo antes de começar a codificar a Semana 1.
