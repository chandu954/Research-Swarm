# ResearchSwarm dev tooling
#
# E2E database/storage maintenance against the local Supabase instance.
# Both targets are safe: they only touch the E2E test account
# (E2E_TEST_EMAIL, default ph4-test@example.com) on a local instance.

.PHONY: cleanup-e2e seed-e2e

cleanup-e2e:
	.venv/bin/python scripts/cleanup_e2e.py

seed-e2e:
	.venv/bin/python scripts/seed_e2e.py
