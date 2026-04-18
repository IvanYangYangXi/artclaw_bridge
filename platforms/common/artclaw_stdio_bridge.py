#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw stdio→WebSocket MCP Bridge
====================================

Bridges stdio MCP transport (used by Cursor, Claude Code, WorkBuddy, etc.)
to ArtClaw's WebSocket MCP Server running inside the DCC application.

Architecture:
    [MCP Client (stdio)] <--stdin/stdout--> [this bridge] <--WebSocket--> [DCC MCP Server]

Two independent paths run concurrently:
    stdin  → WebSocket  (forward client requests to server)
    WebSocket → stdout  (forward server responses/notifications to client)

Uses a background thread for stdin reading to work correctly on Windows,
where asyncio.connect_read_pipe() does not support pipe handles from
subprocess stdin.

Usage:
    python artclaw_stdio_bridge.py                       # default ws://127.0.0.1:8080 (UE)
    python artclaw_stdio_bridge.py --port 8081           # Maya
    python artclaw_stdio_bridge.py --port 8082           # Max
    python artclaw_stdio_bridge.py --url ws://host:port  # custom URL

MCP config example (Cursor ~/.cursor/mcp.json):
    {
      "mcpServers": {
        "artclaw-ue": {
          "command": "python",
          "args": ["/path/to/artclaw_stdio_bridge.py", "--port", "8080"]
        }
      }
    }
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import logging
import threading
import queue

# ---------------------------------------------------------------------------
# Logging → stderr (stdout is reserved for MCP JSON-RPC)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("artclaw-stdio-bridge")


# ---------------------------------------------------------------------------
# WebSocket connection with retry
# ---------------------------------------------------------------------------

async def connect_ws(url: str, max_retries: int = 10, retry_delay: float = 2.0):
    """Connect to the DCC WebSocket MCP Server with retries."""
    try:
        import websockets
    except ImportError:
        log.error("Missing dependency: pip install websockets")
        sys.exit(1)

    for attempt in range(1, max_retries + 1):
        try:
            ws = await websockets.connect(url, max_size=64 * 1024 * 1024)
            log.info("Connected to MCP Server: %s", url)
            return ws
        except Exception as e:
            if attempt < max_retries:
                log.warning(
                    "Connection failed (%d/%d): %s — retrying in %ss",
                    attempt, max_retries, e, retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                log.error("Connection failed after %d attempts: %s", max_retries, e)
                raise


# ---------------------------------------------------------------------------
# Thread-based stdin reader (Windows compatible)
# ---------------------------------------------------------------------------

def _stdin_reader_thread(stdin_queue: queue.Queue, stop_event: threading.Event):
    """Read lines from stdin in a background thread.
    
    asyncio.connect_read_pipe() doesn't work on Windows for subprocess pipes
    (WinError 6: invalid handle with IOCP). Using a thread avoids this entirely.
    """
    try:
        for line in sys.stdin:
            if stop_event.is_set():
                break
            stripped = line.strip()
            if stripped:
                stdin_queue.put(stripped)
    except (EOFError, ValueError, OSError):
        pass
    finally:
        stdin_queue.put(None)  # Sentinel: stdin closed


# ---------------------------------------------------------------------------
# Forward: stdin queue → WebSocket
# ---------------------------------------------------------------------------

async def stdin_to_ws(stdin_queue: queue.Queue, ws, shutdown: asyncio.Event):
    """Read from the thread-safe stdin queue and forward to WebSocket."""
    loop = asyncio.get_event_loop()
    try:
        while not shutdown.is_set():
            # Non-blocking poll from thread queue
            try:
                line = await asyncio.wait_for(
                    loop.run_in_executor(None, stdin_queue.get, True, 1.0),
                    timeout=2.0,
                )
            except (asyncio.TimeoutError, queue.Empty):
                continue

            if line is None:
                log.info("stdin closed, initiating shutdown")
                shutdown.set()
                return

            # Validate JSON
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                log.warning("Invalid JSON from stdin, skipping: %s", e)
                continue

            log.debug("-> WS: %s", line[:200])

            try:
                await ws.send(line)
            except Exception as e:
                log.error("WebSocket send failed: %s", e)
                shutdown.set()
                return
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error("stdin_to_ws error: %s", e)
        shutdown.set()


# ---------------------------------------------------------------------------
# Forward: WebSocket → stdout
# ---------------------------------------------------------------------------

def write_stdout(data: str):
    """Write a JSON-RPC message to stdout (newline-delimited)."""
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


async def ws_to_stdout(ws, shutdown: asyncio.Event):
    """Read messages from WebSocket and write to stdout."""
    try:
        async for message in ws:
            if shutdown.is_set():
                return
            text = message if isinstance(message, str) else message.decode("utf-8")
            log.debug("<- WS: %s", text[:200])
            write_stdout(text)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        if not shutdown.is_set():
            log.error("ws_to_stdout error: %s", e)
        shutdown.set()


# ---------------------------------------------------------------------------
# Main bridge loop
# ---------------------------------------------------------------------------

async def bridge_loop(ws_url: str):
    """
    1. Connect to DCC WebSocket MCP Server
    2. Start a background thread for stdin reading
    3. Run two async forwarding tasks concurrently
    4. Shut down cleanly when either side disconnects
    """
    ws = await connect_ws(ws_url)

    # Thread-safe queue for stdin lines
    stdin_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    # Start stdin reader thread
    reader_thread = threading.Thread(
        target=_stdin_reader_thread,
        args=(stdin_queue, stop_event),
        daemon=True,
    )
    reader_thread.start()

    shutdown = asyncio.Event()

    # Run both directions concurrently
    tasks = [
        asyncio.create_task(stdin_to_ws(stdin_queue, ws, shutdown)),
        asyncio.create_task(ws_to_stdout(ws, shutdown)),
    ]

    # Wait for shutdown signal
    await shutdown.wait()

    # Stop stdin reader thread
    stop_event.set()

    # Cancel remaining tasks
    for t in tasks:
        if not t.done():
            t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    # Close WebSocket
    try:
        await ws.close()
    except Exception:
        pass

    log.info("Bridge shut down")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

DCC_PORTS = {
    "ue": 8080,
    "maya": 8081,
    "max": 8082,
    "blender": 8083,
    "houdini": 8084,
    "sp": 8085,
    "sd": 8086,
    "comfyui": 8087,
}


def main():
    parser = argparse.ArgumentParser(
        description="ArtClaw stdio->WebSocket MCP Bridge",
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help=f"DCC MCP Server port (default: 8080). Ports: {DCC_PORTS}",
    )
    parser.add_argument(
        "--url", type=str, default="",
        help="Custom WebSocket URL (overrides --port)",
    )
    args = parser.parse_args()

    ws_url = args.url or f"ws://127.0.0.1:{args.port}"
    log.info("ArtClaw stdio Bridge starting — target: %s", ws_url)

    try:
        asyncio.run(bridge_loop(ws_url))
    except KeyboardInterrupt:
        log.info("Interrupted")
    except Exception as e:
        log.error("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
