"""Tests for configuration management."""

import json
import tempfile
from pathlib import Path

import pytest

from sleap_viz.config import ViewerConfig, ConfigManager, get_current_config, apply_config


def test_viewer_config_defaults():
    """Test ViewerConfig default values."""
    config = ViewerConfig()
    
    assert config.fps == 25.0
    assert config.playback_speed == 1.0
    assert config.loop is False
    assert config.color_by == "instance"
    assert config.colormap == "tab20"
    assert config.gain == 1.0
    assert config.bias == 0.0
    assert config.gamma == 1.0


def test_viewer_config_serialization():
    """Test config serialization to/from dict."""
    config = ViewerConfig(
        fps=30.0,
        color_by="node",
        gain=1.5,
        bias=0.2
    )
    
    # Test to_dict
    data = config.to_dict()
    assert data["fps"] == 30.0
    assert data["color_by"] == "node"
    assert data["gain"] == 1.5
    assert data["bias"] == 0.2
    
    # Test from_dict
    config2 = ViewerConfig.from_dict(data)
    assert config2.fps == 30.0
    assert config2.color_by == "node"
    assert config2.gain == 1.5
    assert config2.bias == 0.2
    
    # Test from_dict with extra keys (should be ignored)
    data["unknown_key"] = "value"
    config3 = ViewerConfig.from_dict(data)
    assert not hasattr(config3, "unknown_key")


def test_viewer_config_update():
    """Test updating config from dict."""
    config = ViewerConfig()
    
    config.update_from_dict({
        "fps": 60.0,
        "colormap": "hsv",
        "unknown_key": "ignored"
    })
    
    assert config.fps == 60.0
    assert config.colormap == "hsv"
    assert config.color_by == "instance"  # Unchanged


def test_config_manager_save_load():
    """Test saving and loading configurations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ConfigManager(Path(tmpdir))
        
        # Create and save a config
        config = ViewerConfig(fps=60.0, color_by="track")
        path = manager.save_config(config, name="test_config")
        
        assert path.exists()
        assert path.name == "test_config.json"
        
        # Load the config
        loaded = manager.load_config(name="test_config")
        assert loaded.fps == 60.0
        assert loaded.color_by == "track"
        
        # Load non-existent config (should return defaults)
        default = manager.load_config(name="nonexistent")
        assert default.fps == 25.0
        assert default.color_by == "instance"


def test_config_manager_default_config():
    """Test default config handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ConfigManager(Path(tmpdir))
        
        # Save as default (no name)
        config = ViewerConfig(gamma=2.0)
        path = manager.save_config(config)
        assert path.name == "default.json"
        
        # Load default (no name)
        loaded = manager.load_config()
        assert loaded.gamma == 2.0


def test_config_manager_list_configs():
    """Test listing available configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ConfigManager(Path(tmpdir))
        
        # Initially empty
        assert manager.list_configs() == []
        
        # Save some configs
        manager.save_config(ViewerConfig(), name="config1")
        manager.save_config(ViewerConfig(), name="config2")
        manager.save_config(ViewerConfig())  # default
        
        configs = manager.list_configs()
        assert "config1" in configs
        assert "config2" in configs
        assert "default" in configs
        assert len(configs) == 3


def test_config_manager_delete():
    """Test deleting configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ConfigManager(Path(tmpdir))
        
        # Save a config
        manager.save_config(ViewerConfig(), name="to_delete")
        assert "to_delete" in manager.list_configs()
        
        # Delete it
        assert manager.delete_config("to_delete") is True
        assert "to_delete" not in manager.list_configs()
        
        # Try to delete non-existent
        assert manager.delete_config("nonexistent") is False


