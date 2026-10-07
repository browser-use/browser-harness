"""Console entry point for the optional Browser Harness MCP server."""


def main() -> None:
    """Run the MCP server, or explain how to install its optional dependency."""
    try:
        from mcp_server import main as run_server
    except ModuleNotFoundError as exc:
        if exc.name == "mcp" or (exc.name and exc.name.startswith("mcp.")):
            raise SystemExit(
                "browser-harness-mcp requires MCP support. "
                "Install it with: pip install 'browser-harness[mcp]'"
            ) from None
        raise

    run_server()
