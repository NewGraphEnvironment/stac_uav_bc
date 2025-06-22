#!/bin/bash
# This script registers a collection and items from S3.

set -e  # Exit immediately if a command fails

BUCKET_URL="https://imagery-uav-bc.s3.amazonaws.com"
JSON_NAME="collection.json"
COLLECTION_JSON=$(curl -s "${BUCKET_URL}/${JSON_NAME}")
COLLECTION_ID=$(echo "$COLLECTION_JSON" | jq -r '.id')

curl -X DELETE http://localhost:8000/collections/${COLLECTION_ID}

# --- Register Collection from S3 ---
echo "Registering STAC Collection '${COLLECTION_ID}' from S3..."
# @- grabs $COLLECTION_JSON from the other side of the pipe
echo "$COLLECTION_JSON" | curl -X POST "http://localhost:8000/collections" \
     -H "Content-Type: application/json" \
     --data-binary @-

# --- Register STAC Items ---
echo "Registering STAC Items from S3..."
for item in $(echo "$COLLECTION_JSON" | jq -r '.links[] | select(.rel=="item") | .href'); do
  curl -X POST "http://localhost:8000/collections/${COLLECTION_ID}/items" \
       -H "Content-Type: application/json" \
       --data-binary @<(curl -s "$item")
done
