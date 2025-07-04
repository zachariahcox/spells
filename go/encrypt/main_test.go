package main

import (
	"bytes"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Capture stdout helper function
func captureOutput(f func()) string {
	// Keep backup of the real stdout
	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	// Execute the function
	f()

	// Close the writer and restore stdout
	w.Close()
	os.Stdout = oldStdout

	// Read the output from the reader
	var buf bytes.Buffer
	io.Copy(&buf, r)
	return buf.String()
}

func TestHelpOption(t *testing.T) {
	tests := []struct {
		args []string
		want string
	}{
		{[]string{"-h"}, "Usage: " + tool_name},
		{[]string{"--help"}, "Usage: " + tool_name},
		{[]string{}, "Usage: " + tool_name}, // No args should show help
	}

	for _, tt := range tests {
		t.Run(strings.Join(tt.args, " "), func(t *testing.T) {
			output := captureOutput(func() {
				cli(tt.args)
			})
			if !strings.Contains(output, tt.want) {
				t.Errorf("cli(%v) output = %q, want to contain %q", tt.args, output, tt.want)
			}
			// Verify help content
			if !strings.Contains(output, "Options:") || !strings.Contains(output, "Description:") {
				t.Errorf("Help output missing expected sections")
			}
		})
	}
}

func TestVersionOption(t *testing.T) {
	tests := []struct {
		args []string
		want string
	}{
		{[]string{"-v"}, tool_name + " version " + tool_version},
		{[]string{"--version"}, tool_name + " version " + tool_version},
	}

	for _, tt := range tests {
		t.Run(strings.Join(tt.args, " "), func(t *testing.T) {
			output := captureOutput(func() {
				cli(tt.args)
			})
			if !strings.Contains(output, tt.want) {
				t.Errorf("cli(%v) output = %q, want to contain %q", tt.args, output, tt.want)
			}
		})
	}
}

func TestEncryptAndDecrypt(t *testing.T) {
	password := []byte("mysecretpassword")
	testFile := "test.txt"
	encryptedFile := "test.txt.enc"
	decryptedFile := "test_decrypted.txt"

	cleanupFiles := []string{
		testFile,
		encryptedFile,
		decryptedFile,
	}
	defer cleanup(cleanupFiles)
	cleanup(cleanupFiles)

	// Create a test file
	content := []byte("This is a test file.")
	if err := os.WriteFile(testFile, content, 0644); err != nil {
		t.Fatalf("error creating test file: %v", err)
	}

	// Encrypt the test file
	if err := encryptFile(testFile, encryptedFile, password); err != nil {
		t.Fatalf("error encrypting test file: %v", err)
	}

	// Decrypt the encrypted file
	if err := decryptFile(encryptedFile, decryptedFile, password); err != nil {
		t.Fatalf("error decrypting test file: %v", err)
	}

	// Verify the contents of the decrypted file
	decryptedContent, err := os.ReadFile(decryptedFile)
	if err != nil {
		t.Fatalf("error reading decrypted file: %v", err)
	}

	if string(decryptedContent) != string(content) {
		t.Fatalf("error: decrypted content does not match original content")
	}
}

func TestZip(t *testing.T) {
	testFolder := "test_folder"
	zipFileName := testFolder + ".zip"
	unzipFolderName := testFolder + "_unzipped"

	cleanupFiles := []string{
		testFolder,
		unzipFolderName,
		zipFileName,
	}
	defer cleanup(cleanupFiles)
	cleanup(cleanupFiles)

	// Create some dummy files in the folder
	generateTestFiles(testFolder, 5)

	// Create a zip file of that folder
	if err := zipFolder(testFolder, zipFileName); err != nil {
		t.Fatalf("error zipping folder: %v", err)
	}

	// Unzip the zip file
	if err := unzipFolder(zipFileName, unzipFolderName); err != nil {
		t.Fatalf("error unzipping folder: %v", err)
	}

	// Verify the contents of the unzipped folder
	if err := verifyFolderContents(testFolder, unzipFolderName+"/"+testFolder); err != nil {
		t.Fatalf("%v", err)
	}
}

func TestZipAndEncrypt(t *testing.T) {
	password := []byte("mysecretpassword")
	testFolder := "test_folder"

	cleanupFiles := []string{
		testFolder,
		testFolder + "_unzipped",
		testFolder + ".zip",
		testFolder + ".zip.enc",
		testFolder + "_decrypted.zip",
	}
	defer cleanup(cleanupFiles)
	cleanup(cleanupFiles)

	// Create some dummy files in the folder
	generateTestFiles(testFolder, 5)

	// Create a zip file of that folder
	zipFileName := testFolder + ".zip"
	if err := zipFolder(testFolder, zipFileName); err != nil {
		t.Fatalf("Error zipping folder: %v", err)
	}

	// Encrypt the zip file with the password
	if err := encryptFile(zipFileName, zipFileName+".enc", password); err != nil {
		t.Fatalf("Error encrypting zip file: %v", err)
	}

	// Decrypt the zip file with the password
	if err := decryptFile(zipFileName+".enc", testFolder+"_decrypted.zip", password); err != nil {
		t.Fatalf("Error decrypting zip file: %v", err)
	}

	// Unzip the zip file
	if err := unzipFolder(testFolder+"_decrypted.zip", testFolder+"_unzipped"); err != nil {
		t.Fatalf("Error unzipping folder: %v", err)
	}

	// Verify the contents of the unzipped folder
	if err := verifyFolderContents(testFolder, testFolder+"_unzipped/"+testFolder); err != nil {
		t.Fatalf("%v", err)
	}
}

func verifyFolderContents(originalFolder, unzippedFolder string) error {
	originalFiles, err := filepath.Glob(filepath.Join(originalFolder, "*"))
	if err != nil {
		return fmt.Errorf("error reading original folder: %v", err)
	}

	unzippedFiles, err := filepath.Glob(filepath.Join(unzippedFolder, "*"))
	if err != nil {
		return fmt.Errorf("error reading unzipped folder: %v", err)
	}

	if len(originalFiles) != len(unzippedFiles) {
		return fmt.Errorf("error: number of files in original and unzipped folders do not match")
	}

	for i, originalFile := range originalFiles {
		originalInfo, err := os.Stat(originalFile)
		if err != nil {
			return fmt.Errorf("error stating original file: %v", err)
		}

		unzippedInfo, err := os.Stat(unzippedFiles[i])
		if err != nil {
			return fmt.Errorf("error stating unzipped file: %v", err)
		}

		if originalInfo.Mode() != unzippedInfo.Mode() {
			return fmt.Errorf("error: file permissions do not match for %s", originalFile)
		}

		originalContent, err := os.ReadFile(originalFile)
		if err != nil {
			return fmt.Errorf("error reading original file: %v", err)
		}

		unzippedContent, err := os.ReadFile(unzippedFiles[i])
		if err != nil {
			return fmt.Errorf("error reading unzipped file: %v", err)
		}

		if string(originalContent) != string(unzippedContent) {
			return fmt.Errorf("error: file contents do not match for %s", originalFile)
		}
	}

	return nil
}

// cleanup function to remove test files after tests
func cleanup(cleanupFiles []string) {
	for _, file := range cleanupFiles {
		if info, err := os.Stat(file); err == nil {
			if info.IsDir() {
				if err := os.RemoveAll(file); err != nil {
					fmt.Println("Error deleting directory", file, ":", err)
				}
			} else if err := os.Remove(file); err != nil {
				fmt.Println("Error deleting", file, ":", err)
			}
		} else if !os.IsNotExist(err) {
			fmt.Println("Error checking file", file, ":", err)
		}
	}
}

// Create some dummy files in the folder
func generateTestFiles(folder string, numFiles int) {
	for i := 1; i <= numFiles; i++ {
		filepath := filepath.Join(folder, fmt.Sprintf("file%d.txt", i))
		content := fmt.Appendf(nil, "This is the content of file %d.", i)
		os.MkdirAll(folder, os.ModePerm)
		if err := os.WriteFile(filepath, content, 0644); err != nil {
			fmt.Println("Error creating test file:", err)
		}
	}
}
