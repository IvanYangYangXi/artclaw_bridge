# ArtClaw Bridge — Installation Guide

This guide covers installation for both **human users** and **AI Agents** performing the installation on behalf of users.

---

## Quick Start (Human)

```bash
git clone https://github.com/IvanYangYangXi/artclaw_bridge.git
cd artclaw_bridge

# Interactive menu (Windows):
install.bat

# Or CLI:
python install.py --maya --openclaw
```

---

## AI Agent Installation Guide

If you are an AI Agent helping a user install ArtClaw Bridge, follow these steps exactly.

### Prerequisites Check

1. **Python 3.9+** must be available (`python --version`)
2. **Agent platform** must be installed:
   - OpenClaw: `openclaw --version` (install via `npm install -g openclaw`)
   - LobsterAI: check app is running
3. **Target DCC software** installed on the user's machine

### Step 1: Clone Repository

```bash
git clone https://github.com/IvanYangYangXi/artclaw_bridge.git
cd artclaw_bridge
```

### Step 2: Install DCC Plugins

Run `install.py` with the appropriate flags. **Only include DCCs the user actually has installed.**

```bash
# Single DCC:
python install.py --maya                                      # Maya (default 2023)
python install.py --maya --maya-version 2024                  # Maya 2024
python install.py --max --max-version 2024                    # 3ds Max 2024
python install.py --ue --ue-project "C:\path\to\project"     # Unreal Engine (requires .uproject path)
python install.py --blender --blender-version 5.1             # Blender
python install.py --houdini --houdini-version 20.5            # Houdini
python install.py --sp                                        # Substance Painter
python install.py --sd                                        # Substance Designer
python install.py --comfyui --comfyui-path "C:\ComfyUI"       # ComfyUI (requires install path)

# Multiple DCCs in one command:
python install.py --maya --blender --sp --sd --force

# All DCCs (UE requires --ue-project):
python install.py --all --ue-project "C:\path\to\project" --comfyui-path "C:\ComfyUI" --force
```

**Important notes:**
- `--force` skips overwrite confirmation prompts
- UE installation requires `--ue-project` with the path containing the `.uproject` file
- ComfyUI installation requires `--comfyui-path` pointing to the directory containing `main.py`
- Blender version defaults to 4.2, Houdini to 20.5, Maya to 2023, Max to 2024

### Step 3: Configure Agent Platform

```bash
# For OpenClaw (default):
python install.py --openclaw

# For LobsterAI:
python install.py --openclaw --platform lobster
```

This step:
1. Copies the `mcp-bridge` Gateway plugin to `~/.openclaw/extensions/mcp-bridge/`
2. Installs all official Skills to `~/.openclaw/skills/`
3. Writes `~/.artclaw/config.json` with project root and platform settings
4. Runs `setup_openclaw_config.py` to configure MCP servers in `~/.openclaw/openclaw.json`

### Step 4: Configure MCP Servers

The `setup_openclaw_config.py` script configures which DCC MCP servers the Agent can connect to. **Run it with flags matching the DCCs installed in Step 2:**

```bash
cd platforms/openclaw
python setup_openclaw_config.py --ue --maya --max --blender --houdini --sp --sd --comfyui
```

This adds the following MCP server entries to `~/.openclaw/openclaw.json`:

| DCC | Server Name | Port |
|-----|------------|------|
| Unreal Engine | `ue-editor-agent` | 8080 |
| Maya | `maya-primary` | 8081 |
| 3ds Max | `max-primary` | 8082 |
| Blender | `blender-editor` | 8083 |
| Houdini | `houdini-editor` | 8084 |
| Substance Painter | `sp-editor` | 8085 |
| Substance Designer | `sd-editor` | 8086 |
| ComfyUI | `comfyui-editor` | 8087 |

It also injects wildcard `tools.allow` entries (e.g., `mcp_maya-primary_*`) into all configured agents.

### Step 5: Restart Gateway

```bash
openclaw gateway restart
```

### Step 6: Verify Installation

Run the sync verification to ensure all files are properly deployed:

```bash
python verify_sync.py
```

Expected output: `Summary: XXX/XXX OK`

### Step 7: Verify in DCC

