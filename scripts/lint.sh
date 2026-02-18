#!/bin/bash

set -e  # Exit on any error

echo "🔍 Running Ruff linter..."
cd backend
uv run ruff check .

echo "📐 Running Ruff formatter check..."
uv run ruff format --check .

echo "✅ All checks passed!"