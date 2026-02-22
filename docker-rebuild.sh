#!/bin/bash

# docker-rebuild.sh - Rebuild nanobot docker image with latest code

set -e

echo "building nanobot image with latest code..."
docker build -t nanobot .

if [ $? -ne 0 ]; then
  echo "error: docker build failed"
  exit 1
fi

echo "nanobot image rebuilt successfully"
