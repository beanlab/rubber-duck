#!/bin/bash

# Usage: ./upload-config.sh <local_file_path> <s3_bucket_name> <s3_key>

# Exit if any command fails
set -e

# Input arguments
LOCAL_FILE=$1
BUCKET_NAME=$2
S3_KEY=$3

# Check if all arguments are provided
if [[ -z "$LOCAL_FILE" || -z "$BUCKET_NAME" || -z "$S3_KEY" ]]; then
  echo "Usage: $0 <local_file_path> <s3_bucket_name> <s3_key>"
  echo "Example: $0 config/production-config.json my-config-bucket path/to/config/production-config.json"
  exit 1
fi

# Validate that the file exists
if [ ! -f "$LOCAL_FILE" ]; then
  echo "Error: Local file '$LOCAL_FILE' does not exist."
  exit 1
fi

echo "Uploading $LOCAL_FILE to s3://$BUCKET_NAME/$S3_KEY ..."

# Upload to S3
aws s3 cp "$LOCAL_FILE" "s3://$BUCKET_NAME/$S3_KEY"

if [ $? -eq 0 ]; then
  echo "✅ Upload successful!"
else
  echo "❌ Upload failed!"
  exit 1
fi
