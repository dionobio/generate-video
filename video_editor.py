"""
Video Translator Tool - Video Editor
CapCut-like video editing features using FFmpeg.
Supports: trim, speed, crop/resize, background music, watermark, concat.
"""

import os
import subprocess
import json
import tempfile


class VideoEditor:
    """FFmpeg-based video editing operations."""

    def __init__(self):
        pass

    # --- Probe helpers ---

    def get_video_info(self, video_path):
        """Get video metadata: duration, width, height, fps, has_audio."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        info = json.loads(result.stdout)

        duration = float(info["format"].get("duration", 0))
        width = height = fps = 0
        has_audio = False

        for stream in info.get("streams", []):
            if stream["codec_type"] == "video" and width == 0:
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
                # Parse fps from r_frame_rate like "30/1"
                rfr = stream.get("r_frame_rate", "30/1")
                parts = rfr.split("/")
                if len(parts) == 2 and int(parts[1]) > 0:
                    fps = round(int(parts[0]) / int(parts[1]), 2)
                else:
                    fps = 30
            elif stream["codec_type"] == "audio":
                has_audio = True

        return {
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "has_audio": has_audio,
        }

    def get_duration(self, path):
        """Get duration of a media file in seconds."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", path,
        ]
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])

    # --- Trim / Cut ---

    def trim(self, input_path, output_path, start_time, end_time, progress_callback=None):
        """
        Trim video from start_time to end_time (seconds).
        Uses stream copy for speed when possible.
        """
        if progress_callback:
            progress_callback(f"Cắt video: {start_time:.1f}s -> {end_time:.1f}s")

        duration = end_time - start_time
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", input_path,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Trim failed:\n{result.stderr}")

        if progress_callback:
            progress_callback("Cắt video xong!")
        return output_path

    # --- Speed adjustment ---

    def change_speed(self, input_path, output_path, speed_factor, progress_callback=None):
        """
        Change video speed.
        speed_factor: 0.25 to 4.0 (1.0 = normal, 2.0 = 2x fast, 0.5 = half speed)
        """
        if progress_callback:
            progress_callback(f"Thay doi toc do video: {speed_factor}x")

        # video: setpts=PTS/speed (inverse), audio: atempo (only supports 0.5-2.0 per filter)
        video_filter = f"setpts={1.0/speed_factor}*PTS"

        # Chain atempo filters for extreme speeds (each atempo limited to 0.5-2.0)
        atempo_chain = self._build_atempo_chain(speed_factor)

        info = self.get_video_info(input_path)
        cmd = ["ffmpeg", "-y", "-i", input_path]

        if info["has_audio"] and atempo_chain:
            cmd.extend([
                "-filter_complex",
                f"[0:v]{video_filter}[v];[0:a]{atempo_chain}[a]",
                "-map", "[v]", "-map", "[a]",
            ])
        else:
            cmd.extend(["-vf", video_filter, "-an"])

        cmd.extend([
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ])

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"Speed change failed:\n{result.stderr}")

        if progress_callback:
            progress_callback("Thay doi toc do xong!")
        return output_path

    def _build_atempo_chain(self, speed_factor):
        """Build chained atempo filters for arbitrary speed (atempo range: 0.5-2.0)."""
        filters = []
        remaining = speed_factor
        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0
        while remaining < 0.5:
            filters.append("atempo=0.5")
            remaining /= 0.5
        filters.append(f"atempo={remaining:.4f}")
        return ",".join(filters)

    # --- Crop / Resize ---

    def crop_resize(self, input_path, output_path, aspect_ratio="9:16", progress_callback=None):
        """
        Crop and resize video to target aspect ratio.
        aspect_ratio: "9:16", "16:9", "1:1", "4:3"
        Centers the crop on the source video.
        """
        if progress_callback:
            progress_callback(f"Crop video thanh {aspect_ratio}")

        info = self.get_video_info(input_path)
        src_w, src_h = info["width"], info["height"]

        ratio_map = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1), "4:3": (4, 3)}
        tw, th = ratio_map.get(aspect_ratio, (9, 16))

        # Calculate crop dimensions (largest centered rectangle with target ratio)
        if src_w / src_h > tw / th:
            # Source is wider: crop width
            crop_h = src_h
            crop_w = int(src_h * tw / th)
        else:
            # Source is taller: crop height
            crop_w = src_w
            crop_h = int(src_w * th / tw)

        # Make even
        crop_w = crop_w - (crop_w % 2)
        crop_h = crop_h - (crop_h % 2)

        x = (src_w - crop_w) // 2
        y = (src_h - crop_h) // 2

        vf = f"crop={crop_w}:{crop_h}:{x}:{y}"

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "copy",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"Crop/resize failed:\n{result.stderr}")

        if progress_callback:
            progress_callback("Crop video xong!")
        return output_path

    # --- Background music ---

    def add_background_music(self, input_path, music_path, output_path,
                              music_volume=0.3, keep_original=True,
                              progress_callback=None):
        """
        Add background music to video.
        music_volume: 0.0-1.0 volume of the music track
        keep_original: if True, mix with original audio; if False, replace
        """
        if progress_callback:
            progress_callback("Them nhac nen...")

        video_duration = self.get_duration(input_path)

        if keep_original:
            # Mix original audio with looped music
            filter_complex = (
                f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={video_duration},"
                f"volume={music_volume}[music];"
                f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-i", music_path,
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                output_path,
            ]
        else:
            # Replace audio with music only
            filter_complex = (
                f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={video_duration},"
                f"volume={music_volume}[music]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-i", music_path,
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[music]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                output_path,
            ]

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"Add music failed:\n{result.stderr}")

        if progress_callback:
            progress_callback("Them nhac nen xong!")
        return output_path

    # --- Watermark / Logo overlay ---

    def add_watermark(self, input_path, watermark_path, output_path,
                       position="top-right", opacity=0.7, scale=0.15,
                       progress_callback=None):
        """
        Add image watermark/logo overlay.
        position: "top-left", "top-right", "bottom-left", "bottom-right", "center"
        opacity: 0.0-1.0
        scale: watermark size relative to video width (0.05-0.5)
        """
        if progress_callback:
            progress_callback(f"Them watermark ({position})...")

        info = self.get_video_info(input_path)
        wm_w = int(info["width"] * scale)

        # Position mapping (with 20px padding)
        pad = 20
        pos_map = {
            "top-left": f"x={pad}:y={pad}",
            "top-right": f"x=W-w-{pad}:y={pad}",
            "bottom-left": f"x={pad}:y=H-h-{pad}",
            "bottom-right": f"x=W-w-{pad}:y=H-h-{pad}",
            "center": "x=(W-w)/2:y=(H-h)/2",
        }
        pos_str = pos_map.get(position, pos_map["top-right"])

        # Scale watermark and apply opacity, then overlay
        filter_complex = (
            f"[1:v]scale={wm_w}:-1,format=rgba,"
            f"colorchannelmixer=aa={opacity}[wm];"
            f"[0:v][wm]overlay={pos_str}[vout]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-i", watermark_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "copy",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"Watermark failed:\n{result.stderr}")

        if progress_callback:
            progress_callback("Them watermark xong!")
        return output_path

    # --- Concat multiple videos ---

    def concat_videos(self, input_paths, output_path, progress_callback=None):
        """
        Concatenate multiple videos into one.
        Re-encodes to ensure compatibility between different sources.
        """
        if not input_paths or len(input_paths) < 2:
            raise ValueError("Can it nhat 2 video de ghep noi.")

        if progress_callback:
            progress_callback(f"Ghep {len(input_paths)} video...")

        # Find target resolution (use first video's dimensions)
        info = self.get_video_info(input_paths[0])
        target_w = info["width"]
        target_h = info["height"]
        # Make even
        target_w = target_w - (target_w % 2)
        target_h = target_h - (target_h % 2)

        # Build filter: scale + pad each input to same size, then concat
        inputs = []
        filter_parts = []
        for i, path in enumerate(input_paths):
            inputs.extend(["-i", path])
            # Scale to fit, pad to exact target size (black bars if needed)
            filter_parts.append(
                f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
                f"setsar=1[v{i}]"
            )
            filter_parts.append(
                f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]"
            )

        # Concat filter
        v_streams = "".join(f"[v{i}]" for i in range(len(input_paths)))
        a_streams = "".join(f"[a{i}]" for i in range(len(input_paths)))
        filter_parts.append(
            f"{v_streams}{a_streams}concat=n={len(input_paths)}:v=1:a=1[vout][aout]"
        )

        filter_complex = ";".join(filter_parts)

        cmd = ["ffmpeg", "-y"]
        cmd.extend(inputs)
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ])

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8",
                                errors="replace", timeout=1200)
        if result.returncode != 0:
            raise RuntimeError(f"Concat failed:\n{result.stderr}")

        if progress_callback:
            progress_callback(f"Ghep video xong! ({len(input_paths)} video)")
        return output_path

    # --- Extract thumbnail / preview frame ---

    def extract_frame(self, video_path, timestamp, output_path):
        """Extract a single frame at given timestamp (seconds)."""
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8",
                                errors="replace", timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"Frame extraction failed:\n{result.stderr}")
        return output_path
