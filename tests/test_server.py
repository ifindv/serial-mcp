"""Unit tests for Serial MCP Server."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from serial_mcp.server import (
    ClosePortInput,
    ConnectionManager,
    GetSignalsInput,
    ListConnectionsInput,
    ListPortsInput,
    OpenPortInput,
    ReadDataInput,
    ResponseFormat,
    SetSignalsInput,
    WriteDataInput,
    _connection_manager,
    serial_close,
    serial_get_signals,
    serial_list_connections,
    serial_list_ports,
    serial_open,
    serial_read,
    serial_set_signals,
    serial_write,
)


@pytest.fixture
def mock_serial():
    """Create a mock serial port."""
    serial = MagicMock()
    serial.port = "COM3"
    serial.baudrate = 9600
    serial.write.return_value = 12
    serial.read.return_value = b"Hello"
    serial.is_open = True
    serial.dtr = True
    serial.rts = False
    serial.cts = True
    serial.dsr = True
    serial.dcd = False
    return serial


@pytest.fixture
def manager():
    """Get a fresh connection manager for each test."""
    _connection_manager.clear()
    return _connection_manager


class TestConnectionManager:
    """Test ConnectionManager class."""

    def test_add_connection(self, manager, mock_serial):
        """Test adding a new connection."""
        info = manager.add(
            port="COM3",
            baud_rate=9600,
            path="COM3",
            serial_port=mock_serial,
        )

        assert info.id == "conn_1"
        assert info.port == "COM3"
        assert info.baud_rate == 9600
        assert info.is_open is True
        assert manager.size() == 1

    def test_get_connection(self, manager, mock_serial):
        """Test retrieving a connection by ID."""
        manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        info = manager.get("conn_1")
        assert info is not None
        assert info.id == "conn_1"

    def test_get_nonexistent_connection(self, manager):
        """Test retrieving a nonexistent connection."""
        info = manager.get("conn_999")
        assert info is None

    def test_has_connection(self, manager, mock_serial):
        """Test checking if a connection exists."""
        manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        assert manager.has("conn_1") is True
        assert manager.has("conn_999") is False

    def test_remove_connection(self, manager, mock_serial):
        """Test removing a connection."""
        manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        removed = manager.remove("conn_1")
        assert removed is True
        assert manager.size() == 0
        mock_serial.close.assert_called_once()

    def test_remove_nonexistent_connection(self, manager):
        """Test removing a nonexistent connection."""
        removed = manager.remove("conn_999")
        assert removed is False

    def test_get_all_connections(self, manager, mock_serial):
        """Test getting all connections."""
        manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)
        manager.add(port="COM4", baud_rate=115200, path="COM4", serial_port=mock_serial)

        connections = manager.get_all()
        assert len(connections) == 2

    def test_clear_connections(self, manager, mock_serial):
        """Test clearing all connections."""
        manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)
        manager.clear()

        assert manager.size() == 0
        mock_serial.close.assert_called_once()


class TestPydanticModels:
    """Test Pydantic input models."""

    def test_list_ports_input_defaults(self):
        """Test ListPortsInput with default values."""
        model = ListPortsInput()
        assert model.response_format == ResponseFormat.MARKDOWN

    def test_list_ports_input_json(self):
        """Test ListPortsInput with JSON format."""
        model = ListPortsInput(response_format=ResponseFormat.JSON)
        assert model.response_format == ResponseFormat.JSON

    def test_open_port_input_defaults(self):
        """Test OpenPortInput with default values."""
        model = OpenPortInput(port="COM3")
        assert model.port == "COM3"
        assert model.baud_rate == 9600
        assert model.data_bits == 8
        assert model.stop_bits == 1.0
        assert model.parity == "N"

    def test_open_port_input_custom(self):
        """Test OpenPortInput with custom values."""
        model = OpenPortInput(port="COM3", baud_rate=115200, data_bits=7, stop_bits=2.0, parity="E")
        assert model.baud_rate == 115200
        assert model.data_bits == 7
        assert model.stop_bits == 2.0
        assert model.parity == "E"

    def test_open_port_input_invalid_baud_rate(self):
        """Test OpenPortInput with invalid baud rate."""
        with pytest.raises(ValueError):
            OpenPortInput(port="COM3", baud_rate=0)

    def test_open_port_input_invalid_parity(self):
        """Test OpenPortInput with invalid parity."""
        with pytest.raises(ValueError):
            OpenPortInput(port="COM3", parity="X")

    def test_write_data_input_defaults(self):
        """Test WriteDataInput with default values."""
        model = WriteDataInput(connection_id="conn_1", data="Hello")
        assert model.connection_id == "conn_1"
        assert model.data == "Hello"
        assert model.encoding == "utf-8"
        assert model.timeout == 5.0

    def test_read_data_input_defaults(self):
        """Test ReadDataInput with default values."""
        model = ReadDataInput(connection_id="conn_1")
        assert model.connection_id == "conn_1"
        assert model.max_bytes == 1024
        assert model.timeout == 1.0
        assert model.encoding == "utf-8"

    def test_set_signals_input_defaults(self):
        """Test SetSignalsInput with default values."""
        model = SetSignalsInput(connection_id="conn_1")
        assert model.connection_id == "conn_1"
        assert model.dtr is None
        assert model.rts is None

    def test_set_signals_input_with_values(self):
        """Test SetSignalsInput with signal values."""
        model = SetSignalsInput(connection_id="conn_1", dtr=True, rts=False)
        assert model.dtr is True
        assert model.rts is False


class TestSerialTools:
    """Test serial tool functions."""

    @pytest.mark.asyncio
    async def test_serial_list_ports_empty(self):
        """Test listing ports when none are available."""
        with patch("serial_mcp.server.list_ports.comports") as mock_comports:
            mock_comports.return_value = []

            params = ListPortsInput()
            result = await serial_list_ports(params)

            assert result == "No serial ports found on this system."

    @pytest.mark.asyncio
    async def test_serial_list_ports_with_ports(self):
        """Test listing ports with available ports."""
        mock_port = MagicMock()
        mock_port.device = "COM3"
        mock_port.manufacturer = "FTDI"
        mock_port.serial_number = "ABC123"
        mock_port.pid = 0x6001
        mock_port.vid = 0x0403

        with patch("serial_mcp.server.list_ports.comports") as mock_comports:
            mock_comports.return_value = [mock_port]

            params = ListPortsInput()
            result = await serial_list_ports(params)

            assert "COM3" in result
            assert "FTDI" in result

    @pytest.mark.asyncio
    async def test_serial_open_success(self, mock_serial):
        """Test successfully opening a serial port."""
        with patch("serial_mcp.server.pyserial.Serial") as mock_serial_class:
            mock_serial_class.return_value = mock_serial

            params = OpenPortInput(port="COM3")
            result = await serial_open(params)

            assert result == "Connection opened: conn_1"
            mock_serial_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_serial_open_error(self):
        """Test opening a serial port with error."""
        import serial as pyserial

        with patch("serial_mcp.server.pyserial.Serial") as mock_serial_class:
            mock_serial_class.side_effect = pyserial.SerialException("Permission denied")

            params = OpenPortInput(port="COM3")
            result = await serial_open(params)

            assert result.startswith("Error:")

    @pytest.mark.asyncio
    async def test_serial_close_success(self, mock_serial):
        """Test successfully closing a serial port."""
        _connection_manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        params = ClosePortInput(connection_id="conn_1")
        result = await serial_close(params)

        assert result == "Connection closed: conn_1"

    @pytest.mark.asyncio
    async def test_serial_close_not_found(self):
        """Test closing a nonexistent connection."""
        params = ClosePortInput(connection_id="conn_999")
        result = await serial_close(params)

        assert result == "Error: Connection 'conn_999' not found"

    @pytest.mark.asyncio
    async def test_serial_write_success(self, mock_serial):
        """Test successfully writing to a serial port."""
        _connection_manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        params = WriteDataInput(connection_id="conn_1", data="Hello")
        result = await serial_write(params)

        assert result == "Wrote 12 bytes to conn_1"
        mock_serial.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_serial_write_not_found(self):
        """Test writing to a nonexistent connection."""
        params = WriteDataInput(connection_id="conn_999", data="Hello")
        result = await serial_write(params)

        assert result == "Error: Connection 'conn_999' not found"

    @pytest.mark.asyncio
    async def test_serial_read_success(self, mock_serial):
        """Test successfully reading from a serial port."""
        _connection_manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        params = ReadDataInput(connection_id="conn_1")
        result = await serial_read(params)

        assert "Hello" in result
        assert "Bytes read" in result

    @pytest.mark.asyncio
    async def test_serial_read_timeout(self, mock_serial):
        """Test reading with timeout."""
        mock_serial.read.return_value = b""
        _connection_manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        params = ReadDataInput(connection_id="conn_1", timeout=1.0)
        result = await serial_read(params)

        assert "timed out" in result

    @pytest.mark.asyncio
    async def test_serial_set_signals_success(self, mock_serial):
        """Test successfully setting signals."""
        _connection_manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        params = SetSignalsInput(connection_id="conn_1", dtr=True, rts=False)
        result = await serial_set_signals(params)

        assert "Signals set on conn_1" in result
        assert "DTR=HIGH" in result
        assert "RTS=LOW" in result

    @pytest.mark.asyncio
    async def test_serial_get_signals_success(self, mock_serial):
        """Test successfully getting signal states."""
        _connection_manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        params = GetSignalsInput(connection_id="conn_1")
        result = await serial_get_signals(params)

        assert "dtr" in result.lower()
        assert "rts" in result.lower()
        assert "cts" in result.lower()

    @pytest.mark.asyncio
    async def test_serial_list_connections_empty(self):
        """Test listing connections when none are active."""
        params = ListConnectionsInput()
        result = await serial_list_connections(params)

        assert result == "No active connections"

    @pytest.mark.asyncio
    async def test_serial_list_connections_with_active(self, mock_serial):
        """Test listing connections with active connections."""
        _connection_manager.add(port="COM3", baud_rate=9600, path="COM3", serial_port=mock_serial)

        params = ListConnectionsInput()
        result = await serial_list_connections(params)

        assert "conn_1" in result
        assert "COM3" in result