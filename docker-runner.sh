#!/bin/bash

# docker-runner.sh - Build and run nanobot container for cloud deployment
# This script is designed for server deployment via git pull

# define variables
CONTAINER_NAME="nanobot-dev"
DATA_DIR="./nanobot-data"
PROJECT_DIR="."
NAPCAT_PORT=18790

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

# remove corrupted data directory with sudo
if [ -e "$DATA_DIR" ]; then
  echo "cleaning old data directory with sudo..."
  sudo rm -rf "$DATA_DIR"
  if [ $? -ne 0 ]; then
    echo "error: failed to remove $DATA_DIR. check your sudo permissions."
    exit 1
  fi
  echo "cleaned old data directory"
fi

# create data directory
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/skills"
mkdir -p "$DATA_DIR/workspace"
mkdir -p "$DATA_DIR/memory"

# copy workspace files
if [ -d "$PROJECT_DIR/workspace" ]; then
  cp -r "$PROJECT_DIR/workspace/"* "$DATA_DIR/workspace/" 2>/dev/null || true
  echo "workspace files copied to $DATA_DIR/workspace/"
fi

# onboard nanobot to generate default config first
docker run --rm --name "$CONTAINER_NAME" \
  -v "$(pwd)/$DATA_DIR:/root/.nanobot" \
  nanobot onboard

# check onboard success
if [ $? -ne 0 ]; then
  echo "warn: nanobot onboard failed, please check error message"
  exit 1
fi

# copy userskills
if [ -d "$PROJECT_DIR/userskills" ]; then
  cp -r "$PROJECT_DIR/userskills/"* "$DATA_DIR/workspace/skills/"
  echo "userskills copied to $DATA_DIR/workspace/skills/"
else
  echo "warn: userskills directory not found"
fi

# copy custom config.json to overwrite default config
if [ -f "$PROJECT_DIR/config/config.json" ]; then
  cp "$PROJECT_DIR/config/config.json" "$DATA_DIR/config.json"
  echo "config file copied to $DATA_DIR/config.json"
else
  echo "warn: config file not found, use default config"
fi

# start nanobot gateway with napcat websocket port exposed
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
  echo "napcat configuration guide:"
  echo "  1. set reverse websocket url: ws://<server-ip>:18790"
  echo "  2. set access token to match config.json"
  echo "  3. restart napcat to connect"
else
  echo "warn: nanobot gateway start failed, please check error message"
  exit 1
fi
