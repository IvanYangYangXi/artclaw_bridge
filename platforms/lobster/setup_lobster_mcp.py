#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LobsterAI MCP Configuration Guide
=================================
Detects Python environment and generates step-by-step manual MCP config instructions
for the LobsterAI client UI.

Custom stdio MCP configs are stored in the LobsterAI client's local database and
cannot be injected via openclaw.json. This script detects the best Python interpreter
(with websockets), then prints the exact values to fill into the LobsterAI MCP UI.

Usage:
    python setup_lobster_mcp.py                    # detect env + print guide
    python setup_lobster_mcp.py --guide-only       # print guide only (skip checks)
    python setup_lobster_mcp.py --verify           # test WebSocket connection
"""

import argparse
import glob
import os
import socket
import subprocess
import sys
from pathlib import Path


# ---- Port mapping ----
MCP_PORTS = {
    'ue': 8080,
    'maya': 8081,
    'max': 8082,
    'blender': 8083,
}

DCC_NAMES = {
    'ue': 'Unreal Editor',
    'maya': 'Maya',
    'max': '3ds Max',
    'blender': 'Blender',
}


# ---- Helpers ----

def find_bridge_dir() -> str:
    """Locate artclaw_bridge root from this script's location."""
    return str(Path(__file__).resolve().parent.parent.parent)


def _check_ws(py: str) -> bool:
    """Check if a python interpreter has websockets installed."""
    try:
        result = subprocess.run(
            [py, '-c', 'import websockets'],
            capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def find_python() -> tuple[str, str]:
    """Find Python interpreter with websockets. Returns (path, source_label)."""
    if _check_ws(sys.executable):
        return sys.executable, "current Python"

    if _check_ws('python'):
        return 'python', "system PATH"

    # Search common install locations
    candidates = []
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    prog_files = os.environ.get('ProgramFiles', r'C:\Program Files')

    if local_appdata:
        candidates.extend(sorted(
            glob.glob(os.path.join(local_appdata, 'Programs', 'Python', 'Python*', 'python.exe')),
            reverse=True
        ))
    candidates.extend(sorted(
        glob.glob(os.path.join(prog_files, 'Python*', 'python.exe')), reverse=True
    ))
    candidates.extend(sorted(glob.glob(r'C:\Python*\python.exe'), reverse=True))

    for py in candidates:
        if _check_ws(py):
            return py, "auto-detected"

    return 'python', "NOT FOUND (install websockets manually)"


def check_port(port: int) -> bool:
    """Check if localhost:port is listening."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0
    except Exception:
        return False
    finally:
        s.close()


def run_test(python_path: str, port: int) -> tuple[bool, str]:
    """Run test_ue_ws.py to verify connection."""
    test_script = Path(find_bridge_dir()) / 'tests' / 'test_ue_ws.py'
    if not test_script.exists():
        return False, "Test script not found"
    try:
        result = subprocess.run(
            [python_path, str(test_script), '--port', str(port)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and '[OK] Success!' in result.stdout:
            return True, result.stdout
        return False, result.stderr or result.stdout
    except subprocess.TimeoutExpired:
        return False, "Connection timed out"
    except Exception as e:
        return False, str(e)


# ---- Output ----

def sep(title: str = ""):
    print()
    print("=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def print_guide(python_path: str, python_source: str, bridge_dir: str):
    sep("ArtClaw MCP -> LobsterAI Configuration Guide")

    # Environment summary
    ws_ok = _check_ws(python_path)
    bridge_path = os.path.join(bridge_dir, 'platforms', 'common', 'artclaw_stdio_bridge.py')
    bridge_ok = Path(bridge_path).exists()

    print()
    print("  [Environment Check]")
    print("  " + "-" * 56)
    print(f"  Python path        {python_path}")
    print(f"  Source             {python_source}")
    print(f"  websockets         {'[OK] installed' if ws_ok else '[X] MISSING!'}")
    print(f"  Bridge script      {'[OK]' if bridge_ok else '[X] MISSING!'}")
    if not ws_ok:
        print(f"\n  >> Install websockets first:")
        print(f"     {python_path} -m pip install websockets")

    # Manual config steps
    sep("Manual Configuration (LobsterAI Client UI)")

    for dcc in ['ue', 'maya', 'max']:
        port = MCP_PORTS[dcc]
        name = DCC_NAMES[dcc]
        label = "listening" if check_port(port) else "DCC not running"

        print(f"""
  --- {name} ---

  In LobsterAI client:
    1. Open Settings -> MCP Services
    2. Click "Add MCP Service"
    3. Fill in:

       Service Name    artclaw-{dcc}
       Description     ArtClaw {name} MCP Bridge
       Transport       Standard I/O (stdio)
       Command         {python_path}
       Arguments       {bridge_path} --port {port}

       Status          {label}
""")

    # Verification
    sep("Verification")
    test_script = os.path.join(bridge_dir, 'tests', 'test_ue_ws.py')
    print(f"""
  After saving the config:

  1. Make sure the DCC app (UE/Maya/Max) is running
  2. In LobsterAI chat, try:
     "Get the selected objects in UE"
     (AI should call run_ue_python and return the selection)

  3. Or run the test script manually:
     {python_path} {test_script} --port 8080
""")


# ---- Main ----

def main():
    parser = argparse.ArgumentParser(
        description='LobsterAI MCP Configuration Guide',
    )
    parser.add_argument('--guide-only', action='store_true',
                        help='Only print the manual config guide')
    parser.add_argument('--verify', action='store_true',
                        help='Run WebSocket connection test')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port for verify (default: 8080)')
    args = parser.parse_args()

    bridge_dir = find_bridge_dir()
    python_path, python_source = find_python()

    if args.verify:
        print(f"Testing ws://127.0.0.1:{args.port} ...")
        ok, output = run_test(python_path, args.port)
        print(output)
        sys.exit(0 if ok else 1)

    print_guide(python_path, python_source, bridge_dir)


if __name__ == '__main__':
    main()
