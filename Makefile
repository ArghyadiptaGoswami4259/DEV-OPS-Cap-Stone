.DEFAULT_GOAL := help
SHELL := /bin/bash
PY := .venv/bin/python
PIP := .venv/bin/pip
IMAGE ?= taskflow:local

.PHONY: help env install lint test coverage run validate configure configure-check release-check \
        lab-manual diagrams evidence-install evidence evidence-showcase tools tools-check \
        local-runtime local-runtime-check local-cluster-up local-cluster-check \
        local-cluster-down docker-build compose-up compose-observability kind-up deploy-local \
        verify-platform canary-drill rollback hooks clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

env: ## Generate a local .env with random development-only passwords
	@test -f .env || { umask 077; printf 'POSTGRES_PASSWORD=%s\nGRAFANA_PASSWORD=%s\nAPP_VERSION=1.0.0\nAPP_GIT_SHA=local\n' "$$(openssl rand -hex 24)" "$$(openssl rand -hex 18)" > .env; }
	@echo "Created .env with random local passwords."

install: env ## Create the virtualenv and install runtime + development dependencies
	@python3 -m venv .venv
	@$(PIP) install --quiet --disable-pip-version-check -r requirements-dev.txt -r requirements-tools.txt

lint: ## Run formatting rules, static typing, repository validation, and dependency audit
	@$(PY) -m ruff check .
	@$(PY) -m mypy app
	@$(PY) -m bandit -r app -ll -f txt
	@$(PY) tools/validate_repo.py
	@$(PY) -m pip_audit -r requirements.txt --strict

test: ## Run the API test suite
	@$(PY) -m pytest -q

coverage: ## Run tests with branch coverage
	@$(PY) -m pytest --cov=app --cov-report=term-missing --cov-report=xml

run: ## Run TaskFlow locally with a disposable SQLite database
	@mkdir -p .cache
	@DATABASE_URL=sqlite:///./.cache/taskflow.db APP_ENVIRONMENT=local HOST=0.0.0.0 $(PY) -m app

configure: ## Render platform manifests from config/platform.env and environment overrides
	@$(PY) tools/configure_platform.py --apply

configure-check: ## Verify platform manifests are synchronized with config/platform.env
	@$(PY) tools/configure_platform.py --check

validate: configure-check ## Parse every manifest and verify required platform files
	@$(PY) tools/validate_repo.py

tools: ## Install local Go/Helm/kubectl/Kind/Docker CLI tooling into ignored .tools/
	@bash tools/install-platform-tools.sh

tools-check: ## Verify the locally installed platform toolchain
	@$(PY) tools/check-platform-tools.py

local-runtime: ## Build a Docker-independent container/Kubernetes runtime into ignored .tools/
	@bash tools/install-local-runtime.sh

local-runtime-check: ## Verify source-built Podman/runc/CNI/containerd/etcd/Kubernetes binaries
	@$(PY) tools/check-local-runtime.py --offline

local-cluster-up: ## Start the Docker-independent local Kubernetes control plane
	@bash tools/local-cluster.sh up

local-cluster-check: ## Verify local Kubernetes readiness, node health, scheduling and logs
	@$(PY) tools/check-local-runtime.py --cluster

local-cluster-down: ## Stop the Docker-independent local Kubernetes control plane
	@bash tools/local-cluster.sh down

release-check: ## Verify the production release manifest and policy gates
	@$(PY) tools/verify_release.py --environment prod

lab-manual: ## Regenerate the original DevOps lab manual (PDF, DOCX and Markdown)
	@$(PY) tools/generate_diagrams.py
	@$(PY) tools/generate_lab_manual.py

evidence-install: ## Install optional local screenshot-capture dependencies
	@$(PIP) install --quiet --disable-pip-version-check -r requirements-evidence.txt

evidence: ## Capture local-host screenshots and rebuild the screenshot-enhanced manual
	@$(PY) tools/capture_implementation_evidence.py
	@$(MAKE) lab-manual

evidence-showcase: ## Serve the local implementation evidence gallery on port 8011
	@python3 -m http.server 8011 --bind 0.0.0.0 --directory docs/implementation-showcase

diagrams: ## Regenerate architecture and evidence diagrams
	@$(PY) tools/generate_diagrams.py

docker-build: ## Build the immutable container image
	@docker build --build-arg VERSION=1.0.0 --build-arg GIT_SHA="$$(git rev-parse --short HEAD)" -t $(IMAGE) .

compose-up: env ## Run TaskFlow and PostgreSQL with Docker Compose
	@docker compose up --build -d
	@echo "TaskFlow: http://localhost:8000"

compose-observability: env ## Run TaskFlow plus Prometheus, Loki, Promtail and Grafana
	@docker compose --profile observability up --build -d
	@echo "TaskFlow: http://localhost:8000 | Grafana: http://localhost:3000"

kind-up: ## Create a reproducible local Kubernetes cluster and install the platform
	@bash infra/scripts/bootstrap-local.sh

deploy-local: ## Build, load and deploy the local GitOps overlay into Kind
	@docker build --build-arg VERSION=local --build-arg GIT_SHA="$$(git rev-parse --short HEAD)" -t taskflow:local .
	@kind load docker-image taskflow:local --name taskflow
	@kubectl apply -k deploy/gitops/environments/dev

verify-platform: ## Check cluster resources, rollout health and app endpoints
	@bash infra/scripts/verify-platform.sh

canary-drill: ## Inject failures and observe an automated canary abort
	@bash infra/scripts/canary-drill.sh

rollback: ## Abort the current rollout and return to the last stable ReplicaSet
	@bash infra/scripts/rollback.sh

hooks: ## Install local Git hooks for commit-message and pre-commit validation
	@bash tools/install-git-hooks.sh

clean: ## Remove local caches and tool binaries (never removes the repository or .git)
	@rm -rf .cache .tools .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
