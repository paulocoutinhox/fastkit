.DEFAULT_GOAL := help

PYTHON ?= python3
UV ?= uv
VENV ?= .venv
NPM ?= npm
PACKAGE ?=
TEST_ARGS ?=

PACKAGES = fastkit-core fastkit-config fastkit-db fastkit-logging fastkit-tenancy \
	fastkit-accounts fastkit-permissions fastkit-auth fastkit-cache fastkit-storage \
	fastkit-tasks fastkit-assets fastkit-mail fastkit-i18n fastkit-content fastkit-admin \
	fastkit-vendor-jquery fastkit-vendor-tabler fastkit-vendor-tabler-icons \
	fastkit-vendor-tinymce fastkit-vendor-jsoneditor \
	fastkit-reports fastkit-webhooks fastkit-cli fastkit-testkit

COV = $(foreach pkg,$(subst -,_,$(PACKAGES)),--cov=$(pkg))

# general
help:
	@echo "FastKit development commands"
	@echo "  make install         create the virtualenv and install every workspace package"
	@echo "  make install-admin   install the Playwright e2e dependencies"
	@echo "  make test            run the Python test suite"
	@echo "  make coverage        run the Python suite with a 100% branch coverage gate"
	@echo "  make test-package    run one package (PACKAGE=fastkit-core)"
	@echo "  make test-e2e        run the Playwright browser suite"
	@echo "  make seed            seed the demo database"
	@echo "  make dev             run the demo API server"
	@echo "  make lint            lint the code"
	@echo "  make format          format the code"
	@echo "  make clean           remove build and coverage artifacts"

install:
	$(UV) venv --python 3.12 $(VENV)
	$(UV) pip install $(foreach pkg,$(PACKAGES),-e packages/$(pkg)) -e examples/demo \
		"uvicorn[standard]" pytest pytest-asyncio pytest-cov httpx ruff \
		argon2-cffi pyjwt pillow jinja2 redis

install-admin:
	cd frontend/admin && $(NPM) install

test:
	$(VENV)/bin/python -m pytest $(TEST_ARGS)

test-package:
	@test -n "$(PACKAGE)" || (echo "PACKAGE is required" && exit 1)
	$(VENV)/bin/python -m pytest packages/$(PACKAGE) $(TEST_ARGS)

coverage:
	$(VENV)/bin/python -m pytest packages examples tests \
		$(COV) --cov-branch --cov-report=term-missing --cov-fail-under=100

seed:
	cd examples/demo && ../../$(VENV)/bin/python -m app.main

dev:
	cd examples/demo && FASTKIT__TASKS__RUN_WORKER=true ../../$(VENV)/bin/uvicorn app.main:app --reload --port 8100

worker:
	cd examples/demo && FASTKIT__TASKS__RUN_WORKER=true ../../$(VENV)/bin/python -m app.worker

test-e2e:
	cd frontend/admin && $(NPM) run test:e2e

lint:
	$(VENV)/bin/ruff check packages examples

format:
	$(VENV)/bin/ruff format packages examples

clean:
	rm -rf .coverage coverage.xml htmlcov
	rm -rf frontend/admin/node_modules frontend/admin/test-results
	find packages examples -type d -name "__pycache__" -prune -exec rm -rf {} +
