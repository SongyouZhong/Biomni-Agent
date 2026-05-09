#!/bin/bash
# Automatically build the sandbox, start it, and run tests
echo "====================================="
echo "1. Starting Docker Build (This will take ~15 mins)..."
echo "====================================="
docker build -t biomni-sandbox -f sandbox/Dockerfile .
if [ $? -ne 0 ]; then
    echo "❌ Docker build failed!"
    exit 1
fi

echo "====================================="
echo "2. Starting Sandbox Container..."
echo "====================================="
docker rm -f biomni-exec-sandbox 2>/dev/null || true
docker run -d --name biomni-exec-sandbox -p 8081:8081 -v $(pwd)/data:/data biomni-sandbox
if [ $? -ne 0 ]; then
    echo "❌ Docker run failed!"
    exit 1
fi

echo "Waiting for container to initialize..."
sleep 5

echo "====================================="
echo "3. Running Integration Test..."
echo "====================================="
conda run -n biomni_agent python test_sandbox.py

echo "====================================="
echo "Done! You can close this window."
echo "====================================="
