# ArtClaw Bridge — Installation Guide

This guide covers installation for both **human users** and **AI Agents** performing the installation on behalf of users.

> 🤖 **AI Agents**: This is the primary installation reference. Follow the "AI Agent Installation Guide" section below step by step. Key points:
> - Always use `python install.py` (not `install.bat`) — it handles junction/symlink, dependency installation, and platform configuration automatically.
> - After DCC plugin installation, always run `python install.py --openclaw` (or `--platform lobster`) to configure the Agent platform.
> - Gateway token is read dynamically from the platform config file — do not hardcode any token values.
> - See also: [QUICK_INSTALL_REFERENCE.md](QUICK_INSTALL_REFERENCE.md) for common command combinations.

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

### Step 3: Configure Agent Platform (Automated MCP Configuration)

```bash
# For OpenClaw (default):
python install.py --openclaw

# For LobsterAI:
python install.py --openclaw --platform lobster
```

This step automatically:
1. Copies the `mcp-bridge` Gateway plugin to `~/.openclaw/extensions/mcp-bridge/`
2. Installs all official Skills to `~/.openclaw/skills/` (or LobsterAI SKILLs directory)
3. Writes `~/.artclaw/config.json` with project root and platform settings
4. **Automatically configures MCP servers** in the platform's config file:
   - OpenClaw: `~/.openclaw/openclaw.json`
   - LobsterAI: `%APPDATA%\LobsterAI\openclaw\state\openclaw.json`

### Step 4: Verify MCP Server Configuration

The platform configuration script automatically adds MCP server entries for the DCCs you installed:

| DCC | Server Name | Port |
|-----|------------|------|
| Unreal Engine | `artclaw-ue` | 8080 |
| Maya | `artclaw-maya` | 8081 |
| 3ds Max | `artclaw-max` | 8082 |
| Blender | `artclaw-blender` | 8083 |
| Houdini | `artclaw-houdini` | 8084 |
| Substance Painter | `artclaw-sp` | 8085 |
| Substance Designer | `artclaw-sd` | 8086 |
| ComfyUI | `artclaw-comfyui` | 8087 |

**For LobsterAI users:** The configuration is automatically written to `openclaw.json`. You can verify by running:

```bash
# Check current MCP configuration
python platforms\lobster\setup_lobster_config.py --status

# Manually configure if needed
python platforms\lobster\setup_lobster_config.py --ue --maya --max
```

### Step 5: Restart Gateway

```bash
# For OpenClaw:
openclaw gateway restart

# For LobsterAI:
# Fully exit LobsterAI (including system tray), then restart
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

## Manual Configuration (If Automation Fails)

### LobsterAI Manual MCP Configuration

If the automatic configuration doesn't work, manually configure via the script:

```bash
cd platforms\lobster
python setup_lobster_config.py --ue --maya --max
```

Or manually edit `%APPDATA%\LobsterAI\openclaw\state\openclaw.json`:

> **Note:** Replace `<artclaw_bridge_root>` below with the actual path where you cloned the repository.

```json
{
  "plugins": {
    "entries": {
      "mcp-bridge": {
        "enabled": true,
        "config": {
          "servers": {
            "artclaw-ue": {
              "type": "stdio",
              "command": "python",
              "args": ["<artclaw_bridge_root>\\platforms\\common\\artclaw_stdio_bridge.py", "--port", "8080"]
            },
            "artclaw-maya": {
              "type": "stdio",
              "command": "python",
              "args": ["<artclaw_bridge_root>\\platforms\\common\\artclaw_stdio_bridge.py", "--port", "8081"]
            }
          }
        }
      }
    }
  }
}
```

### OpenClaw Manual MCP Configuration

```bash
cd platforms\openclaw
python setup_openclaw_config.py --ue --maya --max
```

Or manually edit `~/.openclaw/openclaw.json` as shown in the OpenClaw section above.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| MCP tools show as "unknown" | DCC not running or port mismatch. Start the DCC first, then restart the Agent |
| "mcp-bridge not loaded" | Check `plugins.allow` includes `"mcp-bridge"` in the platform config |
| Skills not found | Run `python install.py --openclaw --platform <platform>` to reinstall Skills |
| verify_sync shows DIFF | Run `python verify_sync.py --fix` to sync source → destination |
| Port conflict | Check if another process uses the port: `netstat -ano | findstr :8080` |
| ComfyUI MCP fails to start | Ensure `websockets` and `pydantic` are installed in ComfyUI's Python: `pip install websockets pydantic` |
| LobsterAI config not applied | Fully exit LobsterAI (including system tray), then restart. Check config with `setup_lobster_config.py --status` |

---

## Upgrade

When ArtClaw Bridge is updated:

```bash
# 1. Pull latest code
git pull origin main

