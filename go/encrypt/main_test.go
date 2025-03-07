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

// test just encrypting and decrypting a file
func TestEncryptAndDecrypt(t *testing.T) {
	password := "mysecretpassword"
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

	fmt.Println("Encryption and decryption tests passed successfully.")
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
	defer cleanup(cleanupFiles)
	cleanup(cleanupFiles)

	// Create some dummy files in the folder
	for i := 1; i <= 3; i++ {
		filepath := filepath.Join(testFolder, fmt.Sprintf("file%d.txt", i))
		content := fmt.Appendf(nil, "This is the content of file %d.", i)
		os.MkdirAll(testFolder, os.ModePerm)
		if err := os.WriteFile(filepath, content, 0644); err != nil {
			t.Fatalf("Error creating test file: %v", err)
		}
	}

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

	fmt.Println("All tests passed successfully.")
}
