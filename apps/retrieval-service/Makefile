run: 
	uvicorn src.main:app --host 0.0.0.0 --port 8080
test:
	pytest -q
build:
	docker build -t retrieval-service:local .
migrate:
	echo "noop"
lint:
	python -m pyflakes src || true

