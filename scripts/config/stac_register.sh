#!/bin/bash
# This script registers a STAC collection and its items from S3 in chunks of 1000.

set -e

# Define S3 bucket and collection
BUCKET_URL="https://stac-dem-bc.s3.amazonaws.com"
BUCKET_URL="https://stac-orthophoto-bc.s3.amazonaws.com"
JSON_NAME="collection.json"
COLLECTION_URL="${BUCKET_URL}/${JSON_NAME}"

# Download collection JSON
echo "Fetching collection from ${COLLECTION_URL}..."
COLLECTION_JSON=$(curl -sL "$COLLECTION_URL")
COLLECTION_ID=$(echo "$COLLECTION_JSON" | jq -r '.id')

# Delete existing collection if exists
echo "Deleting any existing collection with ID '${COLLECTION_ID}'..."
curl -s -X DELETE "http://localhost:8000/collections/${COLLECTION_ID}" > /dev/null || true

# Register the collection
echo "Registering collection '${COLLECTION_ID}'..."
echo "$COLLECTION_JSON" | curl -s -X POST "http://localhost:8000/collections" \
  -H "Content-Type: application/json" \
  --data-binary @-

# Extract all item hrefs to a temp file
echo "Extracting item URLs..."
TMP_ITEMS_FILE=$(mktemp)
echo "$COLLECTION_JSON" | jq -r '.links[] | select(.rel=="item") | .href' > "$TMP_ITEMS_FILE"

# Register items in chunks of 1000
echo "Registering items in chunks of 1000..."
split -l 1000 "$TMP_ITEMS_FILE" items_chunk_

for chunk in items_chunk_*; do
  echo "Registering chunk: $chunk"
  while read -r item_url; do
    echo "  → $item_url"
    curl -sL "$item_url" | curl -s -X POST "http://localhost:8000/collections/${COLLECTION_ID}/items" \
      -H "Content-Type: application/json" \
      --data-binary @-
  done < "$chunk"
done

# Clean up
rm "$TMP_ITEMS_FILE" items_chunk_*

echo "✅ Registration complete."
