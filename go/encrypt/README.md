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

### Automated Creation (Recommended)

Use the provided `portable` make target to automatically create a complete emergency kit:

```bash
make portable
```

This will:

1. Build all binaries for all supported platforms
2. Create a `portable` directory with the full emergency kit structure
3. Copy all necessary files to the correct locations
4. Set appropriate permissions for executable files
5. Create a user-friendly README.txt file

After running this command, simply copy the contents of the `portable` directory to your USB drive:

```bash
cp -r portable/zc/* /path/to/usb/
```

Then add your encrypted data to the `data` folder on the USB drive.

### Using the Emergency Kit

The emergency kit includes easy-to-use scripts in the `tools` directory that make decryption simple, even for users who aren't comfortable with the command line.

#### For Command-Line Users

If you're comfortable with the command line:

1. Open a terminal/command prompt
2. Navigate to the appropriate binary directory for your system:
   - **Linux (Intel/AMD)**: `/path/to/usb/zc/linux/amd64/`
   - **Linux (ARM)**: `/path/to/usb/zc/linux/arm64/`
   - **macOS (Intel)**: `/Volumes/YOUR_USB_NAME/zc/macos/amd64/`
   - **macOS (Apple Silicon)**: `/Volumes/YOUR_USB_NAME/zc/macos/arm64/`
   - **Windows**: `D:\zc\windows\amd64\` (replace D: with your USB drive letter)
3. Run the zc tool with your encrypted file:
   - **Linux/macOS**: `./zc ../../data/your-encrypted-file.enc`
   - **Windows**: `zc.exe ..\..\data\your-encrypted-file.enc`

#### For Non-Command-Line Users

For those who prefer a more user-friendly approach, we provide clickable scripts:

##### Windows Users

1. Navigate to the `tools` folder on your USB drive
2. Double-click the `decrypt.bat` file
3. When prompted, either:
   - Type the full path to your encrypted file, or
   - Drag and drop your encrypted file into the command window
4. Enter your password when prompted
5. Your files will be extracted to the same directory as the zc.exe program

##### macOS Users

1. Navigate to the `tools` folder on your USB drive
2. Double-click the `decrypt.command` file
   - If you get a security warning, right-click the file, choose "Open", then click "Open" in the dialog
3. When prompted, enter the path to your encrypted file
4. Enter your password when prompted
5. Your files will be extracted to the macOS binary directory

##### Linux Users

1. Navigate to the `tools` folder on your USB drive
2. Right-click on `decrypt.sh` and select "Run as Program" or "Execute"
3. When prompted, enter the path to your encrypted file
4. Enter your password when prompted
5. Your files will be extracted to the Linux binary directory

#### Troubleshooting

- **Windows Security Warning**: If you see "Windows protected your PC":
  - Click "More info"
  - Click "Run anyway"

- **macOS Security Warning**: If macOS prevents opening the script:
  - Open System Preferences > Security & Privacy
  - Click "Open Anyway" for the blocked script

- **Linux Permission Error**: If you get "Permission denied":
  - Open a terminal
  - Run `chmod +x /path/to/usb/tools/decrypt.sh`

- **Output Directory Already Exists**: If you get an error about the output directory already existing:
  - Rename or move the existing directory before decrypting
