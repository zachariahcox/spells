#!/bin/bash

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "ZC Decryption Tool"
echo "------------------"
echo
echo "Please enter the path to your encrypted file (or drag and drop the file here):"
read FILE_TO_DECRYPT

# Remove quotes if present
FILE_TO_DECRYPT="${FILE_TO_DECRYPT//\"}"

echo
echo "Starting decryption process..."
echo

# Change to the appropriate architecture directory
if [[ $(uname -m) == "arm64" ]]; then
    cd "$DIR/tools/darwin/arm64"
    chmod +x ./zc
else
    cd "$DIR/tools/darwin/amd64"
    chmod +x ./zc
fi

./zc "$FILE_TO_DECRYPT"

echo
echo "If the decryption was successful, your files have been extracted."
echo "Press Enter to exit."
read
