#!/usr/bin/env bash
set -euo pipefail
echo "Running P0 tests (smoke) ..."
pytest -q -m p0 apps/control-plane/policy-adapter/tests
pytest -q -m p0 apps/control-plane/config-service/tests
pytest -q -m p0 apps/control-plane/feature-flags-service/tests
pytest -q -m p0 apps/control-plane/registry-service/tests
pytest -q -m p0 apps/control-plane/usage-metering/tests
pytest -q -m p0 apps/control-plane/audit-log/tests
pytest -q -m p0 apps/data-plane/model-gateway/tests
pytest -q -m p0 apps/data-plane/retrieval-service/tests
pytest -q -m p0 apps/data-plane/ingestion-service/tests
pytest -q -m p0 apps/data-plane/api-gateway/tests
pytest -q -m p0 apps/data-plane/event-relay-service/tests
pytest -q -m p0 apps/data-plane/migration-runner/tests
echo "OK"
