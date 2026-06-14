package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCreateKit(t *testing.T) {
	outputDir := t.TempDir()

	if err := createKit(outputDir); err != nil {
		t.Fatalf("createKit: %v", err)
	}

	readme, err := os.ReadFile(filepath.Join(outputDir, "README.md"))
	if err != nil {
		t.Fatalf("read README.md: %v", err)
	}
	if len(readme) == 0 {
		t.Fatal("README.md is empty")
	}
	if !strings.Contains(string(readme), "ZC") {
		t.Fatal("README.md missing expected content")
	}

	for _, name := range []string{"decrypt.sh", "decrypt.command", "decrypt.bat"} {
		path := filepath.Join(outputDir, name)
		info, err := os.Stat(path)
		if err != nil {
			t.Fatalf("stat %s: %v", name, err)
		}
		if info.Size() == 0 {
			t.Fatalf("%s is empty", name)
		}
	}

	shInfo, err := os.Stat(filepath.Join(outputDir, "decrypt.sh"))
	if err != nil {
		t.Fatalf("stat decrypt.sh: %v", err)
	}
	if shInfo.Mode()&0111 == 0 {
		t.Fatal("decrypt.sh is not executable")
	}
}

func TestKitOption(t *testing.T) {
	outputDir := filepath.Join(t.TempDir(), "my-kit")
	output := captureOutput(func() {
		if err := cli([]string{"--new-kit", outputDir}); err != nil {
			t.Fatalf("cli --new-kit: %v", err)
		}
	})

	if !strings.Contains(output, "Kit created at") {
		t.Fatalf("unexpected output: %q", output)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "README.md")); err != nil {
		t.Fatalf("kit output missing README.md: %v", err)
	}
}

func TestKitOptionDefaultDir(t *testing.T) {
	const kitDir = "emergency-kit"
	t.Cleanup(func() { os.RemoveAll(kitDir) })
	os.RemoveAll(kitDir)

	if err := cli([]string{"--new-kit"}); err != nil {
		t.Fatalf("cli --new-kit: %v", err)
	}
	if _, err := os.Stat(filepath.Join(kitDir, "decrypt.sh")); err != nil {
		t.Fatalf("default kit dir missing decrypt.sh: %v", err)
	}
}
