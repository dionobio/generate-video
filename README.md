# Video Translator Tool

Desktop tool để tải video từ Douyin, RedNote, TikTok... sau đó tự động:
1. Trích xuất phụ đề (Whisper AI)
2. Dịch sang tiếng Việt (OpenAI GPT)
3. Tạo giọng đọc tiếng Việt (OpenAI TTS)
4. Burn phụ đề + ghép audio → Xuất video hoàn chỉnh

## Yêu cầu hệ thống

- Python 3.9+
- FFmpeg (cài sẵn trên hệ thống)
- OpenAI API Key

## Cài đặt

```bash
# 1. Cài FFmpeg (nếu chưa có)
# macOS:
brew install ffmpeg
# Ubuntu/Debian:
sudo apt install ffmpeg
# Windows: tải từ https://ffmpeg.org/download.html

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Chạy app
python main.py
```

## Sử dụng

### Cách 1: Xử lý tự động (khuyến nghị)
1. Mở app → Tab **Cài đặt** → Nhập OpenAI API Key → **Lưu Cài Đặt**
2. Quay lại tab **Xử lý Video**
3. Dán link video hoặc chọn file local
4. Bấm **XỬ LÝ TẤT CẢ** → Đợi hoàn thành

### Cách 2: Từng bước
1. Tải video hoặc chọn file local
2. Bấm **Trích Phụ Đề** → Whisper sẽ nhận dạng
3. Bấm **Dịch sang Tiếng Việt** → GPT dịch
4. Bấm **Tạo Giọng Đọc** → OpenAI TTS
5. Bấm **Xuất Video** → FFmpeg ghép tất cả

## Tùy chỉnh

| Option | Mô tả |
|--------|--------|
| Whisper model | tiny/base/small/medium/large - model lớn hơn chính xác hơn nhưng chậm hơn |
| Giọng đọc | alloy/echo/fable/onyx/nova/shimmer - các giọng OpenAI TTS |
| Font size | Kích thước chữ phụ đề |
| Giữ âm thanh gốc | Mix audio gốc (nhỏ tiếng) với giọng đọc mới |
| TTS Model | tts-1 (nhanh) hoặc tts-1-hd (chất lượng cao hơn) |

## Cấu trúc project

```
video-translator-tool/
├── main.py                 # GUI chính (PyQt5)
├── config.py               # Quản lý cài đặt
├── downloader.py           # Tải video (yt-dlp)
├── subtitle_extractor.py   # Trích xuất phụ đề (Whisper)
├── translator.py           # Dịch thuật (OpenAI)
├── tts_generator.py        # Text-to-Speech (OpenAI)
├── video_processor.py      # Xử lý video (FFmpeg)
└── requirements.txt        # Dependencies
```

## Nền tảng hỗ trợ

- Douyin (抖音)
- RedNote / Xiaohongshu (小红书)
- TikTok
- Bilibili (哔哩哔哩)
- YouTube
- Và các nền tảng khác mà yt-dlp hỗ trợ
