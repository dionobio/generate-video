"""
Video Translator Tool - Video Downloader
Supports Douyin, RedNote (Xiaohongshu), TikTok, and other platforms via yt-dlp.
"""

import os
import re
import subprocess
import tempfile


class VideoDownloader:
    """Download videos from various platforms."""

    SUPPORTED_PLATFORMS = {
        "douyin": ["douyin.com", "iesdouyin.com"],
        "rednote": ["xiaohongshu.com", "xhslink.com"],
        "tiktok": ["tiktok.com"],
        "bilibili": ["bilibili.com", "b23.tv"],
        "youtube": ["youtube.com", "youtu.be"],
    }

    def __init__(self, output_dir=None):
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="vtool_")
        os.makedirs(self.output_dir, exist_ok=True)

    def detect_platform(self, url):
        for platform, domains in self.SUPPORTED_PLATFORMS.items():
            for domain in domains:
                if domain in url:
                    return platform
        return "unknown"

    def download(self, url, progress_callback=None):
        """
        Download video from URL.
        Returns path to downloaded video file.
        """
        platform = self.detect_platform(url)
        output_template = os.path.join(self.output_dir, "%(title).50s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            "--print", "after_move:filepath",
        ]

        # Platform-specific options
        if platform == "douyin":
            cmd.extend(["--extractor-args", "douyinvod:referer=https://www.douyin.com/"])
        elif platform == "rednote":
            cmd.extend([
                "--user-agent",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            ])

        cmd.append(url)

        if progress_callback:
            progress_callback("Đang tải video...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Tải video thất bại:\n{result.stderr}")

        # Get the output file path from stdout
        filepath = result.stdout.strip().split("\n")[-1].strip()

        if not os.path.exists(filepath):
            # Fallback: find the most recent mp4 in output dir
            files = [
                os.path.join(self.output_dir, f)
                for f in os.listdir(self.output_dir)
                if f.endswith(".mp4")
            ]
            if files:
                filepath = max(files, key=os.path.getmtime)
            else:
                raise RuntimeError("Không tìm thấy file video sau khi tải.")

        if progress_callback:
            progress_callback(f"Tải xong: {os.path.basename(filepath)}")

        return filepath
