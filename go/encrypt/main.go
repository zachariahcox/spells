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
	"strings"

	"golang.org/x/crypto/scrypt"
	"golang.org/x/term"
)

// config for scrypt
const tool_name = "zc"
const tool_ext = ".enc"
const tool_version = "1.0.0"
const scrypt_N = 1048576 // 2**20
const scrypt_r = 8
const scrypt_p = 1
const scrypt_nonce_len = 12
const scrypt_salt_len = 32
const scrypt_key_len = 32 // aes-256bit has a 32byte derived key length

func getPassword(prompt string) ([]byte, error) {
	// this function is used to read a password from the terminal
	// it uses the term package to read the password without echoing it
	// it returns the password as a byte slice.
	// this byte slice must be zeroed out after use!

	fmt.Print(prompt)
	pwd, err := term.ReadPassword(int(os.Stdin.Fd()))
	if err != nil {
		return nil, err
	}
	fmt.Println() // Add a newline after reading the password
	return pwd, nil
}
func zeroBytes(bytes []byte) {
	for i := range bytes {
		bytes[i] = 0
	}
}

func encryptFile(filename string, encrypted_file_name string, password []byte) error {
	// Read contents to be encrypted
	plain_text, err := os.ReadFile(filename)
	if err != nil {
		return err
	}

	// generate random salt
	salt := make([]byte, scrypt_salt_len)
	if _, err := rand.Read(salt); err != nil {
		return err
	}

	// derive key from password and salt
	key, err := scrypt.Key(
		password,
		salt,
		scrypt_N,
		scrypt_r,
		scrypt_p,
		scrypt_key_len)

	if err != nil {
		return err
	}
	defer zeroBytes(key)
	defer zeroBytes(salt)

	// create cipher block
	block, err := aes.NewCipher(key)
	if err != nil {
		return err
	}

	aesgcm, err := cipher.NewGCM(block)
	if err != nil {
		return err
	}

	// generate random nonce
	nonce := make([]byte, scrypt_nonce_len)
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

func decryptFile(encrypted_file_name string, decrypted_file_name string, password []byte) error {
	// Read the encrypted file
	encrypted_data, err := os.ReadFile(encrypted_file_name)
	if err != nil {
		return err
	}
	defer zeroBytes(encrypted_data)

	// Extract the salt, nonce, and cipher_text
	salt := encrypted_data[:scrypt_salt_len]
	nonce := encrypted_data[scrypt_salt_len : scrypt_salt_len+scrypt_nonce_len]
	cipher_text := encrypted_data[scrypt_salt_len+scrypt_nonce_len:]
	key, err := scrypt.Key(
		password,
		salt,
		scrypt_N,
		scrypt_r,
		scrypt_p,
		scrypt_key_len)
	if err != nil {
		return err
	}
	defer zeroBytes(key)
	defer zeroBytes(salt)

	// Create a cipher block
	block, err := aes.NewCipher(key)
	if err != nil {
		return err
	}
	aesgcm, err := cipher.NewGCM(block)
	if err != nil {
		return err
	}

	// Decrypt the cipher text
	plain_text, err := aesgcm.Open(nil, nonce, cipher_text, nil)
	if err != nil {
		// if the password is wrong, the error will be "cipher: message authentication failed"
		if err.Error() == "cipher: message authentication failed" {
			return fmt.Errorf("decryption failed: invalid password or corrupted file")
		}
		return err
	}
	defer zeroBytes(plain_text)

	// Write the decrypted data to the output file
	err = os.WriteFile(decrypted_file_name, plain_text, 0644)
	if err != nil {
		return err
	}

	return nil
}

func zipFolder(folder string, zipFileName string) error {
	// Create output file
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
	for _, zf := range zipReader.File {
		filePath := filepath.Join(folder, zf.Name)

		// fail if theres a path traversal attack (no escaping into parent directories)
		if !strings.HasPrefix(filepath.Clean(filePath), filepath.Clean(folder)+string(os.PathSeparator)) {
			return fmt.Errorf("%s is not located in %s", filePath, folder)
		}

		if zf.FileInfo().IsDir() {
			// Create directories
			os.MkdirAll(filePath, os.ModePerm)
		} else {
			// Create a file
			if err := os.MkdirAll(filepath.Dir(filePath), os.ModePerm); err != nil {
				return err
			}

			outFile, err := os.OpenFile(filePath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, zf.Mode())
			if err != nil {
				return err
			}

			rc, err := zf.Open()
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

func printHelp() {
	fmt.Printf("Usage: %s [options] <folder name or file that ends in %s>\n\n", tool_name, tool_ext)
	fmt.Printf("Options:\n")
	fmt.Printf("  -h, --help     Show this help message and exit\n")
	fmt.Printf("  -v, --version  Show version information and exit\n\n")
	fmt.Printf("Description:\n")
	fmt.Printf("  Provides compression of a folder, encryption and decryption.\n")
	fmt.Printf("  - To encrypt a folder: %s <folder_name>\n", tool_name)
	fmt.Printf("  - To decrypt a file: %s <filename%s>\n", tool_name, tool_ext)
}

func printVersion() {
	fmt.Printf("%s version %s\n", tool_name, tool_version)
}

func cli(args []string) error {
	// check args
	if len(args) == 0 {
		printHelp()
		return nil
	}

	// Check for help or version flags
	if args[0] == "-h" || args[0] == "--help" {
		printHelp()
		return nil
	}

	if args[0] == "-v" || args[0] == "--version" {
		printVersion()
		return nil
	}

	// check for arguments
	if len(args) != 1 {
		return fmt.Errorf("usage: %s <folder name or file that ends in .enc>", tool_name)
	}

	// argument must be a directory or a file that ends with .enc
	filename := args[0]
	fileInfo, err := os.Stat(filename)
	if err != nil {
		return fmt.Errorf("file does not exist: %s", filename)
	}
	if !fileInfo.IsDir() && !strings.HasSuffix(filename, ".enc") {
		return fmt.Errorf("file is not a directory, and doesn't have a '%s' extension: %s", filename, tool_ext)
	}

	// make temp dir in the current directory to prevent leaks into the real temp dir
	filename = filepath.Clean(filename) // make sure it doesn't end in a slash
	wd, err := filepath.Abs(filepath.Dir(filename))
	if err != nil {
		return fmt.Errorf("error getting current directory: %v", err)
	}
	temp, err := os.MkdirTemp(wd, "temp")
	if err != nil {
		return fmt.Errorf("error creating temp directory: %v", err)
	}
	defer os.RemoveAll(temp) // clean up temp directory

	// collect password
	password, err := getPassword("Enter password: ")
	if err != nil {
		return fmt.Errorf("error reading password: %v", err)
	}
	defer zeroBytes(password)

	// do the work
	if strings.HasSuffix(filename, ".enc") {
		log.Println("Decrypting file...")
		output := strings.TrimSuffix(filename, ".enc")

		// Check if the output directory already exists
		if _, err := os.Stat(output); err == nil {
			return fmt.Errorf("output directory already exists: %s", output)
		} else if !os.IsNotExist(err) {
			return fmt.Errorf("error checking output directory: %v", err)
		}

		zipFile := filepath.Join(temp, filepath.Base(output))
		if err := decryptFile(filename, zipFile, password); err != nil {
			return fmt.Errorf("error decrypting file: %v", err)
		}
		log.Println("Unzipping file...")
		if err := unzipFolder(zipFile, wd); err != nil {
			return fmt.Errorf("error unzipping file: %v", err)
		}
	} else {
		log.Println("Zipping folder...")
		output := filename + ".enc"
		zipFile := filepath.Join(temp, filepath.Base(output))
		if err := zipFolder(filename, zipFile); err != nil {
			return fmt.Errorf("error zipping folder: %v", err)
		}
		log.Println("Encrypting file...")
		if err := encryptFile(zipFile, output, password); err != nil {
			return fmt.Errorf("error encrypting file: %v", err)
		}
	}
	log.Println("Done!")
	return nil
}

func main() {
	if err := cli(os.Args[1:]); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		fmt.Fprintf(os.Stderr, "Run '%s --help' for usage information.\n", tool_name)
		os.Exit(1)
	}
}