def test_config_manager_export_import():
    """Test exporting and importing configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ConfigManager(Path(tmpdir))
        export_path = Path(tmpdir) / "exported.json"
        
        # Export a config
        config = ViewerConfig(loop=True, bias=0.5)
        manager.export_config(config, export_path)
        assert export_path.exists()
        
        # Import the config
        imported = manager.import_config(export_path)
        assert imported.loop is True
        assert imported.bias == 0.5


def test_config_manager_sanitize_names():
    """Test that config names are sanitized for filesystem."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ConfigManager(Path(tmpdir))
        
        # Save with unsafe characters
        config = ViewerConfig()
        path = manager.save_config(config, name="test/config:name*")
        
        # Should sanitize to safe name
        assert "/" not in path.name
        assert ":" not in path.name
        assert "*" not in path.name
        
        # Should be loadable with original name
        loaded = manager.load_config(name="test/config:name*")
        assert loaded is not None


def test_get_current_config():
    """Test extracting config from controller and visualizer."""
    # Create mock objects
    class MockController:
        play_fps = 30.0
        playback_speed = 2.0
        loop = True
        missing_frame_policy = "error"
        timeline_controller = None
    
    class MockVisualizer:
        gain = 1.5
        bias = 0.1
        gamma = 1.2
        tone_map = "lut"
        lut_mode = "histogram"
        lut_channel_mode = "rgb"
        lut_params = {"clip_limit": 3.0}
        width = 1920
        height = 1080
        
        class MockColorPolicy:
            color_by = "node"
            palette_name = "tab10"
            invisible_mode = "hide"
        
        color_policy = MockColorPolicy()
    
    controller = MockController()
    visualizer = MockVisualizer()
    
    config = get_current_config(controller, visualizer)
    
    assert config.fps == 30.0
    assert config.playback_speed == 2.0
    assert config.loop is True
    assert config.missing_frame_policy == "error"
    assert config.gain == 1.5
    assert config.bias == 0.1
    assert config.gamma == 1.2
    assert config.tone_map == "lut"
    assert config.lut_mode == "histogram"
    assert config.lut_channel_mode == "rgb"
    assert config.clahe_clip_limit == 3.0
    assert config.color_by == "node"
    assert config.colormap == "tab10"
    assert config.invisible_mode == "hide"
    assert config.window_width == 1920
    assert config.window_height == 1080


def test_apply_config():
    """Test applying config to controller and visualizer."""
    # Create mock objects
    class MockController:
        play_fps = 25.0
        playback_speed = 1.0
        loop = False
        missing_frame_policy = "blank"
        timeline_controller = None
    
    class MockVisualizer:
        gain = 1.0
        bias = 0.0
        gamma = 1.0
        tone_map = "linear"
        
        def set_color_policy(self, **kwargs):
            self.color_policy_args = kwargs
        
        def set_image_adjust(self, **kwargs):
            self.image_adjust_args = kwargs
        
        def draw(self):
            self.drawn = True
    
    controller = MockController()
    visualizer = MockVisualizer()
    
    # Apply a config
    config = ViewerConfig(
        fps=60.0,
        playback_speed=0.5,
        loop=True,
        missing_frame_policy="error",
        color_by="track",
        colormap="hsv",
        invisible_mode="hide",
        gain=2.0,
        bias=0.3,
        gamma=0.8,
        tone_map="lut",
        lut_mode="clahe",
        lut_channel_mode="luminance",
        clahe_clip_limit=4.0
    )
    
    apply_config(config, controller, visualizer)
    
    # Check controller settings
    assert controller.play_fps == 60.0
    assert controller.playback_speed == 0.5
    assert controller.loop is True
    assert controller.missing_frame_policy == "error"
    
    # Check visualizer calls
    assert visualizer.color_policy_args == {
        "color_by": "track",
        "colormap": "hsv",
        "invisible_mode": "hide"
    }
    
    assert visualizer.image_adjust_args["gain"] == 2.0
    assert visualizer.image_adjust_args["bias"] == 0.3
    assert visualizer.image_adjust_args["gamma"] == 0.8
    assert visualizer.image_adjust_args["tone_map"] == "lut"
    assert visualizer.image_adjust_args["lut_mode"] == "clahe"
    assert visualizer.image_adjust_args["lut_params"]["channel_mode"] == "luminance"
    assert visualizer.image_adjust_args["lut_params"]["clip_limit"] == 4.0
    
    assert visualizer.drawn is True