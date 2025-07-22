#!/bin/bash

# Usage: ./upload-file-s3.sh <file> <s3-destination-path>
# Example: ./upload-file-s3.sh myconfig.yaml s3://test-bucket/my-subdirectory/myconfig.yaml

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <file> <s3-destination-path>"
  exit 1
fi

FILE="$1"
DEST_PATH="$2"

if [ -f "$FILE" ]; then
  echo "Uploading $FILE to $DEST_PATH"
  aws s3 cp "$FILE" "$DEST_PATH"
else
  echo "File not found: $FILE"
  exit 2
fi
