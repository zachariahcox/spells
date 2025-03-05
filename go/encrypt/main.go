package main

import (
	"archive/zip"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"syscall"

	"golang.org/x/crypto/scrypt"
	"golang.org/x/term"
)

// config for scrypt
const scrypt_N = 1048576 // 2**20
const scrypt_nonce = 12
const scrypt_salt = 32

func encryptFile(filename, encrypted_file_name, password string) error {
	// Read contents to be encrypted
	plain_text, err := os.ReadFile(filename)
	if err != nil {
		return err
	}

	// salt should be randomly generated and at least 16 bytes
	salt := make([]byte, scrypt_salt)
	if _, err := rand.Read(salt); err != nil {
		return err
	}

	// aes-256bit has a 32byte derived key length settings
	key, err := scrypt.Key([]byte(password), salt, scrypt_N, 8, 1, 32)
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

	nonce := make([]byte, scrypt_nonce)
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

	// Extract the salt, nonce, and cipher_text
	salt := encrypted_data[:scrypt_salt]
	nonce := encrypted_data[scrypt_salt : scrypt_salt+scrypt_nonce]
	cipher_text := encrypted_data[scrypt_salt+scrypt_nonce:]
	key, err := scrypt.Key([]byte(password), salt, scrypt_N, 8, 1, 32)
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

func getPassword(prompt string) (string, error) {
	fmt.Print(prompt)
	bytePassword, err := term.ReadPassword(int(syscall.Stdin))
	if err != nil {
		return "", err
	}
	fmt.Println() // Add a newline after reading the password
	return string(bytePassword), nil
}

func main() {
	// verbs
	encrypt := "e"
	decrypt := "d"
	compress := "z"
	uncompress := "u"
	verbs := []string{encrypt, decrypt, compress, uncompress}

	// get args
	args := os.Args[1:]
	if len(args) != 2 {
		log.Fatalf("Usage: zcrypt [%s] <filename>", strings.Join(verbs, ", "))
	}

	action := args[0]
	filename := args[1]
	if !slices.Contains(verbs, action) {
		log.Fatalf("Invalid action. Use '%s' or '%s'.", encrypt, decrypt)
	}
	_, err := os.Stat(filename)
	if err != nil {
		log.Fatalf("File does not exist: %s", filename)
	}

	password, err := getPassword("Enter password: ")
	if err != nil {
		log.Fatalf("Error reading password: %v", err)
	}

	switch action {
	case compress:
		output := filename + ".zip"
		if err := zipFolder(filename, output); err != nil {
			log.Fatalf("Error zipping folder: %v", err)
		}
		if err := encryptFile(output, output+".enc", password); err != nil {
			log.Fatalf("Error encrypting zip file: %v", err)
		}
		fmt.Println("Folder zipped and encrypted successfully:", output+".enc")

	case uncompress:
		if !strings.HasSuffix(filename, ".zip") {
			log.Fatalf("File is not a zip file. Please provide a file with .zip extension.")
		}
		output := strings.TrimSuffix(filename, ".zip")
		if err := unzipFolder(filename, output); err != nil {
			log.Fatalf("Error unzipping file: %v", err)
		}
		fmt.Println("File unzipped successfully:", output)
	case encrypt:
		output := filename + ".enc"
		if err := encryptFile(filename, output, password); err != nil {
			log.Fatalf("Error encrypting file: %v", err)
		}
		fmt.Println("File encrypted successfully:", output)
	case decrypt:
		if !strings.HasSuffix(filename, ".enc") {
			log.Fatalf("File is not encrypted. Please provide a file with .enc extension.")
		}
		output := strings.TrimSuffix(filename, ".enc")
		if err := decryptFile(filename, output, password); err != nil {
			log.Fatalf("Error decrypting file: %v", err)
		}
		fmt.Println("File decrypted successfully:", output)
	default:
		log.Fatalf("Invalid action. Use '%s' or '%s'.", encrypt, decrypt)
	}
}
