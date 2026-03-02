"""NapCat channel implementation using OneBot v11 Reverse WebSocket.

NapCat is a QQ bot framework that provides OneBot v11 protocol support.
This channel uses Reverse WebSocket to receive and send messages.
The local NapCat instance connects to nanobot's WebSocket server.

Supports both long connection (direct NapCat) and short connection (via MidLayer) modes.
"""

import asyncio
import json
import uuid
from collections import deque
from typing import Any

import aiohttp
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
        # For short connection mode: track pending response futures
        self._pending_responses: dict[str, asyncio.Future[OutboundMessage]] = {}

    async def start(self) -> None:
        """Start the NapCat channel.

        Starts WebSocket server to accept connections from NapCat.
        """
        if not self.config.port:
            logger.error("NapCat port not configured")
            return

        self._running = True

        # Start WebSocket server
        # Note: subprotocols is optional to support clients that don't send it
        self._server = await websockets.serve(
            self._handle_connection,
            self.config.host,
            self.config.port,
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
        """Send a message through NapCat.

        Supports multiple modes:
        1. Long connection: via WebSocket (direct NapCat connection)
        2. Short connection sync: via Future (request/response pattern)
        3. MidLayer callback: via HTTP POST to MidLayer (preferred for async mode)
        4. NapCat HTTP API: direct HTTP API call (fallback)

        Args:
            msg: The message to send
        """
        # Check if this is a short connection response (has request_id in metadata)
        request_id = msg.metadata.get("request_id")
        if request_id and request_id in self._pending_responses:
            # Short connection sync mode: set the future result
            future = self._pending_responses.get(request_id)
            if future and not future.done():
                future.set_result(msg)
                logger.debug(f"Short connection response set for request {request_id[:8]}")
            return

        # Long connection mode: send via WebSocket
        if self._ws:
            try:
                # Build message content (text + images)
                message_content = self._build_message_content(msg)
                
                payload = {
                    "action": "send_private_msg",
                    "params": {
                        "user_id": int(msg.chat_id),
                        "message": message_content,
                    },
                }

                async with self._send_lock:
                    await self._ws.send(json.dumps(payload))

                logger.debug(f"Message sent via WebSocket to {msg.chat_id}: {msg.content[:50]}")
                return
            except Exception as e:
                logger.error(f"Error sending via WebSocket: {e}")
                # Fall through to other modes

        # Try MidLayer callback first (preferred for async mode)
        if self.config.midlayer_callback_url:
            await self._send_via_midlayer(msg)
            return

        # Fallback to NapCat HTTP API
        await self._send_via_http(msg)

    async def _send_via_midlayer(self, msg: OutboundMessage) -> None:
        """Send message via MidLayer HTTP callback.

        Args:
            msg: The message to send
        """
        callback_url = self.config.midlayer_callback_url

        try:
            payload = {
                "user_id": int(msg.chat_id),
                "content": msg.content,
                "metadata": msg.metadata,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    callback_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("status") == "ok":
                            logger.debug(f"Message sent via MidLayer to {msg.chat_id}: {msg.content[:50]}")
                        else:
                            logger.warning(f"MidLayer callback error: {result}")
                    else:
                        logger.warning(f"MidLayer callback returned {resp.status}")

        except Exception as e:
            logger.error(f"Error sending via MidLayer callback: {e}")

    async def _send_via_http(self, msg: OutboundMessage) -> None:
        """Send message via NapCat HTTP API (for async mode).

        Args:
            msg: The message to send
        """
        # NapCat HTTP API endpoint (default port 3000)
        # This should be configured based on your NapCat setup
        napcat_http_url = self.config.http_api_url or "http://localhost:3000"
        token = self.config.access_token

        try:
            # Build message content (text + images)
            message_content = self._build_message_content(msg)
            
            payload = {
                "user_id": int(msg.chat_id),
                "message": message_content,
            }

            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{napcat_http_url}/send_private_msg",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("status") == "ok":
                            logger.debug(f"Message sent via HTTP to {msg.chat_id}: {msg.content[:50]}")
                        else:
                            logger.warning(f"NapCat HTTP API error: {result}")
                    else:
                        logger.warning(f"NapCat HTTP API returned {resp.status}")

        except Exception as e:
            logger.error(f"Error sending via NapCat HTTP API: {e}")

    def _build_message_content(self, msg: OutboundMessage) -> str | list[dict]:
        """Build OneBot message content from text and media.
        
        OneBot v11 supports two message formats:
        1. String format: simple text
        2. Array format: list of message segments (text, image, etc.)
        
        Args:
            msg: The outbound message with content and optional media
            
        Returns:
            String for text-only messages, or array for messages with media
        """
        # If no media, return simple text
        if not msg.media:
            return msg.content
        
        # Build message array for mixed content
        message_array = []
        
        # Add text content if present
        if msg.content:
            message_array.append({
                "type": "text",
                "data": {"text": msg.content}
            })
        
        # Add images
        for media_path in msg.media:
            # Support both URLs and local file paths
            if media_path.startswith("http://") or media_path.startswith("https://"):
                # URL-based image
                message_array.append({
                    "type": "image",
                    "data": {"file": media_path}
                })
            elif media_path.startswith("base64://"):
                # Base64-encoded image
                message_array.append({
                    "type": "image",
                    "data": {"file": media_path}
                })
            else:
                # Local file path - convert to base64 or file URL
                # For now, use file:// protocol
                import os
                if os.path.exists(media_path):
                    # Try to read and encode as base64
                    try:
                        with open(media_path, "rb") as f:
                            import base64
                            image_data = base64.b64encode(f.read()).decode()
                            message_array.append({
                                "type": "image",
                                "data": {"file": f"base64://{image_data}"}
                            })
                    except Exception as e:
                        logger.warning(f"Failed to encode image {media_path}: {e}")
                else:
                    logger.warning(f"Image file not found: {media_path}")
        
        return message_array

    async def _handle_connection(self, ws: WebSocketServerProtocol) -> None:
        """Handle incoming WebSocket connection from NapCat (long-lived connection).

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

    async def _handle_short_connection(self, ws: WebSocketServerProtocol) -> None:
        """Handle short-lived WebSocket connection for async processing.

        Args:
            ws: The WebSocket connection
        """
        try:
            # Receive message
            message = await ws.recv()
            logger.debug(f"Received message: {message[:200]}")
            data = json.loads(message)

            post_type = data.get("post_type")
            logger.debug(f"Message post_type: {post_type}")

            if post_type == "message":
                # Async mode: return immediately, process in background
                # Send acknowledgment
                ack_response = {
                    "status": "ok",
                    "retcode": 0,
                    "data": {"message_id": data.get("message_id", 0)},
                    "echo": data.get("echo"),
                }
                await ws.send(json.dumps(ack_response))

                # Process message asynchronously (don't wait)
                asyncio.create_task(self._process_message_async(data))

            elif post_type == "meta_event":
                # No response needed for meta events in short connection
                pass

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from NapCat: {message[:100]}")
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error processing NapCat message: {e}")

    async def _process_message_async(self, data: dict[str, Any]) -> None:
        """Process message asynchronously (background task).

        Args:
            data: The message data from NapCat
        """
        try:
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
                chat_id=user_id,
                content=content,
                metadata={
                    "message_id": message_id,
                    "message_type": message_type,
                    "raw_data": data,
                },
            )

            # Publish to bus
            await self.bus.publish_inbound(msg)
            logger.info(f"Async message published from {user_id}: {content[:50]}")

        except Exception as e:
            logger.error(f"Error in async message processing: {e}")

    async def _message_loop(self) -> None:
        """Main message loop for handling WebSocket messages (legacy long connection mode)."""
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
            # Note: OneBot v11 heartbeat events don't require a response
            # NapCat sends heartbeat to maintain the connection
        elif "status" in data:
            # Response to API call
            if data.get("retcode") != 0:
                logger.warning(f"NapCat API error: {data}")
        else:
            # Other events (notice, request, etc.)
            pass

    async def _process_onebot_message_with_response(
        self, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Process message from NapCat and return response (for short connection mode).

        Args:
            data: The message data from NapCat

        Returns:
            Response dict or None
        """
        post_type = data.get("post_type")

        if post_type == "message":
            return await self._handle_message_event_with_response(data)
        elif post_type == "meta_event":
            # For short connections, no need to respond to heartbeat
            return None
        elif "status" in data:
            if data.get("retcode") != 0:
                logger.warning(f"NapCat API error: {data}")
            return None
        else:
            return None

    async def _handle_message_event_with_response(
        self, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Handle message event and wait for AI response (short connection mode).

        Args:
            data: The message event data

        Returns:
            OneBot response dict or None
        """
        # Extract message info
        user_id = str(data.get("user_id", ""))
        message_id = data.get("message_id")
        message_type = data.get("message_type")

        # Only handle private messages for now
        if message_type != "private":
            return None

        # Check if already processed (dedup)
        if message_id in self._processed_ids:
            return None
        self._processed_ids.append(message_id)

        # Check if sender is allowed
        if not self.is_allowed(user_id):
            logger.debug(f"Message from unauthorized user: {user_id}")
            return None

        # Parse message content
        raw_message = data.get("raw_message", "")

        # Handle array format messages
        message_array = data.get("message", [])
        if isinstance(message_array, list):
            text_parts = []
            for item in message_array:
                if item.get("type") == "text":
                    text_parts.append(item.get("data", {}).get("text", ""))
            content = " ".join(text_parts) if text_parts else raw_message
        else:
            content = raw_message

        if not content:
            return None

        # Create unique request ID for tracking response
        request_id = str(uuid.uuid4())

        # Create future to wait for response
        response_future: asyncio.Future[OutboundMessage] = asyncio.get_event_loop().create_future()
        self._pending_responses[request_id] = response_future

        # Create inbound message with request_id in metadata
        msg = InboundMessage(
            channel=self.name,
            sender_id=user_id,
            chat_id=user_id,
            content=content,
            metadata={
                "message_id": message_id,
                "message_type": message_type,
                "raw_data": data,
                "request_id": request_id,
            },
        )

        # Publish to bus
        await self.bus.publish_inbound(msg)
        logger.debug(f"Received message from {user_id}: {content[:50]}")

        try:
            # Wait for response with timeout
            response_msg = await asyncio.wait_for(response_future, timeout=60.0)

            # Build OneBot response
            return {
                "status": "ok",
                "retcode": 0,
                "data": {
                    "message_id": response_msg.metadata.get("message_id", 0),
                },
                "echo": data.get("echo"),
            }
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response to message from {user_id}")
            return {
                "status": "failed",
                "retcode": -1,
                "msg": "Timeout waiting for AI response",
                "echo": data.get("echo"),
            }
        finally:
            # Clean up
            self._pending_responses.pop(request_id, None)

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
