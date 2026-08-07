# 📄 Especificação Funcional — JellyNews
### O que o sistema faz, para quem, e como ele se comporta

**Complementa:** `jellynews-spec-comunidade.md` (especificação técnica)
**Não contém:** nomes de framework, tabelas de banco, endpoints — isso está no documento técnico.

---

## 1. Propósito

Manter os usuários de um servidor Jellyfin informados sobre o que foi adicionado às bibliotecas (filmes, séries, músicas) e sobre avisos do admin (manutenção, mudanças, segurança), através de newsletters automáticas e recorrentes, entregues no canal que cada admin preferir — sem depender de nenhum serviço de terceiros pago ou centralizado.

**Não é objetivo do sistema:**
- Recomendar conteúdo com base em algoritmo (não é um "for you").
- Substituir os clients do Jellyfin — é só um canal de aviso passivo (push), não uma interface de navegação.
- Ser uma plataforma multi-tenant (SaaS). Cada instância serve **um** servidor Jellyfin, gerenciado por **um ou poucos** admins.

---

## 2. Personas

| Persona | Quem é | O que quer do sistema |
|---|---|---|
| **Admin do servidor** | Dono/mantenedor do Jellyfin, quem instala e configura o JellyNews | Configurar uma vez, esquecer que existe, confiar que vai disparar certo |
| **Assinante da newsletter** | Usuário do Jellyfin (família, amigos, comunidade) | Receber um resumo legível do que tem de novo, sem spam, com opção de sair |
| **Contribuidor da comunidade** (secundário) | Alguém que quer criar/publicar um template ou canal novo | Conseguir contribuir sem entender o core do sistema |

---

## 3. Fluxos Principais (User Flows)

### 3.1 Primeiro uso (Setup)
1. Admin sobe o container e acessa a UI pela primeira vez → é redirecionado para `/setup`.
2. Cria a conta admin (usuário + senha) — **não existe senha padrão**.
3. Informa URL do Jellyfin + API Key → sistema testa a conexão na hora e mostra sucesso/erro específico (ex: "Jellyfin respondeu, mas a API Key é inválida" vs. "Não foi possível alcançar o host").
4. Escolhe um template inicial (a partir da galeria built-in) — pode trocar depois.
5. Escolhe pelo menos um canal de envio e configura suas credenciais (mesma lógica de teste em tempo real).
6. Define a periodicidade (ex: semanal, toda sexta às 18h) — com preview em linguagem natural ("Vou enviar toda sexta-feira às 18:00, horário de São Paulo").
7. Setup concluído → vai para o Dashboard.

**Critério de aceite:** um admin não-técnico consegue concluir o setup sem consultar documentação, e recebe feedback claro em cada erro de configuração (nunca um erro genérico tipo "500 Internal Server Error").

### 3.2 Ciclo automático de newsletter (o "coração" do sistema)
1. No horário configurado, o sistema consulta o Jellyfin por itens adicionados desde o último envio.
2. **Se não houver itens novos e não houver notícia manual pendente:** o sistema **não envia nada** (evita spam de "newsletter vazia"). Essa decisão é configurável (alguns admins podem preferir sempre enviar, mesmo vazio, como um "sinal de vida").
3. Se houver conteúdo (itens e/ou notícia manual), o sistema monta a newsletter usando o template ativo de cada canal e dispara.
4. Cada envio é registrado (sucesso, falha, o que foi enviado) — visível no Dashboard.
5. Se um canal falhar (ex: Telegram fora do ar), os outros canais configurados **continuam funcionando** — falha é isolada por canal.

**Critério de aceite:** um item nunca é reportado duas vezes em newsletters diferentes; uma falha de um canal não impede os demais; o admin consegue ver no Dashboard exatamente o que foi enviado, quando e por qual canal.

### 3.3 Notícia manual (avisos do admin)
1. Admin escreve um aviso no editor rich-text (ex: "manutenção programada para sábado").
2. Pode marcar como **rascunho** (não entra na próxima newsletter), **agendada** (entra na próxima newsletter automática) ou **enviar agora** (dispara imediatamente, fora do cron, útil para avisos urgentes de segurança).
3. Depois de enviada, fica em histórico — não é reenviada.

