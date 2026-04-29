#!/usr/bin/env python3
"""Minimal twozero MCP bridge for Claude Code → TouchDesigner communication."""

import json
import sys
import urllib.request

MCP_URL = "http://localhost:40404/mcp"
_REQ_ID = 0


def call(method, arguments=None):
    """Call a twozero MCP tool and return the text content."""
    global _REQ_ID
    _REQ_ID += 1
    payload = {
        "jsonrpc": "2.0",
        "id": _REQ_ID,
        "method": "tools/call",
        "params": {"name": method, "arguments": arguments or {}},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        MCP_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    # Extract text content
    content = result.get("result", {}).get("content", [])
    texts = [c["text"] for c in content if c.get("type") == "text"]
    return "\n".join(texts)


def main():
    if len(sys.argv) < 2:
        print("Usage: td_mcp.py <tool_name> [json_args]")
        sys.exit(1)

    tool = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(call(tool, args))


if __name__ == "__main__":
    main()
