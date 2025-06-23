#!/bin/bash
# Generate a self-signed certificate for testing HTTPS

echo "Generating self-signed certificate for MCP Gateway..."

# Create certs directory if it doesn't exist
mkdir -p ../certs

# Generate private key and certificate
openssl req -x509 -newkey rsa:4096 \
  -keyout ../certs/key.pem \
  -out ../certs/cert.pem \
  -days 365 \
  -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Combine into single file
cat ../certs/cert.pem ../certs/key.pem > ../certs/server.pem

# Clean up temporary files
rm ../certs/cert.pem ../certs/key.pem

echo "Certificate generated at: certs/server.pem"
echo ""
echo "WARNING: This is a self-signed certificate for testing only!"
echo "For production, use a certificate from a trusted CA."
echo ""
echo "To use with the MCP Gateway skill, set verify_ssl: false"