**Critério de aceite:** um aviso urgente ("saiu uma vulnerabilidade crítica, servidor vai reiniciar em 10 minutos") não precisa esperar o próximo ciclo agendado.

### 3.4 Escolha e customização de template
1. Admin navega pela galeria de templates com preview visual (dados de exemplo, não precisa disparar e-mail real para ver).
2. Seleciona um template por canal (o e-mail pode usar um template rico, o Telegram um enxuto).
3. Pode editar o template selecionado (modo avançado) vendo o preview atualizar em tempo real.
4. Pode importar um template de terceiro — nesse caso, o sistema avisa claramente que é "não verificado" e pede confirmação explícita antes de ativar.

**Critério de aceite:** o admin nunca precisa enviar um e-mail de teste real só para ver como o template ficou — o preview reflete fielmente o resultado final.

### 3.5 Descadastro / opt-out (assinante)
1. Todo e-mail enviado contém um link de descadastro.
2. Ao clicar, o e-mail é removido da lista de destinatários (se o sistema gerenciar lista própria de e-mails) **ou** instruções claras de como sair (se o envio for para uma lista externa gerenciada pelo próprio admin, ex: um grupo de e-mail já existente).
3. Descadastro é imediato e não requer login.

**Critério de aceite:** conformidade básica de boas práticas de e-mail — ninguém fica preso recebendo a newsletter.

### 3.6 Recuperação de falhas do Jellyfin
1. Se o Jellyfin estiver offline/inacessível no momento do ciclo agendado, o sistema **não falha silenciosamente** — registra o erro, tenta novamente conforme uma política simples de retry, e se persistir, **não envia uma newsletter vazia por engano** nem trava o próximo ciclo.
2. Admin recebe um aviso visível no Dashboard ("última sincronização falhou às 18:03").

**Critério de aceite:** uma instabilidade momentânea do Jellyfin não gera newsletters incorretas nem exige intervenção manual para o sistema voltar ao normal no próximo ciclo.

---

## 4. Regras de Negócio (o que geralmente fica ambíguo se não for escrito)

- **O que conta como "item novo"?** Baseado em `DateCreated` no Jellyfin **e** verificado contra o histórico interno por ID — um item re-escaneado (ex: metadata refresh) não deve ser reportado de novo.
- **O que acontece se dois ciclos se sobrepõem?** O segundo ciclo não roda enquanto o primeiro não terminar (lock).
- **O que acontece se o admin trocar de template no meio de um envio?** O envio em andamento usa o template que estava ativo quando o ciclo começou; a troca só vale a partir do próximo ciclo.
- **Newsletter vazia é enviada?** Configurável por instância, default = não enviar.
- **Quantos itens cabem em uma newsletter?** Sem limite artificial de "top N" — mostra tudo que foi adicionado no período; se ficar muito longo para o Telegram, é dividido (chunking), nunca cortado silenciosamente.
- **Idiomas:** interface e templates built-in devem suportar, no mínimo, PT-BR e inglês (i18n desde o início, pois é um projeto voltado à comunidade internacional do Jellyfin).

---

## 5. Fora de escopo (v1)

Para deixar explícito o que **não** entra na primeira versão, evitando scope creep durante o desenvolvimento:
- Recomendações personalizadas por usuário (newsletter é a mesma para todos os assinantes de um canal).
- Estatísticas de audiência/engajamento (open rate, cliques) — não é uma ferramenta de marketing.
- Suporte a múltiplos servidores Jellyfin em uma única instância do JellyNews.
- App mobile dedicado (o Telegram/Discord já cobrem a necessidade de notificação móvel).

---

## 6. Decisões de Design (Resolução de Ambiguidades)

Estas decisões foram tomadas após revisão cruzada com a especificação técnica. Servem como fonte oficial de verdade para implementação.

### 6.1 Lista de destinatários e opt-out
**Decisão:** O sistema gerencia lista própria de assinantes (model `Subscriber`).
- Link de opt-out usa token UUID criptografado via SecretsVault, válido por 30 dias, sem necessidade de login.
- Ao clicar, `Subscriber.active = False` com `unsubscribed_at` timestamp.
- Admin gerencia a lista via UI com upload de CSV.
- Nenhuma dependência de lista externa de e-mails.

