//go:build !embedtools

package main

import "embed"

var embeddedKit embed.FS

const embeddedKitRoot = ""
