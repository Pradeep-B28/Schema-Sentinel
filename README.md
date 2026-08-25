<p align="center">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white" alt="GitHub Actions" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="MIT License" />
  <img src="https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge" alt="Code Style: Black" />
</p>

<h1 align="center">🔍 Schema Sentinel</h1>

<p align="center">
  <b>Stop guessing. Start knowing.</b><br>
  <i>Pre-migration risk analysis for PostgreSQL — catch dangerous schema changes before they reach production.</i>
</p>

<p align="center">
  <a href="#-key-features">Key Features</a> •
  <a href="#-how-it-works">How It Works</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-usage--cli-reference">Usage</a> •
  <a href="#-github-actions-integration">GitHub Action</a> •
  <a href="#-risk-rules-reference">Risk Matrix</a>
</p>

---

## 🚀 Why Schema Sentinel?

Database migrations are **one of the single greatest vectors for production outages**. 

- A innocent-looking `ALTER TABLE` on a 10M+ row table acquires an `ACCESS EXCLUSIVE` lock, stalling application traffic for minutes.
- Adding a `NOT NULL` constraint without a `DEFAULT` value aborts immediately on existing rows.
- Executing `CREATE INDEX` without `CONCURRENTLY` locks writes across entire tenant data sets.
- Dropping or renaming columns silently breaks legacy microservices and downstream data pipelines.

**Schema Sentinel** shifts database safety **left into your CI/CD workflow**. By parsing SQL migration files and dynamically fetching production database metadata via safe, read-only connections, Schema Sentinel scores risk vectors, alerts engineering teams, and blocks unsafe pull requests before they touch production.

---

## ✨ Key Features

- 🔍 **AST-Based SQL Migration Parser**: Accurately extracts `CREATE`, `ALTER`, `DROP`, `RENAME`, and constraint statements using `sqlparse`.
- 📊 **Production-Aware Dynamic Profiling**: Reads real PostgreSQL table metrics (row count, table size, index size, column count, PK/FK constraints) to deliver context-specific risk evaluations.
- 🎯 **Deep `ALTER TABLE` Antipattern Engine**: Identifies hazardous database changes like type coercions, non-default `NOT NULL` additions, and un-isolated constraints.
- 🚦 **4-Axis Risk Scoring Engine**: Computes scores (0–10 scale) for **Lock Risk**, **Data Integrity Risk**, **Compatibility Risk**, and **Performance Risk**.
- 🔒 **Strict Read-Only Enforcement**: Automatically sets `SET session characteristics AS TRANSACTION READ ONLY;` when querying live PostgreSQL schemas to guarantee zero side-effects.
- 🤖 **CI/CD Native & GitHub Action**: Generates terminal reports, rich GitHub PR Markdown comment summaries, and raw JSON logs for automated pipeline gating (`--fail-on-high`).

---

## 🛠️ How It Works

```
   ┌───────────────────────┐
   │  SQL Migration Files  │  (e.g., migrations/*.sql)
   └───────────┬───────────┘
               │
               ▼
┌─────────────────────────────┐
│  AST Engine & SQL Parser    │  Extracts DDL operations & target tables
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ PostgreSQL Read-Only Profiler│  Queries pg_class & pg_indexes for table size & row count
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  4-Axis Risk Matrix Engine  │  Evaluates Lock, Integrity, Compatibility & Performance risks
└──────────────┬──────────────┘
               │
               ├──────────────────────────┬──────────────────────────┐
               ▼                          ▼                          ▼
      🖥️  Human CLI Report       📝 GitHub PR Markdown       🤖 Machine-Readable JSON
```

---

## ⚡ Quick Start & Installation

### Option 1: Install Local Package
Clone the repository and install locally:

```bash
git clone https://github.com/Pradeep-B28/Schema-Sentinel.git
cd Schema-Sentinel
pip install -e .
```

### Option 2: Environment Configuration
Create a `.env` file in your root directory or export your `DATABASE_URL`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/my_production_db
```

*Note: If no database connection string is supplied, Schema Sentinel operates in `--no-db` mode using intelligent static heuristics.*

---

## 💻 Usage & CLI Reference

Schema Sentinel provides a clean CLI with two primary commands: `analyze` and `profile`.

### 1. Analyzing Migration Files (`analyze`)

Analyze a migration SQL file against production database metrics:

```bash
# Analyze using environment DATABASE_URL
schema-sentinel analyze migrations/001_add_users.sql

# Run offline without a database connection (Heuristic mode)
schema-sentinel analyze migrations/001_add_users.sql --no-db

# Format output for GitHub PR comments
schema-sentinel analyze migrations/001_add_users.sql --format github

# Output raw JSON for custom CI tool parsing
schema-sentinel analyze migrations/001_add_users.sql --format json

