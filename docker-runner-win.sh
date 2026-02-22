#!/bin/bash

# docker-runner.sh - Build and run nanobot container for cloud deployment

# define variables
CONTAINER_NAME="nanobot-dev"
DATA_DIR="./nanobot-data"
PROJECT_DIR="."
NAPCAT_PORT=18790
NETWORK_NAME="nanobot-network"

# check if port is already in use
PORT_IN_USE=$(docker ps -q --filter "publish=$NAPCAT_PORT" 2>/dev/null)
if [ -n "$PORT_IN_USE" ]; then
  echo "warn: port $NAPCAT_PORT is already allocated by container:"
  docker ps --filter "publish=$NAPCAT_PORT" --format "  {{.Names}} ({{.ID}})"
  echo "stopping conflicting container..."
  docker stop $PORT_IN_USE 2>/dev/null || true
  docker rm $PORT_IN_USE 2>/dev/null || true
  echo "conflicting container stopped"
fi

# clean old container
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# check nanobot image exists
if ! docker images | grep -q "^nanobot "; then
  echo "error: nanobot image not found"
  echo "please run: bash docker-rebuild.sh"
  exit 1
fi
echo "nanobot image found"

# create docker network for inter-container communication
# this allows napcat to connect to nanobot using container name
if ! docker network ls | grep -q "$NETWORK_NAME"; then
  echo "creating docker network: $NETWORK_NAME..."
  docker network create "$NETWORK_NAME"
  echo "network created"
else
  echo "docker network $NETWORK_NAME already exists"
fi

# remove old data directory
if [ -e "$DATA_DIR" ]; then
  echo "cleaning old data directory..."
  rm -rf "$DATA_DIR"
  echo "cleaned old data directory"
fi

# create data directory
mkdir -p "$DATA_DIR/skills"
mkdir -p "$DATA_DIR/workspace"
mkdir -p "$DATA_DIR/memory"
echo "created data directory structure"

# onboard nanobot to generate default config
docker run --rm --name "${CONTAINER_NAME}-onboard" \
  -v "$(pwd)/$DATA_DIR:/root/.nanobot" \
  nanobot onboard

# check onboard success
if [ $? -ne 0 ]; then
  echo "warn: nanobot onboard failed"
  exit 1
fi
echo "onboard completed"

# copy workspace files
if [ -d "$PROJECT_DIR/workspace" ]; then
  cp -r "$PROJECT_DIR/workspace/"* "$DATA_DIR/workspace/" 2>/dev/null || true
  echo "workspace files copied"
fi

# copy userskills
if [ -d "$PROJECT_DIR/userskills" ]; then
  mkdir -p "$DATA_DIR/workspace/skills"
  cp -r "$PROJECT_DIR/userskills/"* "$DATA_DIR/workspace/skills/"
  echo "userskills copied"
else
  echo "warn: userskills directory not found"
fi

# copy custom config.json
if [ -f "$PROJECT_DIR/config/config.json" ]; then
  cp "$PROJECT_DIR/config/config.json" "$DATA_DIR/config.json"
  echo "config file copied"
fi

# start nanobot gateway with napcat websocket port exposed
# note: image already contains latest code, no volume mount needed for nanobot/
docker run -d --name "$CONTAINER_NAME" \
  -p 18790:18790 \
  -v "$(pwd)/$DATA_DIR:/root/.nanobot" \
  nanobot gateway

# check gateway start success
if [ $? -eq 0 ]; then
  echo "nanobot gateway started successfully!"
  echo "container name: $CONTAINER_NAME"
  echo "napcat websocket: ws://<server-ip>:18790"
  echo ""
  echo "for local napcat connection:"
  echo "  url: ws://nanobot-dev:18790 (within docker network)"
  echo "  url: ws://host.docker.internal:18790 (from host)"
else
  echo "warn: nanobot gateway start failed"
  exit 1
fi
