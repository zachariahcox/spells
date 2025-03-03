package main

import (
	"archive/zip"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"golang.org/x/crypto/scrypt"
)

func encryptFile(filename, encrypted_file_name, password string) error {
	// Read contents to be encrypted
	plain_text, err := os.ReadFile(filename)
	if err != nil {
		return err
	}

	salt := make([]byte, 32)
	if _, err := rand.Read(salt); err != nil {
		return err
	}

	key, err := scrypt.Key([]byte(password), salt, 32768, 8, 1, 32)
	if err != nil {
		return err
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return err
	}

	aesgcm, err := cipher.NewGCM(block)
	if err != nil {
		return err
	}

	nonce := make([]byte, aesgcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return err
	}

	cipher_text := aesgcm.Seal(nil, nonce, plain_text, nil)

	encrypted_file, err := os.Create(encrypted_file_name)
	if err != nil {
		return err
	}
	defer encrypted_file.Close()

	_, err = encrypted_file.Write(salt)
	if err != nil {
		return err
	}

	_, err = encrypted_file.Write(nonce)
	if err != nil {
		return err
	}
	_, err = encrypted_file.Write(cipher_text)
	if err != nil {
		return err
	}

	return nil
}

func decryptFile(encrypted_file_name, decrypted_file_name, password string) error {
	// Read the encrypted file
	encrypted_data, err := os.ReadFile(encrypted_file_name)
	if err != nil {
		return err
	}

	// Extract the salt, nonce, and ciphertext
	salt := encrypted_data[:32]
	nonce := encrypted_data[32 : 32+12]
	cipher_text := encrypted_data[32+12:]

	key, err := scrypt.Key([]byte(password), salt, 32768, 8, 1, 32)
	if err != nil {
		return err
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return err
	}

	aesgcm, err := cipher.NewGCM(block)
	if err != nil {
		return err
	}

	plain_text, err := aesgcm.Open(nil, nonce, cipher_text, nil)
	if err != nil {
		return err
	}

	// Write the decrypted data to the output file
	err = os.WriteFile(decrypted_file_name, plain_text, 0644)
	if err != nil {
		return err
	}

	return nil
}

func zipFolder(folder string, zipFileName string) error {
	zipFile, err := os.Create(zipFileName)
	if err != nil {
		return err
	}
	defer zipFile.Close()

	// Create a zip writer
	zipWriter := zip.NewWriter(zipFile)
	defer zipWriter.Close()

	// Walk through the folder and add files to the zip file
	err = filepath.Walk(folder, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Create a zip header from the file info
		header, err := zip.FileInfoHeader(info)
		if err != nil {
			return err
		}

		// Set the header name to the relative path
		header.Name, err = filepath.Rel(filepath.Dir(folder), path)
		if err != nil {
			return err
		}

		// If the file is a directory, add a trailing slash to the header name
		if info.IsDir() {
			header.Name += "/"
		} else {
			// Set the compression method for files
			header.Method = zip.Deflate
		}

		// Create a writer for the file in the zip archive
		writer, err := zipWriter.CreateHeader(header)
		if err != nil {
			return err
		}

		// If the file is not a directory, copy its contents to the zip writer
		if !info.IsDir() {
			file, err := os.Open(path)
			if err != nil {
				return err
			}
			defer file.Close()

			_, err = io.Copy(writer, file)
			if err != nil {
				return err
			}
		}

		return nil
	})

	if err != nil {
		return err
	}

	return nil
}

func unzipFolder(zipFileName, folder string) error {
	// Open the zip file
	zipFile, err := os.Open(zipFileName)
	if err != nil {
		return err
	}
	defer zipFile.Close()

	// Create a zip reader
	stat, err := zipFile.Stat()
	if err != nil {
		return err
	}

	zipReader, err := zip.NewReader(zipFile, stat.Size())
	if err != nil {
		return err
	}

	// Extract files from the zip file into the specified folder
	for _, file := range zipReader.File {
		filePath := filepath.Join(folder, file.Name)

		if file.FileInfo().IsDir() {
			// Create directories
			os.MkdirAll(filePath, os.ModePerm)
		} else {
			// Create a file
			if err := os.MkdirAll(filepath.Dir(filePath), os.ModePerm); err != nil {
				return err
			}

			outFile, err := os.OpenFile(filePath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, file.Mode())
			if err != nil {
				return err
			}

			rc, err := file.Open()
			if err != nil {
				return err
			}

			_, err = io.Copy(outFile, rc)

			// Close the file without defer to close before next iteration of loop
			outFile.Close()
			rc.Close()

			if err != nil {
				return err
			}
		}
	}

	return nil
}

func main() {
	password := "mysecretpassword"
	testFolder := "test_folder"
	cleanupFiles := []string{
		testFolder,
		testFolder + "_unzipped",
		testFolder + ".zip",
		testFolder + ".zip.enc",
		testFolder + "_decrypted.zip",
	}
	defer func() {
		for _, file := range cleanupFiles {
			if err := os.RemoveAll(file); err != nil {
				fmt.Println("Error deleting", file, ":", err)
			}
		}
	}()

	// delete any cleanup files if they exist
	for _, file := range cleanupFiles {
		if _, err := os.Stat(file); err == nil {
			if err := os.RemoveAll(file); err != nil {
				fmt.Println("Error deleting", file, ":", err)
			}
		} else if !os.IsNotExist(err) {
			fmt.Println("Error checking file", file, ":", err)
		}
	}

	// Create a folder of test files
	if err := os.Mkdir(testFolder, 0755); err != nil {
		fmt.Println("Error creating test folder:", err)
		os.Exit(1)
	}

	// Create some dummy files in the folder
	for i := 1; i <= 3; i++ {
		if err := os.WriteFile(filepath.Join(testFolder, fmt.Sprintf("file%d.txt", i)), []byte(fmt.Sprintf("This is the content of file %d.", i)), 0644); err != nil {
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
