#!/usr/bin/env bash
set -euo pipefail

# Regenerate Supabase database types.
# Requires: npx supabase (Supabase CLI) and SUPABASE_PROJECT_ID env var.
#
# Usage:
#   SUPABASE_PROJECT_ID=your-project-id ./scripts/gen-supabase-types.sh
#
# Output: frontend/lib/supabase/database.types.ts

PROJECT_ID="${SUPABASE_PROJECT_ID:-}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: SUPABASE_PROJECT_ID environment variable is required" >&2
  echo "  Example: SUPABASE_PROJECT_ID=abc123 ./scripts/gen-supabase-types.sh" >&2
  exit 1
fi

npx supabase gen types typescript --project-id "$PROJECT_ID" > frontend/lib/supabase/database.types.ts

echo "Regenerated frontend/lib/supabase/database.types.ts"
