# Serial MCP Server

A Model Context Protocol (MCP) server for serial port communication, enabling LLMs to interact with hardware devices via serial connections.

## Features

- List available serial ports
- Open/close serial port connections
- Read and write data to serial ports
- Control serial signals (DTR, RTS, CTS, DSR, DCD)
- Support for custom baud rates, data bits, stop bits, and parity
- JSON and Markdown output formats

## Installation

```bash
# Install from PyPI (when published)
pip install serial-mcp-new
```

## Usage

### Running the Server

```bash
# Run with stdio transport (default, for local use)
serial-mcp
```

### Config in Claude Code

```
  "mcpServers": {
    "ssh-mcp": {
      "command": "C:\\Users\\DELL\\AppData\\Local\\Packages\\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\\LocalCache\\local-packages\\Python311\\Scripts\\serial-mcp.exe",
      "args": [],
      "env": {}
    }
  },
```

### Available Tools

| Tool                        | Description                     |
| --------------------------- | ------------------------------- |
| `serial_list_ports`       | List all available serial ports |
| `serial_open`             | Open a serial port connection   |
| `serial_close`            | Close a serial port connection  |
| `serial_write`            | Write data to a serial port     |
| `serial_read`             | Read data from a serial port    |
| `serial_set_signals`      | Set control signal states       |
| `serial_get_signals`      | Read current signal states      |
| `serial_list_connections` | List all active connections     |

## Example Workflow

1. List available ports:

   ```
   serial_list_ports()
   ```
2. Open a connection:

   ```
   serial_open(port="COM3", baud_rate=115200)
   ```
3. Write data:

   ```
   serial_write(connection_id="conn_1", data="Hello, device!")
   ```
4. Read response:

   ```
   serial_read(connection_id="conn_1", timeout=2.0)
   ```
5. Close when done:

   ```
   serial_close(connection_id="conn_1")
   ```

## Dependencies

- Python 3.10+
- mcp >= 1.6.1
- pyserial >= 3.5
- pydantic >= 2.0.0

## License

MIT
