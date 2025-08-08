"""Adapter over `sio.Labels` producing per-frame arrays for rendering."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import numpy as np
import sleap_io as sio


class AnnotationSource:
    """Random-access SLEAP annotations via `sio.Labels`.

    Provides merged, per-frame arrays for GPU upload with precedence rules.
    """

    def __init__(self, labels: sio.Labels) -> None:
        """Initialize with a `Labels` object.

        Args:
            labels: SLEAP labels loaded from `.slp`.
        """
        self.labels = labels
        self._edges_cache: dict[int, np.ndarray] = {}

    def get_edges(self, skeleton: sio.Skeleton) -> np.ndarray:
        """Return static edge indices for a skeleton (int32 [E, 2])."""
        key = id(skeleton)
        if key not in self._edges_cache:
            self._edges_cache[key] = np.asarray(skeleton.edge_inds, dtype=np.int32)
        return self._edges_cache[key]

    def get_frame_data(
        self,
        video: sio.Video,
        index: int,
        *,
        missing_policy: Literal["error", "blank"] = "error",
        include_user: bool = True,
        include_predicted: bool = True,
        precedence: Literal[
            "user_over_from_predicted", "show_both", "user_only", "predicted_only"
        ] = "user_over_from_predicted",
        render_invisible: Literal["dim", "hide"]
        | Callable[[np.ndarray], np.ndarray] = "dim",
    ) -> dict[str, np.ndarray | list[str]]:
        """Return per-frame arrays for rendering.

        Args:
            video: Video object present in `labels.videos`.
            index: Frame index in the given video.
            missing_policy: "error" to raise if absent, "blank" to return empty data.
            include_user: Include user instances.
            include_predicted: Include predicted instances.
            precedence: Policy for user instances referencing predicted via `from_predicted`.
            render_invisible: How to treat invisible points ("dim" | "hide" | callable mask → style flags).

        Returns:
            Dict with points_xy [N_inst,N_nodes,2], visible [N_inst,N_nodes], inst_kind [N_inst],
            track_id [N_inst], node_ids [N_nodes], edges [E,2], labels list[str], skeleton_id int.
        """
        try:
            lf = self.labels[(video, index)]
        except Exception:
            if missing_policy == "blank":
                # Create an empty structure.
                return {
                    "points_xy": np.zeros((0, 0, 2), dtype=np.float32),
                    "visible": np.zeros((0, 0), dtype=bool),
                    "inst_kind": np.zeros((0,), dtype=np.uint8),
                    "track_id": np.zeros((0,), dtype=np.int32),
                    "node_ids": np.zeros((0,), dtype=np.int32),
                    "edges": np.zeros((0, 2), dtype=np.int32),
                    "labels": [],
                    "skeleton_id": -1,
                }
            raise

        # Instances
        insts_user = lf.user_instances if include_user else []
        insts_pred = lf.predicted_instances if include_predicted else []

        if precedence == "user_over_from_predicted":
            pred_refs = {getattr(inst, "from_predicted", None) for inst in insts_user}
            insts_pred = [pi for pi in insts_pred if pi not in pred_refs]
        elif precedence == "user_only":
            insts_pred = []
        elif precedence == "predicted_only":
            insts_user = []

        insts = list(insts_user) + list(insts_pred)
        kinds = ([0] * len(insts_user)) + ([1] * len(insts_pred))

        if not insts:
            # No instances.
            skel = (
                lf.video.skeleton
                if hasattr(lf.video, "skeleton")
                else self.labels.skeletons[-1]
            )
            edges = self.get_edges(skel)
            return {
                "points_xy": np.zeros((0, 0, 2), dtype=np.float32),
                "visible": np.zeros((0, 0), dtype=bool),
                "inst_kind": np.zeros((0,), dtype=np.uint8),
                "track_id": np.zeros((0,), dtype=np.int32),
                "node_ids": np.arange(0, 0, dtype=np.int32),
                "edges": edges,
                "labels": [],
                "skeleton_id": id(skel),
            }

        skel = insts[0].skeleton
        edges = self.get_edges(skel)
        node_ids = np.arange(len(skel.nodes), dtype=np.int32)

        pts = [np.asarray(inst.points["xy"], dtype=np.float32) for inst in insts]
        vis = [np.asarray(inst.points["visible"], dtype=bool) for inst in insts]

        points_xy = np.stack(pts, axis=0)  # [N_inst,N_nodes,2]
        visible = np.stack(vis, axis=0)  # [N_inst,N_nodes]
        inst_kind = np.asarray(kinds, dtype=np.uint8)
        track_ids = []
        for inst in insts:
            track = getattr(inst, "track", None)
            if track is None:
                track_ids.append(-1)
            elif hasattr(track, "name"):
                # Track object, try to get an ID
                try:
                    track_ids.append(int(track.name) if track.name.isdigit() else hash(track.name) % 1000000)
                except:
                    track_ids.append(-1)
            else:
                track_ids.append(-1)
        track_id = np.asarray(track_ids, dtype=np.int32)

        return {
            "points_xy": points_xy,
            "visible": visible,
            "inst_kind": inst_kind,
            "track_id": track_id,
            "node_ids": node_ids,
            "edges": edges,
            "labels": [str(getattr(inst, "track", "")) for inst in insts],
            "skeleton_id": id(skel),
        }
    
    def get_frame_data_simple(self, frame_idx: int) -> sio.LabeledFrame | None:
        """Get labeled frame by index, searching across all videos.
        
        Args:
            frame_idx: Frame index to get.
            
        Returns:
            LabeledFrame or None if not found.
        """
        # Try to find frame in any video
        for video in self.labels.videos:
            try:
                lf = self.labels[(video, frame_idx)]
                return lf
            except:
                continue
        return None
