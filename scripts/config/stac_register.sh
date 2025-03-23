#!/bin/bash
# This script registers a collection from S3.

set -e  # Exit immediately if a command fails

# --- Register Collection from S3 ---
echo "Registering STAC Collection from S3..."
curl -X POST "http://localhost:8000/collections" \
     -H "Content-Type: application/json" \
     --data-binary @<(curl -s https://imagery-uav-bc.s3.amazonaws.com/collection.json)

# --- Register STAC Items ---
echo "Registering STAC Items from S3..."
for item in $(jq -r '.links[] | select(.rel=="item") | .href' <(curl -s https://imagery-uav-bc.s3.amazonaws.com/collection.json)); do
  curl -X POST "http://localhost:8000/collections/imagery-uav-bc-prod/items" \
       -H "Content-Type: application/json" \
       --data-binary @<(curl -s "$item")
done