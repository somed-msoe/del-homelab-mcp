from mcp.server.mcpserver.exceptions import ToolError


class UserError(ToolError, ValueError):
    """A failure the model should see and can correct (bad input, refused target).

    In SDK 2.x only ToolError messages reach the client; any other exception is
    reported as a bare "Error executing tool" and logged as a crash.
    """
