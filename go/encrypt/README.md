# ZC - Zip and Encrypt Tool

A simple command-line tool for securely encrypting folders and files using AES-256 encryption with scrypt key derivation.

## Overview

ZC (short for "Zip and Crypt") is a Go utility that:

- Encrypts directories by first zipping them, then applying AES-256 encryption
- Decrypts and extracts previously encrypted files and directories
- Uses secure password-based encryption with scrypt for key derivation
- Handles the complete process of zipping, encrypting, decrypting, and unzipping

## Installation

### Prerequisites

- Go 1.18 or higher
- Make (for using the provided Makefile)

### Building from Source

1. Clone the repository or navigate to this directory:

   ```bash
   cd /path/to/go/encrypt
   ```

2. Build the project for your platform:

   ```bash
   make build
   ```

   This will create binaries for multiple platforms in the `build` directory.

3. Install the binary to your user bin directory:

   ```bash
   make install
   ```

   This will install the binary to `~/bin`.

## Usage

### Encrypting a Folder

```bash
zc /path/to/folder
```

This will:

1. Prompt you for a password
2. Zip the folder
3. Encrypt the zip file with your password
4. Output the encrypted file as `/path/to/folder.enc`

### Decrypting a File

```bash
zc /path/to/file.enc
```

This will:

1. Prompt you for the password
2. Decrypt the file
3. Unzip the contents to the current directory

## Development

### Running Tests

```bash
make test
```

### Building for Multiple Platforms

The default `make build` command builds for multiple platforms:

- Linux (amd64, arm64)
- Windows (amd64)
- macOS (amd64, arm64)

### Clean Build Files

```bash
make clean
```

### Uninstalling

```bash
make uninstall
```

## Security Features

- AES-256 bit encryption
- Scrypt key derivation with secure parameters:
  - N: 1048576 (2^20)
  - r: 8
  - p: 1
- Secure password input without echoing
- Memory zeroing for sensitive data
- Random salt (32 bytes) and nonce (12 bytes) generation

## License

See the LICENSE file for details.

## Creating an Emergency Kit on a Jump Drive

You can create a portable emergency kit on a USB drive that includes both your encrypted data and the tools to decrypt it on any computer.

### Step-by-Step Instructions

1. Build binaries for all supported platforms:

   ```bash
   make build
   ```

2. Create a directory structure on your USB drive:

   ```bash
   mkdir -p /path/to/usb/zc/{linux,windows,macos,data}
   ```

3. Copy the appropriate binaries to each platform folder:

   ```bash
   # Copy Linux binaries
   mkdir -p /path/to/usb/zc/linux/amd64 /path/to/usb/zc/linux/arm64
   cp build/linux/amd64/zc /path/to/usb/zc/linux/amd64/
   cp build/linux/arm64/zc /path/to/usb/zc/linux/arm64/
   
   # Copy Windows binary
   mkdir -p /path/to/usb/zc/windows/amd64
   cp build/windows/amd64/zc.exe /path/to/usb/zc/windows/amd64/
   
   # Copy macOS binaries
   mkdir -p /path/to/usb/zc/macos/amd64 /path/to/usb/zc/macos/arm64
   cp build/darwin/amd64/zc /path/to/usb/zc/macos/amd64/
   cp build/darwin/arm64/zc /path/to/usb/zc/macos/arm64/
   ```

4. Add a README with instructions:

   ```bash
   cat > /path/to/usb/zc/README.txt << 'EOF'
   ZC Emergency Kit Instructions:
   
   1. Choose the binary for your operating system and architecture:
      - Linux (Intel/AMD): Use linux/amd64/zc
      - Linux (ARM): Use linux/arm64/zc
      - Windows: Use windows/amd64/zc.exe
      - macOS (Intel): Use macos/amd64/zc
      - macOS (Apple Silicon): Use macos/arm64/zc
   
   2. To decrypt data, run:
      - Linux/macOS: ./zc data/your-encrypted-file.enc
      - Windows: zc.exe data\your-encrypted-file.enc
   EOF
   ```

5. Encrypt your important data:

   ```bash
   # First, organize your important files in a folder
   mkdir -p ~/emergency-data
   cp /path/to/important/documents ~/emergency-data/
   
   # Encrypt the folder
   ./zc ~/emergency-data
   
   # Copy the encrypted file to your USB drive
   cp ~/emergency-data.enc /path/to/usb/zc/data/
   ```

### Using the Emergency Kit

On any computer with your USB drive:

1. Open a terminal/command prompt
2. Navigate to the appropriate platform directory on your USB
3. Run the zc tool to decrypt your data
4. Enter your password when prompted

This ensures you can access your critical data on any operating system, without needing to install the tool or have internet access.
