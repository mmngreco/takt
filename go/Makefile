NAME=takt
VERSION := $(shell git describe --abbrev=0 --tags)
BUMP := $(shell echo $(VERSION) | awk -F. '{$$NF = $$NF + 1;} 1' | sed 's/ /./g')

.PHONY: bump
bump:
	git tag -a $(BUMP) -m 'Release $(BUMP)'
	@if [ "$(shell uname)" = "Darwin" ]; then \
		sed -i '' 's/Version = "$(VERSION)"/Version = "$(BUMP)"/g' main.go; \
	else \
		sed -i 's/Version = "$(VERSION)"/Version = "$(BUMP)"/g' main.go; \
	fi

.PHONY: build
build:
	go build -o $(NAME)  main.go

.PHONY: all
all: build
	cp -f ./$(NAME) ~/.local/bin/$(NAME)

.PHONY: test
test: build
	./takt version
	@echo
	./takt cat 5
	@echo
	./takt day 5
	@echo
	./takt week 5
	@echo
	./takt month 5
	@echo
	./takt year 5
	@echo
	./takt check "delete this"
	@echo
	./takt cat 5
