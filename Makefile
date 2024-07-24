# variables
PYVER  := 3.10
venv   := .venv
python := $(venv)/bin/python
pip    := $(venv)/bin/pip


##@ Utility
.PHONY: help
help:  ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target>\033[36m\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


##@ Setup
$(venv):
	python$(PYVER) -m venv $(venv);


.PHONY: install
install: $(venv)  ## install
	$(pip) install . -r requirements.txt


##@ Versioning
.PHONY: release
release:  ## release a new version use v=<version>
	sed -i 's/version = ".*"/version = "$(v)"/' pyproject.toml
	git add pyproject.toml
	git commit -m "Bump version $(v)"
	git tag -a $(v) -m "Release $(v)"

.PHONY: publish
publish:  ## publish to origin
	git push origin main
	git push --tags


##@ Development
.PHONY: dev
dev: $(venv) ## install dev mode
	$(pip) install -e .

.PHONY: test
test: $(venv) ## run tests
	@$(pip) -q install pytest
	$(python) -m pytest tests

.PHONY: lint
lint: $(venv)  ## run linting check
	@$(pip) -q install ruff
	$(python) -m ruff ./src

.PHONY: black
black: $(venv)  ## apply black to source code
	@$(pip) -q install black
	$(python) -m black -l79

requirements.txt:  ## generate requirements.txt
	@test -d /tmp/venv && rm -r /tmp/venv || true
	@$(python) -m venv /tmp/venv
	@/tmp/venv/bin/python -m pip -q install pip -U
	@/tmp/venv/bin/python -m pip -q install . --progress-bar off
	@/tmp/venv/bin/python -m pip freeze > requirements.txt
	$(MAKE) fix-requirements.txt

.PHONY: fix-requirements.txt
fix-requirements.txt:  ## fix requirements.txt using GH_TOKEN variable for privates repos.
	@sed -i 's/git+ssh:\/\/git@/git+https:\/\/$${GH_TOKEN}@/' requirements.txt
	@sed -i '/file:/d' requirements.txt   # removes project installation
	@cat requirements.txt

