"""
Video Translator Tool - Video Processor
Combines translated subtitles, TTS audio, and original video using FFmpeg.
"""

import os
import subprocess
import tempfile
import json


class VideoProcessor:
    """Process video: burn subtitles, replace/mix audio, export."""

    def __init__(self):
        pass

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

    def create_subtitle_file(self, segments, output_path, font_size=24):
        """Create ASS subtitle file for burning into video."""
        # ASS header
        header = f"""[Script Info]
Title: Translated Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,40,1

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
            # Delay each audio segment to its correct position
            delay_ms = int(start_time * 1000)
            filter_parts.append(
                f"[{input_idx}:a]adelay={delay_ms}|{delay_ms}[a{input_idx}]"
            )
            input_idx += 1

        if input_idx == 0:
            raise RuntimeError("Không có audio segment nào để ghép.")

        # Mix all delayed audio streams
        mix_inputs = "".join(f"[a{i}]" for i in range(input_idx))
        filter_parts.append(
            f"{mix_inputs}amix=inputs={input_idx}:duration=longest:dropout_transition=0[aout]"
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
                     original_audio_volume=0.1, progress_callback=None):
        """
        Final export: burn subtitles + replace/mix audio.
        """
        if progress_callback:
            progress_callback("Đang tạo file phụ đề...")

        # Create subtitle file
        sub_path = tempfile.mktemp(suffix=".ass")
        self.create_subtitle_file(segments, sub_path, font_size)

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

        if keep_original_audio:
            # Mix original audio (lowered) with TTS
            filter_complex = (
                f"[0:a]volume={original_audio_volume}[orig];"
                f"[orig][1:a]amix=inputs=2:duration=first[aout];"
                f"[0:v]ass='{_escape_filter_path(sub_path)}'[vout]"
            )
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "[aout]",
            ])
        else:
            # Replace audio entirely with TTS
            filter_complex = f"[0:v]ass='{_escape_filter_path(sub_path)}'[vout]"
            cmd.extend([
                "-filter_complex", filter_complex,
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
