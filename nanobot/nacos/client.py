"""Nacos service registry client using nacos-sdk-python v2."""

import asyncio
from typing import Any

from loguru import logger

from nanobot.config.schema import NacosConfig


class NacosClient:
    """Nacos service registry client for nanobot using official SDK.

    Uses persistent instances (ephemeral=False) with manual refresh
    for reliable service registration.
    """

    def __init__(self, config: NacosConfig, port: int = 18790):
        """Initialize Nacos client.

        Args:
            config: Nacos configuration
            port: Service port for registration
        """
        self.config = config
        self.port = port
        self._naming_service = None
        self._running = False
        self._refresh_task = None

        # Import here to avoid import errors when Nacos is disabled
        try:
            from v2.nacos.common.client_config_builder import ClientConfigBuilder
            from v2.nacos.naming.nacos_naming_service import NacosNamingService
            from v2.nacos.naming.model.naming_param import RegisterInstanceParam
            self._sdk_available = True
        except ImportError:
            self._sdk_available = False
            logger.warning("nacos-sdk-python not installed, Nacos disabled")

    def _get_local_ip(self) -> str:
        """Get local IP address for service registration."""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def start(self) -> None:
        """Start Nacos client and register service."""
        if not self.config.enabled:
            logger.info("Nacos service registry disabled")
            return

        if not self._sdk_available:
            logger.error("nacos-sdk-python not installed, cannot start Nacos client")
            return

        try:
            from v2.nacos.common.client_config_builder import ClientConfigBuilder
            from v2.nacos.naming.nacos_naming_service import NacosNamingService

            # Build client config
            client_config = (ClientConfigBuilder()
                           .server_address(self.config.server_addr)
                           .namespace_id(self.config.namespace)
                           .username(self.config.username or None)
                           .password(self.config.password or None)
                           .build())

            # Create naming service
            self._naming_service = await NacosNamingService.create_naming_service(client_config)
            logger.info(f"Nacos connected to {self.config.server_addr}")

            # Register service immediately
            await self._register()

            # Start refresh loop
            self._running = True
            self._refresh_task = asyncio.create_task(self._refresh_loop())

            logger.info(
                f"Nacos service registered: {self.config.service_name} "
                f"at {self._get_local_ip()}:{self.port}"
            )

        except Exception as e:
            logger.error(f"Nacos service registration failed: {e}")
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop Nacos client and deregister service."""
        if not self._running:
            return

        self._running = False

        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        if self._naming_service:
            try:
                from v2.nacos.naming.model.naming_param import DeregisterInstanceParam

                deregister_param = DeregisterInstanceParam(
                    service_name=self.config.service_name,
                    ip=self._get_local_ip(),
                    port=self.port,
                    group_name=self.config.group,
                )
                await self._naming_service.deregister_instance(deregister_param)
                logger.info("Nacos service deregistered")
            except Exception as e:
                logger.error(f"Nacos service deregistration failed: {e}")

    async def _register(self, silent: bool = False) -> bool:
        """Register service to Nacos.

        Args:
            silent: If True, don't log success message (for refresh calls)

        Returns:
            True if registration succeeded, False otherwise
        """
        if not self._naming_service:
            return False

        try:
            from v2.nacos.naming.model.naming_param import RegisterInstanceParam

            register_param = RegisterInstanceParam(
                service_name=self.config.service_name,
                ip=self._get_local_ip(),
                port=self.port,
                group_name=self.config.group,
                metadata=self.config.metadata,
                ephemeral=False,  # Use persistent instance for reliability
            )

            success = await self._naming_service.register_instance(register_param)
            if success:
                if not silent:
                    logger.info(f"Nacos service registered: {self.config.service_name}")
                return True
            else:
                logger.error("Nacos service registration failed")
                return False

        except Exception as e:
            logger.error(f"Nacos registration error: {e}")
            return False

    async def _refresh_loop(self) -> None:
        """Periodically refresh registration to prevent cleanup."""
        while self._running:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                if self._running:
                    await self._register(silent=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Nacos refresh failed: {e}")

    async def get_service(self, service_name: str, group: str | None = None) -> list[dict[str, Any]]:
        """Get service instances from Nacos.

        Args:
            service_name: Service name to query
            group: Service group (defaults to config group)

        Returns:
            List of healthy service instances
        """
        if not self._naming_service:
            return []

        try:
            from v2.nacos.naming.model.naming_param import ListInstanceParam

            list_param = ListInstanceParam(
                service_name=service_name,
                group_name=group or self.config.group,
                subscribe=False,
                healthy_only=False,
            )

            result = await self._naming_service.list_instances(list_param)

            # Handle different return types
            if isinstance(result, list):
                return [{"ip": inst.ip, "port": inst.port, "healthy": inst.healthy}
                        for inst in result]
            elif hasattr(result, 'hosts'):
                return [{"ip": inst.ip, "port": inst.port, "healthy": inst.healthy}
                        for inst in result.hosts]
            else:
                return []

        except Exception as e:
            logger.error(f"Nacos service discovery failed: {e}")
            return []
