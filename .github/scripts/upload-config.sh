#!/bin/bash

# Usage: ./upload_to_s3.sh rubber-duck-config file1 file2 ...

# This script uploads specified files to an S3 bucket.

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <s3-bucket-name> <file1> [file2 ... fileN]"
  exit 1
fi

BUCKET="$1"
shift

for FILE in "$@"; do
  if [ -f "$FILE" ]; then
    echo "Uploading $FILE to s3://$BUCKET/"
    aws s3 cp "$FILE" "s3://$BUCKET/"
  else
    echo "File not found: $FILE"
  fi
done
