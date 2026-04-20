"""
Video Translator Tool - Translator
Uses OpenAI API to translate subtitles to Vietnamese.
"""

from openai import OpenAI


class Translator:
    """Translate subtitle segments using OpenAI API."""

    def __init__(self, api_key, model="gpt-4o-mini", base_url=None):
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.model = model

    def translate_segments(self, segments, source_lang="auto", target_lang="Vietnamese",
                           progress_callback=None):
        """
        Translate a list of subtitle segments.
        Translates in batches for efficiency.
        Returns segments with 'translated_text' field added.
        """
        if not segments:
            return segments

        batch_size = 20
        total = len(segments)
        translated = []

        for i in range(0, total, batch_size):
            batch = segments[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            if progress_callback:
                progress_callback(
                    f"Đang dịch batch {batch_num}/{total_batches}..."
                )

            translated_batch = self._translate_batch(batch, source_lang, target_lang)
            translated.extend(translated_batch)

        return translated

    def _translate_batch(self, segments, source_lang, target_lang):
        """Translate a batch of segments."""
        # Build numbered text for batch translation
        numbered_lines = []
        for idx, seg in enumerate(segments):
            numbered_lines.append(f"[{idx}] {seg['text']}")

        text_block = "\n".join(numbered_lines)

        system_prompt = (
            f"You are a professional subtitle translator. "
            f"Translate the following subtitles to {target_lang}. "
            f"Maintain the same numbering format [N]. "
            f"Keep translations natural, concise, and suitable for subtitles. "
            f"Do not add explanations. Only output the translated lines."
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_block},
            ],
            temperature=0.3,
        )

        translated_text = response.choices[0].message.content.strip()

        # Parse the translated lines back
        translated_map = {}
        for line in translated_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Match [N] pattern
            import re
            match = re.match(r"\[(\d+)\]\s*(.*)", line)
            if match:
                idx = int(match.group(1))
                text = match.group(2).strip()
                translated_map[idx] = text

        # Apply translations to segments
        result = []
        for idx, seg in enumerate(segments):
            new_seg = seg.copy()
            new_seg["translated_text"] = translated_map.get(idx, seg["text"])
            result.append(new_seg)

        return result
