package main

import (
	"embed"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

const defaultKitDir = "emergency-kit"

func getWorkingDirectory() (string, error) {
	wd, err := os.Getwd()
	if err == nil {
		return wd, nil
	}

	// Linux-only fallback: getwd can fail if the cwd inode was removed while
	// /proc/self/cwd still points at the path (common after deleting the cwd).
	if runtime.GOOS == "linux" {
		if wd, err := os.Readlink("/proc/self/cwd"); err == nil {
			return wd, nil
		}
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

// pathWithinRoot reports whether path stays inside root after cleaning.
// embed.FS rejects ".." today, but this mirrors unzipFolder and blocks escapes
// if the embedded tree or build pipeline is ever compromised.
func pathWithinRoot(root, path string) bool {
	cleanRoot := filepath.Clean(root)
	cleanPath := filepath.Clean(path)
	if cleanPath == cleanRoot {
		return true
	}
	return strings.HasPrefix(cleanPath, cleanRoot+string(os.PathSeparator))
}

// ensureOutputRoot verifies the kit destination is a real directory.
// A symlinked output root (e.g. USB mount -> $HOME) would otherwise let
// kit extraction write anywhere that link targets.
func ensureOutputRoot(outputRoot string) error {
	info, err := os.Lstat(outputRoot)
	if err != nil {
		if os.IsNotExist(err) {
			return os.Mkdir(outputRoot, 0755)
		}
		return err
	}
	if info.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("refusing to write kit through symlinked output directory: %s", outputRoot)
	}
	if !info.IsDir() {
		return fmt.Errorf("kit output path is not a directory: %s", outputRoot)
	}
	return nil
}

// safeMkdirAll creates directories under outputRoot without following symlinks.
// os.MkdirAll follows symlinks, so a malicious USB layout like
// tools/linux -> /tmp/escape could redirect writes outside the kit folder.
func safeMkdirAll(outputRoot, dir string) error {
	dir = filepath.Clean(dir)
	if !pathWithinRoot(outputRoot, dir) {
		return fmt.Errorf("%s is outside %s", dir, outputRoot)
	}
	if dir == outputRoot {
		return ensureOutputRoot(outputRoot)
	}

	rel, err := filepath.Rel(outputRoot, dir)
	if err != nil {
		return err
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
		return fmt.Errorf("%s is outside %s", dir, outputRoot)
	}

	current := outputRoot
	for _, part := range strings.Split(filepath.ToSlash(rel), "/") {
		if part == "" || part == "." {
			continue
		}
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if err != nil {
			if os.IsNotExist(err) {
				if err := os.Mkdir(current, 0755); err != nil {
					return err
				}
				continue
			}
			return err
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("refusing to follow symlink: %s", current)
		}
		if !info.IsDir() {
			return fmt.Errorf("path component is not a directory: %s", current)
		}
	}
	return nil
}

func safeWriteFile(outputRoot, dest string, data []byte, perm os.FileMode) error {
	dest = filepath.Clean(dest)
	if !pathWithinRoot(outputRoot, dest) {
		return fmt.Errorf("%s is outside %s", dest, outputRoot)
	}
	if err := safeMkdirAll(outputRoot, filepath.Dir(dest)); err != nil {
		return err
	}
	return writeFileNoSymlink(dest, data, perm)
}

func extractEmbeddedDir(efs embed.FS, embedRoot, outputRoot string) error {
	outputRoot = filepath.Clean(outputRoot)
	if err := ensureOutputRoot(outputRoot); err != nil {
		return err
	}

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
		if rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
			return fmt.Errorf("invalid embedded path: %s", rel)
		}

		dest := filepath.Clean(filepath.Join(outputRoot, rel))
		if !pathWithinRoot(outputRoot, dest) {
			return fmt.Errorf("%s is outside %s", dest, outputRoot)
		}

		if d.IsDir() {
			return safeMkdirAll(outputRoot, dest)
		}

		data, err := efs.ReadFile(path)
		if err != nil {
			return err
		}

		return safeWriteFile(outputRoot, dest, data, embeddedFileMode(rel))
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
