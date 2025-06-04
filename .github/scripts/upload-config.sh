#!/bin/bash

# Usage: ./upload-config.sh <local_file_path> <s3_bucket_name> <s3_key> <second_local_file_path>

# Exit if any command fails
set -e

# Input arguments
LOCAL_FILE=$1
BUCKET_NAME=$2
S3_KEY=$3
SECOND_LOCAL_FILE=$4

# Check if all required arguments are provided
if [[ -z "$LOCAL_FILE" || -z "$BUCKET_NAME" || -z "$S3_KEY" || -z "$SECOND_LOCAL_FILE" ]]; then
  echo "Usage: $0 <local_file_path> <s3_bucket_name> <s3_key> <second_local_file_path>"
  echo "Example: $0 config/production-config.json my-config-bucket path/to/config/production-config.json config/production-config.yaml"
  exit 1
fi

# Validate that the first file exists
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

# Validate that the second file exists
if [ ! -f "$SECOND_LOCAL_FILE" ]; then
  echo "Error: Second local file '$SECOND_LOCAL_FILE' does not exist."
  exit 1
fi

# Determine the second file's S3 key by appending a suffix
SECOND_S3_KEY="${S3_KEY%.*}.yaml"

echo "Uploading $SECOND_LOCAL_FILE to s3://$BUCKET_NAME/$SECOND_S3_KEY ..."

# Upload the second file to S3
aws s3 cp "$SECOND_LOCAL_FILE" "s3://$BUCKET_NAME/$SECOND_S3_KEY"

if [ $? -eq 0 ]; then
  echo "✅ Second upload successful!"
else
  echo "❌ Second upload failed!"
  exit 1
fi
