




# Backup & Restore Guide

## What to back up

JellyNews stores all data in a single SQLite database. To back up your instance:

### 1. Database file

```bash
# Stop the application first
cp /path/to/jellynews.db /backup/jellynews-$(date +%Y%m%d).db
```

Alternatively, use SQLite's online backup:

```bash
sqlite3 /path/to/jellynews.db ".backup /backup/jellynews-$(date +%Y%m%d).db"
```

### 2. Templates directory

If you've imported custom templates:

```bash
cp -r /path/to/backend/templates /backup/templates-$(date +%Y%m%d)/
```

### 3. Configuration

Keep a copy of your `.env` file:

```bash
cp .env /backup/jellynews-$(date +%Y%m%d).env
```

## Restoring

### Database

```bash
# Stop the application
cp /backup/jellynews-20260101.db /path/to/jellynews.db
# Start the application — Alembic will run any pending migrations automatically
```

### Templates

```bash
cp -r /backup/templates-20260101/* /path/to/backend/templates/
# The template registry will pick them up at startup or via API reload
```

## Automated backup (cron)

```bash
0 3 * * * sqlite3 /opt/jellynews/data/jellynews.db ".backup /backup/jellynews-$(date +\%Y\%m\%d).db" && find /backup -name 'jellynews-*.db' -mtime +30 -delete
```

This keeps 30 days of daily backups.

## Disaster recovery checklist

1. Copy backup database file to the correct location
2. Restore `.env` with correct `APP_SECRET_KEY` and `SECRETS_ENCRYPTION_KEY`
3. If encryption keys changed, secrets will need to be re-entered
4. Start the application and verify login works
5. Check Jellyfin connection via the channels settings page
6. Run a manual newsletter send to verify delivery



