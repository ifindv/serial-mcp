#!/usr/bin/env python3
"""
MCP Server for Serial Port Communication.

This server provides tools to interact with serial ports, including listing ports,
opening/closing connections, reading/writing data, and controlling signals.
"""

import os
import argparse
import asyncio
import json
import secrets
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, TypedDict

import serial as pyserial
from serial.tools import list_ports
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, ConfigDict, field_validator

# Constants
CHARACTER_LIMIT = 25000
MAX_READ_SIZE = 65536
MAX_CONNECTIONS = 20

ALLOWED_ENCODINGS = {"utf-8", "utf-8-sig", "ascii", "latin-1", "iso-8859-1", "cp1252"}


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# Type definitions
class SignalState(TypedDict):
    """Control signal states."""
    dtr: Optional[bool]
    rts: Optional[bool]
    cts: Optional[bool]
    dsr: Optional[bool]
    dcd: Optional[bool]


@dataclass
class ConnectionInfo:
    """Information about an active serial connection."""
    id: str
    port: str
    baud_rate: int
    path: str
    serial_port: pyserial.Serial
    is_open: bool
    created_at: float


class ConnectionManager:
    """Manages active serial port connections."""

    def __init__(self) -> None:
        self._connections: OrderedDict[str, ConnectionInfo] = OrderedDict()

    def add(self, port: str, baud_rate: int, path: str, serial_port: pyserial.Serial) -> ConnectionInfo:
        """Add a new connection. Raises RuntimeError if max connections exceeded."""
        if len(self._connections) >= MAX_CONNECTIONS:
            raise RuntimeError(f"Maximum number of connections ({MAX_CONNECTIONS}) reached")

        conn_id = secrets.token_hex(8)
        info = ConnectionInfo(
            id=conn_id,
            port=port,
            baud_rate=baud_rate,
            path=path,
            serial_port=serial_port,
            is_open=True,
            created_at=datetime.now().timestamp(),
        )
        self._connections[conn_id] = info
        return info

    def get(self, conn_id: str) -> Optional[ConnectionInfo]:
        """Get a connection by ID."""
        return self._connections.get(conn_id)

    def has(self, conn_id: str) -> bool:
        """Check if a connection exists."""
        return conn_id in self._connections

    def remove(self, conn_id: str) -> bool:
        """Remove a connection."""
        info = self._connections.pop(conn_id, None)
        if info and info.is_open:
            try:
                info.serial_port.close()
            except Exception:
                pass
        return info is not None

    def update_open_state(self, conn_id: str, is_open: bool) -> None:
        """Update the open state of a connection."""
        info = self._connections.get(conn_id)
        if info:
            info.is_open = is_open

    def get_all(self) -> List[ConnectionInfo]:
        """Get all connections."""
        return list(self._connections.values())

    def size(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)

    def clear(self) -> None:
        """Clear all connections."""
        for info in self._connections.values():
            if info.is_open:
                try:
                    info.serial_port.close()
                except Exception:
                    pass
        self._connections.clear()


# Global connection manager
_connection_manager = ConnectionManager()


def _handle_serial_error(e: Exception) -> str:
    """Format serial port errors consistently."""
    if isinstance(e, pyserial.SerialException):
        msg = str(e)
        if "could not open port" in msg.lower():
            return f"Error: Could not open serial port. The port may be in use or does not exist. Details: {msg}"
        if "permission denied" in msg.lower():
            return "Error: Permission denied. You may need administrator privileges to access this port."
        if "device reports readiness" in msg.lower():
            return "Error: The device is not ready. Check that the device is connected and powered on."
        return f"Error: Serial port error - {msg}"
    return f"Error: Unexpected error occurred - {type(e).__name__}: {e}"


def _format_port_info(port: Dict[str, Any], format_type: ResponseFormat) -> str:
    """Format serial port information."""
    if format_type == ResponseFormat.JSON:
        return json.dumps(port, indent=2)

    lines = [f"## {port.get('path', 'Unknown')}", ""]
    for key, value in port.items():
        if value is not None:
            lines.append(f"- **{key}**: {value}")
    return "\n".join(lines)


def _truncate_response(text: str) -> tuple[str, bool]:
    """Truncate response if it exceeds character limit."""
    if len(text) <= CHARACTER_LIMIT:
        return text, False

    truncated = text[:CHARACTER_LIMIT] + "\n\n... [Response truncated due to size limit]"
    return truncated, True


