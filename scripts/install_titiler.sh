#!/bin/bash

# Exit on error
set -e


# sudo apt update && sudo apt upgrade -y
# 
# # Pull Titiler Docker image
# echo "Pulling the latest Titiler Docker image..."
# docker pull developmentseed/titiler:latest

# Create Titiler container
echo "Creating Titiler container..."
docker run -d \
  --name titiler \
  -p 8001:80 \
  developmentseed/titiler:latest
  
# allowaccess through the firewall
sudo ufw allow 8001/tcp