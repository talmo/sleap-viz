"""Interactive controls for keyboard and mouse input."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .controller import Controller
    from .picking import GPUPicker, PickingResult


class InteractiveControls:
    """Handles keyboard and mouse events for the viewer.
    
    Keyboard shortcuts:
    - Space: Play/pause
    - Left/Right arrows: Previous/next frame
    - Shift+Left/Right: Skip 10 frames
    - Home/End: Go to start/end
    - J/K: Frame step backward/forward (vim-style)
    - L: Toggle loop mode
    - 0-9: Set playback speed (0=10x, 1=1x, 2=2x, etc.)
    - -/+: Decrease/increase playback speed
    - B/Shift+B: Increase/decrease brightness
    - C/Shift+C: Increase/decrease contrast
    - G/Shift+G: Decrease/increase gamma
    - R: Reset image adjustments
    - T: Toggle tone mapping (linear/LUT)
    - Shift+H: Toggle histogram equalization
    - E: Toggle CLAHE (enhanced contrast)
    - M: Cycle through LUT modes
    - Ctrl/Cmd + +/-: Zoom in/out video
    - Ctrl/Cmd + 0: Reset video zoom
    - Z/Shift+Z: Zoom in/out timeline
    - X: Reset timeline zoom
    - A/D: Pan timeline left/right
    - S: Clear selection
    - P: Play selection (if selected)
    - Q/Escape: Quit
    
    Mouse controls:
    - Mouse wheel: Zoom in/out video (at cursor position)
    - Click and drag: Pan video
    - Click on timeline: Jump to frame
    - Drag on timeline: Scrub through frames
    - Ctrl+Drag on timeline: Select range
    - Shift+Drag on timeline: Pan timeline
    - Mouse wheel on timeline: Zoom in/out timeline
    - Hover over points: Show tooltip with node name
    - Click on points: Select point
    
    Trackpad gestures:
    - Pinch: Zoom in/out video
    - Two-finger drag: Pan video
    """
    
    def __init__(self, controller: Controller, canvas=None, picker: Optional[GPUPicker] = None):
        """Initialize interactive controls.
        
        Args:
            controller: The Controller instance to control.
            canvas: The render canvas to attach event handlers to.
            picker: Optional GPU picker for point selection.
        """
        self.controller = controller
        self.canvas = canvas
        self.picker = picker
        self._handlers_attached = False
        self._is_dragging = False
        self._is_panning = False
        self._is_selecting = False
        self._selection_start_x = None
        self._quit_callback: Callable[[], None] | None = None
        
        # Video pan state
        self._is_video_panning = False
        self._pan_start_x = None
        self._pan_start_y = None
        self._pan_start_vis_x = None
        self._pan_start_vis_y = None
        
        # Picking state
        self._hovered_pick: Optional[PickingResult] = None
        self._selected_pick: Optional[PickingResult] = None
        self._tooltip_element = None
        
    def attach_handlers(self) -> None:
        """Attach event handlers to the canvas."""
        if not self.canvas or self._handlers_attached:
            return
            
        # Attach keyboard and mouse handlers
        if hasattr(self.canvas, "add_event_handler"):
            self.canvas.add_event_handler(self._on_key, "key_down")
            self.canvas.add_event_handler(self._on_mouse_down, "pointer_down")
            self.canvas.add_event_handler(self._on_mouse_move, "pointer_move")
            self.canvas.add_event_handler(self._on_mouse_up, "pointer_up")
            self.canvas.add_event_handler(self._on_wheel, "wheel")
            # Try to add pinch/gesture handlers if supported
            try:
                self.canvas.add_event_handler(self._on_pinch, "pinch")
            except:
                pass  # Pinch not supported
            try:
                # Safari-specific gesture event
                self.canvas.add_event_handler(self._on_gesture, "gesturechange")
            except:
                pass  # GestureEvent not supported
            self._handlers_attached = True
            
    def detach_handlers(self) -> None:
        """Detach event handlers from the canvas."""
        if not self.canvas or not self._handlers_attached:
            return
            
        if hasattr(self.canvas, "remove_event_handler"):
            self.canvas.remove_event_handler(self._on_key, "key_down")
            self.canvas.remove_event_handler(self._on_mouse_down, "pointer_down")
            self.canvas.remove_event_handler(self._on_mouse_move, "pointer_move")
            self.canvas.remove_event_handler(self._on_mouse_up, "pointer_up")
            self.canvas.remove_event_handler(self._on_wheel, "wheel")
            try:
                self.canvas.remove_event_handler(self._on_pinch, "pinch")
            except:
                pass  # Pinch not supported
            try:
                self.canvas.remove_event_handler(self._on_gesture, "gesturechange")
            except:
                pass  # GestureEvent not supported
            self._handlers_attached = False
            
    def set_quit_callback(self, callback: Callable[[], None]) -> None:
        """Set a callback to be called when quit is requested.
        
        Args:
            callback: Function to call when Q or Escape is pressed.
        """
        self._quit_callback = callback
    
    def _adjust_image(self, param: str, delta: float) -> None:
        """Adjust image parameter by delta.
        
        Args:
            param: Parameter to adjust ('gain', 'bias', or 'gamma').
            delta: Amount to adjust by.
        """
        if not hasattr(self.controller, 'vis'):
            return
            
        vis = self.controller.vis
        current_gain = vis.gain
        current_bias = vis.bias
        current_gamma = vis.gamma
        
        if param == "gain":
            new_gain = max(0.1, min(5.0, current_gain + delta))
            vis.set_image_adjust(gain=new_gain, bias=current_bias, gamma=current_gamma)
            print(f"Contrast (gain): {new_gain:.1f}")
        elif param == "bias":
            new_bias = max(-1.0, min(1.0, current_bias + delta))
            vis.set_image_adjust(gain=current_gain, bias=new_bias, gamma=current_gamma)
            print(f"Brightness (bias): {new_bias:.1f}")
        elif param == "gamma":
            new_gamma = max(0.1, min(5.0, current_gamma + delta))
            vis.set_image_adjust(gain=current_gain, bias=current_bias, gamma=new_gamma)
            print(f"Gamma: {new_gamma:.1f}")
        
        # Trigger redraw by re-rendering current frame
        asyncio.create_task(self.controller.goto(self.controller.current_frame))
    
    def _reset_image_adjustments(self) -> None:
        """Reset all image adjustments to default values."""
        if not hasattr(self.controller, 'vis'):
            return
            
        self.controller.vis.set_image_adjust(
            gain=1.0, bias=0.0, gamma=1.0, tone_map="linear", 
            lut_mode="none", lut=None
        )
        print("Image adjustments reset")
        
        # Trigger redraw by re-rendering current frame
        asyncio.create_task(self.controller.goto(self.controller.current_frame))
    
    def _toggle_tone_map(self) -> None:
        """Toggle between linear and LUT tone mapping."""
        if not hasattr(self.controller, 'vis'):
            return
        
        vis = self.controller.vis
        new_mode = "lut" if vis.tone_map == "linear" else "linear"
        
        vis.set_image_adjust(
            gain=vis.gain, bias=vis.bias, gamma=vis.gamma,
            tone_map=new_mode, lut=vis.lut, lut_mode=vis.lut_mode,
            lut_params=vis.lut_params
        )
        print(f"Tone mapping: {new_mode}")
        
        # Trigger redraw
        asyncio.create_task(self.controller.goto(self.controller.current_frame))
    
    def _set_lut_mode(self, mode: str) -> None:
        """Set a specific LUT mode.
        
        Args:
            mode: LUT mode to set (none, histogram, clahe, gamma, sigmoid).
        """
        if not hasattr(self.controller, 'vis'):
            return
        
        vis = self.controller.vis
        
        # If we're toggling the same mode, turn it off
        if vis.lut_mode == mode:
            mode = "none"
            tone_map = "linear"
        else:
            tone_map = "lut"
        
        # Clear existing LUT to force regeneration
        vis.lut = None
        
        vis.set_image_adjust(
            gain=vis.gain, bias=vis.bias, gamma=vis.gamma,
            tone_map=tone_map, lut=None, lut_mode=mode,
            lut_params=vis.lut_params
        )
        print(f"LUT mode: {mode}")
        
        # Trigger redraw
        asyncio.create_task(self.controller.goto(self.controller.current_frame))
    
    def _cycle_lut_mode(self) -> None:
        """Cycle through available LUT modes."""
        if not hasattr(self.controller, 'vis'):
            return
        
        vis = self.controller.vis
        modes = ["none", "histogram", "clahe", "gamma", "sigmoid"]
        
        # Find current mode index and cycle to next
        current_idx = modes.index(vis.lut_mode) if vis.lut_mode in modes else 0
        next_idx = (current_idx + 1) % len(modes)
        next_mode = modes[next_idx]
        
        # Set tone_map based on mode
        tone_map = "linear" if next_mode == "none" else "lut"
        
        # Clear existing LUT to force regeneration
        vis.lut = None
        
        vis.set_image_adjust(
            gain=vis.gain, bias=vis.bias, gamma=vis.gamma,
            tone_map=tone_map, lut=None, lut_mode=next_mode,
            lut_params=vis.lut_params
        )
        print(f"LUT mode: {next_mode}")
        
        # Trigger redraw
        asyncio.create_task(self.controller.goto(self.controller.current_frame))
    
    def _save_config(self) -> None:
        """Save current viewer settings to default config."""
        try:
            from .config import ConfigManager, get_current_config
            
            vis = getattr(self.controller, 'vis', None)
            if vis is None:
                print("Unable to access visualizer for config save")
                return
            
            config_manager = ConfigManager()
            current_config = get_current_config(self.controller, vis)
            saved_path = config_manager.save_config(current_config)
            print(f"Config saved to: {saved_path}")
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    def _load_config(self) -> None:
        """Load viewer settings from default config."""
        try:
            from .config import ConfigManager, apply_config
            
            vis = getattr(self.controller, 'vis', None)
            if vis is None:
                print("Unable to access visualizer for config load")
                return
            
            config_manager = ConfigManager()
            loaded_config = config_manager.load_config()
            apply_config(loaded_config, self.controller, vis)
            print("Config loaded from default settings")
            
            # Trigger redraw
            asyncio.create_task(self.controller.goto(self.controller.current_frame))
        except Exception as e:
            print(f"Failed to load config: {e}")
            
    def _on_key(self, event) -> None:
        """Handle keyboard events.
        
        Args:
            event: The keyboard event.
        """
        key = event.get("key", "")
        modifiers = event.get("modifiers", [])
        
        # Create async task for controller methods
        loop = asyncio.get_event_loop()
        
        # Play/pause
        if key == " ":
            loop.create_task(self.controller.toggle_play_pause())
            
        # Frame navigation
        elif key == "ArrowLeft":
            if "Shift" in modifiers:
                loop.create_task(self.controller.skip_frames(-10))
            else:
                loop.create_task(self.controller.prev_frame())
                
        elif key == "ArrowRight":
            if "Shift" in modifiers:
                loop.create_task(self.controller.skip_frames(10))
            else:
                loop.create_task(self.controller.next_frame())
                
        # Vim-style navigation
        elif key == "j":
            loop.create_task(self.controller.prev_frame())
        elif key == "k":
            loop.create_task(self.controller.next_frame())
            
        # Jump to start/end
        elif key == "Home":
            loop.create_task(self.controller.goto_start())
        elif key == "End":
            loop.create_task(self.controller.goto_end())
            
        # Loop mode
        elif key == "l":
            self.controller.loop = not self.controller.loop
            print(f"Loop mode: {'on' if self.controller.loop else 'off'}")
            
        # Playback speed with number keys
        elif key in "0123456789":
            speed = 10.0 if key == "0" else float(key)
            self.controller.set_playback_speed(speed)
            print(f"Playback speed: {speed}x")
            
        # Adjust speed (when not used for zoom)
        elif key == "-" or key == "_":
            if "Control" in modifiers or "Meta" in modifiers:
                # Zoom out video
                self._zoom_video_out()
            else:
                new_speed = max(0.1, self.controller.playback_speed - 0.5)
                self.controller.set_playback_speed(new_speed)
                print(f"Playback speed: {new_speed}x")
            
        elif key == "=" or key == "+":
            if "Control" in modifiers or "Meta" in modifiers:
                # Zoom in video
                self._zoom_video_in()
            else:
                new_speed = min(10.0, self.controller.playback_speed + 0.5)
                self.controller.set_playback_speed(new_speed)
                print(f"Playback speed: {new_speed}x")
        
        elif key == "0" and ("Control" in modifiers or "Meta" in modifiers):
            # Reset video zoom
            self._reset_video_zoom()
            
        # Image adjustments
        elif key == "b":
            # Increase brightness (bias)
            if "Shift" in modifiers:
                self._adjust_image("bias", -0.1)
            else:
                self._adjust_image("bias", 0.1)
                
        elif key == "c":
            # Increase contrast (gain)
            if "Shift" in modifiers:
                self._adjust_image("gain", -0.2)
            else:
                self._adjust_image("gain", 0.2)
                
        elif key == "g":
            # Adjust gamma
            if "Shift" in modifiers:
                self._adjust_image("gamma", 0.1)
            else:
                self._adjust_image("gamma", -0.1)
                
        elif key == "r":
            # Reset image adjustments
            self._reset_image_adjustments()
        
        elif key == "t":
            # Toggle tone mapping mode (linear vs LUT)
            self._toggle_tone_map()
        
        elif key == "h" and "Shift" in modifiers:
            # Toggle histogram equalization
            self._set_lut_mode("histogram")
        
        elif key == "e":
            # Toggle CLAHE (enhanced contrast)
            self._set_lut_mode("clahe")
        
        elif key == "m":
            # Cycle through LUT modes
            self._cycle_lut_mode()
            
        # Timeline zoom/pan controls
        elif key == "z":
            # Zoom timeline
            if hasattr(self.controller, 'timeline_controller'):
                if "Shift" in modifiers:
                    self.controller.timeline_controller.zoom_out()
                else:
                    self.controller.timeline_controller.zoom_in()
                    
        elif key == "x":
            # Reset timeline zoom
            if hasattr(self.controller, 'timeline_controller'):
                self.controller.timeline_controller.reset_zoom()
                
        elif key == "a":
            # Pan timeline left
            if hasattr(self.controller, 'timeline_controller'):
                visible = self.controller.timeline_controller.model.frame_max - self.controller.timeline_controller.model.frame_min
                pan_amount = max(1, visible // 10)  # Pan by 10% of visible range
                self.controller.timeline_controller.model.pan(-pan_amount)
                self.controller.timeline_controller.request_update()
                
        elif key == "d":
            # Pan timeline right
            if hasattr(self.controller, 'timeline_controller'):
                visible = self.controller.timeline_controller.model.frame_max - self.controller.timeline_controller.model.frame_min
                pan_amount = max(1, visible // 10)  # Pan by 10% of visible range
                self.controller.timeline_controller.model.pan(pan_amount)
                self.controller.timeline_controller.request_update()
                
        elif key == "s":
            # Clear selection
            if hasattr(self.controller, 'timeline_controller'):
                self.controller.timeline_controller.set_selection(None, None)
                print("Selection cleared")
                
        elif key == "p":
            # Play selection
            if hasattr(self.controller, 'timeline_controller'):
                model = self.controller.timeline_controller.model
                if model.selection_start is not None and model.selection_end is not None:
                    # Jump to start of selection and play
                    loop.create_task(self.controller.goto(model.selection_start))
                    # Set up playback to stop at end of selection
                    print(f"Playing selection: frames {model.selection_start} to {model.selection_end}")
                    # Note: Full implementation would require modifying Controller to support play range
                else:
                    print("No selection to play")
        
        # Config operations
        elif key == "f" and "Control" in modifiers and "Shift" in modifiers:
            # Ctrl+Shift+F: Save config
            self._save_config()
        elif key == "o" and "Control" in modifiers and "Shift" in modifiers:
            # Ctrl+Shift+O: Load config
            self._load_config()
            
        # Quit
        elif key == "q" or key == "Escape":
            if self._quit_callback:
                self._quit_callback()
            else:
                print("Quit requested")
                
    def _on_mouse_down(self, event) -> None:
        """Handle mouse down events.
        
        Args:
            event: The mouse event.
        """
        x = event.get("x", 0)
        y = event.get("y", 0)
        modifiers = event.get("modifiers", [])
        
        if hasattr(self.canvas, "get_logical_size"):
            width, height = self.canvas.get_logical_size()
            
            # Timeline is in bottom 50 pixels (timeline height)
            # Note: pygfx Y coordinates are from top, so timeline is at height - 50
            if y > height - 50:
                if "Control" in modifiers and hasattr(self.controller, 'timeline_controller'):
                    # Start range selection
                    self._is_selecting = True
                    self._selection_start_x = x
                    # Clear existing selection
                    self.controller.timeline_controller.set_selection(None, None)
                elif "Shift" in modifiers and hasattr(self.controller, 'timeline_controller'):
                    # Start panning
                    self._is_panning = True
                    self.controller.timeline_controller.start_pan(x)
                else:
                    # Start dragging for seeking
                    self._is_dragging = True
                    # Adjust x coordinate for timeline (timeline uses full width)
                    self._handle_timeline_interaction(x, width)
            else:
                # In main video area
                # Start video panning
                self._is_video_panning = True
                self._pan_start_x = x
                self._pan_start_y = y
                if hasattr(self.controller, 'vis'):
                    self._pan_start_vis_x = self.controller.vis.pan_x
                    self._pan_start_vis_y = self.controller.vis.pan_y
                
    def _on_mouse_move(self, event) -> None:
        """Handle mouse move events.
        
        Args:
            event: The mouse event.
        """
        x = event.get("x", 0)
        y = event.get("y", 0)
        
        # Handle video panning
        if self._is_video_panning:
            if self._pan_start_x is not None and hasattr(self.controller, 'vis'):
                dx = x - self._pan_start_x
                dy = y - self._pan_start_y
                # X: natural panning (drag right moves image right)
                # Y: inverted panning (drag down moves image up)
                self.controller.vis.set_pan(
                    self._pan_start_vis_x + dx,
                    self._pan_start_vis_y - dy  # Inverted Y
                )
                self.controller.vis.draw()
        # Check for hover over points (if not dragging)
        elif not self._is_dragging and not self._is_selecting and not self._is_panning:
            if self.picker and hasattr(self.canvas, "get_logical_size"):
                width, height = self.canvas.get_logical_size()
                # Only check for hover if not over timeline
                if y <= height - 50:
                    pick_result = self.picker.pick(x, y)
                    if pick_result.is_valid != (self._hovered_pick and self._hovered_pick.is_valid):
                        # Hover state changed
                        self._hovered_pick = pick_result
                        if pick_result.is_valid:
                            # Show tooltip
                            self._show_tooltip(pick_result)
                        else:
                            # Hide tooltip
                            self._hide_tooltip()
        
        if self._is_selecting and hasattr(self.controller, 'timeline_controller'):
            # Update selection range
            if self._selection_start_x is not None:
                start_frame, end_frame = self.controller.timeline_controller.handle_drag(
                    self._selection_start_x, x
                )
                self.controller.timeline_controller.set_selection(start_frame, end_frame)
        elif self._is_panning and hasattr(self.controller, 'timeline_controller'):
            # Update pan
            self.controller.timeline_controller.update_pan(x)
        elif self._is_dragging:
            # Continue dragging for seeking
            if hasattr(self.canvas, "get_logical_size"):
                width, _ = self.canvas.get_logical_size()
                self._handle_timeline_interaction(x, width)
            
    def _on_mouse_up(self, event) -> None:
        """Handle mouse up events.
        
        Args:
            event: The mouse event.
        """
        if self._is_video_panning:
            self._is_video_panning = False
            self._pan_start_x = None
            self._pan_start_y = None
            self._pan_start_vis_x = None
            self._pan_start_vis_y = None
        elif self._is_selecting:
            self._is_selecting = False
            self._selection_start_x = None
            # Selection is already set in _on_mouse_move
            if hasattr(self.controller, 'timeline_controller'):
                selection = self.controller.timeline_controller.model
                if selection.selection_start is not None and selection.selection_end is not None:
                    print(f"Selected frames {selection.selection_start} to {selection.selection_end}")
        elif self._is_panning and hasattr(self.controller, 'timeline_controller'):
            self.controller.timeline_controller.end_pan()
        self._is_dragging = False
        self._is_panning = False
        
    def _handle_timeline_interaction(self, x: float, width: float) -> None:
        """Handle timeline click or drag.
        
        Args:
            x: X coordinate of the click/drag.
            width: Width of the canvas.
        """
        if hasattr(self.controller, 'timeline_controller'):
            # Use timeline controller to handle click with zoom support
            target_frame = self.controller.timeline_controller.handle_click(x, 0)
        else:
            # Fallback to simple calculation
            frame_ratio = x / width
            target_frame = int(frame_ratio * self.controller.total_frames)
            target_frame = max(0, min(target_frame, self.controller.total_frames - 1))
        
        # Jump to frame
        loop = asyncio.get_event_loop()
        loop.create_task(self.controller.goto(target_frame))
    
    def _on_wheel(self, event) -> None:
        """Handle mouse wheel events.
        
        Args:
            event: The wheel event.
        """
        # Get wheel position and delta
        x = event.get("x", 0)
        y = event.get("y", 0)
        dy = event.get("dy", 0)  # Wheel delta
        dx = event.get("dx", 0)  # Horizontal delta (might be used for pinch)
        modifiers = event.get("modifiers", [])
        
        # MacBook trackpad pinch gestures come as wheel events with Control modifier
        # The event.ctrlKey might be set even when user isn't pressing Ctrl
        is_pinch = "Control" in modifiers or event.get("ctrlKey", False)
        
        # Debug output to understand the events
        if is_pinch and dy != 0:
            print(f"Pinch detected: dy={dy:.2f}, dx={dx:.2f}, modifiers={modifiers}")
        
        if hasattr(self.canvas, "get_logical_size"):
            width, height = self.canvas.get_logical_size()
            
            # Timeline is in bottom 50 pixels
            if y > height - 50:
                # Handle zoom on timeline
                if hasattr(self.controller, 'timeline_controller'):
                    self.controller.timeline_controller.handle_wheel(-dy, x)
            else:
                # Handle zoom on video
                if is_pinch and dy != 0:
                    # MacBook trackpad pinch zoom
                    # dy is negative for zoom in, positive for zoom out
                    if hasattr(self.controller, 'vis'):
                        # Use exponential scaling for smoother zoom
                        scale = pow(1.01, -dy)  # Negative because pinch in = negative dy = zoom in
                        current_zoom = self.controller.vis.zoom_level
                        self.controller.vis.set_zoom(current_zoom * scale, x, y)
                        self.controller.vis.draw()
                        # Remove debug print after testing
                        # print(f"Video zoom: {self.controller.vis.zoom_level:.1f}x")
                elif not is_pinch:
                    # Regular mouse wheel zoom (without Ctrl)
                    if dy > 0:
                        self._zoom_video_out(center_x=x, center_y=y)
                    elif dy < 0:
                        self._zoom_video_in(center_x=x, center_y=y)
    
    def _show_tooltip(self, pick_result: PickingResult) -> None:
        """Show tooltip for hovered point.
        
        Args:
            pick_result: The picking result with point information.
        """
        if pick_result.node_name:
            tooltip_text = f"{pick_result.node_name}"
        else:
            tooltip_text = f"Node {pick_result.node_id}"
        
        # Add instance info if multiple instances
        if hasattr(self.controller, 'annotation_source'):
            frame_data = self.controller.annotation_source.get_frame_data(
                self.controller.current_frame
            )
            if frame_data and len(frame_data.instances) > 1:
                tooltip_text = f"Instance {pick_result.instance_id}: {tooltip_text}"
        
        # For now, just print to console
        # TODO: Implement actual tooltip rendering
        print(f"Hover: {tooltip_text}")
    
    def _hide_tooltip(self) -> None:
        """Hide the tooltip."""
        # TODO: Implement actual tooltip hiding
        pass
    
    def _update_selection_highlight(self) -> None:
        """Update visualization to highlight selected point."""
        if not self._selected_pick:
            return
        
        # Update renderer to highlight the selected point
        if hasattr(self.controller, 'vis'):
            vis = self.controller.vis
            # Store selection for renderer to use
            vis.selected_instance = self._selected_pick.instance_id
            vis.selected_node = self._selected_pick.node_id
            
            # Trigger redraw
            asyncio.create_task(self.controller.goto(self.controller.current_frame))
    
    def _zoom_video_in(self, center_x: float = None, center_y: float = None) -> None:
        """Zoom in the video view."""
        if hasattr(self.controller, 'vis'):
            self.controller.vis.zoom_in(center_x=center_x, center_y=center_y)
            self.controller.vis.draw()
            print(f"Video zoom: {self.controller.vis.zoom_level:.1f}x")
    
    def _zoom_video_out(self, center_x: float = None, center_y: float = None) -> None:
        """Zoom out the video view."""
        if hasattr(self.controller, 'vis'):
            self.controller.vis.zoom_out(center_x=center_x, center_y=center_y)
            self.controller.vis.draw()
            print(f"Video zoom: {self.controller.vis.zoom_level:.1f}x")
    
    def _reset_video_zoom(self) -> None:
        """Reset video zoom to fit window."""
        if hasattr(self.controller, 'vis'):
            self.controller.vis.reset_zoom()
            self.controller.vis.draw()
            print("Video zoom reset")
    
    def _on_pinch(self, event) -> None:
        """Handle pinch gestures for zooming.
        
        Args:
            event: The pinch event.
        """
        scale = event.get("scale", 1.0)
        x = event.get("x", self.canvas.get_logical_size()[0] / 2 if hasattr(self.canvas, "get_logical_size") else 0)
        y = event.get("y", self.canvas.get_logical_size()[1] / 2 if hasattr(self.canvas, "get_logical_size") else 0)
        
        if hasattr(self.controller, 'vis'):
            # Apply scale directly
            current_zoom = self.controller.vis.zoom_level
            self.controller.vis.set_zoom(current_zoom * scale, x, y)
            self.controller.vis.draw()
    
    def _on_gesture(self, event) -> None:
        """Handle Safari-specific gesture events.
        
        Args:
            event: The gesture event.
        """
        scale = event.get("scale", 1.0)
        if scale != 1.0 and hasattr(self.controller, 'vis'):
            # Apply incremental scale
            self.controller.vis.set_zoom(self.controller.vis.zoom_level * scale, 
                                        self.canvas.get_logical_size()[0] / 2,
                                        self.canvas.get_logical_size()[1] / 2)
            self.controller.vis.draw()