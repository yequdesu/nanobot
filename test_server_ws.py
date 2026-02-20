"""Test WebSocket connection to nanobot server."""

import asyncio
import json
import socket
import sys

import websockets


async def test_tcp_connection(host: str, port: int) -> bool:
    """Test basic TCP connectivity."""
    print(f"Testing TCP connection to {host}:{port}...")
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5
        )
        writer.close()
        await writer.wait_closed()
        print(f"✅ TCP connection successful")
        return True
    except Exception as e:
        print(f"❌ TCP connection failed: {e}")
        return False


async def test_connection():
    """Test WebSocket connection to nanobot server."""
    host = "47.254.33.250"
    port = 18790
    uri = f"ws://{host}:{port}"

    print(f"Testing connection to nanobot server")
    print(f"Server: {host}:{port}")
    print("=" * 50)

    # Step 1: Test TCP connectivity
    if not await test_tcp_connection(host, port):
        print("\n⚠️  Cannot establish TCP connection.")
        print("   Possible causes:")
        print("   - Server is not running")
        print("   - Firewall is blocking port 18790")
        print("   - Docker container is not started")
        return False

    print()

    # Step 2: Test WebSocket connection
    print(f"Testing WebSocket connection...")
    print(f"URI: {uri}")
    print(f"Subprotocol: OneBot.v11")
    print("-" * 50)

    try:
        async with websockets.connect(
            uri,
            subprotocols=["OneBot.v11"],
            open_timeout=10,
        ) as ws:
            print(f"✅ WebSocket connected successfully!")
            print(f"   Local: {ws.local_address}")
            print(f"   Remote: {ws.remote_address}")
            print(f"   Subprotocol: {ws.subprotocol}")
            print("-" * 50)

            # Send OneBot lifecycle connect event
            lifecycle = {
                "post_type": "meta_event",
                "meta_event_type": "lifecycle",
                "time": 1700000000,
                "self_id": 123456,
                "sub_type": "connect",
            }

            print(f"📤 Sending lifecycle connect event...")
            await ws.send(json.dumps(lifecycle))
            print(f"✅ Sent")

            # Send heartbeat
            heartbeat = {
                "post_type": "meta_event",
                "meta_event_type": "heartbeat",
                "time": 1700000000,
                "self_id": 123456,
                "status": {"online": True, "good": True},
                "interval": 5000,
            }

            print(f"📤 Sending heartbeat...")
            await ws.send(json.dumps(heartbeat))
            print(f"✅ Sent")

            # Wait a bit
            await asyncio.sleep(2)

            print("-" * 50)
            print("✅ All tests passed!")
            return True

    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ Connection closed: code={e.code}, reason={e.reason}")
        if e.code == 1008:
            print("   Authentication failed - check access token")
        return False
    except websockets.exceptions.InvalidStatus as e:
        print(f"❌ HTTP error: {e.status_code}")
        return False
    except asyncio.TimeoutError:
        print(f"❌ Connection timeout")
        return False
    except socket.gaierror as e:
        print(f"❌ DNS resolution failed: {e}")
        return False
    except ConnectionRefusedError:
        print(f"❌ Connection refused - server not accepting connections")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_connection())
    sys.exit(0 if result else 1)
