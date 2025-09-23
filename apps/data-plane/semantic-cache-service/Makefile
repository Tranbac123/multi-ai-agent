run:
	uvicorn src.main:app --host 0.0.0.0 --port 8088

test:
	pytest -q

build:
	docker build -t semantic-cache-service:local .

docker-build:
	docker build -t semantic-cache-service:local .

docker-push:
	docker tag semantic-cache-service:local $${DOCKER_REGISTRY:-ghcr.io}/semantic-cache-service:latest
	docker push $${DOCKER_REGISTRY:-ghcr.io}/semantic-cache-service:latest

lint:
	python -m pyflakes src || true

migrate:
	echo "noop"

