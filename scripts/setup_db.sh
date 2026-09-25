#!/usr/bin/env bash
# Create the FarsiYab database role, database and extensions.
#
# Run as a PostgreSQL superuser (on Linux: `sudo -u postgres scripts/setup_db.sh`).
# Creating the postgis extension needs superuser rights; everything else is
# done later by `farsiyab db init` as the normal application user.
#
#   DB_NAME      database name        (default: farsiyab)
#   DB_USER      application role     (default: farsiyab)
#   DB_PASSWORD  application password (default: farsiyab — change it on servers)
set -euo pipefail

DB_NAME="${DB_NAME:-farsiyab}"
DB_USER="${DB_USER:-farsiyab}"
DB_PASSWORD="${DB_PASSWORD:-farsiyab}"

psql -v ON_ERROR_STOP=1 --no-psqlrc -q <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE "${DB_USER}" LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE "${DB_NAME}" OWNER "${DB_USER}"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec
SQL

psql -v ON_ERROR_STOP=1 --no-psqlrc -q -d "${DB_NAME}" <<SQL
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
GRANT ALL ON SCHEMA public TO "${DB_USER}";
SQL

echo "Database '${DB_NAME}' is ready for role '${DB_USER}'."
echo "Next: cd services/api && uv run farsiyab db init"
