/**
 * MCP Bridge Plugin for OpenClaw
 *
 * Connects to external MCP servers via WebSocket and registers their tools
 * as OpenClaw agent tools. Supports late discovery: if a DCC (e.g. UE) starts
 * after the Gateway, tools are discovered and registered on reconnect.
 *
 * Config example (in openclaw.json → plugins.entries.mcp-bridge.config):
 * {
 *   "servers": {
 *     "my-server": {
 *       "type": "websocket",
 *       "url": "ws://127.0.0.1:8080"
 *     }
 *   }
 * }
 */

// --- MCP JSON-RPC helpers ---

let nextRequestId = 1;

function createJsonRpcRequest(method, params) {
  return JSON.stringify({
    jsonrpc: "2.0",
    id: nextRequestId++,
    method,
    params: params || {},
  });
}

function parseJsonRpcResponse(data) {
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

// --- WebSocket MCP Client ---

class McpWebSocketClient {
  constructor(name, url, logger, onToolsDiscovered) {
    this.name = name;
    this.url = url;
    this.logger = logger;
    this.onToolsDiscovered = onToolsDiscovered; // callback(tools[]) — called on every (re)connect
    this.ws = null;
    this.tools = [];
    this.pendingRequests = new Map();
    this.connected = false;
    this.reconnectTimer = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = Infinity;
    this.reconnectDelay = 3000;
    this.maxReconnectDelay = 30000;
    this.pingInterval = null;
    this.pingIntervalMs = 15000; // ping every 15s to keep alive
    this._disposed = false;

    // Health stats
    this.stats = {
      totalReconnects: 0,
      lastConnectedAt: null,
      lastDisconnectedAt: null,
      toolCallCount: 0,
      toolErrorCount: 0,
    };
  }

  async connect() {
    if (this._disposed) return;

    return new Promise((resolve, reject) => {
      try {
        const WebSocket = globalThis.WebSocket || require("ws");
        this.ws = new WebSocket(this.url);

        const timeout = setTimeout(() => {
          reject(new Error(`Connection to ${this.url} timed out`));
          this.ws?.close();
        }, 10000);

        this.ws.onopen = async () => {
          clearTimeout(timeout);
          this.connected = true;
          this.reconnectAttempts = 0;
          this.stats.lastConnectedAt = new Date().toISOString();
          this.logger.info(`[mcp-bridge] Connected to MCP server "${this.name}" at ${this.url}`);

          try {
            await this.initialize();
            await this.discoverTools();
            this.startPing();

            // Notify plugin to register/re-register tools
            if (this.onToolsDiscovered && this.tools.length > 0) {
              this.onToolsDiscovered(this.tools);
            }

            resolve();
          } catch (err) {
            reject(err);
          }
        };

        this.ws.onmessage = (event) => {
          const data = typeof event.data === "string" ? event.data : event.data.toString();
          const response = parseJsonRpcResponse(data);
          if (response && response.id && this.pendingRequests.has(response.id)) {
            const { resolve, reject } = this.pendingRequests.get(response.id);
            this.pendingRequests.delete(response.id);
            if (response.error) {
              reject(new Error(`MCP error: ${response.error.message || JSON.stringify(response.error)}`));
            } else {
              resolve(response.result);
            }
          }
        };

        this.ws.onclose = () => {
          const wasConnected = this.connected;
          this.connected = false;
          this.stopPing();
          if (wasConnected) {
            this.stats.lastDisconnectedAt = new Date().toISOString();
            this.stats.totalReconnects++;
            this.logger.warn(`[mcp-bridge] Disconnected from MCP server "${this.name}" (reconnects: ${this.stats.totalReconnects})`);
          }
          this.scheduleReconnect();
        };

        this.ws.onerror = (err) => {
          clearTimeout(timeout);
          if (!this.connected) {
            reject(new Error(`Failed to connect to ${this.url}: ${err.message || err}`));
          } else {
            this.logger.error(`[mcp-bridge] WebSocket error for "${this.name}": ${err.message || err}`);
          }
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  scheduleReconnect() {
    if (this._disposed || this.reconnectTimer) return;
    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), this.maxReconnectDelay);
    this.logger.info(`[mcp-bridge] Reconnecting to "${this.name}" in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      if (this._disposed) return;
      try {
        await this.connect();
        this.logger.info(`[mcp-bridge] Reconnected to "${this.name}" successfully`);
      } catch (err) {
        this.logger.error(`[mcp-bridge] Reconnect failed for "${this.name}": ${err.message}`);
        // scheduleReconnect is called again from onclose
      }
    }, delay);
  }

  startPing() {
    this.stopPing();
    this.pingInterval = setInterval(() => {
      if (this.connected && this.ws) {
        try {
          this.ws.send(JSON.stringify({
            jsonrpc: "2.0",
            id: nextRequestId++,
            method: "ping",
          }));
        } catch (err) {
          this.logger.warn(`[mcp-bridge] Ping failed for "${this.name}": ${err.message}`);
        }
      }
    }, this.pingIntervalMs);
  }

  stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  async sendRequest(method, params) {
    if (!this.connected || !this.ws) {
      throw new Error(`Not connected to MCP server "${this.name}"`);
    }

    return new Promise((resolve, reject) => {
      const id = nextRequestId;
      const msg = createJsonRpcRequest(method, params);

      const timeout = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Request ${method} to "${this.name}" timed out`));
      }, 30000);

      this.pendingRequests.set(id, {
        resolve: (result) => {
          clearTimeout(timeout);
          resolve(result);
        },
        reject: (err) => {
          clearTimeout(timeout);
          reject(err);
        },
      });

      this.ws.send(msg);
    });
  }

  async initialize() {
    const result = await this.sendRequest("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: {
        name: "openclaw-mcp-bridge",
        version: "1.1.0",
      },
    });

    this.serverInfo = result.serverInfo || {};
    this.serverCapabilities = result.capabilities || {};
    this.logger.info(
      `[mcp-bridge] Initialized "${this.name}": ${this.serverInfo.name || "unknown"} v${this.serverInfo.version || "?"}`
    );

    if (this.ws && this.connected) {
      this.ws.send(
        JSON.stringify({
          jsonrpc: "2.0",
          method: "notifications/initialized",
        })
      );
    }
  }

  async discoverTools() {
    if (!this.serverCapabilities.tools) {
      this.logger.info(`[mcp-bridge] Server "${this.name}" does not advertise tools capability`);
      this.tools = [];
      return;
    }

    const result = await this.sendRequest("tools/list", {});
    this.tools = result.tools || [];
    this.logger.info(`[mcp-bridge] Discovered ${this.tools.length} tools from "${this.name}"`);
  }

  async callTool(toolName, args) {
    return this.sendRequest("tools/call", {
      name: toolName,
      arguments: args || {},
    });
  }

  disconnect() {
    this._disposed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopPing();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
    this.pendingRequests.clear();
  }
}

