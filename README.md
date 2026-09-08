<div align="center">

# 🔍 Schema Sentinel — PostgreSQL Pre-Migration Lock & Risk Analyzer

### *Detect Dangerous ALTER TABLE Commands, Exclusive Table Locks, and Schema Breaking Changes Before Production*

[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](action.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

<p align="center">
  <a href="#-detected-risks--rules">Detected Anti-Patterns</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-github-action-integration">GitHub Action</a>
</p>

---

</div>

> [!WARNING]
> Running an unindexed `ALTER TABLE ADD COLUMN ... DEFAULT` or dropping a table in PostgreSQL can cause catastrophic lock contention and downtime. **Schema Sentinel** acts as a static gatekeeper in your CI/CD pipeline.

---

## 🛑 Detected Risks & Anti-Patterns

<div align="center">

| Risk Level | Anti-Pattern SQL Operation | System Impact |
| :--- | :--- | :--- |
| 🔴 **CRITICAL** | `ALTER TABLE ADD COLUMN` with volatile defaults | Holds `ACCESS EXCLUSIVE` lock; rewrites large tables. |
| 🔴 **CRITICAL** | `DROP TABLE` / `DROP COLUMN` without deprecation phase | Immediately breaks dependent API services & queries. |
| 🟡 **WARNING** | `CREATE INDEX` without `CONCURRENTLY` | Blocks write transactions during index construction. |
| 🟡 **WARNING** | Unindexed Foreign Key Constraints | Causes table-level locks during parent table updates. |

</div>

---

## 🚀 Quick Start & CLI Usage

### Installation
```bash
pip install -e .
```

### Scanning Migration Scripts
```bash
# Scan a single SQL migration file
schema-sentinel scan sample_migration.sql

# Scan an entire directory of migrations
schema-sentinel scan ./migrations/
```

---

## 🐙 GitHub Action Integration

Add Schema Sentinel directly to your pull request workflow (`.github/workflows/schema-sentinel.yml`):

```yaml
name: Schema Sentinel Migration Audit

on:
  pull_request:
    paths:
      - 'migrations/*.sql'

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Pradeep-B28/Schema-Sentinel@v1
        with:
          migration_path: 'migrations/'
```

---

<div align="center">

Developed by **[Pradeep](https://github.com/Pradeep-B28)**

</div>
