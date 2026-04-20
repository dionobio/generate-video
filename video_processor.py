"""
Video Translator Tool - Video Processor
Combines translated subtitles, TTS audio, and original video using FFmpeg.
Auto-detects original subtitle position for overlay.
"""

import os
import subprocess
import tempfile
import json
import shutil


class VideoProcessor:
    """Process video: burn subtitles, replace/mix audio, export."""

    def __init__(self):
        pass

    def detect_subtitle_position(self, video_path, progress_callback=None):
        """
        Auto-detect the Y position of hardcoded subtitles in the video.
        Extracts sample frames, analyzes edge density to find text regions.
        Returns: percentage from bottom (0-90), or 35 as fallback.
        """
        if progress_callback:
            progress_callback("Đang quét vị trí phụ đề gốc...")

        try:
            from PIL import Image, ImageFilter
            import numpy as np
        except ImportError:
            if progress_callback:
                progress_callback("Thiếu Pillow/numpy, dùng vị trí mặc định 35%")
            return 35

        # Get video duration
        try:
            duration = self.get_video_duration(video_path)
        except Exception:
            return 35

        # Extract ~8 sample frames spread across the video (skip first/last 10%)
        tmp_dir = tempfile.mkdtemp(prefix="vtool_detect_")
        num_frames = 8
        timestamps = [
            duration * (0.1 + 0.8 * i / (num_frames - 1))
            for i in range(num_frames)
        ]

        frame_paths = []
        for i, ts in enumerate(timestamps):
            frame_path = os.path.join(tmp_dir, f"frame_{i:02d}.png")
            cmd = [
                "ffmpeg", "-y", "-ss", str(ts),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",
                frame_path,
            ]
            result = subprocess.run(
                cmd, capture_output=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
            if result.returncode == 0 and os.path.exists(frame_path):
                frame_paths.append(frame_path)

        if not frame_paths:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return 35

        # Analyze frames: find horizontal bands with high edge density (= text)
        # Only look at lower 70% of the frame (subtitles are rarely at top)
        strip_height = 20  # pixels per horizontal strip
        vote_counts = {}  # y_percent -> count of frames that have text there

        for fp in frame_paths:
            try:
                img = Image.open(fp).convert("L")  # grayscale
                width, height = img.size

                # Apply edge detection
                edges = img.filter(ImageFilter.FIND_EDGES)
                edge_data = np.array(edges)

                # Scan lower 70% of frame in horizontal strips
                start_y = int(height * 0.30)
                for y in range(start_y, height - strip_height, strip_height):
                    strip = edge_data[y:y + strip_height, :]
                    mean_edge = float(np.mean(strip))

                    # Text regions have significantly higher edge density
                    # Threshold tuned for subtitle text (white/colored text on video)
                    if mean_edge > 15:
                        # Convert to percentage from bottom
                        y_center = y + strip_height // 2
                        pct_from_bottom = int((height - y_center) / height * 100)
                        # Round to nearest 5%
                        pct_rounded = round(pct_from_bottom / 5) * 5
                        pct_rounded = max(0, min(90, pct_rounded))
                        vote_counts[pct_rounded] = vote_counts.get(pct_rounded, 0) + 1

            except Exception:
                continue

        # Cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)

        if not vote_counts:
            if progress_callback:
                progress_callback("Không phát hiện phụ đề gốc, dùng vị trí mặc định 35%")
            return 35

        # Find the position with most votes (most frames had text there)
        # Filter: need at least 3 frames to agree (avoid false positives from scene content)
        candidates = {k: v for k, v in vote_counts.items() if v >= 3}

        if not candidates:
            # Relax threshold: at least 2 frames
            candidates = {k: v for k, v in vote_counts.items() if v >= 2}

        if not candidates:
            return 35

        # Pick the one with highest vote count; tiebreak by closest to typical sub area (30-40%)
        best_pos = max(candidates, key=lambda k: (candidates[k], -abs(k - 35)))

        if progress_callback:
            progress_callback(f"Phát hiện phụ đề gốc ở vị trí ~{best_pos}% từ đáy")

        return best_pos

    def get_video_duration(self, video_path):
        """Get video duration in seconds."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])

    def get_audio_duration(self, audio_path):
        """Get audio file duration in seconds."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])

    def create_subtitle_file(self, segments, output_path, font_size=24, subtitle_position=35):
        """Create ASS subtitle file for burning into video.
        Style: black text on yellow opaque box.
        subtitle_position: 0-90, percentage from bottom of video.
            0 = very bottom, 35 = typical Douyin/TikTok subtitle area, 50 = middle.
        """
        # Convert percentage to ASS MarginV (PlayResY=1080)
        # 0% -> MarginV=15 (bottom), 50% -> MarginV=540 (middle)
        margin_v = max(15, int(1080 * subtitle_position / 100))
        # ASS header
        # BorderStyle=3 = opaque box, OutlineColour = box fill color
        # ASS color format: &HAABBGGRR
        # Yellow box: &H0000FFFF (R=255,G=255,B=0)
        # Black text: &H00000000
        header = f"""[Script Info]
Title: Translated Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00000000,&H000000FF,&H0000FFFF,&H0000FFFF,-1,0,0,0,100,100,0,0,3,1,0,2,20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header.strip()]

        for seg in segments:
            start = self._format_time_ass(seg["start"])
            end = self._format_time_ass(seg["end"])
            text = seg.get("translated_text", seg["text"])
            # Escape special ASS characters
            text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
            text = text.replace("\n", "\\N")
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return output_path

    def merge_tts_audio(self, segments, audio_files, total_duration, output_path):
        """
        Merge all TTS audio segments into a single audio track
        with correct timing (silence between segments).
        Normalizes volume so all segments have consistent loudness.
        """
        # Build FFmpeg filter for concatenating with silence gaps
        inputs = []
        filter_parts = []
        input_idx = 0

        for i, (seg, audio_file) in enumerate(zip(segments, audio_files)):
            if audio_file is None or not os.path.exists(audio_file):
                continue

            start_time = seg["start"]
            inputs.extend(["-i", audio_file])
            # Normalize each segment volume + delay to its correct position
            delay_ms = int(start_time * 1000)
            filter_parts.append(
                f"[{input_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,adelay={delay_ms}|{delay_ms}[a{input_idx}]"
            )
            input_idx += 1

        if input_idx == 0:
            raise RuntimeError("Không có audio segment nào để ghép.")

        # Mix all delayed audio streams
        # normalize=0 prevents amix from dividing volume (segments don't overlap)
        mix_inputs = "".join(f"[a{i}]" for i in range(input_idx))
        filter_parts.append(
            f"{mix_inputs}amix=inputs={input_idx}:duration=longest:dropout_transition=0:normalize=0[aout]"
        )

        filter_complex = ";".join(filter_parts)

        cmd = ["ffmpeg", "-y"]
        cmd.extend(inputs)
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-ac", "2",
            "-ar", "44100",
            "-t", str(total_duration),
            output_path,
        ])

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"Ghép audio thất bại:\n{result.stderr}")

        return output_path

    def export_video(self, video_path, segments, audio_files, output_path,
                     font_size=24, keep_original_audio=False,
                     original_audio_volume=0.1, subtitle_position=35,
                     progress_callback=None):
        """
        Final export: burn subtitles + replace/mix audio.
        subtitle_position: 0-90%, where to place subtitle from bottom of video.
        """
        if progress_callback:
            progress_callback("Đang tạo file phụ đề...")

        # Create subtitle file
        sub_path = tempfile.mktemp(suffix=".ass")
        self.create_subtitle_file(segments, sub_path, font_size, subtitle_position)

        if progress_callback:
            progress_callback("Đang ghép audio giọng đọc...")

        # Get video duration
        duration = self.get_video_duration(video_path)

        # Merge TTS audio
        tts_audio_path = tempfile.mktemp(suffix=".m4a")
        self.merge_tts_audio(segments, audio_files, duration, tts_audio_path)

        if progress_callback:
            progress_callback("Đang xuất video cuối cùng...")

        # Build final FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", tts_audio_path,
        ]

        # Build video filter: burn translated subs
        sub_filter = f"ass='{_escape_filter_path(sub_path)}'"
        video_filter = f"[0:v]{sub_filter}[vout]"

        if keep_original_audio:
            # Mix original audio (lowered) with TTS
            filter_complex = (
                f"[0:a]volume={original_audio_volume}[orig];"
                f"[orig][1:a]amix=inputs=2:duration=first[aout];"
                f"{video_filter}"
            )
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "[aout]",
            ])
        else:
            # Replace audio entirely with TTS
            cmd.extend([
                "-filter_complex", video_filter,
                "-map", "[vout]",
                "-map", "1:a",
            ])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ])

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"Xuất video thất bại:\n{result.stderr}")

        # Cleanup temp files
        for f in [sub_path, tts_audio_path]:
            if os.path.exists(f):
                os.remove(f)

        if progress_callback:
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            progress_callback(f"Xuất video xong! ({size_mb:.1f} MB)")

        return output_path

    def _format_time_ass(self, seconds):
        """Format seconds to ASS time format (H:MM:SS.cc)."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape_filter_path(path):
    """Escape path for FFmpeg filter."""
    return path.replace("\\", "/").replace(":", "\\:").replace("'", "'\\''")
