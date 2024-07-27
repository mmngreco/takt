NAME=takt
head=5
bin=./bin/takt


$(bin):
	mkdir -p ./bin
	go build -o ./bin/$(NAME) main.go

.PHONY: build
build: $(bin)

.PHONY: all
all: build lint test clear
	cp -f $(bin) ~/.local/$(bin)

.PHONY: test
test: build
	$(bin) version
	@sleep 1
	@echo
	$(bin) cat $(head)
	@sleep 1
	@echo
	$(bin) day $(head)
	@sleep 1
	@echo
	$(bin) d $(head)
	@sleep 1
	@echo
	$(bin) week $(head)
	@sleep 1
	@echo
	$(bin) w $(head)
	@sleep 1
	@echo
	$(bin) month $(head)
	@sleep 1
	@echo
	$(bin) m $(head)
	@sleep 1
	@echo
	$(bin) year $(head)
	@sleep 1
	@echo
	$(bin) y $(head)
	@sleep 1
	@echo
	$(bin) check "deleteMe"
	@sleep 1
	@echo
	$(bin) c "deleteMe"
	@sleep 1
	@echo
	$(bin) cat $(head)
	@sleep 1


clear:
	@sed -i '/deleteMe/d' $(shell echo $$TAKT_FILE)
	cat $(shell echo $$TAKT_FILE)


lint:
	go fmt ./...
	go vet ./...
