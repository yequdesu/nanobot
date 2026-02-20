"""NapCat channel implementation using OneBot v11 Reverse WebSocket.

NapCat is a QQ bot framework that provides OneBot v11 protocol support.
This channel uses Reverse WebSocket to receive and send messages.
The local NapCat instance connects to nanobot's WebSocket server.
"""

import asyncio
import json
from collections import deque
from typing import Any

import websockets
from loguru import logger
from websockets.server import WebSocketServerProtocol

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import NapCatConfig


class NapCatChannel(BaseChannel):
    """NapCat channel using OneBot v11 Reverse WebSocket.

    This channel communicates with NapCat through:
    1. WebSocket server for receiving messages (Reverse WS)
    2. Same WebSocket connection for sending messages

    NapCat connects to nanobot as a client, allowing cloud deployment
    without exposing NapCat to the internet.

    Configuration:
        - host: Host to bind WebSocket server (e.g., "0.0.0.0")
        - port: Port to bind WebSocket server (e.g., 18790)
        - access_token: Token for authentication
        - path: WebSocket endpoint path (e.g., "/onebot/v11/ws")
        - allow_from: List of allowed QQ numbers
    """

    name = "napcat"

    def __init__(self, config: NapCatConfig, bus: MessageBus):
        """Initialize NapCat channel.

        Args:
            config: NapCat configuration
            bus: Message bus for communication
        """
        super().__init__(config, bus)
        self.config: NapCatConfig = config
        self._server: websockets.WebSocketServer | None = None
        self._ws: WebSocketServerProtocol | None = None
        self._processed_ids: deque = deque(maxlen=1000)
        self._heartbeat_task: asyncio.Task | None = None
        self._send_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the NapCat channel.

        Starts WebSocket server to accept connections from NapCat.
        """
        if not self.config.port:
            logger.error("NapCat port not configured")
            return

        self._running = True

        # Start WebSocket server
        self._server = await websockets.serve(
            self._handle_connection,
            self.config.host,
            self.config.port,
            subprotocols=["OneBot.v11"],
        )

        logger.info(
            f"NapCat WebSocket server listening on "
            f"{self.config.host}:{self.config.port}"
        )

    async def stop(self) -> None:
        """Stop the NapCat channel."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        logger.info("NapCat channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through NapCat WebSocket.

        Args:
            msg: The message to send
        """
        if not self._ws:
            logger.warning("NapCat WebSocket not connected")
            return

        try:
            # Build OneBot v11 private message request
            payload = {
                "action": "send_private_msg",
                "params": {
                    "user_id": int(msg.chat_id),
                    "message": msg.content,
                },
            }

            async with self._send_lock:
                await self._ws.send(json.dumps(payload))

            logger.debug(f"Message sent to {msg.chat_id}: {msg.content[:50]}")

        except Exception as e:
            logger.error(f"Error sending NapCat message: {e}")

    async def _handle_connection(self, ws: WebSocketServerProtocol) -> None:
        """Handle incoming WebSocket connection from NapCat.

        Args:
            ws: The WebSocket connection
        """
        # Check if already connected
        if self._ws is not None:
            logger.warning("NapCat already connected, rejecting new connection")
            await ws.close(1008, "Already connected")
            return

        # Validate access token
        if self.config.access_token:
            # Handle different websockets library versions
            auth_header = ""
            if hasattr(ws, "request_headers"):
                auth_header = ws.request_headers.get("Authorization", "")
            elif hasattr(ws, "headers"):
                auth_header = ws.headers.get("Authorization", "")

            expected = f"Bearer {self.config.access_token}"
            if auth_header != expected:
                logger.warning("NapCat authentication failed")
                await ws.close(1008, "Authentication failed")
                return

        self._ws = ws
        logger.info("NapCat connected via WebSocket")

        try:
            await self._message_loop()
        except asyncio.CancelledError:
            raise
        except websockets.exceptions.ConnectionClosed:
            logger.info("NapCat WebSocket connection closed")
        except Exception as e:
            logger.error(f"NapCat WebSocket error: {e}")
        finally:
            self._ws = None
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                self._heartbeat_task = None
            logger.info("NapCat disconnected")

    async def _message_loop(self) -> None:
        """Main message loop for handling WebSocket messages."""
        if not self._ws:
            return

        async for message in self._ws:
            try:
                data = json.loads(message)
                await self._process_onebot_message(data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from NapCat: {message[:100]}")
            except Exception as e:
                logger.error(f"Error processing NapCat message: {e}")

    async def _process_onebot_message(self, data: dict[str, Any]) -> None:
        """Process message from NapCat (OneBot v11 format).

        Args:
            data: The message data from NapCat
        """
        # Handle post type events (messages)
        post_type = data.get("post_type")

        if post_type == "message":
            await self._handle_message_event(data)
        elif post_type == "meta_event":
            await self._handle_meta_event(data)
        elif "status" in data:
            # Response to API call
            if data.get("retcode") != 0:
                logger.warning(f"NapCat API error: {data}")
        else:
            # Other events (notice, request, etc.)
            pass

    async def _handle_message_event(self, data: dict[str, Any]) -> None:
        """Handle message event from NapCat.

        Args:
            data: The message event data
        """
        # Extract message info
        user_id = str(data.get("user_id", ""))
        message_id = data.get("message_id")
        message_type = data.get("message_type")

        # Only handle private messages for now
        if message_type != "private":
            return

        # Check if already processed (dedup)
        if message_id in self._processed_ids:
            return
        self._processed_ids.append(message_id)

        # Check if sender is allowed
        if not self.is_allowed(user_id):
            logger.debug(f"Message from unauthorized user: {user_id}")
            return

        # Parse message content
        raw_message = data.get("raw_message", "")

        # Handle array format messages
        message_array = data.get("message", [])
        if isinstance(message_array, list):
            # Extract text from array format
            text_parts = []
            for item in message_array:
                if item.get("type") == "text":
                    text_parts.append(item.get("data", {}).get("text", ""))
            content = " ".join(text_parts) if text_parts else raw_message
        else:
            content = raw_message

        if not content:
            return

        # Create inbound message
        msg = InboundMessage(
            channel=self.name,
            sender_id=user_id,
            chat_id=user_id,  # For private messages, chat_id is user_id
            content=content,
            metadata={
                "message_id": message_id,
                "message_type": message_type,
                "raw_data": data,
            },
        )

        # Publish to bus
        await self.bus.publish_inbound(msg)
        logger.debug(f"Received message from {user_id}: {content[:50]}")

    async def _handle_meta_event(self, data: dict[str, Any]) -> None:
        """Handle meta event from NapCat (heartbeat, lifecycle).

        Args:
            data: The meta event data
        """
        meta_event_type = data.get("meta_event_type")

        if meta_event_type == "heartbeat":
            # Heartbeat received, connection is alive
            pass
        elif meta_event_type == "lifecycle":
            sub_type = data.get("sub_type")
            if sub_type == "connect":
                logger.info("NapCat lifecycle: connected")
            elif sub_type == "enable":
                logger.info("NapCat lifecycle: enabled")
            elif sub_type == "disable":
                logger.info("NapCat lifecycle: disabled")