def _format_signal_state(state: SignalState, format_type: ResponseFormat) -> str:
    """Format signal state for output."""
    if format_type == ResponseFormat.JSON:
        return json.dumps(state, indent=2)

    lines = ["# Signal State", ""]
    for signal, value in state.items():
        if value is not None:
            status = "HIGH" if value else "LOW"
            lines.append(f"- **{signal.upper()}**: {status}")
    return "\n".join(lines)


# Pydantic Input Models
class ListPortsInput(BaseModel):
    """Input model for listing serial ports."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class OpenPortInput(BaseModel):
    """Input model for opening a serial port."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    port: str = Field(..., description="Serial port path (e.g., 'COM3', '/dev/ttyUSB0', '/dev/tty.usbserial-...')", min_length=1)
    baud_rate: int = Field(default=9600, description="Baud rate (e.g., 9600, 115200)", ge=1, le=4000000)
    data_bits: int = Field(default=8, description="Data bits (typically 8)", ge=5, le=8)
    stop_bits: float = Field(default=1.0, description="Stop bits (1, 1.5, or 2)", ge=1.0, le=2.0)
    parity: str = Field(default="N", description="Parity: 'N'=None, 'E'=Even, 'O'=Odd", pattern=r"^[NEO]$")


class ClosePortInput(BaseModel):
    """Input model for closing a serial port."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    connection_id: str = Field(..., description="Connection ID returned by serial_open", min_length=1)


class WriteDataInput(BaseModel):
    """Input model for writing data to a serial port."""
    model_config = ConfigDict(validate_assignment=True, extra="forbid", str_strip_whitespace=False)

    connection_id: str = Field(..., description="Connection ID returned by serial_open", min_length=1)
    data: str = Field(..., description="Data to write as a string", min_length=1)
    encoding: str = Field(default="utf-8", description="Text encoding (e.g., 'utf-8', 'ascii')", min_length=1)
    timeout: float = Field(default=5.0, description="Write timeout in seconds", ge=0.1, le=60.0)

    @field_validator("encoding")
    @classmethod
    def validate_encoding(cls, v: str) -> str:
        if v.lower() not in ALLOWED_ENCODINGS:
            raise ValueError(f"Encoding must be one of: {', '.join(sorted(ALLOWED_ENCODINGS))}")
        return v.lower()


class ReadDataInput(BaseModel):
    """Input model for reading data from a serial port."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    connection_id: str = Field(..., description="Connection ID returned by serial_open", min_length=1)
    max_bytes: int = Field(default=1024, description="Maximum bytes to read", ge=1, le=MAX_READ_SIZE)
    timeout: float = Field(default=1.0, description="Read timeout in seconds", ge=0.1, le=60.0)
    encoding: str = Field(default="utf-8", description="Text encoding (e.g., 'utf-8', 'ascii')", min_length=1)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator("encoding")
    @classmethod
    def validate_encoding(cls, v: str) -> str:
        if v.lower() not in ALLOWED_ENCODINGS:
            raise ValueError(f"Encoding must be one of: {', '.join(sorted(ALLOWED_ENCODINGS))}")
        return v.lower()


