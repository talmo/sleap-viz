"""Tests for LUT (Look-up Table) tone mapping functionality."""

from __future__ import annotations

import numpy as np
import pytest
from sleap_viz import lut


def test_identity_lut():
    """Test that identity LUT performs no transformation."""
    identity = lut.generate_identity_lut()
    
    # Check shape
    assert identity.shape == (256, 3)
    assert identity.dtype == np.uint8
    
    # Check that it's an identity mapping
    for i in range(256):
        assert np.all(identity[i] == i)


def test_histogram_equalization_lut():
    """Test histogram equalization LUT generation."""
    # Create a low-contrast test image
    test_image = np.full((100, 100, 3), 128, dtype=np.uint8)
    # Add some variation
    test_image[25:75, 25:75] = 140
    test_image[40:60, 40:60] = 100
    
    # Test luminance mode
    lut_lum = lut.generate_histogram_equalization_lut(test_image, channel_mode="luminance")
    assert lut_lum.shape == (256, 3)
    assert lut_lum.dtype == np.uint8
    # All channels should be the same for luminance mode
    assert np.allclose(lut_lum[:, 0], lut_lum[:, 1])
    assert np.allclose(lut_lum[:, 1], lut_lum[:, 2])
    
    # Test RGB mode
    lut_rgb = lut.generate_histogram_equalization_lut(test_image, channel_mode="rgb")
    assert lut_rgb.shape == (256, 3)
    assert lut_rgb.dtype == np.uint8


def test_clahe_lut():
    """Test CLAHE LUT generation."""
    # Create a test image with varying contrast
    test_image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    
    # Test with default parameters
    lut_clahe = lut.generate_clahe_lut(test_image)
    assert lut_clahe.shape == (256, 3)
    assert lut_clahe.dtype == np.uint8
    
    # Test with custom clip limit
    lut_clahe_custom = lut.generate_clahe_lut(test_image, clip_limit=4.0)
    assert lut_clahe_custom.shape == (256, 3)
    # Different clip limits should produce different LUTs
    assert not np.array_equal(lut_clahe, lut_clahe_custom)
    
    # Test RGB mode
    lut_clahe_rgb = lut.generate_clahe_lut(test_image, channel_mode="rgb")
    assert lut_clahe_rgb.shape == (256, 3)


def test_gamma_lut():
    """Test gamma correction LUT generation."""
    # Test gamma > 1 (darkening)
    lut_dark = lut.generate_gamma_lut(gamma=2.2)
    assert lut_dark.shape == (256, 3)
    assert lut_dark.dtype == np.uint8
    # Middle values should be darker
    assert lut_dark[128, 0] < 128
    
    # Test gamma < 1 (brightening)
    lut_bright = lut.generate_gamma_lut(gamma=0.5)
    assert lut_bright.shape == (256, 3)
    # Middle values should be brighter
    assert lut_bright[128, 0] > 128
    
    # Test gamma = 1 (no change)
    lut_neutral = lut.generate_gamma_lut(gamma=1.0)
    # Should be close to identity
    for i in range(256):
        assert abs(lut_neutral[i, 0] - i) <= 1


def test_sigmoid_lut():
    """Test sigmoid tone mapping LUT generation."""
    # Test default sigmoid
    lut_sigmoid = lut.generate_sigmoid_lut()
    assert lut_sigmoid.shape == (256, 3)
    assert lut_sigmoid.dtype == np.uint8
    
    # Test with different midpoint
    lut_low = lut.generate_sigmoid_lut(midpoint=0.3)
    lut_high = lut.generate_sigmoid_lut(midpoint=0.7)
    # Different midpoints should produce different curves
    assert not np.array_equal(lut_low, lut_high)
    
    # Test with different slope
    lut_gentle = lut.generate_sigmoid_lut(slope=5.0)
    lut_steep = lut.generate_sigmoid_lut(slope=20.0)
    # Different slopes should produce different curves
    assert not np.array_equal(lut_gentle, lut_steep)


def test_combine_luts():
    """Test combining multiple LUTs."""
    # Create two simple LUTs
    lut1 = lut.generate_gamma_lut(gamma=1.5)
    lut2 = lut.generate_gamma_lut(gamma=0.8)
    
    # Combine them
    combined = lut.combine_luts(lut1, lut2)
    assert combined.shape == (256, 3)
    assert combined.dtype == np.uint8
    
    # Test that combining identity with another LUT gives the same LUT
    identity = lut.generate_identity_lut()
    gamma_lut = lut.generate_gamma_lut(gamma=2.0)
    combined_identity = lut.combine_luts(identity, gamma_lut)
    assert np.allclose(combined_identity, gamma_lut, atol=1)


def test_lut_with_float_image():
    """Test LUT generation with float input images."""
    # Create a float test image
    test_image_float = np.random.rand(50, 50, 3).astype(np.float32)
    
    # Test histogram equalization
    lut_hist = lut.generate_histogram_equalization_lut(test_image_float)
    assert lut_hist.shape == (256, 3)
    
    # Test CLAHE
    lut_clahe = lut.generate_clahe_lut(test_image_float)
    assert lut_clahe.shape == (256, 3)


def test_lut_edge_cases():
    """Test LUT generation with edge case inputs."""
    # Test with all black image
    black_image = np.zeros((50, 50, 3), dtype=np.uint8)
    lut_black = lut.generate_histogram_equalization_lut(black_image)
    assert lut_black.shape == (256, 3)
    
    # Test with all white image
    white_image = np.full((50, 50, 3), 255, dtype=np.uint8)
    lut_white = lut.generate_histogram_equalization_lut(white_image)
    assert lut_white.shape == (256, 3)
    
    # Test with single color image
    single_color = np.full((50, 50, 3), 128, dtype=np.uint8)
    lut_single = lut.generate_clahe_lut(single_color)
    assert lut_single.shape == (256, 3)