#!/usr/bin/env node

/**
 * OkoCRM MCP Stdio-to-HTTP Bridge for Antigravity
 */

const readline = require('readline');

const URL = process.env.OKOCRM_MCP_URL || 'https://mcp.okocrm.com/crm';
const TOKEN = process.env.OKOCRM_TOKEN || 'OKOCRM_TOKEN_PLACEHOLDER';

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

rl.on('line', async (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;

  let request;
  try {
    request = JSON.parse(trimmed);
  } catch (err) {
    console.error('Invalid JSON received:', trimmed);
    return;
  }

  // Handle notifications (no id) - do not wait for response or return error
  const isNotification = request.id === undefined || request.id === null;

  try {
    const res = await fetch(URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${TOKEN}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request)
    });

    if (!res.ok) {
      if (!isNotification) {
        const errorText = await res.text();
        const errResp = {
          jsonrpc: '2.0',
          id: request.id,
          error: {
            code: -32603,
            message: `HTTP ${res.status}: ${errorText}`
          }
        };
        process.stdout.write(JSON.stringify(errResp) + '\n');
      }
      return;
    }

    const json = await res.json();
    if (!isNotification) {
      process.stdout.write(JSON.stringify(json) + '\n');
    }
  } catch (err) {
    if (!isNotification) {
      const errResp = {
        jsonrpc: '2.0',
        id: request.id,
        error: {
          code: -32603,
          message: err.message || 'Bridge request failed'
        }
      };
      process.stdout.write(JSON.stringify(errResp) + '\n');
    }
  }
});