# 2. Reinstall DCC plugins
python install.py --maya --max --force

# 3. Reconfigure platform
python install.py --openclaw --platform lobster

# 4. Verify sync
python verify_sync.py

# 5. Restart Gateway / LobsterAI
```

---

## Uninstall

### Remove DCC Plugins

```bash
# Single DCC
python install.py --uninstall --maya

# Multiple DCCs
python install.py --uninstall --maya --max

# All DCCs
python install.py --uninstall --all
```

### Remove MCP Configuration

```bash
# LobsterAI
python platforms\lobster\setup_lobster_config.py --remove

# OpenClaw
python platforms\openclaw\setup_openclaw_config.py --remove
```

### Full Uninstall

```bash
# 1. Uninstall all DCC plugins
python install.py --uninstall --all

# 2. Remove MCP configuration
python platforms\lobster\setup_lobster_config.py --remove

# 3. Delete global config directory (optional)
rmdir /s %USERPROFILE%\.artclaw
```

---

## Project Structure Quick Reference

```
artclaw_bridge/
├── install.bat                    # Windows interactive installer
├── install.py                     # CLI installer (cross-platform)
├── post_install_configure.py      # Post-install MCP configuration
├── verify_sync.py                 # Shared module sync checker (--fix to repair)
├── core/                          # Shared modules (source of truth)
├── platforms/
│   ├── openclaw/
│   │   ├── setup_openclaw_config.py   # OpenClaw MCP configuration
│   │   └── gateway/
│   ├── lobster/
│   │   ├── setup_lobster_config.py    # LobsterAI MCP configuration (AUTO)
│   │   └── lobster_adapter.py
│   ├── claudecode/
│   │   └── setup_claudecode_config.py # Claude Code MCP configuration
│   ├── cursor/
│   │   └── setup_cursor_config.py     # Cursor MCP configuration
│   ├── workbuddy/
│   │   └── workbuddy_adapter.py
│   └── common/
│       └── artclaw_stdio_bridge.py    # Universal stdio bridge for all DCCs
├── skills/official/               # Official Skills (installed to platform dirs)
├── skills/marketplace/            # Marketplace Skills
├── subprojects/
│   ├── UEDAgentProj/Plugins/UEClawBridge/   # UE plugin
│   ├── DCCClawBridge/                        # Maya/Max/Blender/Houdini/SP/SD plugin
│   ├── ComfyUIClawBridge/                    # ComfyUI custom node
│   └── ArtClawToolManager/                   # Web management dashboard
└── docs/                          # Documentation
```

---

## Automation Summary

The installation process is now **fully automated** for MCP configuration:

1. **DCC Plugin Installation** → `install.py` links (junction/symlink) plugin files to DCC directories (fallback to copy; use `--copy` to force copy mode)
2. **Platform Configuration** → `install.py --openclaw` installs Skills and runs MCP config script
3. **MCP Server Registration** → Platform-specific scripts (`setup_*_config.py`) automatically add stdio server entries
4. **No Manual Editing Required** → All configuration is handled by scripts

**Supported Platforms:**
- ✅ OpenClaw (via `setup_openclaw_config.py`)
- ✅ LobsterAI (via `setup_lobster_config.py`)
- ✅ Claude Code (via `setup_claudecode_config.py`)
- ✅ Cursor (via `setup_cursor_config.py`)
- ✅ WorkBuddy (via `setup_workbuddy_config.py`)
