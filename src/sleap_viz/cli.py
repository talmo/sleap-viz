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
    "--style",
    type=str,
    default="instance",
    show_default=True,
    help="Color policy: instance|node|track|<meta>.",
)
@click.option(
    "--colormap",
    type=str,
    default="tab20",
    show_default=True,
    help="Palette: tab10|tab20|brewer_*|hsv|...",
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
@click.version_option(package_name="sleap-viz")
def main(
    labels_path: Path,
    fps: float,
    video_index: int,
    offscreen: bool,
    debug: bool,
    style: str,
    colormap: str,
    gain: float,
    bias: float,
    gamma: float,
    tone_map: str,
    lut: str | None,
) -> None:
    """Run the sleap-viz viewer on a SLEAP .slp file.

    Args:
        labels_path: Path to the `.slp` file.
        fps: Playback FPS (default 25).
        video_index: Which video in the labels to open.
        offscreen: If True, run an offscreen renderer (headless).
        debug: If True, enable debug logging.
        style: Color policy name.
        colormap: Palette name.
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
    from .controller import Controller
    from .renderer import Visualizer
    from .video_source import VideoSource

    labels = sio.load_slp(str(labels_path), open_videos=True)
    try:
        video = labels.videos[video_index]
    except Exception as exc:
        _eprint(f"[sleap-viz] Invalid --video-index {video_index}: {exc}")
        raise SystemExit(2) from exc

    anno = AnnotationSource(labels)
    vs = VideoSource(video)
    vis = Visualizer(
        width=1280, height=720, mode="offscreen" if offscreen else "desktop"
    )

    # Apply initial style/image settings.
    vis.set_color_policy(color_by=style, colormap=colormap, invisible_mode="dim")
    vis.set_image_adjust(gain=gain, bias=bias, gamma=gamma, tone_map=tone_map)

    controller = Controller(vs, anno, vis, video, play_fps=fps)

    # For MVP, just seek to frame 0 and draw once (interactive loop TBD).
    import asyncio

    async def _run() -> None:
        await controller.goto(0)
        vis.draw()
        if offscreen:
            arr = vis.read_pixels()
            _eprint(f"[sleap-viz] Rendered one frame offscreen: shape={arr.shape}")
        else:
            _eprint("[sleap-viz] Interactive viewer not yet implemented (MVP stub).")

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    main()
