/**
 * MCP Bridge Plugin for OpenClaw
 *
 * Connects to external MCP servers via WebSocket and registers their tools
 * as OpenClaw agent tools.
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
  constructor(name, url, logger) {
    this.name = name;
    this.url = url;
    this.logger = logger;
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
  }

  async connect() {
    return new Promise((resolve, reject) => {
      try {
        // Use dynamic import for WebSocket (Node.js built-in or ws package)
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
          this.logger.info(`[mcp-bridge] Connected to MCP server "${this.name}" at ${this.url}`);

          try {
            // MCP initialize handshake
            await this.initialize();
            // Discover tools
            await this.discoverTools();
            // Start ping keepalive
            this.startPing();
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
          this.connected = false;
          this.stopPing();
          this.logger.warn(`[mcp-bridge] Disconnected from MCP server "${this.name}"`);
          this.scheduleReconnect();
        };

        this.ws.onerror = (err) => {
          clearTimeout(timeout);
          this.logger.error(`[mcp-bridge] WebSocket error for "${this.name}": ${err.message || err}`);
          if (!this.connected) {
            reject(new Error(`Failed to connect to ${this.url}: ${err.message || err}`));
          }
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  scheduleReconnect() {
    if (this.reconnectTimer) return; // already scheduled
    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), this.maxReconnectDelay);
    this.logger.info(`[mcp-bridge] Reconnecting to "${this.name}" in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      try {
        await this.connect();
        this.logger.info(`[mcp-bridge] Reconnected to "${this.name}" successfully`);
      } catch (err) {
        this.logger.error(`[mcp-bridge] Reconnect failed for "${this.name}": ${err.message}`);
      }
    }, delay);
  }

  startPing() {
    this.stopPing();
    this.pingInterval = setInterval(() => {
      if (this.connected && this.ws) {
        try {
          // Send MCP ping request to keep connection alive
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
        version: "1.0.0",
      },
    });

    this.serverInfo = result.serverInfo || {};
    this.serverCapabilities = result.capabilities || {};
    this.logger.info(
      `[mcp-bridge] Initialized "${this.name}": ${this.serverInfo.name || "unknown"} v${this.serverInfo.version || "?"}`
    );

    // Send initialized notification
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

  // Track registered tool names for cleanup
  const registeredTools = [];

  // Connect to each configured server and register tools
  const initPromise = (async () => {
    for (const [serverName, serverDef] of Object.entries(servers)) {
      if (serverDef.enabled === false) {
        logger.info(`[mcp-bridge] Server "${serverName}" is disabled, skipping`);
        continue;
      }

      if (serverDef.type !== "websocket") {
        logger.warn(`[mcp-bridge] Server "${serverName}" has unsupported type "${serverDef.type}" (only websocket is supported currently)`);
        continue;
      }

      if (!serverDef.url) {
        logger.error(`[mcp-bridge] Server "${serverName}" is missing "url" field`);
        continue;
      }

      const client = new McpWebSocketClient(serverName, serverDef.url, logger);
      clients.set(serverName, client);

      try {
        await client.connect();

        // Register each discovered tool as an OpenClaw agent tool
        for (const tool of client.tools) {
          const openclawToolName = `mcp_${serverName}_${tool.name}`;

          // Convert MCP tool inputSchema to OpenClaw tool parameters
          const parameters = tool.inputSchema || {
            type: "object",
            properties: {},
          };

          api.registerTool({
            name: openclawToolName,
            description: `[MCP:${serverName}] ${tool.description || tool.name}`,
            parameters,
            async execute(_id, params) {
              try {
                const result = await client.callTool(tool.name, params);

                // Format MCP response content
                if (result && result.content) {
                  const textParts = result.content
                    .filter((c) => c.type === "text")
                    .map((c) => c.text);
                  return {
                    content: [
                      {
                        type: "text",
                        text: textParts.join("\n") || JSON.stringify(result),
                      },
                    ],
                  };
                }

                return {
                  content: [
                    {
                      type: "text",
                      text: JSON.stringify(result, null, 2),
                    },
                  ],
                };
              } catch (err) {
                return {
                  content: [
                    {
                      type: "text",
                      text: `Error calling MCP tool "${tool.name}" on server "${serverName}": ${err.message}`,
                    },
                  ],
                  isError: true,
                };
              }
            },
          });

          registeredTools.push(openclawToolName);
          logger.info(`[mcp-bridge] Registered tool: ${openclawToolName}`);
        }
      } catch (err) {
        logger.error(`[mcp-bridge] Failed to connect to server "${serverName}": ${err.message}`);
      }
    }

    if (registeredTools.length > 0) {
      logger.info(`[mcp-bridge] Total tools registered: ${registeredTools.length}`);
    } else {
      logger.warn(`[mcp-bridge] No tools registered. Check server config and connectivity.`);
    }
  })();

  // Return cleanup hook
  return {
    async dispose() {
      for (const [name, client] of clients) {
        logger.info(`[mcp-bridge] Disconnecting from "${name}"`);
        client.disconnect();
      }
      clients.clear();
    },
  };
}