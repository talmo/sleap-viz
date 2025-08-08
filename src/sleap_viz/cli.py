"""Command-line interface for sleap-viz.

Entry point: `sleap-viz labels.slp [OPTIONS]`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

# Lazy imports to improve startup time.


def _eprint(msg: str) -> None:
    """Print to stderr.

    Args:
        msg: Message to print.
    """
    print(msg, file=sys.stderr)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "labels_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--fps", type=float, default=25.0, show_default=True, help="Playback FPS."
)
@click.option(
    "--video-index",
    type=int,
    default=0,
    show_default=True,
    help="Which video in the .slp to open.",
)
@click.option(
    "--offscreen",
    is_flag=True,
    help="Run headless renderer (no window); useful for testing.",
)
@click.option("--debug", is_flag=True, help="Enable debug logging.")
@click.option(
    "--color-by",
    type=click.Choice(["instance", "node", "track"]),
    default="instance",
    show_default=True,
    help="Color policy: instance|node|track.",
)
@click.option(
    "--colormap",
    type=click.Choice(["tab10", "tab20", "hsv"]),
    default="tab20",
    show_default=True,
    help="Color palette for overlays.",
)
@click.option(
    "--gain", type=float, default=1.0, show_default=True, help="Contrast gain."
)
@click.option(
    "--bias",
    type=float,
    default=0.0,
    show_default=True,
    help="Brightness bias (-1..+1).",
)
@click.option(
    "--gamma", type=float, default=1.0, show_default=True, help="Gamma correction."
)
@click.option(
    "--tone-map",
    type=click.Choice(["linear", "lut"]),
    default="linear",
    show_default=True,
)
@click.option(
    "--lut",
    type=click.Path(exists=True, dir_okay=False),
    help="Optional LUT (.npy 256x3 uint8) for tone mapping.",
)
@click.option(
    "--lut-mode",
    type=click.Choice(["none", "histogram", "clahe", "gamma", "sigmoid"]),
    default="none",
    show_default=True,
    help="LUT generation mode for tone mapping.",
)
@click.option(
    "--lut-channel-mode",
    type=click.Choice(["rgb", "luminance"]),
    default="luminance",
    show_default=True,
    help="Channel mode for histogram/CLAHE tone mapping.",
)
@click.option(
    "--clahe-clip-limit",
    type=float,
    default=2.0,
    show_default=True,
    help="Clip limit for CLAHE tone mapping.",
)
@click.option(
    "--sigmoid-midpoint",
    type=float,
    default=0.5,
    show_default=True,
    help="Midpoint for sigmoid tone mapping (0-1).",
)
@click.option(
    "--sigmoid-slope",
    type=float,
    default=10.0,
    show_default=True,
    help="Slope for sigmoid tone mapping.",
)
@click.option(
    "--missing-frame-policy",
    type=click.Choice(["error", "blank"]),
    default="blank",
    show_default=True,
    help="Policy for frames without annotations: error or blank.",
)
@click.option(
    "--load-config",
    type=str,
    help="Load viewer settings from config (name or path to .json file).",
)
@click.option(
    "--save-config",
    type=str,
    help="Save current viewer settings to config (name or path to .json file).",
)
@click.version_option(package_name="sleap-viz")
def main(
    labels_path: Path,
    fps: float,
    video_index: int,
    offscreen: bool,
    debug: bool,
    color_by: str,
    colormap: str,
    gain: float,
    bias: float,
    gamma: float,
    tone_map: str,
    lut: str | None,
    lut_mode: str,
    lut_channel_mode: str,
    clahe_clip_limit: float,
    sigmoid_midpoint: float,
    sigmoid_slope: float,
    missing_frame_policy: str,
    load_config: str | None,
    save_config: str | None,
) -> None:
    """Run the sleap-viz viewer on a SLEAP .slp file.

    Args:
        labels_path: Path to the `.slp` file.
        fps: Playback FPS (default 25).
        video_index: Which video in the labels to open.
        offscreen: If True, run an offscreen renderer (headless).
        debug: If True, enable debug logging.
        color_by: Color policy (instance|node|track).
        colormap: Color palette (tab10|tab20|hsv).
        gain: Contrast gain multiplier.
        bias: Brightness bias.
        gamma: Gamma correction.
        tone_map: Tone mapping mode (linear or lut).
        lut: Optional path to a `.npy` 256x3 uint8 LUT.
    """
    try:
        import sleap_io as sio  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        _eprint(f"[sleap-viz] Missing dependency: {exc}")
        raise SystemExit(2) from exc

    # Lazy import our modules to keep CLI startup quick.
    from .annotation_source import AnnotationSource
    from .config import ConfigManager, ViewerConfig, get_current_config, apply_config
    from .controller import Controller
    from .interactive import InteractiveControls
    from .renderer import Visualizer
    from .timeline import TimelineModel, TimelineView, TimelineController
    from .video_source import VideoSource

    import asyncio
    from pathlib import Path

    async def _run() -> None:
        # Use nonlocal to access outer scope variables
        nonlocal fps, color_by, colormap, gain, bias, gamma, tone_map, lut_mode
        nonlocal lut_channel_mode, clahe_clip_limit, sigmoid_midpoint, sigmoid_slope
        nonlocal missing_frame_policy
        
        labels = sio.load_slp(str(labels_path), open_videos=True)
        try:
            video = labels.videos[video_index]
        except Exception as exc:
            _eprint(f"[sleap-viz] Invalid --video-index {video_index}: {exc}")
            raise SystemExit(2) from exc

        anno = AnnotationSource(labels)
        vs = VideoSource(video)
        
        # Get video dimensions
        width = video.backend.shape[2] if len(video.backend.shape) > 2 else 640
        height = video.backend.shape[1] if len(video.backend.shape) > 1 else 480
        
        vis = Visualizer(
            width=width, height=height, mode="offscreen" if offscreen else "desktop",
            timeline_height=50
        )
        
        # Create timeline components
        timeline_model = TimelineModel(len(video))
        timeline_view = TimelineView(width=width, height=50)
        timeline_controller = TimelineController(timeline_model, timeline_view)
        
        # Set annotation source for timeline
        timeline_controller.set_annotation_source(anno)
        
        # Connect timeline to visualizer
        vis.set_timeline(timeline_view)
        
        # Load config if specified
        config_manager = ConfigManager()
        if load_config:
            # Check if it's a path or a name
            if load_config.endswith(".json"):
                config_path = Path(load_config)
                viewer_config = config_manager.import_config(config_path) if config_path.exists() else ViewerConfig()
            else:
                viewer_config = config_manager.load_config(name=load_config)
            
            # Override CLI parameters with config values
            fps = viewer_config.fps
            color_by = viewer_config.color_by
            colormap = viewer_config.colormap
            gain = viewer_config.gain
            bias = viewer_config.bias
            gamma = viewer_config.gamma
            tone_map = viewer_config.tone_map
            lut_mode = viewer_config.lut_mode
            lut_channel_mode = viewer_config.lut_channel_mode
            clahe_clip_limit = viewer_config.clahe_clip_limit
            sigmoid_midpoint = viewer_config.sigmoid_midpoint
            sigmoid_slope = viewer_config.sigmoid_slope
            missing_frame_policy = viewer_config.missing_frame_policy
            
            _eprint(f"[sleap-viz] Loaded config from: {load_config}")

        # Apply initial style/image settings.
        vis.set_color_policy(color_by=color_by, colormap=colormap, invisible_mode="dim")
        
        # Build LUT parameters based on mode
        lut_params = {}
        if lut_mode in ["histogram", "clahe"]:
            lut_params["channel_mode"] = lut_channel_mode
        if lut_mode == "clahe":
            lut_params["clip_limit"] = clahe_clip_limit
        if lut_mode == "sigmoid":
            lut_params["midpoint"] = sigmoid_midpoint
            lut_params["slope"] = sigmoid_slope
        
        # Load LUT from file if provided
        lut_array = None
        if lut:
            import numpy as np
            lut_array = np.load(lut)
        
        vis.set_image_adjust(
            gain=gain, 
            bias=bias, 
            gamma=gamma, 
            tone_map=tone_map,
            lut=lut_array,
            lut_mode=lut_mode,
            lut_params=lut_params
        )

        controller = Controller(vs, anno, vis, video, play_fps=fps, missing_frame_policy=missing_frame_policy)
        
        # Connect controller to timeline
        controller.timeline_controller = timeline_controller

        # Seek to frame 0 initially
        await controller.goto(0)
        
        # Update timeline for initial frame
        timeline_controller.set_current_frame(0)
        await timeline_controller._update_timeline()
        
        vis.draw()
        
        # Save config if specified
        if save_config:
            current_config = get_current_config(controller, vis)
            # Check if it's a path or a name
            if save_config.endswith(".json"):
                config_path = Path(save_config)
                config_manager.export_config(current_config, config_path)
                _eprint(f"[sleap-viz] Saved config to: {config_path}")
            else:
                saved_path = config_manager.save_config(current_config, name=save_config)
                _eprint(f"[sleap-viz] Saved config to: {saved_path}")
        
        if offscreen:
            arr = vis.read_pixels()
            _eprint(f"[sleap-viz] Rendered one frame offscreen: shape={arr.shape}")
        else:
            # Set up interactive controls
            controls = InteractiveControls(controller, vis.canvas)
            controls.attach_handlers()
            
            # Set up quit callback
            stop_event = asyncio.Event()
            controls.set_quit_callback(lambda: stop_event.set())
            
            _eprint("[sleap-viz] Interactive viewer ready. Press 'h' for help or 'q' to quit.")
            _eprint("Controls: Space=play/pause, Arrows=navigate, 0-9=speed, L=loop")
            _eprint("Image adjustments: B=brightness, C=contrast, G=gamma, R=reset")
            _eprint("Tone mapping: T=toggle, Shift+H=histogram, E=CLAHE, M=cycle modes")
            _eprint("Config: Ctrl+Shift+F=save, Ctrl+Shift+O=load")
            
            # Keep running until quit is requested or window is closed
            while not stop_event.is_set():
                # Check if window was closed
                if vis.canvas.is_closed():
                    _eprint("[sleap-viz] Window closed.")
                    break
                # Small sleep to prevent busy waiting
                await asyncio.sleep(0.1)
            
            # Clean up
            await controller.stop()
            controls.detach_handlers()
            _eprint("[sleap-viz] Viewer closed.")

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    main()
