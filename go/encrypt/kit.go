package main

import (
	"embed"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
)

const defaultKitDir = "emergency-kit"

func getWorkingDirectory() (string, error) {
	wd, err := os.Getwd()
	if err == nil {
		return wd, nil
	}

	// When the cwd inode was removed, getwd can fail even though /proc/self/cwd still works.
	if wd, err := os.Readlink("/proc/self/cwd"); err == nil {
		return wd, nil
	}

	return "", fmt.Errorf("cannot determine current directory: %w (pass an absolute output path)", err)
}

func resolveKitOutputDir(path string) (string, error) {
	if filepath.IsAbs(path) {
		return filepath.Clean(path), nil
	}

	wd, err := getWorkingDirectory()
	if err != nil {
		return "", err
	}
	return filepath.Join(wd, path), nil
}

func createKit(absOutputDir string) error {
	absOutputDir = filepath.Clean(absOutputDir)
	if !filepath.IsAbs(absOutputDir) {
		return fmt.Errorf("kit output path is not absolute: %s", absOutputDir)
	}

	if embeddedKitRoot == "" {
		return fmt.Errorf("embedded kit missing; run make prepare-kit-embed and rebuild with -tags embedtools")
	}

	if err := extractEmbeddedDir(embeddedKit, embeddedKitRoot, absOutputDir); err != nil {
		return fmt.Errorf("extract kit: %w", err)
	}

	return nil
}

func extractEmbeddedDir(efs embed.FS, embedRoot, outputRoot string) error {
	return fs.WalkDir(efs, embedRoot, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if path == embedRoot {
			return nil
		}

		rel, err := filepath.Rel(embedRoot, path)
		if err != nil {
			return err
		}
		rel = filepath.FromSlash(rel)

		dest := filepath.Join(outputRoot, rel)
		if d.IsDir() {
			return os.MkdirAll(dest, 0755)
		}

		if err := os.MkdirAll(filepath.Dir(dest), 0755); err != nil {
			return err
		}

		data, err := efs.ReadFile(path)
		if err != nil {
			return err
		}

		if err := os.WriteFile(dest, data, embeddedFileMode(rel)); err != nil {
			return err
		}
		return nil
	})
}

func embeddedFileMode(relPath string) os.FileMode {
	base := filepath.Base(relPath)
	if base == "zc" || base == "zc.exe" {
		return 0755
	}
	if strings.HasSuffix(relPath, ".sh") || strings.HasSuffix(relPath, ".command") {
		return 0755
	}
	return 0644
}

func runKitCommand(args []string) error {
	outputDir := defaultKitDir
	if len(args) > 1 {
		return fmt.Errorf("usage: %s --new-kit <output-directory>", tool_name)
	}
	if len(args) == 1 {
		outputDir = args[0]
	}

	resolved, err := resolveKitOutputDir(outputDir)
	if err != nil {
		return err
	}

	if err := createKit(resolved); err != nil {
		return err
	}

	fmt.Printf("Kit created at %s\n", resolved)
	return nil
}
