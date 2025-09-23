run:
	uvicorn src.main:app --host 0.0.0.0 --port 8093
test:
	pytest -q
build:
	docker build -t feature-flags-service:local .

