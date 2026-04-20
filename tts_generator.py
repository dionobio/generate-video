"""
Video Translator Tool - TTS Generator
Supports multiple TTS engines: OpenAI TTS (paid) and Google TTS (free).
"""

import os
import tempfile


class BaseTTSEngine:
    """Base class for TTS engines."""

    def generate_segment_audio(self, text, output_path):
        raise NotImplementedError

    def generate_all_segments(self, segments, output_dir=None, progress_callback=None):
        """
        Generate TTS audio for all translated segments.
        Returns list of audio file paths aligned with segments.
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="vtool_tts_")
        os.makedirs(output_dir, exist_ok=True)

        audio_files = []
        total = len(segments)

        for i, seg in enumerate(segments):
            text = seg.get("translated_text", seg["text"])
            if not text.strip():
                audio_files.append(None)
                continue

            if progress_callback:
                progress_callback(f"Đang tạo giọng nói {i + 1}/{total}...")

            audio_path = os.path.join(output_dir, f"seg_{i:04d}.mp3")
            try:
                self.generate_segment_audio(text, audio_path)
                audio_files.append(audio_path)
            except Exception as e:
                print(f"TTS error for segment {i}: {e}")
                audio_files.append(None)

        success_count = len([f for f in audio_files if f])
        if progress_callback:
            progress_callback(f"Tạo giọng nói xong: {success_count}/{total} đoạn")

        return audio_files


class OpenAITTSEngine(BaseTTSEngine):
    """OpenAI TTS - High quality, paid."""

    VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"]

    def __init__(self, api_key, model="tts-1", voice="alloy", base_url=None):
        from openai import OpenAI
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.model = model
        self.voice = voice

    def generate_segment_audio(self, text, output_path):
        response = self.client.audio.speech.create(
            model=self.model,
            voice=self.voice,
            input=text,
            response_format="mp3",
        )
        response.stream_to_file(output_path)
        return output_path


class GoogleTTSEngine(BaseTTSEngine):
    """Google TTS (gTTS) - Free, decent quality."""

    # Supported languages with common codes
    LANGUAGES = {
        "vi": "Tiếng Việt",
        "en": "English",
        "zh-CN": "Chinese (Simplified)",
        "zh-TW": "Chinese (Traditional)",
        "ja": "Japanese",
        "ko": "Korean",
        "th": "Thai",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
    }

    def __init__(self, lang="vi", slow=False):
        self.lang = lang
        self.slow = slow

    def generate_segment_audio(self, text, output_path):
        from gtts import gTTS
        tts = gTTS(text=text, lang=self.lang, slow=self.slow)
        tts.save(output_path)
        return output_path


class EdgeTTSEngine(BaseTTSEngine):
    """Microsoft Edge TTS - Free, high quality, many voices."""

    # Popular Vietnamese voices
    VI_VOICES = [
        "vi-VN-HoaiMyNeural",   # Female
        "vi-VN-NamMinhNeural",  # Male
    ]

    # Other popular voices
    VOICES = {
        "vi": ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"],
        "en": ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural"],
        "zh": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"],
        "ja": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
        "ko": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural"],
    }

    def __init__(self, voice="vi-VN-HoaiMyNeural", rate="+0%", pitch="+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    def generate_segment_audio(self, text, output_path):
        import asyncio
        import edge_tts

        async def _generate():
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch,
            )
            await communicate.save(output_path)

        # Run async in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    loop2 = asyncio.new_event_loop()
                    pool.submit(loop2.run_until_complete, _generate()).result()
                    loop2.close()
            else:
                loop.run_until_complete(_generate())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_generate())

        return output_path


def create_tts_engine(provider, **kwargs):
    """
    Factory function to create TTS engine.

    provider: "openai", "google", or "edge"
    kwargs: provider-specific arguments
    """
    if provider == "openai":
        return OpenAITTSEngine(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "tts-1"),
            voice=kwargs.get("voice", "alloy"),
            base_url=kwargs.get("base_url"),
        )
    elif provider == "google":
        return GoogleTTSEngine(
            lang=kwargs.get("lang", "vi"),
            slow=kwargs.get("slow", False),
        )
    elif provider == "edge":
        return EdgeTTSEngine(
            voice=kwargs.get("voice", "vi-VN-HoaiMyNeural"),
            rate=kwargs.get("rate", "+0%"),
            pitch=kwargs.get("pitch", "+0Hz"),
        )
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")
