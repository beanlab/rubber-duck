# MCP Calculator Server

A simple Model Context Protocol (MCP) server that provides basic mathematical operations through tools, integrated with OpenAI's API for conversational math assistance.

## Overview

This project consists of two main components:
- **Server** (`server.py`): An MCP server that exposes mathematical operation tools
- **Client** (`client.py`): A client that connects to the MCP server and uses OpenAI's API to provide conversational math assistance

## Prerequisites

- Python 3.8+
- OpenAI API key
- Required Python packages (see Installation)

## Installation

1. **Clone or download the project files**

2. **Install required dependencies**:
   ```bash
   pip install fastmcp python-dotenv openai mcp
   ```

3. **Set up environment variables**:
   Create a `.env` file in the parent directory of your server script:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## Project Structure

```
your-project/
├── .env                 # Environment variables
├── server.py           # MCP server implementation
├── client.py           # MCP client with OpenAI integration
└── README.md           # This file
```

## Usage

### Running the Server

1. **Start the MCP server**:
   ```bash
   python server.py
   ```

   The server will start on `http://localhost:8050` with SSE (Server-Sent Events) transport.

   You should see output like:
   ```
   Running server with SSE transport
   ```

### Running the Client

1. **In a separate terminal, start the client**:
   ```bash
   python client.py
   ```

2. **Interact with the calculator**:
   ```
   Enter your math query (or 'exit' to quit): What is 15 + 27?
   AI: Using the add function, 15 + 27 equals 42.
   
   Enter your math query (or 'exit' to quit): Calculate 2 to the power of 8
   AI: Using the power function, 2 to the power of 8 equals 256.
   
   Enter your math query (or 'exit' to quit): exit
   ```

## Available Mathematical Operations

The server provides the following tools:

- **add(a, b)**: Add two numbers together
- **subtract(a, b)**: Subtract two numbers
- **multiply(a, b)**: Multiply two numbers together  
- **divide(a, b)**: Divide two numbers
- **power(base, exponent)**: Calculate base to the power of exponent

## Important Notes

- The division operation uses integer division (`//`) which returns whole numbers only
- All operations work with integers as input and output
- The server uses SSE (Server-Sent Events) for real-time communication

## Configuration

### Server Configuration
- **Host**: `0.0.0.0` (accepts connections from any IP)
- **Port**: `8050`
- **Transport**: SSE (Server-Sent Events)
- **Stateless HTTP**: Enabled

### Client Configuration  
- **Model**: `gpt-4o` (OpenAI model)
- **Server URL**: `http://localhost:8050/sse`


### Debugging

- The server runs with debug information printed to console
- Check server logs for any error messages
- Verify the client can connect to `http://localhost:8050/sse`

## Extending the Server

To add new mathematical operations:

1. **Add a new tool function**:
   ```python
   @mcp.tool()
   def square_root(n: float) -> float:
       """Calculate the square root of a number"""
       import math
       return math.sqrt(n)
   ```

2. **Restart the server** for changes to take effect
