"""
Video Translator Tool - Web Application
Flask-based web interface replacing the PyQt5 desktop app.
"""

import os
import sys
import json
import time
import threading
import queue
import tempfile
from datetime import datetime

from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename

from config import load_config, save_config

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global log queue for SSE
log_queues = {}
log_history = []

# Processing state
processing_state = {
    'current_video': None,
    'segments': None,
    'audio_files': None,
    'status': {},
}


def add_log(message, level='info'):
    """Add a log message and broadcast to all SSE clients."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    entry = {'time': timestamp, 'message': message, 'level': level}
    log_history.append(entry)
    if len(log_history) > 500:
        log_history.pop(0)
    for q in list(log_queues.values()):
        try:
            q.put_nowait(entry)
        except queue.Full:
            pass


def progress_callback(msg):
    add_log(msg)


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/video/<path:filename>')
def serve_video(filename):
    """Serve uploaded video files for preview."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/config', methods=['GET'])
def get_config():
    config = load_config()
    # Mask API keys for security
    safe = config.copy()
    if safe.get('openai_api_key'):
        key = safe['openai_api_key']
        safe['openai_api_key_masked'] = key[:8] + '...' + key[-4:] if len(key) > 12 else '***'
    if safe.get('fpt_api_key'):
        key = safe['fpt_api_key']
        safe['fpt_api_key_masked'] = key[:8] + '...' + key[-4:] if len(key) > 12 else '***'
    return jsonify(safe)


@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    config = load_config()
    for key in data:
        if key in config and not key.endswith('_masked'):
            config[key] = data[key]
    save_config(config)
    add_log('Đã lưu cài đặt', 'success')
    return jsonify({'status': 'ok'})


