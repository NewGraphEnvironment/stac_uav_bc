#!/bin/bash

# Exit on error
set -e

# Variables
DOMAIN="a11s.one"
EMAIL="al@newgraphenvironment.com"  
NGINX_CONF="/etc/nginx/sites-available/$DOMAIN"

# sudo apt update && sudo apt upgrade -y
# 
# sudo apt install -y \
#     certbot \
#     python3-certbot-nginx
    
# Obtain SSL certificate with Certbot
echo "Requesting SSL certificate..."
sudo certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive --redirect
sudo certbot --nginx -d images.a11s.one --email "$EMAIL" --agree-tos --non-interactive --redirect
sudo certbot --nginx -d rstudio.a11s.one --email "$EMAIL" --agree-tos --non-interactive --redirect
sudo certbot --nginx -d viewer.a11s.one --email "$EMAIL" --agree-tos --non-interactive --redirect
sudo certbot --nginx -d titiler.a11s.one --email "$EMAIL" --agree-tos --non-interactive --redirect

# Verify certificate renewal works
echo "Setting up automatic renewal check..."
sudo systemctl enable certbot.timer
sudo systemctl restart certbot.timer
