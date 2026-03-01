"""Remote execution tool for calling microservices via Nacos."""

from typing import Any

import httpx
from loguru import logger

from nanobot.agent.tools.base import Tool

# Try to import Nacos SDK
try:
    from v2.nacos.common.client_config_builder import ClientConfigBuilder
    from v2.nacos.naming.nacos_naming_service import NacosNamingService
    from v2.nacos.naming.model.naming_param import ListInstanceParam

    NACOS_SDK_AVAILABLE = True
except ImportError:
    NACOS_SDK_AVAILABLE = False
    logger.warning("nacos-sdk-python not available for remote_exec tool")


class RemoteExecTool(Tool):
    """Tool to execute commands on remote microservices discovered via Nacos."""

    def __init__(
        self,
        nacos_server: str = "8.152.198.61:8848",
        namespace: str = "5843c114-2ed2-4956-b7cd-07debfd67554",
        group: str = "DEFAULT_GROUP",
        timeout: int = 30,
        username: str = "nacos",
        password: str = "nacos",
    ):
        self.nacos_server = nacos_server
        self.namespace = namespace
        self.group = group
        self.timeout = timeout
        self.username = username
        self.password = password
        self._http_client: httpx.AsyncClient | None = None
        self._naming_service: NacosNamingService | None = None

    @property
    def name(self) -> str:
        return "remote_exec"

    @property
    def description(self) -> str:
        return (
            "Execute a command on a remote microservice discovered via Nacos. "
            "Use this to call weather, calculator, time and other services. "
            "First use --help to explore available commands, then execute."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "The service name to call (e.g., weather-service, calculator-service, time-service)",
                },
                "command_line": {
                    "type": "string",
                    "description": "The command line to execute on the remote service (e.g., 'check Beijing', 'add 1 2', '--help')",
                },
            },
            "required": ["service_name", "command_line"],
        }

    async def execute(
        self, service_name: str, command_line: str, **kwargs: Any
    ) -> str:
        """Execute command on remote service.

        Args:
            service_name: Service name in Nacos
            command_line: Command to execute

        Returns:
            Command output or error message
        """
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)

        try:
            # 1. Discover service from Nacos
            instance = await self._discover_service(service_name)
            if not instance:
                return f"Error: Service '{service_name}' not found in Nacos"

            ip = instance.get("ip")
            port = instance.get("port")

            # 2. Call remote service
            url = f"http://{ip}:{port}/exec"
            payload = {"command_line": command_line}

            logger.info(f"Calling {service_name} at {ip}:{port}: {command_line}")

            response = await self._http_client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            # 3. Parse response
            result = response.json()
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            exit_code = result.get("exit_code", 0)

            # Format output
            output_parts = []
            if stdout:
                output_parts.append(stdout)
            if stderr:
                output_parts.append(f"[STDERR]\n{stderr}")
            if exit_code != 0:
                output_parts.append(f"[Exit code: {exit_code}]")

            return "\n".join(output_parts) if output_parts else "(no output)"

        except httpx.TimeoutException:
            return f"Error: Timeout calling service '{service_name}'"
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} from service"
        except Exception as e:
            return f"Error executing remote command: {str(e)}"

    async def _discover_service(self, service_name: str) -> dict[str, Any] | None:
        """Discover service instance from Nacos using SDK.

        Args:
            service_name: Service name to discover

        Returns:
            Instance dict with ip and port, or None
        """
        if not NACOS_SDK_AVAILABLE:
            logger.error("Nacos SDK not available")
            return None

        try:
            # Lazy initialize naming service
            if not self._naming_service:
                client_config = (
                    ClientConfigBuilder()
                    .server_address(self.nacos_server)
                    .namespace_id(self.namespace)
                    .username(self.username)
                    .password(self.password)
                    .build()
                )
                self._naming_service = await NacosNamingService.create_naming_service(client_config)
                logger.info(f"Nacos naming service connected to {self.nacos_server}")

            # Query service instances
            list_param = ListInstanceParam(
                service_name=service_name,
                group_name=self.group,
                healthy_only=True,
            )

            hosts = await self._naming_service.list_instances(list_param)

            # hosts is a list of Instance objects
            if not hosts:
                logger.warning(f"No healthy instances for service: {service_name}")
                return None

            # Select first instance
            instance = hosts[0]
            return {
                "ip": instance.ip,
                "port": instance.port,
            }

        except Exception as e:
            logger.error(f"Failed to discover service {service_name}: {e}")
            return None
