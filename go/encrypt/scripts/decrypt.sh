#!/bin/bash

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "ZC Decryption Tool"
echo "------------------"
echo
echo "Please enter the path to your encrypted file (or drag and drop the file here):"
read FILE_TO_DECRYPT

echo
echo "Starting decryption process..."
echo

# Change to the appropriate architecture directory based on the system architecture
if [[ $(uname -m) == "aarch64" ]]; then
    cd "$DIR/tools/linux/arm64"
else
    cd "$DIR/tools/linux/amd64"
fi

chmod +x ./zc
./zc "$FILE_TO_DECRYPT"

echo
echo "If the decryption was successful, your files have been extracted."
echo "Press Enter to exit."
read
