run:
	uvicorn src.main:app --host 0.0.0.0 --port 8097

test:
	pytest -q

build:
	docker build -t notification-service:local .

docker-build:
	docker build -t notification-service:local .

docker-push:
	docker tag notification-service:local $${DOCKER_REGISTRY:-ghcr.io}/notification-service:latest
	docker push $${DOCKER_REGISTRY:-ghcr.io}/notification-service:latest

lint:
	python -m pyflakes src || true

migrate:
	echo "noop"

