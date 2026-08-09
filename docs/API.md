





# JellyNews API Reference

> Base URL: `http://{host}:8000/api/v1`

All endpoints accept/return JSON. Protected endpoints require `Authorization: Bearer <access_token>`.

---

## Authentication

### `POST /auth/login`

```json
{"username": "admin", "password": "your-password"}
```

Returns `access_token` (15 min), `refresh_token`, `expires_in`.

### `POST /auth/refresh`

```json
{"refresh_token": "..."}
```

Returns new token pair.

---

## Custom News

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/news` | No | List news (query: `published_only`, `skip`, `limit`) |
| `GET` | `/news/{id}` | No | Get single news item |
| `POST` | `/news` | Yes | Create news |
| `PATCH` | `/news/{id}` | Yes | Update news |
| `DELETE` | `/news/{id}` | Yes | Delete news |

**Create body:**
```json
{
  "title": "Hello World",
  "body_html": "<p>Welcome to <strong>JellyNews</strong></p>",
  "published": true
}
```

HTML is sanitized server-side (nh3). Only safe tags/attributes are preserved.

---

## Templates

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/templates` | Yes | List templates |
| `POST` | `/templates` | Yes | Create template |
| `GET` | `/templates/{id}` | Yes | Get template |
| `PATCH` | `/templates/{id}` | Yes | Update template |
| `DELETE` | `/templates/{id}` | Yes | Delete template |

---

## Channels

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/channels` | Yes | List channels |
| `POST` | `/channels` | Yes | Create channel |
| `GET` | `/channels/{id}` | Yes | Get channel |
| `PATCH` | `/channels/{id}` | Yes | Update channel |
| `DELETE` | `/channels/{id}` | Yes | Delete channel |

---

## Subscribers

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/subscribers` | Yes | List subscribers |
| `POST` | `/subscribers` | Yes | Add subscriber |
| `DELETE` | `/subscribers/{id}` | Yes | Remove subscriber |

---

## Delivery Logs

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/logs` | Yes | List delivery logs (query: `channel_type`, `status`, `skip`, `limit`) |

---

## Audit Logs (admin only)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/audit-logs` | Owner | List audit entries (query: `action`, `resource_type`, `page`, `page_size`) |

---

## Jellyfin

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/jellyfin/status` | Yes | Test Jellyfin connection |
| `GET` | `/jellyfin/recent` | Yes | Fetch recently added items |

---

## Newsletter

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/newsletter/send` | Yes | Trigger newsletter send (query: `channel_ids`) |
| `POST` | `/newsletter/preview` | Yes | Preview rendered template |

---

## Setup

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/setup/status` | No | Check if setup is needed |
| `POST` | `/setup/complete` | No | Create admin user and initial config |

---

## System

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/healthz` | No | Health check |

---

## Error Responses

All errors follow:
```json
{"detail": "Human-readable error message"}
```

| Status | Meaning |
|---|---|
| 401 | Missing or invalid token |
| 403 | Insufficient permissions (e.g., audit logs require owner role) |
| 404 | Resource not found |
| 422 | Validation error (invalid body) |
| 429 | Rate limit exceeded |

---

## Rate Limiting

- `POST /auth/login` — configurable (default 5/minute)
- Mutation endpoints (`POST/PATCH/DELETE`) — 20–30/minute
- Read endpoints — unauthenticated requests may be restricted in production

Rate limit headers (`X-RateLimit-*`) are included in responses.




