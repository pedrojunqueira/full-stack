#!/bin/bash
set -e

echo "🚀 Starting application..."

# Parse database host from DATABASE_URL
DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=5432

# Wait for database to be ready
echo "⏳ Waiting for database at $DB_HOST:$DB_PORT..."
timeout=60
counter=0
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U postgres 2>/dev/null; do
  counter=$((counter + 1))
  if [ $counter -gt $timeout ]; then
    echo "❌ Database not ready after ${timeout}s, starting anyway..."
    break
  fi
  echo "  Database not ready, waiting... ($counter/${timeout}s)"
  sleep 1
done
echo "✅ Database is ready!"

# Run migrations
echo "📦 Running database migrations..."
cd /usr/src/app

# Initialize aerich if needed (first deployment)
if [ ! -d "migrations" ]; then
  echo "  Initializing aerich..."
  uv run aerich init -t app.db.TORTOISE_ORM || true
  uv run aerich init-db || true
else
  echo "  Running pending migrations..."
  uv run aerich upgrade || true
fi

echo "✅ Migrations complete!"

# Start the application
echo "🌐 Starting uvicorn..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000