@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Không có file'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'Chưa chọn file'}), 400
    filename = secure_filename(f.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    f.save(filepath)
    processing_state['current_video'] = filepath
    add_log(f'Đã upload file: {filename}', 'success')
    return jsonify({'status': 'ok', 'path': filepath, 'filename': filename})


@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'Thiếu URL'}), 400

    def _run():
        try:
            add_log(f'Bắt đầu tải video từ: {url}')
            from downloader import VideoDownloader
            downloader = VideoDownloader()
            config = load_config()
            output_dir = config.get('output_dir', app.config['UPLOAD_FOLDER'])
            os.makedirs(output_dir, exist_ok=True)
            result = downloader.download(url, output_dir, progress_callback=progress_callback)
            processing_state['current_video'] = result
            add_log(f'Tải video xong: {os.path.basename(result)}', 'success')
        except Exception as e:
            add_log(f'Lỗi tải video: {e}', 'error')

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/extract', methods=['POST'])
def extract_subtitles():
    def _run():
        try:
            video = processing_state.get('current_video')
            if not video:
                add_log('Chưa có video để trích xuất', 'error')
                return
            add_log('Bắt đầu trích xuất phụ đề...')
            config = load_config()
            from subtitle_extractor import create_extractor
            extractor = create_extractor(config, progress_callback=progress_callback)
            segments = extractor.extract(video)
            processing_state['segments'] = segments
            add_log(f'Trích xuất xong: {len(segments)} đoạn phụ đề', 'success')
        except Exception as e:
            add_log(f'Lỗi trích xuất: {e}', 'error')

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/translate', methods=['POST'])
def translate_subtitles():
    def _run():
        try:
            segments = processing_state.get('segments')
            if not segments:
                add_log('Chưa có phụ đề để dịch', 'error')
                return
            add_log('Bắt đầu dịch phụ đề...')
            config = load_config()
            from translator import Translator
            translator = Translator(config)
            translated = translator.translate(segments, progress_callback=progress_callback)
            processing_state['segments'] = translated
            add_log(f'Dịch xong {len(translated)} đoạn', 'success')
        except Exception as e:
            add_log(f'Lỗi dịch: {e}', 'error')

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/tts', methods=['POST'])
def generate_tts():
    def _run():
        try:
            segments = processing_state.get('segments')
            if not segments:
                add_log('Chưa có phụ đề để tạo giọng đọc', 'error')
                return
            add_log('Bắt đầu tạo giọng đọc TTS...')
            config = load_config()
            from tts_generator import create_tts_engine
            engine = create_tts_engine(config, progress_callback=progress_callback)
            audio_files = engine.generate(segments)
            processing_state['audio_files'] = audio_files
            add_log(f'Tạo giọng đọc xong: {len(audio_files)} file audio', 'success')
        except Exception as e:
            add_log(f'Lỗi TTS: {e}', 'error')

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/export', methods=['POST'])
def export_video():
    data = request.json or {}

    def _run():
        try:
            video = processing_state.get('current_video')
            segments = processing_state.get('segments')
            audio_files = processing_state.get('audio_files')

            if not video:
                add_log('Chưa có video để xuất', 'error')
                return

            config = load_config()
            output_dir = config.get('output_dir', app.config['UPLOAD_FOLDER'])
            os.makedirs(output_dir, exist_ok=True)
            current = video

            # Feature flags from frontend
            burn_subtitles = data.get('burn_subtitles', True)
            use_tts = data.get('use_tts', True)
            keep_original_audio = data.get('keep_original_audio', False)
            original_audio_volume = data.get('original_audio_volume', 0.1)
            edit_options = data.get('edit_options', {})

            # Apply optional edits first (trim, speed, crop)
            from video_editor import VideoEditor
            editor = VideoEditor()

            if edit_options.get('trim', {}).get('enabled'):
                add_log('Đang cắt video...')
                trim = edit_options['trim']
                out = os.path.join(output_dir, f"exp_trim_{int(time.time())}.mp4")
                current = editor.trim(current, out, float(trim['start']), float(trim['end']),
                                      progress_callback=progress_callback)

            if edit_options.get('speed', {}).get('enabled'):
                add_log('Đang thay đổi tốc độ...')
                out = os.path.join(output_dir, f"exp_speed_{int(time.time())}.mp4")
                current = editor.change_speed(current, out, float(edit_options['speed']['factor']),
                                              progress_callback=progress_callback)

            if edit_options.get('crop', {}).get('enabled'):
                add_log('Đang crop video...')
                out = os.path.join(output_dir, f"exp_crop_{int(time.time())}.mp4")
                current = editor.crop_resize(current, out, edit_options['crop']['ratio'],
                                             progress_callback=progress_callback)

            # Now handle subtitle + TTS export
            from video_processor import VideoProcessor
            processor = VideoProcessor()

            if burn_subtitles and use_tts and segments and audio_files:
                # Full export: subtitles + TTS
                add_log('Đang xuất video với phụ đề + giọng đọc...')
                output_path = os.path.join(output_dir, f"output_{int(time.time())}.mp4")
                processor.export_video(
                    current, segments, audio_files, output_path,
                    font_size=config.get('subtitle_font_size', 24),
                    keep_original_audio=keep_original_audio,
                    original_audio_volume=original_audio_volume,
                    subtitle_position=config.get('subtitle_position', 35),
                    progress_callback=progress_callback,
                )
                current = output_path

            elif burn_subtitles and segments:
                # Only subtitles, no TTS
                add_log('Đang burn phụ đề (không có TTS)...')
                sub_path = tempfile.mktemp(suffix='.ass')
                processor.create_subtitle_file(
                    segments, sub_path,
                    font_size=config.get('subtitle_font_size', 24),
                    subtitle_position=config.get('subtitle_position', 35),
                )
                output_path = os.path.join(output_dir, f"output_{int(time.time())}.mp4")
                import subprocess
                from video_processor import _escape_filter_path
                cmd = [
                    'ffmpeg', '-y', '-i', current,
                    '-vf', f"ass='{_escape_filter_path(sub_path)}'",
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                    '-c:a', 'copy', output_path,
                ]
                subprocess.run(cmd, capture_output=True, timeout=600)
                current = output_path

            elif use_tts and segments and audio_files:
                # Only TTS, no subtitles
                add_log('Đang ghép giọng đọc TTS (không burn phụ đề)...')
                import subprocess
                duration = processor.get_video_duration(current)
                tts_audio = tempfile.mktemp(suffix='.m4a')
                processor.merge_tts_audio(segments, audio_files, duration, tts_audio)
                output_path = os.path.join(output_dir, f"output_{int(time.time())}.mp4")
                if keep_original_audio:
                    fc = f"[0:a]volume={original_audio_volume}[orig];[orig][1:a]amix=inputs=2:duration=first[aout]"
                    cmd = ['ffmpeg', '-y', '-i', current, '-i', tts_audio,
                           '-filter_complex', fc,
                           '-map', '0:v', '-map', '[aout]',
                           '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', output_path]
                else:
                    cmd = ['ffmpeg', '-y', '-i', current, '-i', tts_audio,
                           '-map', '0:v', '-map', '1:a',
                           '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', output_path]
                subprocess.run(cmd, capture_output=True, timeout=600)
                current = output_path
            else:
                add_log('Không có phụ đề/TTS — xuất video gốc (chỉ áp dụng edit)', 'warning')

            add_log(f'Xuất video xong: {current}', 'success')
        except Exception as e:
            add_log(f'Lỗi xuất video: {e}', 'error')

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/edit', methods=['POST'])
def edit_video():
    data = request.json or {}

    def _run():
        try:
            video = data.get('video_path') or processing_state.get('current_video')
            if not video:
                add_log('Chưa có video để chỉnh sửa', 'error')
                return

            from video_editor import VideoEditor
            from video_processor import VideoProcessor
            editor = VideoEditor()
            processor = VideoProcessor()
            config = load_config()
            output_dir = config.get('output_dir', app.config['UPLOAD_FOLDER'])
            os.makedirs(output_dir, exist_ok=True)

            current = video
            options = data.get('options', {})

            # Trim
            if options.get('trim', {}).get('enabled'):
                add_log('Đang cắt video...')
                trim = options['trim']
                out = os.path.join(output_dir, f"trim_{int(time.time())}.mp4")
                current = editor.trim(current, out, float(trim['start']), float(trim['end']),
                                      progress_callback=progress_callback)

            # Speed
            if options.get('speed', {}).get('enabled'):
                add_log('Đang thay đổi tốc độ...')
                out = os.path.join(output_dir, f"speed_{int(time.time())}.mp4")
                current = editor.change_speed(current, out, float(options['speed']['factor']),
                                              progress_callback=progress_callback)

            # Crop
            if options.get('crop', {}).get('enabled'):
                add_log('Đang crop video...')
                out = os.path.join(output_dir, f"crop_{int(time.time())}.mp4")
                current = editor.crop_resize(current, out, options['crop']['ratio'],
                                             progress_callback=progress_callback)

            # Background music
            if options.get('music', {}).get('enabled'):
                add_log('Đang thêm nhạc nền...')
                out = os.path.join(output_dir, f"music_{int(time.time())}.mp4")
                current = editor.add_background_music(
                    current, options['music']['path'], out,
                    music_volume=float(options['music'].get('volume', 0.3)),
                    keep_original=options['music'].get('keep_original', True),
                    progress_callback=progress_callback,
                )

            # Watermark
            if options.get('watermark', {}).get('enabled'):
                add_log('Đang thêm watermark...')
                out = os.path.join(output_dir, f"wm_{int(time.time())}.mp4")
                current = editor.add_watermark(
                    current, options['watermark']['path'], out,
                    position=options['watermark'].get('position', 'top-right'),
                    opacity=float(options['watermark'].get('opacity', 0.7)),
                    scale=float(options['watermark'].get('scale', 0.15)),
                    progress_callback=progress_callback,
                )

            # Subtitles (burn from segments)
            if options.get('subtitles', {}).get('enabled'):
                add_log('Đang thêm phụ đề...')
                segments = processing_state.get('segments')
                if segments:
                    sub_path = tempfile.mktemp(suffix='.ass')
                    processor.create_subtitle_file(
                        segments, sub_path,
                        font_size=int(options['subtitles'].get('font_size', 24)),
                        subtitle_position=int(options['subtitles'].get('position', 35)),
                    )
                    out = os.path.join(output_dir, f"sub_{int(time.time())}.mp4")
                    import subprocess
                    cmd = [
                        'ffmpeg', '-y', '-i', current,
                        '-vf', f"ass='{sub_path}'",
                        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                        '-c:a', 'copy', out,
                    ]
                    subprocess.run(cmd, capture_output=True, timeout=600)
                    current = out
                    add_log('Đã thêm phụ đề', 'success')
                else:
                    add_log('Không có phụ đề để burn (hãy trích xuất trước)', 'warning')

            # Audio adjustments
            if options.get('audio', {}).get('enabled'):
                add_log('Đang chỉnh âm thanh...')
                audio_opt = options['audio']
                mode = audio_opt.get('mode', 'keep')  # keep, mute, adjust
                out = os.path.join(output_dir, f"audio_{int(time.time())}.mp4")
                import subprocess
                if mode == 'mute':
                    cmd = ['ffmpeg', '-y', '-i', current, '-an',
                           '-c:v', 'copy', out]
                else:
                    vol = float(audio_opt.get('volume', 100)) / 100.0
                    cmd = ['ffmpeg', '-y', '-i', current,
                           '-af', f'volume={vol}',
                           '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', out]
                subprocess.run(cmd, capture_output=True, timeout=600)
                current = out
                add_log(f'Đã chỉnh âm thanh (mode={mode})', 'success')

            # TTS voice overlay
            if options.get('voice', {}).get('enabled'):
                add_log('Đang thêm giọng đọc TTS...')
                audio_files = processing_state.get('audio_files')
                segments = processing_state.get('segments')
                if audio_files and segments:
                    tts_audio = tempfile.mktemp(suffix='.m4a')
                    duration = processor.get_video_duration(current)
                    processor.merge_tts_audio(segments, audio_files, duration, tts_audio)
                    out = os.path.join(output_dir, f"voice_{int(time.time())}.mp4")
                    import subprocess
                    orig_vol = float(options['voice'].get('original_volume', 10)) / 100.0
                    fc = (f"[0:a]volume={orig_vol}[orig];[orig][1:a]amix=inputs=2:duration=first[aout]")
                    cmd = ['ffmpeg', '-y', '-i', current, '-i', tts_audio,
                           '-filter_complex', fc,
                           '-map', '0:v', '-map', '[aout]',
                           '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', out]
                    subprocess.run(cmd, capture_output=True, timeout=600)
                    current = out
                    add_log('Đã thêm giọng đọc TTS', 'success')
                else:
                    add_log('Chưa có audio TTS (hãy tạo giọng đọc trước)', 'warning')

            add_log(f'Chỉnh sửa video xong: {current}', 'success')
        except Exception as e:
            add_log(f'Lỗi chỉnh sửa: {e}', 'error')

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/logs')
def logs_sse():
    """Server-Sent Events endpoint for real-time logs."""
    client_id = id(threading.current_thread())
    q = queue.Queue(maxsize=100)
    log_queues[client_id] = q

    def generate():
        try:
            # Send history first
            for entry in log_history[-50:]:
                yield f"data: {json.dumps(entry)}\n\n"
            # Stream new logs
            while True:
                try:
                    entry = q.get(timeout=30)
                    yield f"data: {json.dumps(entry)}\n\n"
                except queue.Empty:
                    yield f": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            log_queues.pop(client_id, None)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/status')
def get_status():
    return jsonify({
        'has_video': processing_state.get('current_video') is not None,
        'has_segments': processing_state.get('segments') is not None,
        'has_audio': processing_state.get('audio_files') is not None,
        'video_path': processing_state.get('current_video', ''),
        'segment_count': len(processing_state.get('segments') or []),
    })


if __name__ == '__main__':
    add_log('Video Translator Tool đã khởi động', 'success')
    app.run(host='0.0.0.0', port=3000, debug=False)
