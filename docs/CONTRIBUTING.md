








# Contributing to JellyNews

Obrigado pelo interesse em contribuir! 🎉

JellyNews é um projeto **open source, self-hosted, focado na comunidade Jellyfin**. Toda contribuição — código, template, tradução, bug report — é bem-vinda.

---

## 🏗️ Ambiente de Desenvolvimento

### Pré-requisitos

- Python 3.12+
- Node.js 22+
- Docker (opcional, para testes de container)

### Setup rápido

```bash
git clone https://github.com/your-org/jellynews.git
cd jellynews

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # edite APP_SECRET_KEY e SECRETS_ENCRYPTION_KEY
python -m uvicorn main:app --reload --port 8000

# Frontend (outro terminal)
cd frontend
npm ci
npm run dev
```

### Rodando os testes

```bash
cd backend
pytest tests/ -v
```

---

## 📁 Estrutura do Projeto

```
backend/
├── api/              # Rotas FastAPI (routes_*.py) + deps + rate_limit
├── core/             # Config, database, security, logging, sanitize, audit
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic schemas (request/response)
├── services/         # Lógica de negócio (auth, jellyfin, channels, templates, newsletter)
├── alembic/          # Migrations
└── tests/            # Testes pytest
```

Princípios:
- **Rotas são finas** — delegam para `services/` imediatamente
- **Models são dumb** — sem lógica de negócio
- **Schemas validam entrada/saída** — nunca expõem models diretamente

---

## 🔐 Segurança — Regras Obrigatórias

1. **Nunca commitar secrets.** Use `.env` (está no `.gitignore`).
2. **Sanitize HTML.** Use `core.sanitize.sanitize_html()` — nunca aceite HTML raw.
3. **Audite mutações.** Toda criação/edição/remoção de Channel, Secret, Template ou CustomNews deve chamar `core.audit.audit_log()`.
4. **Templates Jinja2** devem sempre usar o `SandboxedEnvironment` (ver `services/templates.py`).
5. **Senhas** usam Argon2id (`services/auth.py`).

---

## 🎨 Adicionando um Canal de Notificação

Canais são **plugins** — não modifique o core.

1. Crie `backend/services/channels/seunome.py`
2. Herde de `BaseChannel` e implemente `async def send(notification)`
3. Registre em `backend/services/channels/__init__.py` no dicionário `CHANNEL_REGISTRY`

```python
# Exemplo mínimo
from services.channels.base import BaseChannel

class MeuCanal(BaseChannel):
    async def send(self, notification) -> bool:
        # sua lógica aqui
        return True
```

---

## 🧪 Escrevendo Testes

- Testes vão em `backend/tests/`
- Use `pytest` + `pytest-asyncio` (modo `auto` já configurado)
- Use o fixture `client` para testes HTTP (ver `conftest.py`)
- Teste cenários de erro (401, 404, 422) e fluxos felizes
- Para canais, faça mock de chamadas externas

---

## 📝 Convenções de Commit

Siga [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — nova feature
- `fix:` — correção de bug
- `docs:` — documentação
- `refactor:` — refatoração sem mudança de comportamento
- `test:` — testes
- `chore:` — CI, build, dependências

---

## 🔄 Fluxo de Pull Request

1. Crie uma branch a partir de `main`
2. Faça suas alterações + testes
3. Rode `ruff check . && mypy . && pytest tests/ -v` localmente
4. Abra um PR contra `main`
5. O CI vai rodar lint, typecheck, testes, build Docker e Trivy scan
6. Aguarde revisão

---

## 📄 Licença

Ao contribuir, você concorda que seu código será licenciado sob AGPL-3.0 (a mesma do projeto).

---

**Dúvidas?** Abra uma issue ou discuta em [GitHub Discussions](https://github.com/your-org/jellynews/discussions).




