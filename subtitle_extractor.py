"""
Video Translator Tool - Subtitle Extractor
Supports two modes:
  - Local Whisper (requires torch + openai-whisper)
  - OpenAI Whisper API (cloud, requires only openai package + API key)
"""

import os
import subprocess
import tempfile


def extract_audio(video_path, audio_format="wav"):
    """Extract audio from video file using FFmpeg."""
    suffix = f".{audio_format}"
    audio_path = tempfile.mktemp(suffix=suffix)

    cmd = ["ffmpeg", "-y", "-i", video_path, "-vn"]

    if audio_format == "wav":
        cmd.extend(["-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1"])
    elif audio_format == "mp3":
        cmd.extend(["-acodec", "libmp3lame", "-ar", "16000", "-ac", "1", "-b:a", "64k"])

    cmd.append(audio_path)

    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Trích xuất audio thất bại:\n{result.stderr}")
    return audio_path


class LocalWhisperExtractor:
    """Extract subtitles using local Whisper model (requires torch)."""

    def __init__(self, model_name="base"):
        self.model_name = model_name
        self.model = None

    def _load_model(self):
        if self.model is None:
            import whisper
            self.model = whisper.load_model(self.model_name)

    def extract_subtitles(self, video_path, progress_callback=None):
        if progress_callback:
            progress_callback("Đang trích xuất audio...")

        audio_path = extract_audio(video_path, audio_format="wav")

        try:
            if progress_callback:
                progress_callback(f"Đang load model Whisper local ({self.model_name})...")

            self._load_model()

            if progress_callback:
                progress_callback("Đang nhận dạng giọng nói (local)...")

            result = self.model.transcribe(
                audio_path,
                verbose=False,
                word_timestamps=False,
            )

            segments = []
            for seg in result.get("segments", []):
                segments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"].strip(),
                })

            detected_language = result.get("language", "unknown")

            if progress_callback:
                progress_callback(
                    f"Nhận dạng xong: {len(segments)} đoạn, "
                    f"ngôn ngữ: {detected_language}"
                )

            return segments, detected_language

        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)