class SetSignalsInput(BaseModel):
    """Input model for setting serial port control signals."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    connection_id: str = Field(..., description="Connection ID returned by serial_open", min_length=1)
    dtr: Optional[bool] = Field(default=None, description="Data Terminal Ready signal state")
    rts: Optional[bool] = Field(default=None, description="Request To Send signal state")


class GetSignalsInput(BaseModel):
    """Input model for reading serial port signal states."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    connection_id: str = Field(..., description="Connection ID returned by serial_open", min_length=1)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class ListConnectionsInput(BaseModel):
    """Input model for listing active connections."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


@asynccontextmanager
async def _lifespan(app: FastMCP):
    """Lifespan manager for server initialization and cleanup."""
    yield {"connection_manager": _connection_manager}
    _connection_manager.clear()


mcp = FastMCP("serial_mcp", lifespan=_lifespan, host="127.0.0.1", port=8001)


@mcp.tool(name="serial_list_ports", annotations={"title": "List Serial Ports", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def serial_list_ports(params: ListPortsInput) -> str:
    """
    List all available serial ports on the system.

    This tool scans the system for available serial ports and returns detailed
    information about each port including device path, manufacturer, and serial number.

    Args:
        params (ListPortsInput): Validated input parameters containing:
            - response_format (ResponseFormat): Output format (default: 'markdown')

    Returns:
        str: Formatted list of serial ports.

    Success response format:
    For JSON: Array of port objects with path, manufacturer, serialNumber, etc.
    For Markdown: Formatted list with port details

    Error response: "Error: <error message>"
    """
    try:
        ports = await asyncio.to_thread(lambda: list_ports.comports())
        if not ports:
            return "No serial ports found on this system."

        port_list = []
        for port in ports:
            port_info = {
                "path": port.device,
                "manufacturer": getattr(port, "manufacturer", None),
                "serialNumber": getattr(port, "serial_number", None),
                "productId": getattr(port, "pid", None),
                "vendorId": getattr(port, "vid", None),
            }
            port_list.append(port_info)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(port_list, indent=2)

        lines = ["# Available Serial Ports", ""]
        for port_info in port_list:
            lines.append(_format_port_info(port_info, ResponseFormat.MARKDOWN))

        return "\n".join(lines)

    except Exception as e:
        return _handle_serial_error(e)


@mcp.tool(name="serial_open", annotations={"title": "Open Serial Port", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
async def serial_open(params: OpenPortInput) -> str:
    """
    Open a serial port connection.

    Opens a new serial port connection with specified parameters. Returns a connection
    ID that must be used for subsequent operations on this port.

    Args:
        params (OpenPortInput): Validated input parameters containing:
            - port (str): Serial port path (e.g., 'COM3', '/dev/ttyUSB0')
            - baud_rate (int): Baud rate (default: 9600)
            - data_bits (int): Data bits, 5-8 (default: 8)
            - stop_bits (float): Stop bits, 1.0-2.0 (default: 1.0)
            - parity (str): Parity: 'N', 'E', or 'O' (default: 'N')

    Returns:
        str: Connection ID or error message.

    Success response: "Connection opened: conn_1"
    Error response: "Error: <error message>"
    """
    try:
        serial_conn = await asyncio.to_thread(
            lambda: pyserial.Serial(
                port=params.port,
                baudrate=params.baud_rate,
                bytesize=params.data_bits,
                stopbits=params.stop_bits,
                parity=params.parity,
                timeout=1.0,
            )
        )

        info = _connection_manager.add(
            port=params.port,
            baud_rate=params.baud_rate,
            path=params.port,
            serial_port=serial_conn,
        )

        return f"Connection opened: {info.id}"

    except Exception as e:
        return _handle_serial_error(e)


@mcp.tool(name="serial_close", annotations={"title": "Close Serial Port", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def serial_close(params: ClosePortInput) -> str:
    """
    Close a serial port connection.

    Closes the specified serial port connection and releases resources.
    The connection ID becomes invalid after closing.

    Args:
        params (ClosePortInput): Validated input parameters containing:
            - connection_id (str): Connection ID returned by serial_open

    Returns:
        str: Success message or error message.

    Success response: "Connection closed: conn_1"
    Error response: "Error: Connection 'conn_1' not found"
    """
    if not _connection_manager.has(params.connection_id):
        return f"Error: Connection '{params.connection_id}' not found"

    _connection_manager.remove(params.connection_id)
    return f"Connection closed: {params.connection_id}"


@mcp.tool(name="serial_write", annotations={"title": "Write to Serial Port", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False})
async def serial_write(params: WriteDataInput) -> str:
    """
    Write data to a serial port connection.

    Writes the specified data string to the serial port using the specified encoding.

    Args:
        params (WriteDataInput): Validated input parameters containing:
            - connection_id (str): Connection ID returned by serial_open
            - data (str): Data to write as a string
            - encoding (str): Text encoding (default: 'utf-8')
            - timeout (float): Write timeout in seconds (default: 5.0)

    Returns:
        str: Success message with bytes written or error message.

    Success response: "Wrote 12 bytes to conn_1"
    Error response: "Error: Connection 'conn_1' not found or not open"
    """
    info = _connection_manager.get(params.connection_id)
    if not info:
        return f"Error: Connection '{params.connection_id}' not found"
    if not info.is_open:
        return f"Error: Connection '{params.connection_id}' is not open"

    try:
        data_bytes = params.data.encode(params.encoding)
        info.serial_port.write_timeout = params.timeout

        bytes_written = await asyncio.to_thread(lambda: info.serial_port.write(data_bytes))

        return f"Wrote {bytes_written} bytes to {params.connection_id}"

    except Exception as e:
        return _handle_serial_error(e)


@mcp.tool(name="serial_read", annotations={"title": "Read from Serial Port", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False})
async def serial_read(params: ReadDataInput) -> str:
    """
    Read data from a serial port connection.

    Reads available data from the serial port up to the specified maximum bytes.
    Times out after the specified timeout period if no data is available.

    Args:
        params (ReadDataInput): Validated input parameters containing:
            - connection_id (str): Connection ID returned by serial_open
            - max_bytes (int): Maximum bytes to read (default: 1024, max: 65536)
            - timeout (float): Read timeout in seconds (default: 1.0)
            - encoding (str): Text encoding (default: 'utf-8')
            - response_format (ResponseFormat): Output format (default: 'markdown')

    Returns:
        str: Formatted data or error message.

    Success format for JSON:
    {
        "connection_id": "conn_1",
        "bytes_read": 42,
        "hex": "48656c6c6f",
        "data": "Hello",
        "timestamp": "2024-01-15T10:30:00Z"
    }

    Error response: "Error: Connection 'conn_1' not found or not open"
    """
    info = _connection_manager.get(params.connection_id)
    if not info:
        return f"Error: Connection '{params.connection_id}' not found"
    if not info.is_open:
        return f"Error: Connection '{params.connection_id}' is not open"

    try:
        info.serial_port.timeout = params.timeout

        data_bytes = await asyncio.to_thread(lambda: info.serial_port.read(params.max_bytes))

        if not data_bytes:
            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"connection_id": params.connection_id, "bytes_read": 0, "data": ""}, indent=2)
            return f"No data available from {params.connection_id} (timed out after {params.timeout}s)"

        try:
            data_str = data_bytes.decode(params.encoding)
        except UnicodeDecodeError:
            data_str = f"<Binary data, {len(data_bytes)} bytes, cannot decode as {params.encoding}>"

        if params.response_format == ResponseFormat.JSON:
            response = {
                "connection_id": params.connection_id,
                "bytes_read": len(data_bytes),
                "hex": data_bytes.hex(),
                "data": data_str if isinstance(data_str, str) else None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            return json.dumps(response, indent=2)

        lines = [
            f"# Data from {params.connection_id}",
            "",
            f"**Bytes read**: {len(data_bytes)}",
            f"**Encoding**: {params.encoding}",
            "",
            "## Hex Representation",
            f"```",
            data_bytes.hex(),
            "```",
            "",
            "## Data",
            f"```",
            data_str if isinstance(data_str, str) else "<binary data>",
            "```",
        ]

        text = "\n".join(lines)
        text, was_truncated = _truncate_response(text)

        if was_truncated:
            text += f"\n\n... [Response truncated. Use smaller max_bytes parameter or JSON format for full output]"

        return text

    except Exception as e:
        return _handle_serial_error(e)


@mcp.tool(name="serial_set_signals", annotations={"title": "Set Serial Port Signals", "readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False})
async def serial_set_signals(params: SetSignalsInput) -> str:
    """
    Set control signal states on a serial port connection.

    Sets the DTR (Data Terminal Ready) and/or RTS (Request To Send) control signals.

    Args:
        params (SetSignalsInput): Validated input parameters containing:
            - connection_id (str): Connection ID returned by serial_open
            - dtr (Optional[bool]): DTR signal state (True=HIGH, False=LOW, None=unchanged)
            - rts (Optional[bool]): RTS signal state (True=HIGH, False=LOW, None=unchanged)

    Returns:
        str: Success message or error message.

    Success response: "Signals set on conn_1: DTR=HIGH, RTS=LOW"
    Error response: "Error: Connection 'conn_1' not found or not open"
    """
    info = _connection_manager.get(params.connection_id)
    if not info:
        return f"Error: Connection '{params.connection_id}' not found"
    if not info.is_open:
        return f"Error: Connection '{params.connection_id}' is not open"

    try:
        changes = []
        if params.dtr is not None:
            await asyncio.to_thread(lambda: setattr(info.serial_port, "dtr", params.dtr))
            changes.append(f"DTR={'HIGH' if params.dtr else 'LOW'}")

        if params.rts is not None:
            await asyncio.to_thread(lambda: setattr(info.serial_port, "rts", params.rts))
            changes.append(f"RTS={'HIGH' if params.rts else 'LOW'}")

        if not changes:
            return f"No signals changed on {params.connection_id}"

        return f"Signals set on {params.connection_id}: {', '.join(changes)}"

    except Exception as e:
        return _handle_serial_error(e)


@mcp.tool(name="serial_get_signals", annotations={"title": "Get Serial Port Signals", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def serial_get_signals(params: GetSignalsInput) -> str:
    """
    Read the current state of serial port signals.

    Returns the current state of all control signals including input signals (CTS, DSR, DCD)
    and output signals (DTR, RTS).

    Args:
        params (GetSignalsInput): Validated input parameters containing:
            - connection_id (str): Connection ID returned by serial_open
            - response_format (ResponseFormat): Output format (default: 'markdown')

    Returns:
        str: Formatted signal states or error message.

    Success format for JSON:
    {
        "connection_id": "conn_1",
        "dtr": true,
        "rts": false,
        "cts": true,
        "dsr": true,
        "dcd": false
    }

    Error response: "Error: Connection 'conn_1' not found or not open"
    """
    info = _connection_manager.get(params.connection_id)
    if not info:
        return f"Error: Connection '{params.connection_id}' not found"
    if not info.is_open:
        return f"Error: Connection '{params.connection_id}' is not open"

    try:
        dtr = await asyncio.to_thread(lambda: info.serial_port.dtr)
        rts = await asyncio.to_thread(lambda: info.serial_port.rts)
        cts = await asyncio.to_thread(lambda: info.serial_port.cts)
        dsr = await asyncio.to_thread(lambda: info.serial_port.dsr)
        dcd = await asyncio.to_thread(lambda: info.serial_port.dcd)

        state: SignalState = {
            "dtr": dtr,
            "rts": rts,
            "cts": cts,
            "dsr": dsr,
            "dcd": dcd,
        }

        if params.response_format == ResponseFormat.JSON:
            response = {"connection_id": params.connection_id}
            response.update(state)
            return json.dumps(response, indent=2)

        lines = [
            f"# Signal States for {params.connection_id}",
            "",
            _format_signal_state(state, ResponseFormat.MARKDOWN),
        ]

        return "\n".join(lines)

    except Exception as e:
        return _handle_serial_error(e)


@mcp.tool(name="serial_list_connections", annotations={"title": "List Active Connections", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def serial_list_connections(params: ListConnectionsInput) -> str:
    """
    List all active serial port connections.

    Returns information about all currently open serial port connections.

    Args:
        params (ListConnectionsInput): Validated input parameters containing:
            - response_format (ResponseFormat): Output format (default: 'markdown')

    Returns:
        str: Formatted list of connections or empty message.

    Success format for JSON:
    [
        {
            "id": "conn_1",
            "port": "COM3",
            "baud_rate": 9600,
            "path": "COM3",
            "is_open": true,
            "created_at": "2024-01-15T10:30:00Z"
        }
    ]

    Error response: "No active connections"
    """
    connections = _connection_manager.get_all()

    if not connections:
        return "No active connections"

    if params.response_format == ResponseFormat.JSON:
        conn_list = []
        for info in connections:
            conn_list.append(
                {
                    "id": info.id,
                    "port": info.port,
                    "baud_rate": info.baud_rate,
                    "path": info.path,
                    "is_open": info.is_open,
                    "created_at": datetime.fromtimestamp(info.created_at).isoformat() + "Z",
                }
            )
        return json.dumps(conn_list, indent=2)

    lines = ["# Active Serial Connections", ""]
    for info in connections:
        created = datetime.fromtimestamp(info.created_at).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"## {info.id}")
        lines.append(f"- **Port**: {info.port}")
        lines.append(f"- **Baud Rate**: {info.baud_rate}")
        lines.append(f"- **Path**: {info.path}")
        lines.append(f"- **Status**: {'OPEN' if info.is_open else 'CLOSED'}")
        lines.append(f"- **Created**: {created}")
        lines.append("")

    return "\n".join(lines)

def parse_args():
    parser = argparse.ArgumentParser(description="support stdio and streamable mode")
    parser.add_argument(
        "--mode",
        type=str,
        default=os.getenv("MCP_MODE", "stdio"),
        choices=["stdio", "http"],
        help="set mcp server run mode"
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the serial-mcp CLI command."""
    args = parse_args()
    if args.mode == "stdio":
        mcp.run()
    else:
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()