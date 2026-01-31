"""
Tests for Belt Integration Module

Tests the belt controller, belt manager, and belt integration logic
using mock mode (no hardware required).
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import belt modules
from robotaste.hardware.belt_controller import (
    ConveyorBelt,
    BeltPosition,
    BeltStatus,
    BeltConnectionError,
    BeltCommandError,
    BeltTimeoutError
)
from robotaste.core.belt_manager import (
    get_or_create_belt,
    cleanup_belt,
    cleanup_all_belts,
    is_belt_enabled,
    get_belt_config,
    _belt_cache
)
from robotaste.utils.belt_db import (
    get_db_connection,
    create_belt_operation,
    get_pending_belt_operations,
    get_belt_operation_by_id,
    mark_belt_operation_in_progress,
    mark_belt_operation_completed,
    mark_belt_operation_failed,
    mark_belt_operation_skipped,
    are_all_belt_operations_complete_for_cycle
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db():
    """Create a temporary database with belt tables."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Create tables
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            protocol_id TEXT
        );
        
        CREATE TABLE IF NOT EXISTS belt_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            cycle_number INTEGER NOT NULL,
            operation_type TEXT NOT NULL,
            target_position TEXT,
            mix_count INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP DEFAULT NULL,
            completed_at TIMESTAMP DEFAULT NULL,
            error_message TEXT
        );
        
        CREATE TABLE IF NOT EXISTS belt_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            command TEXT NOT NULL,
            response TEXT,
            success INTEGER NOT NULL,
            error_message TEXT
        );
    """)
    conn.commit()
    conn.close()
    
    yield path
    
    # Cleanup
    os.unlink(path)


@pytest.fixture
def mock_belt():
    """Create a mock mode belt for testing."""
    belt = ConveyorBelt(
        port="/dev/mock",
        baud=9600,
        mock_mode=True
    )
    return belt


@pytest.fixture
def belt_config():
    """Sample belt configuration."""
    return {
        "enabled": True,
        "serial_port": "/dev/mock",
        "baud_rate": 9600,
        "timeout_seconds": 30,
        "mock_mode": True,  # Use mock mode for tests
        "cup_count": 10,
        "mixing": {
            "enabled": True,
            "oscillations": 5,
            "speed": "medium"
        }
    }


@pytest.fixture(autouse=True)
def cleanup_cache():
    """Clean up belt cache before and after each test."""
    _belt_cache.clear()
    yield
    _belt_cache.clear()


# ============================================================================
# Belt Controller Tests
# ============================================================================

class TestBeltController:
    """Tests for ConveyorBelt hardware controller."""

    def test_mock_mode_connect(self, mock_belt):
        """Test connecting in mock mode."""
        mock_belt.connect()
        assert mock_belt.is_connected()
        assert mock_belt.get_status() == BeltStatus.IDLE
        mock_belt.disconnect()

    def test_mock_mode_disconnect(self, mock_belt):
        """Test disconnecting in mock mode."""
        mock_belt.connect()
        mock_belt.disconnect()
        assert not mock_belt.is_connected()
        assert mock_belt.get_status() == BeltStatus.DISCONNECTED

    def test_move_to_spout(self, mock_belt):
        """Test moving cup to spout position."""
        mock_belt.connect()
        result = mock_belt.move_to_spout(wait=True)
        assert result is True
        assert mock_belt.get_position() == BeltPosition.SPOUT
        mock_belt.disconnect()

    def test_move_to_display(self, mock_belt):
        """Test moving cup to display position."""
        mock_belt.connect()
        result = mock_belt.move_to_display(wait=True)
        assert result is True
        assert mock_belt.get_position() == BeltPosition.DISPLAY
        mock_belt.disconnect()

    def test_mix(self, mock_belt):
        """Test mixing oscillation."""
        mock_belt.connect()
        result = mock_belt.mix(oscillations=3, wait=True)
        assert result is True
        mock_belt.disconnect()

    def test_mix_zero_oscillations(self, mock_belt):
        """Test mixing with zero oscillations (should skip)."""
        mock_belt.connect()
        result = mock_belt.mix(oscillations=0, wait=True)
        assert result is True  # Should succeed (skip gracefully)
        mock_belt.disconnect()

    def test_emergency_stop(self, mock_belt):
        """Test emergency stop."""
        mock_belt.connect()
        mock_belt.stop()
        assert mock_belt.get_status() == BeltStatus.IDLE
        mock_belt.disconnect()

    def test_context_manager(self):
        """Test context manager usage."""
        with ConveyorBelt("/dev/mock", mock_mode=True) as belt:
            assert belt.is_connected()
            belt.move_to_spout()
        
        assert not belt.is_connected()


# ============================================================================
# Belt Database Tests
# ============================================================================

class TestBeltDatabase:
    """Tests for belt database operations."""

    def test_create_belt_operation(self, temp_db):
        """Test creating a belt operation."""
        op_id = create_belt_operation(
            session_id="test-session",
            cycle_number=1,
            operation_type="position_spout",
            target_position="spout",
            db_path=temp_db
        )
        
        assert op_id > 0
        
        operation = get_belt_operation_by_id(op_id, temp_db)
        assert operation is not None
        assert operation["session_id"] == "test-session"
        assert operation["cycle_number"] == 1
        assert operation["operation_type"] == "position_spout"
        assert operation["status"] == "pending"

    def test_create_mix_operation(self, temp_db):
        """Test creating a mix operation."""
        op_id = create_belt_operation(
            session_id="test-session",
            cycle_number=1,
            operation_type="mix",
            mix_count=5,
            db_path=temp_db
        )
        
        operation = get_belt_operation_by_id(op_id, temp_db)
        assert operation["operation_type"] == "mix"
        assert operation["mix_count"] == 5

    def test_get_pending_operations(self, temp_db):
        """Test getting pending operations."""
        # Create multiple operations
        create_belt_operation("session1", 1, "position_spout", "spout", db_path=temp_db)
        create_belt_operation("session1", 1, "mix", mix_count=5, db_path=temp_db)
        create_belt_operation("session2", 1, "position_display", "display", db_path=temp_db)
        
        pending = get_pending_belt_operations(limit=10, db_path=temp_db)
        assert len(pending) == 3

    def test_mark_operation_in_progress(self, temp_db):
        """Test marking operation as in progress."""
        op_id = create_belt_operation("test-session", 1, "position_spout", "spout", db_path=temp_db)
        
        mark_belt_operation_in_progress(op_id, temp_db)
        
        operation = get_belt_operation_by_id(op_id, temp_db)
        assert operation["status"] == "in_progress"
        assert operation["started_at"] is not None

    def test_mark_operation_completed(self, temp_db):
        """Test marking operation as completed."""
        op_id = create_belt_operation("test-session", 1, "position_spout", "spout", db_path=temp_db)
        
        mark_belt_operation_completed(op_id, temp_db)
        
        operation = get_belt_operation_by_id(op_id, temp_db)
        assert operation["status"] == "completed"
        assert operation["completed_at"] is not None

    def test_mark_operation_failed(self, temp_db):
        """Test marking operation as failed."""
        op_id = create_belt_operation("test-session", 1, "position_spout", "spout", db_path=temp_db)
        
        mark_belt_operation_failed(op_id, "Test error message", temp_db)
        
        operation = get_belt_operation_by_id(op_id, temp_db)
        assert operation["status"] == "failed"
        assert operation["error_message"] == "Test error message"

    def test_mark_operation_skipped(self, temp_db):
        """Test marking operation as skipped."""
        op_id = create_belt_operation("test-session", 1, "mix", mix_count=5, db_path=temp_db)
        
        mark_belt_operation_skipped(op_id, "Mixing skipped due to error", temp_db)
        
        operation = get_belt_operation_by_id(op_id, temp_db)
        assert operation["status"] == "skipped"

    def test_all_operations_complete_for_cycle(self, temp_db):
        """Test checking if all cycle operations are complete."""
        # Create operations
        op1 = create_belt_operation("test-session", 1, "position_spout", "spout", db_path=temp_db)
        op2 = create_belt_operation("test-session", 1, "mix", mix_count=5, db_path=temp_db)
        op3 = create_belt_operation("test-session", 1, "position_display", "display", db_path=temp_db)
        
        # Initially not complete
        assert not are_all_belt_operations_complete_for_cycle("test-session", 1, temp_db)
        
        # Complete some
        mark_belt_operation_completed(op1, temp_db)
        mark_belt_operation_skipped(op2, "skipped", temp_db)
        assert not are_all_belt_operations_complete_for_cycle("test-session", 1, temp_db)
        
        # Complete all
        mark_belt_operation_completed(op3, temp_db)
        assert are_all_belt_operations_complete_for_cycle("test-session", 1, temp_db)


# ============================================================================
# Belt Manager Tests
# ============================================================================

class TestBeltManager:
    """Tests for belt connection manager."""

    def test_get_or_create_belt(self, belt_config):
        """Test getting or creating belt connection."""
        belt = get_or_create_belt("test-session", belt_config)
        
        assert belt is not None
        assert belt.is_connected()
        assert "test-session" in _belt_cache
        
        cleanup_belt("test-session")

    def test_reuse_cached_belt(self, belt_config):
        """Test that cached belt is reused."""
        belt1 = get_or_create_belt("test-session", belt_config)
        belt2 = get_or_create_belt("test-session", belt_config)
        
        assert belt1 is belt2
        
        cleanup_belt("test-session")

    def test_cleanup_belt(self, belt_config):
        """Test cleaning up belt connection."""
        get_or_create_belt("test-session", belt_config)
        
        cleanup_belt("test-session")
        
        assert "test-session" not in _belt_cache

    def test_cleanup_all_belts(self, belt_config):
        """Test cleaning up all belt connections."""
        get_or_create_belt("session1", belt_config)
        get_or_create_belt("session2", belt_config)
        
        cleanup_all_belts()
        
        assert len(_belt_cache) == 0

    def test_is_belt_enabled(self):
        """Test checking if belt is enabled in protocol."""
        protocol_enabled = {"belt_config": {"enabled": True}}
        protocol_disabled = {"belt_config": {"enabled": False}}
        protocol_missing = {}
        
        assert is_belt_enabled(protocol_enabled) is True
        assert is_belt_enabled(protocol_disabled) is False
        assert is_belt_enabled(protocol_missing) is False

    def test_get_belt_config(self):
        """Test getting belt config from protocol."""
        protocol = {
            "belt_config": {
                "enabled": True,
                "serial_port": "/dev/test"
            }
        }
        
        config = get_belt_config(protocol)
        assert config is not None
        assert config["serial_port"] == "/dev/test"
        
        disabled_protocol = {"belt_config": {"enabled": False}}
        assert get_belt_config(disabled_protocol) is None


# ============================================================================
# Integration Tests
# ============================================================================

class TestBeltIntegration:
    """Integration tests for belt workflow."""

    def test_full_belt_cycle_mock(self, belt_config):
        """Test complete belt cycle in mock mode."""
        from robotaste.core.belt_integration import execute_full_belt_cycle
        
        result = execute_full_belt_cycle(
            session_id="test-session",
            cycle_number=1,
            belt_config=belt_config
        )
        
        assert result["success"] is True
        assert result["error"] is None
        assert result["skipped_mixing"] is False
        
        cleanup_belt("test-session")

    def test_position_functions(self, belt_config):
        """Test position helper functions."""
        from robotaste.core.belt_integration import (
            position_cup_at_spout,
            position_cup_at_display,
            perform_mixing
        )
        
        # Test spout positioning
        result = position_cup_at_spout("test-session", belt_config)
        assert result is True
        
        # Test mixing
        result = perform_mixing("test-session", belt_config, oscillations=3)
        assert result is True
        
        # Test display positioning
        result = position_cup_at_display("test-session", belt_config)
        assert result is True
        
        cleanup_belt("test-session")
