"""Look-up table (LUT) generation for tone mapping.

This module provides functions to generate various tone mapping LUTs including
histogram equalization and CLAHE (Contrast Limited Adaptive Histogram Equalization).
"""

from __future__ import annotations

import numpy as np
from typing import Literal


def generate_identity_lut() -> np.ndarray:
    """Generate an identity LUT (no transformation).
    
    Returns:
        A 256x3 uint8 array where output = input.
    """
    lut = np.arange(256, dtype=np.uint8)
    return np.stack([lut, lut, lut], axis=-1)


def generate_histogram_equalization_lut(
    image: np.ndarray,
    channel_mode: Literal["rgb", "luminance"] = "luminance"
) -> np.ndarray:
    """Generate a LUT for histogram equalization.
    
    Args:
        image: Input image as uint8 array with shape (H, W, 3).
        channel_mode: Whether to equalize each RGB channel independently
            or use luminance-based equalization.
    
    Returns:
        A 256x3 uint8 LUT for tone mapping.
    """
    if image.dtype != np.uint8:
        # Convert to uint8 if needed
        image = np.clip(image * 255, 0, 255).astype(np.uint8)
    
    if channel_mode == "rgb":
        # Equalize each channel independently
        lut = np.zeros((256, 3), dtype=np.uint8)
        for c in range(3):
            hist, bins = np.histogram(image[:, :, c].flatten(), 256, [0, 256])
            cdf = hist.cumsum()
            cdf_normalized = cdf * 255 / cdf[-1]  # Normalize to 0-255
            lut[:, c] = cdf_normalized.astype(np.uint8)
    else:
        # Convert to grayscale for luminance-based equalization
        gray = np.dot(image, [0.299, 0.587, 0.114]).astype(np.uint8)
        hist, bins = np.histogram(gray.flatten(), 256, [0, 256])
        cdf = hist.cumsum()
        cdf_normalized = cdf * 255 / cdf[-1]
        
        # Apply same mapping to all channels
        lut_1d = cdf_normalized.astype(np.uint8)
        lut = np.stack([lut_1d, lut_1d, lut_1d], axis=-1)
    
    return lut


def generate_clahe_lut(
    image: np.ndarray,
    clip_limit: float = 2.0,
    grid_size: tuple[int, int] = (8, 8),
    channel_mode: Literal["rgb", "luminance"] = "luminance"
) -> np.ndarray:
    """Generate a LUT using CLAHE (Contrast Limited Adaptive Histogram Equalization).
    
    Note: This is a simplified version that computes global CLAHE. True adaptive
    CLAHE would require per-pixel computation which isn't suitable for LUT-based
    implementation. For full adaptive CLAHE, consider using OpenCV or scikit-image.
    
    Args:
        image: Input image as uint8 array with shape (H, W, 3).
        clip_limit: Threshold for contrast limiting. Higher values give more contrast.
        grid_size: Size of grid for histogram equalization (not used in simplified version).
        channel_mode: Whether to apply CLAHE to each RGB channel independently
            or use luminance-based processing.
    
    Returns:
        A 256x3 uint8 LUT for tone mapping.
    """
    if image.dtype != np.uint8:
        image = np.clip(image * 255, 0, 255).astype(np.uint8)
    
    def apply_clahe_1d(channel: np.ndarray, clip_limit: float) -> np.ndarray:
        """Apply CLAHE to a single channel."""
        hist, bins = np.histogram(channel.flatten(), 256, [0, 256])
        
        # Clip histogram
        clip_threshold = clip_limit * channel.size / 256
        excess = 0
        for i in range(256):
            if hist[i] > clip_threshold:
                excess += hist[i] - clip_threshold
                hist[i] = clip_threshold
        
        # Redistribute excess evenly
        avg_excess = int(excess // 256)
        hist = hist.astype(np.float64)  # Convert to float for adding
        hist += avg_excess
        hist = hist.astype(np.int64)  # Convert back to int
        
        # Build CDF and normalize
        cdf = hist.cumsum()
        cdf_normalized = cdf * 255 / cdf[-1]
        
        return cdf_normalized.astype(np.uint8)
    
    if channel_mode == "rgb":
        # Apply CLAHE to each channel independently
        lut = np.zeros((256, 3), dtype=np.uint8)
        for c in range(3):
            lut[:, c] = apply_clahe_1d(image[:, :, c], clip_limit)
    else:
        # Convert to grayscale for luminance-based CLAHE
        gray = np.dot(image, [0.299, 0.587, 0.114]).astype(np.uint8)
        lut_1d = apply_clahe_1d(gray, clip_limit)
        lut = np.stack([lut_1d, lut_1d, lut_1d], axis=-1)
    
    return lut


def generate_gamma_lut(gamma: float = 2.2) -> np.ndarray:
    """Generate a LUT for gamma correction.
    
    Args:
        gamma: Gamma value. Values > 1 darken the image, < 1 brighten it.
    
    Returns:
        A 256x3 uint8 LUT for gamma correction.
    """
    # Generate gamma curve
    # Note: gamma > 1 should darken, so we use gamma (not 1/gamma)
    lut_1d = np.array(
        [((i / 255.0) ** gamma) * 255 for i in range(256)]
    ).astype(np.uint8)
    
    return np.stack([lut_1d, lut_1d, lut_1d], axis=-1)


def generate_sigmoid_lut(midpoint: float = 0.5, slope: float = 10.0) -> np.ndarray:
    """Generate a LUT for sigmoid (S-curve) tone mapping.
    
    Args:
        midpoint: Center point of the sigmoid curve (0-1).
        slope: Steepness of the curve. Higher values create sharper transitions.
    
    Returns:
        A 256x3 uint8 LUT for sigmoid tone mapping.
    """
    x = np.linspace(0, 1, 256)
    y = 1 / (1 + np.exp(-slope * (x - midpoint)))
    
    # Normalize to 0-255 range
    y = (y - y.min()) / (y.max() - y.min())
    lut_1d = (y * 255).astype(np.uint8)
    
    return np.stack([lut_1d, lut_1d, lut_1d], axis=-1)


def combine_luts(lut1: np.ndarray, lut2: np.ndarray) -> np.ndarray:
    """Combine two LUTs by applying the second to the output of the first.
    
    Args:
        lut1: First LUT to apply.
        lut2: Second LUT to apply.
    
    Returns:
        Combined LUT that performs both transformations.
    """
    combined = np.zeros((256, 3), dtype=np.uint8)
    for c in range(3):
        for i in range(256):
            intermediate = lut1[i, c]
            combined[i, c] = lut2[intermediate, c]
    return combined