"""
Video Translator Tool - Configuration
"""

import os
import json

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".video_translator_config.json")

DEFAULT_CONFIG = {
    "openai_api_key": "",
    "openai_base_url": "",
    "openai_model": "gpt-4o-mini",
    "tts_model": "tts-1",
    "tts_voice": "alloy",
    "tts_speed": "normal",
    "fpt_api_key": "",
    "whisper_model": "base",
    "target_language": "Vietnamese",
    "subtitle_font_size": 24,
    "subtitle_position": 35,
    "subtitle_font_color": "white",
    "subtitle_bg_color": "black@0.5",
    "output_dir": os.path.join(os.path.expanduser("~"), "VideoTranslator_Output"),
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
            config = DEFAULT_CONFIG.copy()
            config.update(saved)
            return config
    return DEFAULT_CONFIG.copy()


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