class OpenAIWhisperExtractor:
    """Extract subtitles using OpenAI Whisper API (cloud). No torch needed."""

    # API supports files up to 25MB. For larger files, we split.
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB

    def __init__(self, api_key, model="whisper-1", base_url=None):
        from openai import OpenAI
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.model = model

    def _call_whisper_api(self, audio_path):
        """
        Call Whisper API with fallback for proxies that don't support verbose_json.
        Returns (segments_list, detected_language).
        """
        import json as json_mod

        # Try verbose_json first (gives us timestamps)
        try:
            with open(audio_path, "rb") as f:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )

            # Response could be a Pydantic object or a dict or a JSON string
            data = self._normalize_response(response)

            if data and "segments" in data and data["segments"]:
                segments = []
                for seg in data["segments"]:
                    s = self._extract_seg(seg)
                    if s:
                        segments.append(s)
                lang = data.get("language", "unknown")
                return segments, lang

        except Exception as e:
            err_msg = str(e)
            # If it's a real auth/network error, re-raise
            if any(k in err_msg.lower() for k in ["401", "403", "connection", "timeout", "api key"]):
                raise

        # Fallback: use SRT format (most proxies support this)
        try:
            with open(audio_path, "rb") as f:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=f,
                    response_format="srt",
                )

            srt_text = response if isinstance(response, str) else str(response)
            segments = self._parse_srt(srt_text)
            return segments, "unknown"

        except Exception:
            pass

        # Final fallback: plain text (no timestamps)
        with open(audio_path, "rb") as f:
            response = self.client.audio.transcriptions.create(
                model=self.model,
                file=f,
                response_format="text",
            )

        text = response if isinstance(response, str) else str(response)
        if text.strip():
            return [{"start": 0.0, "end": 10.0, "text": text.strip()}], "unknown"

        return [], "unknown"

    def _normalize_response(self, response):
        """Normalize API response to a dict."""
        import json as json_mod

        if response is None:
            return None

        # Already a dict
        if isinstance(response, dict):
            return response

        # JSON string
        if isinstance(response, str):
            try:
                return json_mod.loads(response)
            except (json_mod.JSONDecodeError, TypeError):
                return None

        # Pydantic model or similar object with attributes
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if hasattr(response, "to_dict"):
            return response.to_dict()
        if hasattr(response, "__dict__"):
            data = {}
            for key in ["text", "language", "segments", "duration"]:
                val = getattr(response, key, None)
                if val is not None:
                    if key == "segments" and val:
                        data["segments"] = [
                            self._seg_to_dict(s) for s in val
                        ]
                    else:
                        data[key] = val
            return data

        return None

    def _seg_to_dict(self, seg):
        """Convert a segment object to dict."""
        if isinstance(seg, dict):
            return seg
        if hasattr(seg, "model_dump"):
            return seg.model_dump()
        return {
            "start": getattr(seg, "start", 0),
            "end": getattr(seg, "end", 0),
            "text": getattr(seg, "text", ""),
        }

    def _extract_seg(self, seg):
        """Extract start/end/text from a segment (dict or object)."""
        if isinstance(seg, dict):
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            text = seg.get("text", "").strip()
        else:
            start = getattr(seg, "start", 0)
            end = getattr(seg, "end", 0)
            text = getattr(seg, "text", "").strip()
        if text:
            return {"start": float(start), "end": float(end), "text": text}
        return None

    def _parse_srt(self, srt_text):
        """Parse SRT format text into segments."""
        import re
        segments = []
        blocks = re.split(r"\n\s*\n", srt_text.strip())
        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                time_match = re.match(
                    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})",
                    lines[1].strip(),
                )
                if time_match:
                    g = time_match.groups()
                    start = int(g[0])*3600 + int(g[1])*60 + int(g[2]) + int(g[3])/1000
                    end = int(g[4])*3600 + int(g[5])*60 + int(g[6]) + int(g[7])/1000
                    text = " ".join(lines[2:]).strip()
                    if text:
                        segments.append({"start": start, "end": end, "text": text})
        return segments

    def extract_subtitles(self, video_path, progress_callback=None):
        if progress_callback:
            progress_callback("Đang trích xuất audio cho Whisper API...")

        # Extract as mp3 to reduce file size
        audio_path = extract_audio(video_path, audio_format="mp3")

        try:
            file_size = os.path.getsize(audio_path)
            if progress_callback:
                size_mb = file_size / (1024 * 1024)
                progress_callback(f"Audio: {size_mb:.1f} MB")

            if file_size > self.MAX_FILE_SIZE:
                if progress_callback:
                    progress_callback("File > 25MB, đang chia nhỏ...")
                return self._extract_chunked(audio_path, progress_callback)

            if progress_callback:
                progress_callback("Đang gửi lên OpenAI Whisper API...")

            segments, lang = self._call_whisper_api(audio_path)

            if progress_callback:
                progress_callback(
                    f"Nhận dạng xong: {len(segments)} đoạn, "
                    f"ngôn ngữ: {lang}"
                )

            return segments, lang

        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def _extract_chunked(self, audio_path, progress_callback=None):
        """Split large audio files and process in chunks."""
        import json

        # Get duration
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", audio_path,
        ]
        result = subprocess.run(probe_cmd, capture_output=True, encoding="utf-8", errors="replace")
        info = json.loads(result.stdout)
        total_duration = float(info["format"]["duration"])

        # Split into ~10 minute chunks
        chunk_duration = 600  # 10 minutes
        all_segments = []
        chunk_idx = 0
        offset = 0.0

        while offset < total_duration:
            chunk_path = tempfile.mktemp(suffix=".mp3")
            cmd = [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(offset),
                "-t", str(chunk_duration),
                "-acodec", "libmp3lame",
                "-b:a", "64k",
                chunk_path,
            ]
            subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=120)

            if progress_callback:
                progress_callback(
                    f"Đang xử lý chunk {chunk_idx + 1} "
                    f"({offset:.0f}s - {min(offset + chunk_duration, total_duration):.0f}s)..."
                )

            try:
                chunk_segments, detected_language = self._call_whisper_api(chunk_path)
                for seg in chunk_segments:
                    all_segments.append({
                        "start": seg["start"] + offset,
                        "end": seg["end"] + offset,
                        "text": seg["text"],
                    })
            finally:
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)

            offset += chunk_duration
            chunk_idx += 1

        if progress_callback:
            progress_callback(
                f"Nhận dạng xong: {len(all_segments)} đoạn, "
                f"ngôn ngữ: {detected_language}"
            )

        return all_segments, detected_language


def create_extractor(mode, **kwargs):
    """
    Factory function.
    mode: "local" or "api"
    """
    if mode == "local":
        return LocalWhisperExtractor(
            model_name=kwargs.get("model_name", "base"),
        )
    elif mode == "api":
        return OpenAIWhisperExtractor(
            api_key=kwargs.get("api_key", ""),
            base_url=kwargs.get("base_url"),
        )
    else:
        raise ValueError(f"Unknown extractor mode: {mode}")


# --- Utility functions ---

def segments_to_srt(segments):
    """Convert segments to SRT format string."""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _format_time_srt(seg["start"])
        end = _format_time_srt(seg["end"])
        text = seg.get("translated_text", seg["text"])
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _format_time_srt(seconds):
    """Format seconds to SRT time format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
