//go:build windows

package main

import (
	"fmt"
	"os"
)

// writeFileNoSymlink writes data without following symlinks at the destination.
// Windows has no O_NOFOLLOW; Lstat rejects an existing symlink, and safeMkdirAll
// already prevents creating paths through symlinked directories. Remaining TOCTOU
// risk on Windows is accepted because emergency-kit USBs are the primary threat
// model and NTFS symlinks there are uncommon.
func writeFileNoSymlink(dest string, data []byte, perm os.FileMode) error {
	if info, err := os.Lstat(dest); err == nil {
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("refusing to write through symlink: %s", dest)
		}
	} else if !os.IsNotExist(err) {
		return err
	}

	return os.WriteFile(dest, data, perm)
}
