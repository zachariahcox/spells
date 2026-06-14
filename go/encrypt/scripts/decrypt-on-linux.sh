#!/bin/env bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCH=$([[ $(uname -m) == "aarch64" ]] && echo arm64 || echo amd64)
ZC="$DIR/tools/linux/$ARCH/zc"

echo "ZC Decryption Tool"
echo "------------------"
echo

shopt -s nullglob
enc_files=("$DIR"/*.enc)
if [[ ${#enc_files[@]} -eq 1 ]]; then
	FILE_TO_DECRYPT="${enc_files[0]}"
	echo "Found encrypted file: $(basename "$FILE_TO_DECRYPT")"
	echo "You will be prompted for your password next."
	echo
elif [[ -n "$1" ]]; then
	FILE_TO_DECRYPT="$1"
else
	echo "Please enter the path to your encrypted file (or drag and drop the file here):"
	read -r FILE_TO_DECRYPT
fi

FILE_TO_DECRYPT="${FILE_TO_DECRYPT//\"}"

echo "Starting decryption process..."
echo
chmod +x "$ZC"
"$ZC" "$FILE_TO_DECRYPT"

echo
echo "If the decryption was successful, your files have been extracted."
echo "Press Enter to exit."
read
