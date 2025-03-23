#!/bin/bash
set -e

COLLECTION_ID="imagery-uav-bc-prod"
API_URL="http://localhost:8000"

# Check if collection exists
COLLECTION_EXISTS=$(curl -s -o /dev/null -w "%{http_code}" $API_URL/collections/$COLLECTION_ID)

if [ "$COLLECTION_EXISTS" = "200" ]; then
  echo "Deleting items in $COLLECTION_ID..."

  ITEM_IDS=$(curl -s $API_URL/collections/$COLLECTION_ID/items | jq -r '.features[].id // empty')

  for id in $ITEM_IDS; do
    echo "Deleting item $id"
    curl -s -X DELETE $API_URL/collections/$COLLECTION_ID/items/$id
  done

  echo "Deleting collection $COLLECTION_ID"
  curl -s -X DELETE $API_URL/collections/$COLLECTION_ID
else
  echo "Collection $COLLECTION_ID does not exist. Skipping."
fi







