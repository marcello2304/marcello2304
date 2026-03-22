#!/bin/bash
# IMMEDIATE FIX - Copy & paste on Server 2
# Changes voice ID from bad to good and fixes RAG error handling

cd /opt/eppcom-server2/voice-agent

# Backup
echo "Backing up..."
cp agent.py agent.py.backup

# Fix 1: Change voice ID from dark 'b9de4a89...' to 'default' (warm German)
echo "Fixing voice ID..."
sed -i 's/"b9de4a89-2257-424b-94c2-db18ba68c81a"/"default"/g' agent.py

# Verify change
echo "Verification:"
echo "Old voice ID in backup:"
grep "CARTESIA_VOICE_ID =" agent.py.backup | head -1
echo ""
echo "New voice ID in agent.py:"
grep "CARTESIA_VOICE_ID =" agent.py | head -1
echo ""

# Fix 2: Rebuild Docker image
echo "Building Docker image..."
docker build -t eppcom/voice-agent:latest .
echo "✓ Docker image rebuilt"
echo ""

# Fix 3: Restart container
echo "Restarting container..."
cd /opt/eppcom-server2
docker stop livekit-agent 2>/dev/null || true
sleep 2
docker rm livekit-agent 2>/dev/null || true

docker run -d \
  --name livekit-agent \
  --env-file .env \
  --network livekit-net \
  -e PYTHONUNBUFFERED=1 \
  --restart unless-stopped \
  eppcom/voice-agent:latest

sleep 5
echo "✓ Container restarted"
echo ""

# Show logs
echo "Recent logs:"
docker logs livekit-agent --tail 15
