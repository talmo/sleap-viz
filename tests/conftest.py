"""Pytest fixtures for sleap-viz tests."""

from pathlib import Path
import pytest


@pytest.fixture
def labels_v002_path():
    """Path to minimal labels file with relative video paths.

    This file contains:
    - 10 labeled frames from a 1100 frame video
    - Video: 384x384 grayscale (1 channel)
    - Skeleton: 2 nodes (head, abdomen) with 1 edge
    - No tracks (single instance per frame)
    - Video backend: MediaVideo with relative paths
    """
    return Path("tests/fixtures/labels.v002.rel_paths.slp")


@pytest.fixture
def centered_pair_predictions_path():
    """Path to predictions file with centered pair tracking.

    This file contains:
    - 1100 labeled frames (full video coverage)
    - Video: 384x384 grayscale (1 channel), 1100 frames
    - Skeleton: 24 nodes (full fly anatomy) with 23 edges
        - Body parts: head, neck, thorax, abdomen
        - Wings: wingL, wingR
        - Legs: forelegL/R (1-3), midlegL/R (1-3), hindlegL/R (1-3)
    - 27 tracks with 2 instances per frame (paired flies)
    - Video backend: MediaVideo
    - Generated from SLEAP predictions with tracking
    """
    return Path("tests/fixtures/centered_pair_predictions.slp")


@pytest.fixture
def centered_pair_video_path():
    """Path to low quality video file for centered pair.

    This MP4 video file:
    - Corresponds to the centered_pair SLP files
    - Low quality encoding for small file size
    - 384x384 resolution
    - Grayscale video of paired flies
    """
    return Path("tests/fixtures/centered_pair_low_quality.mp4")


@pytest.fixture
def labels_v002(labels_v002_path):
    """Load labels.v002.rel_paths.slp as a Labels object.

    Returns a sleap_io.Labels object with minimal skeleton and sparse annotations.
    """
    import sleap_io as sio
    return sio.load_slp(labels_v002_path)


@pytest.fixture
def centered_pair_predictions(centered_pair_predictions_path):
    """Load centered_pair_predictions.slp as a Labels object.

    Returns a sleap_io.Labels object with full fly skeleton and dense predictions.
    """
    import sleap_io as sio
    return sio.load_slp(centered_pair_predictions_path)