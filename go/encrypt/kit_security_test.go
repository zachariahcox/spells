package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPathWithinRoot(t *testing.T) {
	root := filepath.Clean("/tmp/kit")
	tests := []struct {
		path string
		want bool
	}{
		{root, true},
		{filepath.Join(root, "README.md"), true},
		{filepath.Join(root, "tools", "linux", "amd64", "zc"), true},
		{"/tmp/kit-evil", false},
		{filepath.Join(root, "..", "outside"), false},
	}
	for _, tt := range tests {
		if got := pathWithinRoot(root, tt.path); got != tt.want {
			t.Errorf("pathWithinRoot(%q, %q) = %v, want %v", root, tt.path, got, tt.want)
		}
	}
}

func TestSafeWriteFile_rejectsSymlink(t *testing.T) {
	if os.Getuid() == 0 {
		t.Skip("root can follow symlinks despite O_NOFOLLOW on some systems")
	}

	root := t.TempDir()
	target := filepath.Join(t.TempDir(), "target")
	if err := os.WriteFile(target, []byte("secret"), 0644); err != nil {
		t.Fatalf("write target: %v", err)
	}

	link := filepath.Join(root, "README.md")
	if err := os.Symlink(target, link); err != nil {
		t.Skip("symlinks not supported:", err)
	}

	err := safeWriteFile(root, link, []byte("pwned"), 0644)
	if err == nil {
		t.Fatal("expected error writing through symlink")
	}

	data, err := os.ReadFile(target)
	if err != nil {
		t.Fatalf("read target: %v", err)
	}
	if string(data) != "secret" {
		t.Fatalf("target was modified through symlink: %q", data)
	}
}

func TestSafeMkdirAll_rejectsSymlinkComponent(t *testing.T) {
	root := t.TempDir()
	nested := filepath.Join(root, "tools")
	if err := os.Mkdir(nested, 0755); err != nil {
		t.Fatalf("mkdir nested: %v", err)
	}

	outside := filepath.Join(t.TempDir(), "outside")
	if err := os.Mkdir(outside, 0755); err != nil {
		t.Fatalf("mkdir outside: %v", err)
	}

	link := filepath.Join(nested, "linux")
	if err := os.Symlink(outside, link); err != nil {
		t.Skip("symlinks not supported:", err)
	}

	err := safeMkdirAll(root, filepath.Join(root, "tools", "linux", "amd64"))
	if err == nil {
		t.Fatal("expected error when path crosses symlink directory")
	}
}
