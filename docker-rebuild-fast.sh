#!/bin/bash
# Fast rebuild script without WhatsApp bridge

echo "Fast rebuilding nanobot image (without WhatsApp bridge)..."
docker build -f Dockerfile.fast -t nanobot:latest .

if [ $? -eq 0 ]; then
    echo "nanobot image rebuilt successfully (fast mode)"
else
    echo "Failed to rebuild image"
    exit 1
fi
