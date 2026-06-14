//go:build embedtools

package main

import "embed"

//go:embed kit
var embeddedKit embed.FS

const embeddedKitRoot = "kit"
