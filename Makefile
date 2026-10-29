# ResearchSwarm dev tooling
#
# E2E database/storage maintenance against the local Supabase instance.
# Both targets are safe: they only touch the E2E test account
# (E2E_TEST_EMAIL, default ph4-test@example.com) on a local instance.

.PHONY: cleanup-e2e seed-e2e test lint check bootstrap

cleanup-e2e:
	.venv/bin/python scripts/cleanup_e2e.py

seed-e2e:
	.venv/bin/python scripts/seed_e2e.py

test:
	PYTHONPATH=.. .venv/bin/python -m pytest backend/tests -q --cov=backend --cov-config=.coveragerc --cov-fail-under=90

lint:
	ruff check backend/
	pnpm -C frontend lint

check: lint
	PYTHONPATH=.. .venv/bin/python -m pytest backend/tests -q --cov=backend --cov-config=.coveragerc --cov-fail-under=90
	pnpm -C frontend typecheck
	pnpm -C frontend test:coverage

bootstrap:
	pnpm install
	pnpm -C frontend install
	pnpm -C scripts install
	cp .env.example .env 2>/dev/null || true
