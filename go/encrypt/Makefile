GIT_TAG?= $(shell git describe --always --tags)
DATE_FMT=+%Y-%m-%d
BUILD_DATE ?= $(shell date "$(DATE_FMT)")
BUILD_FLAGS := "-w -s -X 'main.Version=$(GIT_TAG)' -X 'main.GitTag=$(GIT_TAG)' -X 'main.BuildDate=$(BUILD_DATE)'"
BUILD_DIR := $(CURDIR)/build
INSTALL_DIR := ~

BINARY_NAME := zcrypt

# build these rules even if files with the same name exist.
.PHONY: build clean test install uninstall

clean:
	rm -rf $(BUILD_DIR)

build:
	mkdir -p $(BUILD_DIR)
	CGO_ENABLED=0 go build -tags=netgo -ldflags=$(BUILD_FLAGS) -o $(BUILD_DIR)/$(BINARY_NAME) -v .

test:
	CGO_ENABLED=0 go test -v ./...

# build and install the binary
install: build
	mkdir -p $(INSTALL_DIR)/bin
	cp $(BUILD_DIR)/$(BINARY_NAME) $(INSTALL_DIR)/bin/$(BINARY_NAME)

# uninstall the binary
uninstall:
	rm -f $(INSTALL_DIR)/bin/$(BINARY_NAME)