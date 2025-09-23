run:
	uvicorn src.main:app --host 0.0.0.0 --port 8083

test:
	pytest -q

build:
	docker build -t model-gateway:local .

docker-build:
	docker build -t model-gateway:local .

docker-push:
	docker tag model-gateway:local $${DOCKER_REGISTRY:-ghcr.io}/model-gateway:latest
	docker push $${DOCKER_REGISTRY:-ghcr.io}/model-gateway:latest

lint:
	python -m pyflakes src || true

migrate:
	echo "noop"

