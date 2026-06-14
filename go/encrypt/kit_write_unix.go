//go:build unix

package main

import (
	"fmt"
	"os"

	"golang.org/x/sys/unix"
)

// writeFileNoSymlink writes data without following symlinks at the destination.
// Unix provides O_NOFOLLOW so a TOCTOU symlink swap is rejected at open time.
func writeFileNoSymlink(dest string, data []byte, perm os.FileMode) error {
	if info, err := os.Lstat(dest); err == nil {
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("refusing to write through symlink: %s", dest)
		}
	} else if !os.IsNotExist(err) {
		return err
	}

	flags := unix.O_WRONLY | unix.O_CREAT | unix.O_TRUNC | unix.O_NOFOLLOW
	fd, err := unix.Open(dest, flags, uint32(perm))
	if err != nil {
		return err
	}
	defer unix.Close(fd)

	_, err = unix.Write(fd, data)
	return err
}
