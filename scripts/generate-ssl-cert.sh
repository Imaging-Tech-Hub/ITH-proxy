#!/bin/bash
#
# Self-Signed SSL Certificate Generator
# Generates SSL certificates for HTTPS support in Docker
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/certs"
CERT_FILE="${CERT_DIR}/cert.pem"
KEY_FILE="${CERT_DIR}/key.pem"
DAYS_VALID=365
KEY_SIZE=2048

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SSL Certificate Generator${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if certificates already exist
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo -e "${YELLOW}⚠️  Certificates already exist!${NC}"
    echo "   Certificate: $CERT_FILE"
    echo "   Key: $KEY_FILE"
    echo ""
    read -p "Do you want to regenerate them? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}✓ Keeping existing certificates${NC}"
        exit 0
    fi
    echo ""
fi

# Create certs directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Prompt for domain/IP
echo "Enter domain name or IP address for the certificate"
echo "(Press Enter to use default: localhost)"
read -p "Domain/IP: " DOMAIN
DOMAIN=${DOMAIN:-localhost}

echo ""
echo -e "${GREEN}Generating SSL certificate...${NC}"
echo "   Domain/IP: $DOMAIN"
echo "   Valid for: $DAYS_VALID days"
echo "   Key size: $KEY_SIZE bits"
echo ""

# Generate self-signed certificate
openssl req -x509 -nodes -days $DAYS_VALID -newkey rsa:$KEY_SIZE \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/C=US/ST=State/L=City/O=Development/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:0.0.0.0" \
    2>/dev/null

# Set proper permissions
chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Certificate generated successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Certificate files:"
echo "   Certificate: $CERT_FILE"
echo "   Private Key: $KEY_FILE"
echo ""
echo "Certificate details:"
openssl x509 -in "$CERT_FILE" -noout -subject -dates -ext subjectAltName 2>/dev/null
echo ""
echo -e "${YELLOW}Note:${NC} This is a self-signed certificate."
echo "Browsers will show a security warning that you'll need to accept."
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "1. Start services: docker-compose up"
echo "2. Access: https://localhost"
echo "3. Accept the browser security warning"
echo ""
