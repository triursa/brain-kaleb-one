# brain.kaleb.one

Personal Notes + Mission Control for the kaleb.one ecosystem.

Built from `second-brain-vault` via a Python SSG. Deployed to Cloudflare Pages behind Zero Trust Access.

## Architecture

```
second-brain-vault/domains/{health,household,novel,...}
         ↓
scripts/build.py (Python SSG)
         ↓
brain-site/ (static HTML + CSS + JS)
         ↓
Cloudflare Pages → brain.kaleb.one
```

## Build

```bash
VAULT_DIR=/path/to/second-brain-vault OUTPUT_DIR=/tmp/brain-site python3 scripts/build.py
```

## Domains Served

**Personal Notes** (rendered inline):
- health, household, novel, finance, tools, ai-tooling
- inbox, journal, notes/personal, maps

**Graduated Apps** (launch cards):
- kitchen.kaleb.one, watch.kaleb.one, read.kaleb.one, masks.kaleb.one, music.kaleb.one, wish.kaleb.one

## CI/CD

Vault push → `trigger-brain-rebuild.yml` → `brain-kaleb-one` repo → build → deploy to Cloudflare Pages.