# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-04-23

### Added
- Initial release of Serial MCP Server
- `serial_list_ports` tool for listing available serial ports
- `serial_open` tool for opening serial port connections
- `serial_close` tool for closing connections
- `serial_write` tool for writing data to ports
- `serial_read` tool for reading data from ports
- `serial_set_signals` tool for controlling DTR/RTS signals
- `serial_get_signals` tool for reading signal states
- `serial_list_connections` tool for listing active connections
- Support for configurable baud rates, data bits, stop bits, and parity
- JSON and Markdown output formats
- Connection management with unique IDs
- Comprehensive error handling