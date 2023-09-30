VERSION := $(shell git describe --tags)
venv := .venv
python := $(venv)/bin/python
pip := $(venv)/bin/pip
flit := $(venv)/bin/flit
PY_VERSION := $(shell cat .python-version)


help:
	@echo "Makefile help"
	@echo "Usage: make [target]"
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "    \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

$(venv):  ## Create a virtual environment using conda or venv
	@if command -v conda >/dev/null 2>&1; then \
		conda create --prefix $(venv) -y -q python=; \
	else \
		python3 -m venv $(venv); \
	fi

install: build ## Build the package and install it
	$(pip) install dist/tu_paquete-$(VERSION)-py3-none-any.whl

dev: $(venv)  ## Install development dependencies
	$(pip) install -e .
	$(pip) install -q -r requirements-dev.txt

test: $(venv)  ## Run test
	$(python) -m pytest tests

lint: $(venv)  ## Check lint
	$(python) -m ruff .

black: $(venv)  ## Fix source code applying black
	$(python) -m black -l 79 takt.py tests

update_version: ## Update the version in pyproject.toml to the latest git tag
	sed -i 's/version = .*/version = "$(VERSION)"/' pyproject.toml

build: update_version ## Update the version and build the package
	$(flit) build

publish: build ## Build the package and publish it
	$(flit) publish

info: ## Print the current version
	@echo version: $(VERSION)
	@echo v: $(v)

tag: ## Create a new git tag with the specified version and update pyproject.toml
	@git tag --force -a $(v) -m "version $(v)" > /dev/null
	@$(MAKE) update_version > /dev/null
	@git add pyproject.toml > /dev/null
	git commit -m "Bump version to $(v)"

.PHONY: update_version build install dev publish info help
