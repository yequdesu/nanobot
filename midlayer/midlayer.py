"""Mid-Layer Service - Bridge between NapCat and NanoBot via Nacos.

This service acts as a bridge:
1. Receives WebSocket connections from NapCat (OneBot v11 protocol)
2. Discovers NanoBot instances from Nacos
3. Forwards messages to NanoBot asynchronously
4. Receives responses from NanoBot via HTTP callback and forwards to NapCat

Usage:
    python midlayer.py

NapCat Configuration:
    WebSocket URL: ws://<midlayer-ip>:18800
    Message Format: Array
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp
from aiohttp import web
import websockets
from websockets.legacy.server import WebSocketServerProtocol
from websockets.legacy.client import WebSocketClientProtocol

# Nacos SDK imports
try:
    from v2.nacos.common.client_config_builder import ClientConfigBuilder
    from v2.nacos.naming.nacos_naming_service import NacosNamingService
    from v2.nacos.naming.model.naming_param import (
        RegisterInstanceParam,
        DeregisterInstanceParam,
        ListInstanceParam,
    )
    NACOS_SDK_AVAILABLE = True
except ImportError:
    NACOS_SDK_AVAILABLE = False
    logging.warning("nacos-sdk-python not installed. Install with: pip install nacos-sdk-python>=2.0.0")


@dataclass
class NacosConfig:
    """Nacos configuration."""
    server: str = "39.106.255.3:8848"
    namespace: str = "f45fa327-df31-4547-85a3-7d3dabf7fb19"
    username: str = "nacos"
    password: str = "nacos"


class MidLayer:
    """Mid-layer service for NapCat-NanoBot bridging via Nacos."""

    def __init__(
        self,
        nacos_config: NacosConfig,
        listen_host: str = "0.0.0.0",
        listen_port: int = 18800,
        http_port: int = 18801,  # HTTP port for NanoBot callbacks
        service_name: str = "nanobot-gateway",
        group: str = "DEFAULT_GROUP",
        nanobot_override_addr: str | None = None,  # Override NanoBot address (e.g., host.docker.internal:18790)
    ):
        self.nacos_config = nacos_config
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.http_port = http_port
        self.service_name = service_name
        self.group = group
        self.nanobot_override_addr = nanobot_override_addr

        self._server = None
        self._http_runner = None
        self._http_site = None
        self._running = False
        self._naming_service: Optional[NacosNamingService] = None

        # Track NapCat connections and pending responses
        self._napcat_ws: Optional[WebSocketServerProtocol] = None
        self._pending_messages: dict[str, dict[str, Any]] = {}  # message_id -> {user_id, chat_id, etc.}
        self._response_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start mid-layer service."""
        self._running = True

        # Start WebSocket server for NapCat
        self._server = await websockets.serve(
            self._handle_napcat,
            self.listen_host,
            self.listen_port,
            ping_interval=None,  # Disable server ping, let NapCat handle heartbeat
            ping_timeout=None,
        )

        # Start HTTP server for NanoBot callbacks
        await self._start_http_server()

        # Start response dispatcher
        asyncio.create_task(self._dispatch_responses())

        # Initialize Nacos connection (optional)
        if NACOS_SDK_AVAILABLE and not self.nanobot_override_addr:
            try:
                await self._init_nacos()
                logging.info(f"  Nacos: {self.nacos_config.server}")
            except Exception as e:
                logging.warning(f"Nacos connection failed: {e}")
                logging.warning("Falling back to direct connection mode")

        logging.info(f"Mid-layer started")
        logging.info(f"  WebSocket: ws://{self.listen_host}:{self.listen_port}")
        logging.info(f"  HTTP API: http://{self.listen_host}:{self.http_port}")
        if self.nanobot_override_addr:
            logging.info(f"  Target (direct): {self.nanobot_override_addr}")
        else:
            logging.info(f"  Target Service: {self.service_name}")

    async def stop(self) -> None:
        """Stop mid-layer service."""
        self._running = False

        # Stop HTTP server
        if self._http_site:
            await self._http_site.stop()
        if self._http_runner:
            await self._http_runner.cleanup()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logging.info("Mid-layer stopped")

    async def _start_http_server(self) -> None:
        """Start HTTP server for NanoBot callbacks."""
        app = web.Application()
        app.router.add_post("/callback", self._handle_nanobot_callback)
        app.router.add_get("/health", self._handle_health)

        self._http_runner = web.AppRunner(app)
        await self._http_runner.setup()
        self._http_site = web.TCPSite(self._http_runner, self.listen_host, self.http_port)
        await self._http_site.start()
        logging.info(f"HTTP server started on port {self.http_port}")

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "ok"})

    async def _handle_nanobot_callback(self, request: web.Request) -> web.Response:
        """Handle callback from NanoBot with response message."""
        try:
            data = await request.json()
            logging.debug(f"Received callback from NanoBot: {data}")

            # Add to response queue for dispatch to NapCat
            await self._response_queue.put(data)

            return web.json_response({"status": "ok"})
        except Exception as e:
            logging.error(f"Error handling NanoBot callback: {e}")
            return web.json_response({"status": "error", "msg": str(e)}, status=500)

    async def _dispatch_responses(self) -> None:
        """Dispatch responses from queue to NapCat."""
        while self._running:
            try:
                response = await asyncio.wait_for(self._response_queue.get(), timeout=1.0)
                await self._send_to_napcat(response)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Error dispatching response: {e}")

    async def _send_to_napcat(self, response: dict[str, Any]) -> None:
        """Send response to NapCat via WebSocket.

        Args:
            response: Response data from NanoBot
        """
        if not self._napcat_ws:
            logging.warning("No NapCat connection available, dropping response")
            return

        try:
            # Build OneBot message
            user_id = response.get("user_id")
            content = response.get("content")

            if not user_id or not content:
                logging.warning(f"Invalid response format: {response}")
                return

            payload = {
                "action": "send_private_msg",
                "params": {
                    "user_id": int(user_id),
                    "message": content,
                },
            }

            await self._napcat_ws.send(json.dumps(payload))
            logging.debug(f"Response sent to NapCat user {user_id}")
        except Exception as e:
            logging.error(f"Error sending to NapCat: {e}")

    async def _init_nacos(self) -> None:
        """Initialize Nacos naming service."""
        client_config = (
            ClientConfigBuilder()
            .server_address(self.nacos_config.server)
            .namespace_id(self.nacos_config.namespace)
            .username(self.nacos_config.username or None)
            .password(self.nacos_config.password or None)
            .build()
        )

        self._naming_service = await NacosNamingService.create_naming_service(client_config)
        logging.info(f"Connected to Nacos: {self.nacos_config.server}")

    async def _handle_napcat(self, ws: WebSocketServerProtocol) -> None:
        """Handle NapCat WebSocket connection."""
        try:
            client_addr = f"{ws.remote_address[0]}:{ws.remote_address[1]}"
        except Exception:
            client_addr = "unknown"

        logging.info(f"NapCat connected from {client_addr}")

        # Store the connection for response dispatching
        async with self._lock:
            if self._napcat_ws is not None:
                logging.warning("New NapCat connection, replacing existing one")
            self._napcat_ws = ws

        try:
            async for message in ws:
                try:
                    response = await self._process_message(message)
                    if response:
                        await ws.send(response)
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON from NapCat: {e}")
                except Exception as e:
                    logging.error(f"Error processing message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logging.info(f"NapCat disconnected from {client_addr}")
        except Exception as e:
            logging.warning(f"NapCat connection error from {client_addr}: {e}")
        finally:
            async with self._lock:
                if self._napcat_ws is ws:
                    self._napcat_ws = None

    async def _process_message(self, message: str) -> Optional[str]:
        """Process message from NapCat.

        Args:
            message: OneBot v11 JSON message

        Returns:
            Response JSON string or None
        """
        data = json.loads(message)
        post_type = data.get("post_type")
        logging.debug(f"Processing message with post_type: {post_type}")

        if post_type == "message":
            # Forward to NanoBot
            logging.info(f"Forwarding message to NanoBot: {message[:100]}...")
            return await self._forward_to_nanobot(message)
        elif post_type == "meta_event":
            # Handle meta events (heartbeat, lifecycle)
            meta_event_type = data.get("meta_event_type")
            logging.info(f"Received meta_event: {meta_event_type}")
            
            # Respond to heartbeat to keep connection alive
            if meta_event_type == "heartbeat":
                # Return empty object as heartbeat response
                return "{}"
            return None

        return None

    async def _forward_to_nanobot(self, message: str) -> Optional[str]:
        """Forward message to NanoBot asynchronously.

        In async mode, we immediately return acknowledgment and let NanoBot
        send the response later via HTTP callback.

        Args:
            message: OneBot message JSON string

        Returns:
            Immediate acknowledgment or None
        """
        # Parse message to extract info
        try:
            data = json.loads(message)
            user_id = data.get("user_id")
            message_id = data.get("message_id")

            # Store message info for later response matching
            if message_id:
                async with self._lock:
                    self._pending_messages[str(message_id)] = {
                        "user_id": user_id,
                        "message_id": message_id,
                    }
        except Exception as e:
            logging.warning(f"Failed to parse message: {e}")

        # Get NanoBot address
        if self.nanobot_override_addr:
            ip, port = self.nanobot_override_addr.rsplit(":", 1)
            port = int(port)
        else:
            instance = await self._discover_nanobot()
            if not instance:
                logging.error("No NanoBot instance available in Nacos")
                return None
            ip = instance.get("ip")
            port = instance.get("port")

        uri = f"ws://{ip}:{port}"

        try:
            # Create short-lived connection to forward message
            logging.debug(f"Connecting to NanoBot at {uri}")
            async with websockets.connect(uri) as bot_ws:
                await bot_ws.send(message)
                logging.info(f"Message forwarded to NanoBot at {uri}")

            # Return immediate acknowledgment
            return json.dumps({
                "status": "ok",
                "retcode": 0,
                "data": {"message_id": message_id},
            })

        except Exception as e:
            logging.error(f"Failed to forward to NanoBot at {uri}: {e}")
            return json.dumps({
                "status": "failed",
                "retcode": -1,
                "msg": str(e),
            })

    async def _discover_nanobot(self) -> Optional[dict[str, Any]]:
        """Discover NanoBot service from Nacos.

        Returns:
            Instance dict with ip, port, healthy or None
        """
        if not self._naming_service:
            return None

        try:
            list_param = ListInstanceParam(
                service_name=self.service_name,
                group_name=self.group,
                subscribe=False,
                healthy_only=False,  # Get all instances (including persistent)
            )

            result = await self._naming_service.list_instances(list_param)

            # Handle different return types
            instances = []
            if isinstance(result, list):
                instances = result
            elif hasattr(result, 'hosts'):
                instances = result.hosts

            if not instances:
                logging.warning(f"No healthy instances found for {self.service_name}")
                return None

            # Select first healthy instance (TODO: implement load balancing)
            instance = instances[0]
            return {
                "ip": instance.ip,
                "port": instance.port,
                "healthy": instance.healthy,
            }

        except Exception as e:
            logging.error(f"Nacos discovery failed: {e}")
            return None


async def main():
    """Run mid-layer service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Nacos configuration
    nacos_config = NacosConfig(
        server="39.106.255.3:8848",
        namespace="f45fa327-df31-4547-85a3-7d3dabf7fb19",
        username="nacos",
        password="nacos",
    )

    # Create and start mid-layer
    # For local Docker NanoBot, use override address:
    # nanobot_override_addr="127.0.0.1:18790"
    midlayer = MidLayer(
        nacos_config=nacos_config,
        listen_host="0.0.0.0",
        listen_port=18800,
        service_name="nanobot-gateway",
        group="DEFAULT_GROUP",
        nanobot_override_addr="127.0.0.1:18790",  # NanoBot Docker port mapped to localhost
    )

    await midlayer.start()

    # Keep running
    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        logging.info("\nShutting down...")
        await midlayer.stop()


if __name__ == "__main__":
    asyncio.run(main())
