package main

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

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

func TestZipAndEncode(t *testing.T) {
	password := "mysecretpassword"
	testFolder := "f"

	cleanupFiles := []string{
		testFolder,
		testFolder + "_unzipped",
		testFolder + ".zip",
		testFolder + ".zip.enc",
		testFolder + "_decrypted.zip",
	}
	cleanup := func() {
		for _, file := range cleanupFiles {
			if _, err := os.Stat(file); err == nil {
				if err := os.RemoveAll(file); err != nil {
					fmt.Println("Error deleting", file, ":", err)
				}
			} else if !os.IsNotExist(err) {
				fmt.Println("Error checking file", file, ":", err)
			}
		}
	}
	defer cleanup()

	// Clean up any existing files from previous runs
	cleanup()

	// Create some dummy files in the folder
	for i := 1; i <= 3; i++ {
		filepath := filepath.Join(testFolder, fmt.Sprintf("file%d.txt", i))
		content := fmt.Appendf(nil, "This is the content of file %d.", i)
		os.MkdirAll(testFolder, os.ModePerm)
		if err := os.WriteFile(filepath, content, 0644); err != nil {
			fmt.Println("Error creating test file:", err)
			os.Exit(1)
		}
	}

	// Create a zip file of that folder
	zipFileName := testFolder + ".zip"
	if err := zipFolder(testFolder, zipFileName); err != nil {
		fmt.Println("Error zipping folder:", err)
		os.Exit(1)
	}

	// Encrypt the zip file with the password
	if err := encryptFile(zipFileName, zipFileName+".enc", password); err != nil {
		fmt.Println("Error encrypting zip file:", err)
		os.Exit(1)
	}

	// Decrypt the zip file with the password
	if err := decryptFile(zipFileName+".enc", testFolder+"_decrypted.zip", password); err != nil {
		fmt.Println("Error decrypting zip file:", err)
		os.Exit(1)
	}

	// Unzip the zip file
	if err := unzipFolder(testFolder+"_decrypted.zip", testFolder+"_unzipped"); err != nil {
		fmt.Println("Error unzipping folder:", err)
		os.Exit(1)
	}

	// Verify the contents of the unzipped folder
	if err := verifyFolderContents(testFolder, testFolder+"_unzipped/"+testFolder); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	fmt.Println("All tests passed successfully.")
}