| DCC | How to Verify |
|-----|--------------|
| **UE** | Open project → Edit → Plugins → Enable "UE Claw Bridge" → Restart → Window → UE Claw Bridge → Type `/diagnose` |
| **Maya** | Launch Maya → ArtClaw menu appears in menu bar → Open Chat Panel → Click Connect |
| **3ds Max** | Launch Max → ArtClaw auto-loads → Menu bar → ArtClaw → Chat Panel → Connect |
| **Blender** | Edit → Preferences → Add-ons → Search "ArtClaw" → Enable → Restart → Sidebar (N key) → ArtClaw → Start |
| **Houdini** | Create Shelf Tool with script: `import houdini_shelf; houdini_shelf.toggle_artclaw()` |
| **SP** | Launch SP → Python → Enable artclaw_bridge plugin |
| **SD** | Launch SD → Plugin auto-loads |
| **ComfyUI** | Launch ComfyUI → Check console for "ArtClaw: MCP Server started on port 8087" |

---

## Manual OpenClaw Configuration

If the automatic config script doesn't work, manually edit `~/.openclaw/openclaw.json`:

### 1. Add mcp-bridge plugin

```json
{
  "plugins": {
    "allow": ["mcp-bridge"],
    "entries": {
      "mcp-bridge": {
        "enabled": true,
        "config": {
          "servers": {
            "ue-editor-agent": { "type": "websocket", "url": "ws://127.0.0.1:8080" },
            "maya-primary":    { "type": "websocket", "url": "ws://127.0.0.1:8081" },
            "max-primary":     { "type": "websocket", "url": "ws://127.0.0.1:8082" },
            "blender-editor":  { "type": "websocket", "url": "ws://127.0.0.1:8083" },
            "houdini-editor":  { "type": "websocket", "url": "ws://127.0.0.1:8084" },
            "sp-editor":       { "type": "websocket", "url": "ws://127.0.0.1:8085" },
            "sd-editor":       { "type": "websocket", "url": "ws://127.0.0.1:8086" },
            "comfyui-editor":  { "type": "websocket", "url": "ws://127.0.0.1:8087" }
          }
        }
      }
    }
  }
}
```

Only include servers for DCCs you actually use.

### 2. Add tools.allow to agents

For each agent in `agents.list`, add wildcard entries to `tools.allow`:

```json
{
  "tools": {
    "allow": [
      "mcp_ue-editor-agent_*",
      "mcp_maya-primary_*",
      "mcp_max-primary_*",
      "mcp_blender-editor_*",
      "mcp_houdini-editor_*",
      "mcp_sp-editor_*",
      "mcp_sd-editor_*",
      "mcp_comfyui-editor_*"
    ]
  }
}
```

### 3. Restart Gateway

```bash
openclaw gateway restart
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| MCP tools show as "unknown" | DCC not running or port mismatch. Start the DCC first, then `openclaw gateway restart` |
| "mcp-bridge not loaded" | Check `plugins.allow` includes `"mcp-bridge"` in openclaw.json |
| Skills not found | Run `python install.py --openclaw` to reinstall Skills to `~/.openclaw/skills/` |
| verify_sync shows DIFF | Run `python verify_sync.py --fix` to sync source → destination |
| Port conflict | Check if another process uses the port: `netstat -ano \| findstr :8080` |
| ComfyUI MCP fails to start | Ensure `websockets` and `pydantic` are installed in ComfyUI's Python: `pip install websockets pydantic` |

---

## Project Structure Quick Reference

```
artclaw_bridge/
├── install.bat              # Windows interactive installer
├── install.py               # CLI installer (cross-platform)
├── verify_sync.py           # Shared module sync checker (--fix to repair)
├── core/                    # Shared modules (source of truth)
├── platforms/openclaw/      # OpenClaw adapter + config templates
├── skills/official/         # Official Skill source (installed to ~/.openclaw/skills/)
├── skills/marketplace/      # Marketplace Skills
├── subprojects/
│   ├── UEDAgentProj/Plugins/UEClawBridge/   # UE plugin
│   ├── DCCClawBridge/                        # Maya/Max/Blender/Houdini/SP/SD plugin
│   ├── ComfyUIClawBridge/                    # ComfyUI custom node
│   └── ArtClawToolManager/                   # Web management dashboard
└── docs/                    # Documentation
```