### 6.2 Internacionalização (i18n)
**Decisão:** Estratégia em 3 camadas:
1. **Frontend:** `vue-i18n`, arquivos em `/frontend/src/locales/{pt-BR,en}.json`
2. **Backend:** detecção via header `Accept-Language`, mensagens traduzidas
3. **Templates:** variantes por idioma (`email.pt-BR.html.j2`, `email.en.html.j2`), idioma definido em `Channel.language`, fallback `en`

### 6.3 Token de unsubscribe
**Decisão:** `token = SecretsVault.encrypt("unsub:{subscriber_id}:{email}")`. Endpoint público `GET /api/v1/unsubscribe/{token}`. O token é decriptado, `subscriber_id` extraído, e o registro é marcado `active=False` com `unsubscribed_at` timestamp. Sem necessidade de login.

### 6.4 Roles de usuário (owner/editor)
**Decisão:** v1 = single admin (apenas `owner`). O campo `role` no model `User` já existe como enum `owner`/`editor`, mas na v1 o setup cria apenas um owner. A API e UI da v1 não expõem endpoints de CRUD de usuários adicionais, nem distinção de permissões por role. O enum fica como reserva para v1.x.

### 6.5 CORS e servindo o frontend
**Decisão:**
- **Desenvolvimento:** Vite roda em `:5173` com proxy para o backend em `:8000`
- **Produção:** Vue buildado para `/frontend/dist/` e servido como estático pelo FastAPI via `StaticFiles`
- **Dockerfile multi-stage:** Stage 1 builda o Vue, Stage 3 copia `dist/` para `/app/static/`
- **CORS:** `allow_origins=["*"]` em produção self-hosted (acesso por IP local)

### 6.6 AppSettings — chaves concretas da v1
`AppSettings` é chave/valor simples. Chaves concretas para a v1:
- `send_empty_newsletter` (bool, default false)
- `cron_expression` (string)
- `server_name` (string)
- `language` (string, default "en")
Modelado como `key: str` (unique indexed) + `value: str` (JSON-serializado para tipos não-string).

### 6.7 validate_config vs test_connection (Canais)
**Decisão:** Semanticamente diferentes:
- `validate_config(config: dict) -> bool`: valida schema (campos obrigatórios, formato, tipos). Local, sem network.
- `test_connection() -> ConnectionStatus`: testa conectividade real contra serviço externo. Retorna `ok`, `timeout`, `auth_failed`, `dns_error`.

### 6.8 MediaLog — campos
- `jellyfin_item_id: str` (indexed, unique)
- `item_name: str`
- `item_type: str` ("Movie", "Series", "Audio")
- `library_name: str`
- `production_year: int` (nullable)
- `jellyfin_date_created: datetime`
- `first_seen_at: datetime`
- `last_notified_at: datetime`

### 6.9 Licença
**Decisão:** AGPL-3.0. Arquivo `LICENSE` já existe na raiz do projeto.

### 6.10 DeliveryLog — payload_summary
Campo `payload_summary` armazena JSON com:
```json
{
  "total_items": 42,
  "movies_count": 15,
  "series_count": 20,
  "audio_count": 7,
  "has_custom_news": true,
  "custom_news_title": "Manutenção sábado",
  "item_ids_sample": ["jf_id_1", "jf_id_2", "jf_id_3"]
}
```
Populado pelo `NewsletterService` após o envio. Permite Dashboard mostrar resumo sem joins pesados.

### 6.11 Escopo da Semana 1 (models)
**Decisão:** Na Semana 1, apenas models `User` e `AppSettings`. Os models `Secret`, `MediaLog`, `CustomNews`, `Template`, `Channel`, `DeliveryLog`, `AuditLog` e `Subscriber` serão introduzidos nas semanas em que seus serviços forem implementados. A Semana 1 foca exclusivamente em: infraestrutura Docker, FastAPI skeleton, Auth (JWT + Argon2), SecretsVault, e Setup Wizard (apenas criação do admin).


### 💡 Como usar
Este documento define o **"o quê" e o "porquê"**; o `jellynews-spec-comunidade.md` define o **"como"**. Recomendo colar os dois juntos no OpenSpec/Qwen, nessa ordem — a funcional primeiro, para o modelo entender o comportamento esperado antes de ver a arquitetura.

