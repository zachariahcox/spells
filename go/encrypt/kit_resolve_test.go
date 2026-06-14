package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestResolveKitOutputDir_relative(t *testing.T) {
	dir := t.TempDir()
	origWd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	t.Cleanup(func() { _ = os.Chdir(origWd) })
	if err := os.Chdir(dir); err != nil {
		t.Fatalf("chdir: %v", err)
	}

	got, err := resolveKitOutputDir("emergency-kit")
	if err != nil {
		t.Fatalf("resolveKitOutputDir: %v", err)
	}
	want := filepath.Join(dir, "emergency-kit")
	if got != want {
		t.Fatalf("resolveKitOutputDir = %q, want %q", got, want)
	}
}

func TestResolveKitOutputDir_absolute(t *testing.T) {
	got, err := resolveKitOutputDir("/tmp/my-kit")
	if err != nil {
		t.Fatalf("resolveKitOutputDir: %v", err)
	}
	want := filepath.Clean("/tmp/my-kit")
	if got != want {
		t.Fatalf("resolveKitOutputDir = %q, want %q", got, want)
	}
}

func TestCreateKit_overwritesCurrentWorkingDirectory(t *testing.T) {
	dir := t.TempDir()

	origWd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	t.Cleanup(func() { _ = os.Chdir(origWd) })

	if err := os.Chdir(dir); err != nil {
		t.Fatalf("chdir: %v", err)
	}

	if err := createKit(dir); err != nil {
		t.Fatalf("createKit in cwd: %v", err)
	}

	readme := filepath.Join(dir, "README.md")
	if err := os.WriteFile(readme, []byte("stale content"), 0644); err != nil {
		t.Fatalf("write stale readme: %v", err)
	}

	if err := createKit(dir); err != nil {
		t.Fatalf("createKit overwrite in cwd: %v", err)
	}

	data, err := os.ReadFile(readme)
	if err != nil {
		t.Fatalf("read readme: %v", err)
	}
	if string(data) == "stale content" {
		t.Fatal("README.md was not overwritten")
	}
	if !strings.Contains(string(data), "ZC") {
		t.Fatal("README.md missing expected kit content")
	}
}
