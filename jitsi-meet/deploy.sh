#!/bin/bash
# Deploy Jitsi Meet on Server 1
# Run this ON the server: scp -r jitsi-meet/ root@94.130.170.167:/root/ && ssh root@94.130.170.167 'bash /root/jitsi-meet/deploy.sh'
set -euo pipefail

echo "=== Jitsi Meet Deployment ==="
cd /root/jitsi-meet

# Check .env exists
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Generate secrets first."
  exit 1
fi

# Check if Traefik network exists (from Coolify)
if ! docker network ls | grep -q coolify; then
  echo "WARNING: No coolify network found. Traefik labels may not work."
  echo "Make sure the web service can reach Traefik's network."
fi

# Pull images
echo "Pulling Jitsi images..."
docker compose pull

# Start services
echo "Starting Jitsi services..."
docker compose up -d

# Wait for startup
echo "Waiting 15s for services to start..."
sleep 15

# Check status
echo ""
echo "=== Service Status ==="
docker compose ps

echo ""
echo "=== Next Steps ==="
echo "1. Add DNS A-record: meet.eppcom.de -> 94.130.170.167"
echo "2. Connect web service to Traefik network:"
echo "   docker network connect coolify jitsi-meet-web-1"
echo "3. Test: https://meet.eppcom.de"
echo ""
echo "If using Coolify's Traefik, you may need to add the web container"
echo "to Coolify's proxy network manually."
