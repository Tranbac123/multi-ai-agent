#!/usr/bin/env bash
set -euo pipefail
echo "Running P0 subset (7 services) ..."
export PYTHONPATH=.
pytest -q apps/data-plane/semantic-cache-service/tests/test_p0_semantic_cache.py
pytest -q apps/data-plane/chat-adapters-service/tests/test_p0_chat_adapters.py
pytest -q apps/data-plane/tools-service/tests/test_p0_tools.py
pytest -q apps/data-plane/event-relay-service/tests/test_p0_event_relay.py
pytest -q apps/data-plane/realtime-gateway/tests/test_p0_realtime.py
pytest -q apps/control-plane/notification-service/tests/test_p0_notification.py
pytest -q apps/data-plane/router-service/tests/test_p0_router.py
echo "OK"