# Fail with non-zero exit code if high-risk migrations are detected
schema-sentinel analyze migrations/001_add_users.sql --fail-on-high
```

#### CLI Command Flags

| Flag | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `--connection` | `-c` | PostgreSQL connection string (overrides `DATABASE_URL`) | `None` |
| `--no-db` | - | Run heuristic-only analysis without connecting to DB | `False` |
| `--format` | `-f` | Output format: `human`, `github`, `json` | `human` |
| `--fail-on-high` | - | Exit with code `1` if any `🔴 HIGH` risk operations are detected | `False` |

---

### 2. Table Profiling (`profile`)

Inspect actual statistics for any table in your database to assess scale and index layout:

```bash
schema-sentinel profile users
```

**Example Output:**
```text
📊 Profiling table: users

📋 Table Statistics:
  --------------------------------------------------
  Table Name:      users
  Row Count:       1,452,090
  Total Size:      412.50 MB
  Table Size:      280.10 MB
  Index Size:      132.40 MB
  Columns:         18
  Indexes:         4
  Has Primary Key: True
  Foreign Keys:    accounts, organizations
```

---

## 🤖 GitHub Actions Integration

Automate pre-migration analysis in every Pull Request that introduces database schema changes.

### `.github/workflows/schema-sentinel.yml`

```yaml
name: Schema Sentinel Analysis

on:
  pull_request:
    paths:
      - '**.sql'
      - 'migrations/*.sql'

jobs:
  analyze-migrations:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Schema Sentinel
        run: pip install git+https://github.com/Pradeep-B28/Schema-Sentinel.git

      - name: Run Schema Analysis
        run: |
          schema-sentinel analyze migrations/sample_migration.sql --no-db --format github > report.md || true

      - name: Post Comment to PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('report.md', 'utf8');
            await github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: report
            });

      - name: Block Unsafe High-Risk Migrations
        run: |
          if grep -q "🔴.*HIGH" report.md; then
            echo "❌ High-risk database migrations detected! Please review recommendations."
            exit 1
          fi
```

### GitHub PR Comment Preview

> ## 🔍 Schema Sentinel Migration Analysis
> 
> | Operation | Table | Risk Level | Lock Risk | Data Integrity | Compatibility | Performance |
> |-----------|-------|------------|-----------|----------------|--------------|-------------|
> | Alter Table | `orders` | 🔴 HIGH | 8/10 | 8/10 | 8/10 | 5/10 |
> | Create Index | `users` | 🟡 MEDIUM | 5/10 | 1/10 | 1/10 | 4/10 |
> 
> ### ⚠️ High-Risk Operations
> **Alter Table** on `orders`
> - ❌ Changing column data type (requires full table rewrite & conversion lock)
>   - 💡 *Recommendation:* Test conversion on staging; consider adding a new column, backfilling asynchronously, then dropping the old column.

---

## 🚦 Risk Rules & Antipattern Reference

Schema Sentinel continuously evaluates your SQL migration statements against proven zero-downtime database patterns:

| SQL Pattern | Detected Risk | Severity | Recommendation |
| :--- | :--- | :---: | :--- |
| `DROP TABLE ...` | Permanent data loss | 🔴 HIGH | Backup table & rename first before executing final drop. |
| `ALTER TABLE ... DROP COLUMN ...` | Irreversible column deletion | 🔴 HIGH | Mark column as unused in application code before dropping. |
| `ALTER TABLE ... ADD COLUMN ... NOT NULL` | Migration execution failure | 🔴 HIGH | Add column with a `DEFAULT` value or as nullable, then set `NOT NULL`. |
| `ALTER TABLE ... ALTER COLUMN ... TYPE ...` | Full table rewrite lock | 🔴 HIGH | Add new column, backfill data, and switch references. |
| `ALTER TABLE ... RENAME COLUMN/TABLE` | Application breakage | 🔴 HIGH | Update application queries first; deploy an alias view. |
| `CREATE INDEX ...` (without `CONCURRENTLY`) | Table write locking | 🟡 MEDIUM | Use `CREATE INDEX CONCURRENTLY` to avoid write locks on large tables. |
| `ALTER TABLE ... ADD CONSTRAINT ...` | Validation table scan | 🟡 MEDIUM | Add constraint with `NOT VALID`, then run `VALIDATE CONSTRAINT` during off-peak hours. |

---

## 🧪 Development & Testing

Run unit and integration tests locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run sample migration analysis
schema-sentinel analyze alter_test.sql --no-db
```

---

## 📄 License

This project is distributed under the **MIT License**. See [`LICENSE`](LICENSE) for full details.

---

<p align="center">
  Crafted with ❤️ by <a href="https://github.com/Pradeep-B28"><b>Pradeep-B28</b></a>
</p>