// --- Plugin Entry ---

/** @param {import('openclaw/plugin-sdk/core').PluginAPI} api */
export default function (api) {
  const logger = api.log || console;
  const clients = new Map();

  // Read config
  const pluginConfig = api.config?.plugins?.entries?.["mcp-bridge"]?.config || {};
  const servers = pluginConfig.servers || {};

  // Track registered tool names (Set for dedup)
  const registeredToolNames = new Set();

  /**
   * Register (or re-register) tools from a specific MCP server.
   * Called on initial connect and every reconnect, so late-starting
   * DCC apps get their tools picked up without restarting the Gateway.
   */
  function registerToolsForServer(serverName, client, tools) {
    let newCount = 0;
    for (const tool of tools) {
      const openclawToolName = `mcp_${serverName}_${tool.name}`;

      if (registeredToolNames.has(openclawToolName)) {
        // Tool already registered from a previous connect — skip.
        // The execute handler already references the client instance,
        // which reconnects transparently.
        continue;
      }

      const parameters = tool.inputSchema || {
        type: "object",
        properties: {},
      };

      api.registerTool({
        name: openclawToolName,
        description: `[MCP:${serverName}] ${tool.description || tool.name}`,
        parameters,
        async execute(_id, params) {
          if (!client.connected) {
            client.stats.toolErrorCount++;
            return {
              content: [{ type: "text", text: `MCP server "${serverName}" is not connected. The DCC application may not be running.` }],
              isError: true,
            };
          }
          try {
            client.stats.toolCallCount++;
            const result = await client.callTool(tool.name, params);
            if (result && result.content) {
              const textParts = result.content
                .filter((c) => c.type === "text")
                .map((c) => c.text);
              return {
                content: [{ type: "text", text: textParts.join("\n") || JSON.stringify(result) }],
              };
            }
            return {
              content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
            };
          } catch (err) {
            client.stats.toolErrorCount++;
            return {
              content: [{ type: "text", text: `Error calling MCP tool "${tool.name}" on server "${serverName}": ${err.message}` }],
              isError: true,
            };
          }
        },
      });

      registeredToolNames.add(openclawToolName);
      newCount++;
    }

    if (newCount > 0) {
      logger.info(`[mcp-bridge] Registered ${newCount} new tool(s) from "${serverName}" (total: ${registeredToolNames.size})`);
    }
  }

  // Connect to each configured server
  const initPromise = (async () => {
    for (const [serverName, serverDef] of Object.entries(servers)) {
      if (serverDef.enabled === false) {
        logger.info(`[mcp-bridge] Server "${serverName}" is disabled, skipping`);
        continue;
      }

      if (serverDef.type !== "websocket") {
        logger.warn(`[mcp-bridge] Server "${serverName}" has unsupported type "${serverDef.type}" (only websocket supported)`);
        continue;
      }

      if (!serverDef.url) {
        logger.error(`[mcp-bridge] Server "${serverName}" is missing "url" field`);
        continue;
      }

      const client = new McpWebSocketClient(
        serverName,
        serverDef.url,
        logger,
        // onToolsDiscovered callback — fires on every (re)connect
        (tools) => registerToolsForServer(serverName, client, tools),
      );
      clients.set(serverName, client);

      try {
        await client.connect();
        // Tools are registered via the onToolsDiscovered callback
      } catch (err) {
        logger.warn(`[mcp-bridge] Initial connection to "${serverName}" failed: ${err.message}. Will retry in background.`);
        // scheduleReconnect is already triggered by onclose — tools will be
        // registered when the DCC app eventually starts and the connection succeeds.
      }
    }

    if (registeredToolNames.size > 0) {
      logger.info(`[mcp-bridge] Total tools registered: ${registeredToolNames.size}`);
    } else {
      logger.warn(`[mcp-bridge] No tools registered yet. Tools will be registered when MCP servers come online.`);
    }
  })();

  // Cleanup hook
  return {
    async dispose() {
      for (const [name, client] of clients) {
        const s = client.stats;
        logger.info(
          `[mcp-bridge] Disconnecting from "${name}" ` +
          `(calls: ${s.toolCallCount}, errors: ${s.toolErrorCount}, reconnects: ${s.totalReconnects})`
        );
        client.disconnect();
      }
      clients.clear();
    },
  };
}
