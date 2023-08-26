VERSION := $(shell git describe --tags)

update_version:
	sed -i 's/version = .*/version = "$(VERSION)"/' pyproject.toml

build: update_version
	flit build

install: build
	pip install dist/tu_paquete-$(VERSION)-py3-none-any.whl

dev: update_version
	pip install -e .

publish: build
	flit publish

info:
	@echo version: $(VERSION)
	@echo v: $(v)

tag:
	git tag -a $(v) -m "version $(v)"
	$(MAKE) update_version

.PHONY: update_version build install dev publish info
