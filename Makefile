VERSION := $(shell git describe --tags)

help: ## print help
	@echo "Makefile help"
	@echo "Usage: make [target]"
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "    \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

update_version: ## Update the version in pyproject.toml to the latest git tag
	sed -i 's/version = .*/version = "$(VERSION)"/' pyproject.toml

build: update_version ## Update the version and build the package
	flit build

install: build ## Build the package and install it
	pip install dist/tu_paquete-$(VERSION)-py3-none-any.whl

dev: update_version ## Update the version and install the package in editable mode
	pip install -e .

publish: build ## Build the package and publish it
	flit publish

info: ## Print the current version
	@echo version: $(VERSION)
	@echo v: $(v)

tag: ## Create a new git tag with the specified version and update pyproject.toml
	@git tag --force -a $(v) -m "version $(v)" > /dev/null
	@$(MAKE) update_version VERSION=$(v) > /dev/null
	@git add pyproject.toml > /dev/null
	git commit -m "Bump version to $(v)"

.PHONY: update_version build install dev publish info help
