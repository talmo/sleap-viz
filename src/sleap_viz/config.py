"""Configuration management for sleap-viz viewer settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict, field


@dataclass
class ViewerConfig:
    """Configuration for viewer settings.
    
    All viewer settings that can be persisted and restored.
    """
    
    # Playback settings
    fps: float = 25.0
    playback_speed: float = 1.0
    loop: bool = False
    
    # Color policy settings
    color_by: str = "instance"  # instance|node|track
    colormap: str = "tab20"  # tab10|tab20|hsv
    invisible_mode: str = "dim"  # dim|hide
    
    # Image adjustment settings
    gain: float = 1.0
    bias: float = 0.0
    gamma: float = 1.0
    
    # Tone mapping settings
    tone_map: str = "linear"  # linear|lut
    lut_mode: str = "none"  # none|histogram|clahe|gamma|sigmoid
    lut_channel_mode: str = "luminance"  # rgb|luminance
    clahe_clip_limit: float = 2.0
    sigmoid_midpoint: float = 0.5
    sigmoid_slope: float = 10.0
    
    # Timeline settings
    timeline_zoom: float = 1.0
    timeline_visible_start: int = 0
    timeline_visible_end: Optional[int] = None
    
    # Annotation settings
    missing_frame_policy: str = "blank"  # error|blank
    
    # Window settings (optional)
    window_width: Optional[int] = None
    window_height: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ViewerConfig:
        """Create config from dictionary."""
        # Filter out any unknown keys
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update config values from dictionary."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


class ConfigManager:
    """Manage loading and saving viewer configurations."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config manager.
        
        Args:
            config_dir: Directory for config files. Defaults to ~/.sleap-viz/
        """
        if config_dir is None:
            config_dir = Path.home() / ".sleap-viz"
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.default_config_path = self.config_dir / "default.json"
        
    def save_config(
        self, 
        config: ViewerConfig, 
        name: Optional[str] = None,
        path: Optional[Path] = None
    ) -> Path:
        """Save configuration to file.
        
        Args:
            config: Configuration to save.
            name: Name for the config (without extension). 
                  If None, saves as "default".
            path: Full path to save to. Overrides name if provided.
            
        Returns:
            Path where config was saved.
        """
        if path is None:
            if name is None:
                path = self.default_config_path
            else:
                # Sanitize name to be filesystem-safe
                safe_name = "".join(c for c in name if c.isalnum() or c in "-_")
                path = self.config_dir / f"{safe_name}.json"
        else:
            path = Path(path)
            
        # Save config as JSON
        with open(path, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
            
        return path
    
    def load_config(
        self, 
        name: Optional[str] = None,
        path: Optional[Path] = None
    ) -> ViewerConfig:
        """Load configuration from file.
        
        Args:
            name: Name of the config to load (without extension).
                  If None, loads "default" if it exists.
            path: Full path to load from. Overrides name if provided.
            
        Returns:
            Loaded configuration, or default config if file doesn't exist.
        """
        if path is None:
            if name is None:
                path = self.default_config_path
            else:
                safe_name = "".join(c for c in name if c.isalnum() or c in "-_")
                path = self.config_dir / f"{safe_name}.json"
        else:
            path = Path(path)
            
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
                return ViewerConfig.from_dict(data)
        else:
            # Return default config if file doesn't exist
            return ViewerConfig()
    
    def list_configs(self) -> list[str]:
        """List available saved configurations.
        
        Returns:
            List of config names (without extensions).
        """
        configs = []
        for path in self.config_dir.glob("*.json"):
            configs.append(path.stem)
        return sorted(configs)
    
    def delete_config(self, name: str) -> bool:
        """Delete a saved configuration.
        
        Args:
            name: Name of config to delete (without extension).
            
        Returns:
            True if deleted, False if didn't exist.
        """
        safe_name = "".join(c for c in name if c.isalnum() or c in "-_")
        path = self.config_dir / f"{safe_name}.json"
        if path.exists():
            path.unlink()
            return True
        return False
    
    def export_config(self, config: ViewerConfig, path: Path) -> None:
        """Export configuration to a specific path.
        
        Args:
            config: Configuration to export.
            path: Path to export to.
        """
        path = Path(path)
        with open(path, "w") as f:
            json.dump(config.to_dict(), f, indent=2)
    
    def import_config(self, path: Path) -> ViewerConfig:
        """Import configuration from a specific path.
        
        Args:
            path: Path to import from.
            
        Returns:
            Imported configuration.
        """
        path = Path(path)
        with open(path, "r") as f:
            data = json.load(f)
            return ViewerConfig.from_dict(data)


def get_current_config(controller, visualizer) -> ViewerConfig:
    """Extract current configuration from controller and visualizer.
    
    Args:
        controller: Controller instance.
        visualizer: Visualizer instance.
        
    Returns:
        Current viewer configuration.
    """
    config = ViewerConfig()
    
    # Get playback settings from controller
    config.fps = controller.play_fps
    config.playback_speed = controller.playback_speed
    config.loop = controller.loop
    config.missing_frame_policy = controller.missing_frame_policy
    
    # Get image settings from visualizer
    config.gain = visualizer.gain
    config.bias = visualizer.bias
    config.gamma = visualizer.gamma
    config.tone_map = visualizer.tone_map
    
    # Get LUT settings if available
    if hasattr(visualizer, "lut_mode"):
        config.lut_mode = visualizer.lut_mode
    if hasattr(visualizer, "lut_channel_mode"):
        config.lut_channel_mode = visualizer.lut_channel_mode
    if hasattr(visualizer, "lut_params"):
        params = visualizer.lut_params or {}
        config.clahe_clip_limit = params.get("clip_limit", 2.0)
        config.sigmoid_midpoint = params.get("midpoint", 0.5)
        config.sigmoid_slope = params.get("slope", 10.0)
    
    # Get color policy settings
    if hasattr(visualizer, "color_policy") and visualizer.color_policy:
        config.color_by = visualizer.color_policy.color_by
        config.colormap = visualizer.color_policy.palette_name
        config.invisible_mode = visualizer.color_policy.invisible_mode
    
    # Get timeline settings if available
    if hasattr(controller, "timeline_controller") and controller.timeline_controller:
        timeline_model = controller.timeline_controller.model
        config.timeline_zoom = timeline_model.zoom_level
        config.timeline_visible_start = timeline_model.visible_start
        config.timeline_visible_end = timeline_model.visible_end
    
    # Get window dimensions if available
    if hasattr(visualizer, "width"):
        config.window_width = visualizer.width
    if hasattr(visualizer, "height"):
        config.window_height = visualizer.height
    
    return config


def apply_config(config: ViewerConfig, controller, visualizer) -> None:
    """Apply configuration to controller and visualizer.
    
    Args:
        config: Configuration to apply.
        controller: Controller instance.
        visualizer: Visualizer instance.
    """
    # Apply playback settings
    controller.play_fps = config.fps
    controller.playback_speed = config.playback_speed
    controller.loop = config.loop
    controller.missing_frame_policy = config.missing_frame_policy
    
    # Apply color policy
    visualizer.set_color_policy(
        color_by=config.color_by,
        colormap=config.colormap,
        invisible_mode=config.invisible_mode
    )
    
    # Apply image adjustments and tone mapping
    lut_params = {}
    if config.lut_mode in ["histogram", "clahe"]:
        lut_params["channel_mode"] = config.lut_channel_mode
    if config.lut_mode == "clahe":
        lut_params["clip_limit"] = config.clahe_clip_limit
    if config.lut_mode == "sigmoid":
        lut_params["midpoint"] = config.sigmoid_midpoint
        lut_params["slope"] = config.sigmoid_slope
    
    visualizer.set_image_adjust(
        gain=config.gain,
        bias=config.bias,
        gamma=config.gamma,
        tone_map=config.tone_map,
        lut_mode=config.lut_mode,
        lut_params=lut_params
    )
    
    # Apply timeline settings if available
    if hasattr(controller, "timeline_controller") and controller.timeline_controller:
        timeline_model = controller.timeline_controller.model
        timeline_model.zoom_level = config.timeline_zoom
        if config.timeline_visible_end is not None:
            timeline_model.visible_start = config.timeline_visible_start
            timeline_model.visible_end = config.timeline_visible_end
    
    # Redraw with new settings
    visualizer.draw()