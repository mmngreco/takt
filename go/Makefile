NAME=takt
head=5

.PHONY: build
build:
	go build -o $(NAME)  main.go

.PHONY: all
all: build
	cp -f ./$(NAME) ~/.local/bin/$(NAME)

.PHONY: test
test: build
	./takt version
	@sleep 1
	@echo
	./takt cat $(head)
	@sleep 1
	@echo
	./takt day $(head)
	@sleep 1
	@echo
	./takt week $(head)
	@sleep 1
	@echo
	./takt month $(head)
	@sleep 1
	@echo
	./takt year $(head)
	@sleep 1
	@echo
	./takt check "deleteMe"
	@sleep 1
	@echo
	./takt cat $(head)
	@sleep 1


clean:
	@sed -i '/deleteMe/d' $(shell echo $$TAKT_FILE)
	cat $(shell echo $$TAKT_FILE)


lint:
	go fmt ./...
	go vet ./...
	goci-lint
