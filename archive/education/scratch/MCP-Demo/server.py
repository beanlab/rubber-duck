from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv("../.env")

# Create an MCP server
mcp = FastMCP(
    name="Calculator",
    host="0.0.0.0",
    port=8050,
    stateless_http=True,
)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    print(f"System Message: Using add tool with a={a}, b={b}")
    return a + b

@mcp.tool()
def subtract(a: int, b: int) -> int:
    """Subtract two numbers"""
    print(f"System Message: Using subtract tool with a={a}, b={b}")
    return a - b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers together"""
    print(f"System Message: Using multiply tool with a={a}, b={b}")
    return a * b

@mcp.tool()
def divide(a: int, b: int) -> int:
    """Divide two numbers"""
    print("System Message: Using divide tool with a={a}, b={b}")
    return a//b

@mcp.tool()
def power(base: int, exponent: int) -> int:
    """Take a to the power of b"""
    print(f"System Message: Using power tool with base={base}, exponent={exponent}")
    return pow(base, exponent)

# Run the server
if __name__ == "__main__":
    print("Running server with SSE transport")
    mcp.run(transport="sse")
