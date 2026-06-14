BINARY_NAME := zc
DATE_FMT=+%Y-%m-%d
RELEASE_VERSION ?= $(shell git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo dev)
BUILD_DATE := $(shell date "$(DATE_FMT)")
BUILD_FLAGS := "-w -s -X 'main.tool_version=$(RELEASE_VERSION)' -X 'main.BuildDate=$(BUILD_DATE)'"
BUILD_DIR := $(CURDIR)/build
RELEASE_DIR := $(CURDIR)/release
GOCACHE := $(CURDIR)/.gocache
export GOCACHE
INSTALL_DIR := ~
OS_ARCHES := linux/amd64 linux/arm64 windows/amd64 darwin/amd64 darwin/arm64

GO_TAGS := netgo
GO_TAGS_EMBED := netgo,embedtools

.PHONY: build build-binaries clean test install uninstall prepare-kit-embed release-artifacts

clean:
	rm -rf $(BUILD_DIR)
	rm -rf kit
	rm -rf $(RELEASE_DIR)

# Cross-compile bootstrap binaries (no embedded kit).
build-binaries:
	@for os_arch in $(OS_ARCHES); do \
		os=$$(echo $$os_arch | cut -d'/' -f1); \
		arch=$$(echo $$os_arch | cut -d'/' -f2); \
		bin_suffix=$$(if [ "$$os" = "windows" ]; then echo ".exe"; else echo ""; fi); \
		echo "Building for $$os/$$arch..."; \
		GOOS=$$os GOARCH=$$arch CGO_ENABLED=0 \
		go build \
		-tags=$(GO_TAGS) \
		-ldflags=$(BUILD_FLAGS) \
		-o $(BUILD_DIR)/$$os_arch/$(BINARY_NAME)$$bin_suffix \
		.;\
	done

# Populate the kit/ tree before building with embedtools.
prepare-kit-embed: build-binaries
	rm -rf kit
	mkdir -p kit/tools
	cp $(CURDIR)/README.md kit/
	cp $(CURDIR)/scripts/* kit/
	cp -r $(BUILD_DIR)/* kit/tools/

# Build all platform binaries with embedded kit.
build: prepare-kit-embed
	@for os_arch in $(OS_ARCHES); do \
		os=$$(echo $$os_arch | cut -d'/' -f1); \
		arch=$$(echo $$os_arch | cut -d'/' -f2); \
		bin_suffix=$$(if [ "$$os" = "windows" ]; then echo ".exe"; else echo ""; fi); \
		echo "Building for $$os/$$arch (with embedded tools)..."; \
		GOOS=$$os GOARCH=$$arch CGO_ENABLED=0 \
		go build \
		-tags=$(GO_TAGS_EMBED) \
		-ldflags=$(BUILD_FLAGS) \
		-o $(BUILD_DIR)/$$os_arch/$(BINARY_NAME)$$bin_suffix \
		.;\
	done

# Stage versioned release binaries (RELEASE_VERSION defaults to the latest git tag).
release-artifacts: build
	@if [ -z "$(RELEASE_VERSION)" ]; then echo "RELEASE_VERSION is required"; exit 1; fi
	rm -rf $(RELEASE_DIR)
	mkdir -p $(RELEASE_DIR)
	@for os_arch in $(OS_ARCHES); do \
		os=$$(echo $$os_arch | cut -d'/' -f1); \
		arch=$$(echo $$os_arch | cut -d'/' -f2); \
		bin_suffix=$$(if [ "$$os" = "windows" ]; then echo ".exe"; else echo ""; fi); \
		dest=$(RELEASE_DIR)/$(BINARY_NAME)-$(RELEASE_VERSION)-$$os-$$arch$$bin_suffix; \
		cp $(BUILD_DIR)/$$os_arch/$(BINARY_NAME)$$bin_suffix $$dest; \
		echo "Packaged $$dest"; \
	done

test: prepare-kit-embed
	CGO_ENABLED=0 go test -tags=$(GO_TAGS_EMBED) -v ./...

# build and install the binary
install: build
	@mkdir -p $(INSTALL_DIR)/bin
	@os_arch=$$(go env GOOS)/$$(go env GOARCH); \
		bin_suffix=$$(if [ "$$(go env GOOS)" = "windows" ]; then echo ".exe"; else echo ""; fi); \
		cp $(BUILD_DIR)/$$os_arch/$(BINARY_NAME)$$bin_suffix $(INSTALL_DIR)/bin/$(BINARY_NAME)$$bin_suffix
	@echo "Installed $(BINARY_NAME) to $(INSTALL_DIR)/bin"

# uninstall the binary
uninstall:
	@local_bin_name=$(INSTALL_DIR)/bin/$(BINARY_NAME)$$(if [ "$$(go env GOOS)" = "windows" ]; then echo ".exe"; else echo ""; fi);\
	echo "rm -f $$local_bin_name";\
	rm -f $$local_bin_name
