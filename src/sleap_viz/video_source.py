"""Async, prefetching adapter over `sio.Video` for low-latency scrubbing."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np
import sleap_io as sio


@dataclass
class Frame:
    """Container for a decoded frame.

    Attributes:
        index: Frame index within the video.
        rgb: Image data, H x W x 3 uint8 RGB.
        size: (width, height) in pixels.
    """

    index: int
    rgb: np.ndarray
    size: tuple[int, int]


class VideoSource:
    """Random-access, prefetching frame provider backed by `sio.Video`.

    Long operations (decode/I/O) run in background tasks; UI thread remains non-blocking.
    """

    def __init__(self, video: sio.Video, cache_size: int = 64) -> None:
        """Initialize the video source.

        Args:
            video: A `sio.Video` instance.
            cache_size: Max number of frames to cache in-memory.
        """
        self.video = video
        self.cache_size = cache_size
        self._cache: dict[int, Frame] = {}
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._task = asyncio.create_task(self._worker())
        self._latest_request: int | None = None  # Track most recent request for cancellation

    async def _worker(self) -> None:
        """Background task that decodes requested frames into the cache."""
        while True:
            index = await self._queue.get()
            if index < 0:
                break
            
            # Skip if a newer request has been made
            if self._latest_request is not None and self._latest_request != index:
                self._queue.task_done()
                continue
                
            try:
                arr = self.video[index]  # (H, W, C) or (H, W)
                if arr.ndim == 2:
                    arr = np.repeat(arr[..., None], 3, axis=2)
                elif arr.shape[-1] == 1:
                    arr = np.repeat(arr, 3, axis=2)
                h, w, _ = arr.shape
                frame = Frame(
                    index=index, rgb=arr.astype(np.uint8, copy=False), size=(w, h)
                )
                async with self._lock:
                    if len(self._cache) >= self.cache_size:
                        self._cache.pop(next(iter(self._cache)))
                    self._cache[index] = frame
            except Exception:
                # Missing frames are allowed; skip silently.
                pass
            finally:
                self._queue.task_done()

    async def request(self, index: int) -> None:
        """Queue a high-priority request for a frame index without blocking.

        Args:
            index: Absolute frame index to request.
        """
        self._latest_request = index  # Track this as the latest request
        
        # Clear the queue of pending requests (they're obsolete now)
        try:
            while not self._queue.empty():
                self._queue.get_nowait()
                self._queue.task_done()
        except asyncio.QueueEmpty:
            pass
        
        await self._queue.put(index)

    async def get(self, index: int, timeout: float = 0.01) -> Frame | None:
        """Return a decoded frame if ready; otherwise None.

        Args:
            index: Frame index to retrieve.
            timeout: Max time to wait for availability before returning.

        Returns:
            The `Frame` if available; otherwise `None`.
        """
        try:
            async with self._lock:
                return self._cache.get(index)
        finally:
            await asyncio.sleep(timeout)

    def nearest_available(self, index: int) -> int | None:
        """Return the nearest available cached index, or None if cache is empty."""
        if not self._cache:
            return None
        return min(self._cache.keys(), key=lambda k: abs(k - index))

    def close(self) -> None:
        """Stop the worker task and release resources."""
        if self._task and not self._task.done():
            self._task.cancel()
