#!/bin/bash
# ─────────────────────────────────────────────────────────────
# PostgreSQL init script — create multiple databases
# Called by Docker entrypoint on first container start
# ─────────────────────────────────────────────────────────────
set -e

function create_database() {
    local database=$1
    echo "  Creating database: $database"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        CREATE DATABASE $database;
        GRANT ALL PRIVILEGES ON DATABASE $database TO $POSTGRES_USER;
EOSQL
}

if [ -n "$POSTGRES_MULTIPLE_DATABASES" ]; then
    echo "Creating multiple databases: $POSTGRES_MULTIPLE_DATABASES"
    for db in $(echo $POSTGRES_MULTIPLE_DATABASES | tr ',' ' '); do
        # Skip if it's the default database (already created by Docker)
        if [ "$db" != "$POSTGRES_DB" ] && [ "$db" != "$POSTGRES_USER" ]; then
            create_database $db
        fi
    done
    echo "✅ Multiple databases created."
fi
