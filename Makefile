.DEFAULT_GOAL := help

APP_ENV ?= dev

# general
help:
	@echo "Type: make [rule]. Available options are:"
	@echo ""
	@echo "- help"
	@echo "- deps"
	@echo "- deps-update"
	@echo "- format"
	@echo "- lint"
	@echo ""
	@echo "- start"
	@echo "- test"
	@echo "- test-cov"
	@echo ""
	@echo "- migrate"
	@echo "- recreate-schema"
	@echo "- schema-diff"
	@echo "- administrator"
	@echo "- seed"
	@echo "- delivery"
	@echo "- sweep-files"
	@echo "- sweep-files-apply"
	@echo ""
	@echo "- admin-deps"
	@echo "- admin-start"
	@echo "- admin-build"
	@echo "- admin-test"
	@echo "- admin-test-cov"
	@echo "- admin-format"
	@echo ""
	@echo "- site-deps"
	@echo "- site-start"
	@echo "- site-build"
	@echo "- site-test"
	@echo "- site-test-cov"
	@echo "- site-format"
	@echo ""
	@echo "- docker-build"
	@echo "- docker-start"
	@echo "- docker-stop"
	@echo "- docker-restart"
	@echo "- docker-logs"
	@echo "- docker-migrate"
	@echo "- docker-administrator"
	@echo ""

deps:
	uv sync

deps-update:
	uv lock --upgrade
	uv sync

format:
	uv run ruff check --fix .
	uv run ruff format .
	npm --prefix webapps/admin run format
	npm --prefix webapps/site run format

lint:
	uv run ruff check .
	uv run ruff format --check .

start:
	uv run uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug --reload

# The contrast of both palettes is measured on what the builds write, so the suite states the builds it reads instead of finding them left over from a previous run.
test: admin-build site-build
	uv run pytest

test-cov: admin-build site-build
	uv run pytest --cov --cov-report=html --cov-report=term

migrate:
	uv run python manage.py migrate

recreate-schema:
	uv run python manage.py recreate-schema --yes

schema-diff:
	uv run python manage.py schema-diff $(if $(CURRENT),--current $(CURRENT))

administrator:
	uv run python manage.py create-administrator --username $(USERNAME) --email $(EMAIL) --password $(PASSWORD)

seed:
	uv run python manage.py seed --yes

delivery:
	uv run python manage.py run-delivery

sweep-files:
	uv run python manage.py sweep-files

sweep-files-apply:
	uv run python manage.py sweep-files --yes

admin-deps:
	npm --prefix webapps/admin install

admin-start:
	npm --prefix webapps/admin run dev

admin-build:
	npm --prefix webapps/admin run build

admin-test:
	npm --prefix webapps/admin run test

admin-test-cov:
	npm --prefix webapps/admin run test:cov

admin-format:
	npm --prefix webapps/admin run format

site-deps:
	npm --prefix webapps/site install

site-start:
	npm --prefix webapps/site run dev

site-build:
	npm --prefix webapps/site run build

site-test: site-build
	npm --prefix webapps/site run test

site-test-cov:
	npm --prefix webapps/site run test:cov

site-format:
	npm --prefix webapps/site run format

docker-build:
	docker compose build

docker-start:
	APP_ENV=$(APP_ENV) docker compose up -d

docker-stop:
	docker compose down

docker-restart:
	docker compose restart

docker-logs:
	docker compose logs -f

docker-migrate:
	APP_ENV=$(APP_ENV) docker compose run --rm --entrypoint python app manage.py migrate

docker-administrator:
	APP_ENV=$(APP_ENV) docker compose run --rm --entrypoint python app manage.py create-administrator --username $(USERNAME) --email $(EMAIL) --password $(PASSWORD)
