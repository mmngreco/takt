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
	sleep 0.5
	@echo
	./takt cat $(head)
	sleep 0.5
	@echo
	./takt day $(head)
	sleep 0.5
	@echo
	./takt week $(head)
	sleep 0.5
	@echo
	./takt month $(head)
	sleep 0.5
	@echo
	./takt year $(head)
	sleep 0.5
	@echo
	./takt check "deleteMe"
	sleep 0.5
	@echo
	./takt cat $(head)
	sleep 0.5


clean:
	sed -i '/deleteMe/d' $(shell echo $$TAKT_FILE)
