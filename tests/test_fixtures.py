"""Test that fixtures load correctly."""

import sleap_io as sio
from pathlib import Path


def test_labels_v002_path_fixture(labels_v002_path):
    """Test labels_v002_path fixture returns valid path."""
    assert isinstance(labels_v002_path, Path)
    assert labels_v002_path.exists()
    assert labels_v002_path.suffix == ".slp"


def test_centered_pair_predictions_path_fixture(centered_pair_predictions_path):
    """Test centered_pair_predictions_path fixture returns valid path."""
    assert isinstance(centered_pair_predictions_path, Path)
    assert centered_pair_predictions_path.exists()
    assert centered_pair_predictions_path.suffix == ".slp"


def test_centered_pair_video_path_fixture(centered_pair_video_path):
    """Test centered_pair_video_path fixture returns valid path."""
    assert isinstance(centered_pair_video_path, Path)
    assert centered_pair_video_path.exists()
    assert centered_pair_video_path.suffix == ".mp4"


def test_labels_v002_fixture(labels_v002):
    """Test labels_v002 fixture loads correctly."""
    assert isinstance(labels_v002, sio.Labels)
    assert len(labels_v002) == 10
    assert len(labels_v002.videos) == 1
    assert len(labels_v002.skeletons) == 1
    assert len(labels_v002.skeletons[0].nodes) == 2
    
    # Test video access
    img = labels_v002.videos[0][0]
    assert img.shape == (384, 384, 1)


def test_centered_pair_predictions_fixture(centered_pair_predictions):
    """Test centered_pair_predictions fixture loads correctly."""
    assert isinstance(centered_pair_predictions, sio.Labels)
    assert len(centered_pair_predictions) == 1100
    assert len(centered_pair_predictions.videos) == 1
    assert len(centered_pair_predictions.skeletons) == 1
    assert len(centered_pair_predictions.skeletons[0].nodes) == 24
    assert len(centered_pair_predictions.tracks) == 27
    
    # Test video access
    img = centered_pair_predictions.videos[0][0]
    assert img.shape == (384, 384, 1)
    
    # Test that frames have 2 instances (paired flies)
    first_frame = centered_pair_predictions[0]
    assert len(first_frame.instances) == 2