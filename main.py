"""
Video Translator Tool - Main GUI Application
PyQt5 desktop application for downloading, translating, and dubbing videos.
"""

import sys
import os
import threading

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QComboBox, QSpinBox, QCheckBox, QFileDialog, QTabWidget,
    QGroupBox, QFormLayout, QMessageBox, QFrame,
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QIcon

from config import load_config, save_config


class WorkerSignals(QObject):
    """Signals for background worker threads."""
    progress = pyqtSignal(str)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.signals = WorkerSignals()
        self.current_video_path = None
        self.current_segments = None
        self.current_audio_files = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setWindowTitle("Video Translator Tool")
        self.setMinimumSize(800, 650)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        # Title
        title = QLabel("Video Translator Tool")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Tải video → Trích phụ đề → Dịch → Giọng đọc → Xuất video")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(subtitle)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._create_main_tab(), "Xử lý Video")
        tabs.addTab(self._create_settings_tab(), "Cài đặt")
        layout.addWidget(tabs)

        # Progress section
        progress_group = QGroupBox("Tiến trình")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(180)
        self.log_text.setFont(QFont("Consolas", 9))
        progress_layout.addWidget(self.log_text)

        layout.addWidget(progress_group)

    def _create_main_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- Input Section ---
        input_group = QGroupBox("Nguồn Video")
        input_layout = QVBoxLayout(input_group)

        # URL input
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "Dán link Douyin, RedNote, TikTok, Bilibili, YouTube..."
        )
        url_row.addWidget(self.url_input)
        self.btn_download = QPushButton("Tải Video")
        self.btn_download.setFixedWidth(120)
        url_row.addWidget(self.btn_download)
        input_layout.addLayout(url_row)

        # Or local file
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Hoặc:"))
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Chọn file video từ máy tính...")
        self.file_path_input.setReadOnly(True)
        file_row.addWidget(self.file_path_input)
        self.btn_browse = QPushButton("Chọn File")
        self.btn_browse.setFixedWidth(120)
        file_row.addWidget(self.btn_browse)
        input_layout.addLayout(file_row)

        layout.addWidget(input_group)

        # --- Processing Section ---
        process_group = QGroupBox("Xử lý")
        process_layout = QVBoxLayout(process_group)

        # Options row 1: Whisper settings
        opts_row = QHBoxLayout()

        opts_row.addWidget(QLabel("Whisper:"))
        self.whisper_mode_combo = QComboBox()
        self.whisper_mode_combo.addItems([
            "API (cloud, không cần torch)",
            "Local (cần cài torch)",
        ])
        self.whisper_mode_combo.setCurrentText(
            self.config.get("whisper_mode", "API (cloud, không cần torch)")
        )
        self.whisper_mode_combo.currentTextChanged.connect(self._on_whisper_mode_changed)
        opts_row.addWidget(self.whisper_mode_combo)

        opts_row.addWidget(QLabel("Model:"))
        self.whisper_combo = QComboBox()
        self._update_whisper_model_options()
        opts_row.addWidget(self.whisper_combo)

        opts_row.addWidget(QLabel("TTS:"))
        self.tts_provider_combo = QComboBox()
        self.tts_provider_combo.addItems(["OpenAI (trả phí)", "Google (miễn phí)", "Edge (miễn phí)"])
        self.tts_provider_combo.setCurrentText(self.config.get("tts_provider", "OpenAI (trả phí)"))
        self.tts_provider_combo.currentTextChanged.connect(self._on_tts_provider_changed)
        opts_row.addWidget(self.tts_provider_combo)

        opts_row.addWidget(QLabel("Giọng đọc:"))
        self.voice_combo = QComboBox()
        opts_row.addWidget(self.voice_combo)

        # Initialize voice list based on current provider
        self._update_voice_options()

        opts_row.addWidget(QLabel("Font size:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 60)
        self.font_size_spin.setValue(self.config.get("subtitle_font_size", 24))
        opts_row.addWidget(self.font_size_spin)

        process_layout.addLayout(opts_row)

        # Keep original audio option
        audio_row = QHBoxLayout()
        self.keep_audio_check = QCheckBox("Giữ âm thanh gốc (nhỏ tiếng)")
        self.keep_audio_check.setChecked(False)
        audio_row.addWidget(self.keep_audio_check)
        audio_row.addStretch()
        process_layout.addLayout(audio_row)

        layout.addWidget(process_group)

        # --- Action Buttons ---
        btn_row = QHBoxLayout()

        self.btn_extract = QPushButton("1. Trích Phụ Đề")
        self.btn_extract.setEnabled(False)
        self.btn_extract.setMinimumHeight(40)
        btn_row.addWidget(self.btn_extract)

        self.btn_translate = QPushButton("2. Dịch sang Tiếng Việt")
        self.btn_translate.setEnabled(False)
        self.btn_translate.setMinimumHeight(40)
        btn_row.addWidget(self.btn_translate)

        self.btn_tts = QPushButton("3. Tạo Giọng Đọc")
        self.btn_tts.setEnabled(False)
        self.btn_tts.setMinimumHeight(40)
        btn_row.addWidget(self.btn_tts)

        self.btn_export = QPushButton("4. Xuất Video")
        self.btn_export.setEnabled(False)
        self.btn_export.setMinimumHeight(40)
        btn_row.addWidget(self.btn_export)

        layout.addLayout(btn_row)

        # One-click button
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self.btn_all = QPushButton("⚡ XỬ LÝ TẤT CẢ (Tự động từ đầu đến cuối)")
        self.btn_all.setMinimumHeight(45)
        self.btn_all.setEnabled(False)
        self.btn_all.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:disabled { background-color: #ccc; color: #666; }"
        )
        layout.addWidget(self.btn_all)

        return tab

    def _create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form_group = QGroupBox("API & Output Settings")
        form = QFormLayout(form_group)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(self.config.get("openai_api_key", ""))
        self.api_key_input.setPlaceholderText("sk-...")
        form.addRow("OpenAI API Key:", self.api_key_input)

        self.base_url_input = QLineEdit()
        self.base_url_input.setText(self.config.get("openai_base_url", ""))
        self.base_url_input.setPlaceholderText(
            "Để trống nếu dùng OpenAI chính hãng, hoặc nhập URL proxy (vd: https://v98store.com/v1)"
        )
        form.addRow("API Base URL:", self.base_url_input)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1-nano"])
        self.model_combo.setCurrentText(self.config.get("openai_model", "gpt-4o-mini"))
        form.addRow("Translation Model:", self.model_combo)

        self.tts_model_combo = QComboBox()
        self.tts_model_combo.addItems(["tts-1", "tts-1-hd"])
        self.tts_model_combo.setCurrentText(self.config.get("tts_model", "tts-1"))
        form.addRow("TTS Model (OpenAI):", self.tts_model_combo)

        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText(self.config.get("output_dir", ""))
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_input)
        btn_out_browse = QPushButton("Browse")
        btn_out_browse.clicked.connect(self._browse_output_dir)
        output_row.addWidget(btn_out_browse)
        form.addRow("Output Directory:", output_row)

        layout.addWidget(form_group)

        btn_save = QPushButton("Lưu Cài Đặt")
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        layout.addStretch()
        return tab

    def _connect_signals(self):
        self.btn_download.clicked.connect(self._on_download)
        self.btn_browse.clicked.connect(self._on_browse_file)
        self.btn_extract.clicked.connect(self._on_extract)
        self.btn_translate.clicked.connect(self._on_translate)
        self.btn_tts.clicked.connect(self._on_tts)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_all.clicked.connect(self._on_process_all)

        self.signals.progress.connect(self._log)
        self.signals.status.connect(self._update_status)
        self.signals.finished.connect(self._on_task_finished)
        self.signals.error.connect(self._on_error)

    def _log(self, msg):
        self.log_text.append(msg)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def _update_status(self, msg):
        self.statusBar().showMessage(msg)

    def _set_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.btn_download.setEnabled(not busy)
        self.btn_browse.setEnabled(not busy)
        if not busy:
            self._update_button_states()

    def _update_button_states(self):
        has_video = self.current_video_path is not None
        has_segments = self.current_segments is not None
        has_translated = (
            has_segments
            and len(self.current_segments) > 0
            and "translated_text" in self.current_segments[0]
        )
        has_audio = self.current_audio_files is not None

        self.btn_extract.setEnabled(has_video)
        self.btn_translate.setEnabled(has_segments)
        self.btn_tts.setEnabled(has_translated)
        self.btn_export.setEnabled(has_audio)
        self.btn_all.setEnabled(has_video)

    def _get_api_key(self):
        key = self.api_key_input.text().strip()
        if not key:
            key = self.config.get("openai_api_key", "")
        if not key:
            QMessageBox.warning(
                self, "Thiếu API Key",
                "Vui lòng nhập OpenAI API Key trong tab Cài đặt."
            )
            return None
        return key

    def _get_base_url(self):
        """Get custom base URL (or None for default OpenAI)."""
        url = self.base_url_input.text().strip()
        if not url:
            url = self.config.get("openai_base_url", "")
        return url if url else None

    # --- Actions ---

    def _on_browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn Video",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.flv);;All Files (*)",
        )
        if path:
            self.file_path_input.setText(path)
            self.current_video_path = path
            self._log(f"Đã chọn file: {path}")
            self._update_button_states()

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục output")
        if d:
            self.output_dir_input.setText(d)

    def _on_tts_provider_changed(self, text):
        self._update_voice_options()

    def _update_voice_options(self):
        """Update voice dropdown based on selected TTS provider."""
        self.voice_combo.clear()
        provider = self.tts_provider_combo.currentText()

        if "OpenAI" in provider:
            self.voice_combo.addItems([
                "alloy", "ash", "ballad", "coral", "echo",
                "fable", "onyx", "nova", "sage", "shimmer",
            ])
            saved_voice = self.config.get("tts_voice", "alloy")
            if saved_voice in [self.voice_combo.itemText(i) for i in range(self.voice_combo.count())]:
                self.voice_combo.setCurrentText(saved_voice)
        elif "Google" in provider:
            self.voice_combo.addItems([
                "vi (Tiếng Việt)",
                "en (English)",
                "zh-CN (Chinese Simplified)",
                "zh-TW (Chinese Traditional)",
                "ja (Japanese)",
                "ko (Korean)",
                "th (Thai)",
                "fr (French)",
            ])
        elif "Edge" in provider:
            self.voice_combo.addItems([
                "vi-VN-HoaiMyNeural (Nữ VN)",
                "vi-VN-NamMinhNeural (Nam VN)",
                "en-US-JennyNeural (Nữ US)",
                "en-US-GuyNeural (Nam US)",
                "en-GB-SoniaNeural (Nữ UK)",
                "zh-CN-XiaoxiaoNeural (Nữ CN)",
                "zh-CN-YunxiNeural (Nam CN)",
                "ja-JP-NanamiNeural (Nữ JP)",
                "ko-KR-SunHiNeural (Nữ KR)",
            ])

    def _on_whisper_mode_changed(self, text):
        self._update_whisper_model_options()

    def _update_whisper_model_options(self):
        """Update Whisper model dropdown based on mode."""
        self.whisper_combo.clear()
        mode = self.whisper_mode_combo.currentText()
        if "API" in mode:
            self.whisper_combo.addItems(["whisper-1"])
        else:
            self.whisper_combo.addItems(["tiny", "base", "small", "medium", "large"])
            saved = self.config.get("whisper_model", "base")
            if saved in [self.whisper_combo.itemText(i) for i in range(self.whisper_combo.count())]:
                self.whisper_combo.setCurrentText(saved)

    def _get_whisper_mode(self):
        """Return 'api' or 'local'."""
        text = self.whisper_mode_combo.currentText()
        return "api" if "API" in text else "local"

    def _save_settings(self):
        self.config["openai_api_key"] = self.api_key_input.text().strip()
        self.config["openai_base_url"] = self.base_url_input.text().strip()
        self.config["openai_model"] = self.model_combo.currentText()
        self.config["tts_model"] = self.tts_model_combo.currentText()
        self.config["tts_provider"] = self.tts_provider_combo.currentText()
        self.config["output_dir"] = self.output_dir_input.text().strip()
        self.config["whisper_mode"] = self.whisper_mode_combo.currentText()
        self.config["whisper_model"] = self.whisper_combo.currentText()
        self.config["tts_voice"] = self.voice_combo.currentText()
        self.config["subtitle_font_size"] = self.font_size_spin.value()
        save_config(self.config)
        self._log("Đã lưu cài đặt.")
        QMessageBox.information(self, "Thành công", "Đã lưu cài đặt!")

    def _on_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập URL video.")
            return
        self._set_busy(True)
        threading.Thread(target=self._do_download, args=(url,), daemon=True).start()

    def _do_download(self, url):
        try:
            from downloader import VideoDownloader
            dl = VideoDownloader()
            path = dl.download(url, progress_callback=self.signals.progress.emit)
            self.current_video_path = path
            self.signals.progress.emit(f"Video đã tải: {path}")
            self.signals.finished.emit("download")
        except Exception as e:
            self.signals.error.emit(f"Lỗi tải video: {e}")

    def _on_extract(self):
        if not self.current_video_path:
            return
        whisper_mode = self._get_whisper_mode()
        api_key = None
        if whisper_mode == "api":
            api_key = self._get_api_key()
            if not api_key:
                return
        self._set_busy(True)
        threading.Thread(
            target=self._do_extract, args=(whisper_mode, api_key), daemon=True
        ).start()

    def _do_extract(self, whisper_mode=None, api_key=None):
        try:
            from subtitle_extractor import create_extractor

            if whisper_mode is None:
                whisper_mode = self._get_whisper_mode()

            if whisper_mode == "api":
                if api_key is None:
                    api_key = self.api_key_input.text().strip() or self.config.get("openai_api_key", "")
                base_url = self._get_base_url()
                self.signals.progress.emit("Sử dụng OpenAI Whisper API (cloud)...")
                extractor = create_extractor("api", api_key=api_key, base_url=base_url)
            else:
                model = self.whisper_combo.currentText()
                self.signals.progress.emit(f"Sử dụng Whisper local (model: {model})...")
                extractor = create_extractor("local", model_name=model)

            segments, lang = extractor.extract_subtitles(
                self.current_video_path,
                progress_callback=self.signals.progress.emit,
            )
            self.current_segments = segments
            self.signals.progress.emit(
                f"Trích xuất xong: {len(segments)} đoạn (ngôn ngữ: {lang})"
            )
            self.signals.finished.emit("extract")
        except Exception as e:
            self.signals.error.emit(f"Lỗi trích xuất phụ đề: {e}")

    def _on_translate(self):
        if not self.current_segments:
            return
        api_key = self._get_api_key()
        if not api_key:
            return
        self._set_busy(True)
        threading.Thread(target=self._do_translate, args=(api_key,), daemon=True).start()

    def _do_translate(self, api_key):
        try:
            from translator import Translator
            model = self.model_combo.currentText()
            base_url = self._get_base_url()
            translator = Translator(api_key=api_key, model=model, base_url=base_url)
            self.current_segments = translator.translate_segments(
                self.current_segments,
                target_lang="Vietnamese",
                progress_callback=self.signals.progress.emit,
            )
            # Log first few translations
            for seg in self.current_segments[:3]:
                self.signals.progress.emit(
                    f"  [{seg['text']}] → [{seg.get('translated_text', '')}]"
                )
            if len(self.current_segments) > 3:
                self.signals.progress.emit(f"  ... và {len(self.current_segments) - 3} đoạn khác")
            self.signals.finished.emit("translate")
        except Exception as e:
            self.signals.error.emit(f"Lỗi dịch: {e}")

    def _get_tts_provider_key(self):
        """Get provider name from combo text."""
        text = self.tts_provider_combo.currentText()
        if "OpenAI" in text:
            return "openai"
        elif "Google" in text:
            return "google"
        elif "Edge" in text:
            return "edge"
        return "openai"

    def _get_voice_value(self):
        """Extract the voice/lang value from combo text (strip description)."""
        text = self.voice_combo.currentText()
        # Format: "value (description)" or just "value"
        return text.split(" (")[0].strip()

    def _create_tts_engine(self, api_key=None):
        """Create TTS engine based on current UI settings."""
        from tts_generator import create_tts_engine
        provider = self._get_tts_provider_key()
        voice_value = self._get_voice_value()

        if provider == "openai":
            return create_tts_engine(
                "openai",
                api_key=api_key,
                model=self.tts_model_combo.currentText(),
                voice=voice_value,
                base_url=self._get_base_url(),
            )
        elif provider == "google":
            return create_tts_engine("google", lang=voice_value)
        elif provider == "edge":
            return create_tts_engine("edge", voice=voice_value)

    def _on_tts(self):
        if not self.current_segments:
            return
        provider = self._get_tts_provider_key()
        api_key = None
        if provider == "openai":
            api_key = self._get_api_key()
            if not api_key:
                return
        self._set_busy(True)
        threading.Thread(target=self._do_tts, args=(api_key,), daemon=True).start()

    def _do_tts(self, api_key):
        try:
            tts = self._create_tts_engine(api_key=api_key)
            provider_name = self.tts_provider_combo.currentText()
            self.signals.progress.emit(f"TTS Engine: {provider_name}")
            self.current_audio_files = tts.generate_all_segments(
                self.current_segments,
                progress_callback=self.signals.progress.emit,
            )
            self.signals.finished.emit("tts")
        except Exception as e:
            self.signals.error.emit(f"Lỗi tạo giọng nói: {e}")

    def _on_export(self):
        if not self.current_audio_files:
            return
        self._set_busy(True)
        threading.Thread(target=self._do_export, daemon=True).start()

    def _do_export(self):
        try:
            from video_processor import VideoProcessor
            processor = VideoProcessor()

            output_dir = self.output_dir_input.text().strip() or self.config.get("output_dir", "")
            if not output_dir:
                output_dir = os.path.join(os.path.expanduser("~"), "VideoTranslator_Output")
            os.makedirs(output_dir, exist_ok=True)

            base_name = os.path.splitext(os.path.basename(self.current_video_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}_vi.mp4")

            processor.export_video(
                video_path=self.current_video_path,
                segments=self.current_segments,
                audio_files=self.current_audio_files,
                output_path=output_path,
                font_size=self.font_size_spin.value(),
                keep_original_audio=self.keep_audio_check.isChecked(),
                progress_callback=self.signals.progress.emit,
            )

            self.signals.progress.emit(f"Video đã xuất: {output_path}")
            self.signals.finished.emit("export")
        except Exception as e:
            self.signals.error.emit(f"Lỗi xuất video: {e}")

    def _on_process_all(self):
        """Run all steps sequentially."""
        if not self.current_video_path:
            url = self.url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "Lỗi", "Vui lòng nhập URL hoặc chọn file video.")
                return
        api_key = self._get_api_key()
        if not api_key:
            return
        self._set_busy(True)
        threading.Thread(target=self._do_all, args=(api_key,), daemon=True).start()

    def _do_all(self, api_key):
        try:
            # Step 0: Download if needed
            if not self.current_video_path:
                url = self.url_input.text().strip()
                self.signals.progress.emit("=== BƯỚC 1: Tải video ===")
                from downloader import VideoDownloader
                dl = VideoDownloader()
                self.current_video_path = dl.download(
                    url, progress_callback=self.signals.progress.emit
                )

            # Step 1: Extract
            self.signals.progress.emit("=== BƯỚC 2: Trích xuất phụ đề ===")
            from subtitle_extractor import create_extractor
            whisper_mode = self._get_whisper_mode()
            if whisper_mode == "api":
                self.signals.progress.emit("Sử dụng OpenAI Whisper API (cloud)...")
                extractor = create_extractor("api", api_key=api_key, base_url=self._get_base_url())
            else:
                model = self.whisper_combo.currentText()
                self.signals.progress.emit(f"Sử dụng Whisper local (model: {model})...")
                extractor = create_extractor("local", model_name=model)

            self.current_segments, lang = extractor.extract_subtitles(
                self.current_video_path,
                progress_callback=self.signals.progress.emit,
            )

            # Step 2: Translate
            self.signals.progress.emit("=== BƯỚC 3: Dịch sang tiếng Việt ===")
            from translator import Translator
            translator = Translator(
                api_key=api_key,
                model=self.model_combo.currentText(),
                base_url=self._get_base_url(),
            )
            self.current_segments = translator.translate_segments(
                self.current_segments,
                target_lang="Vietnamese",
                progress_callback=self.signals.progress.emit,
            )

            # Step 3: TTS
            self.signals.progress.emit("=== BƯỚC 4: Tạo giọng đọc tiếng Việt ===")
            provider_name = self.tts_provider_combo.currentText()
            self.signals.progress.emit(f"TTS Engine: {provider_name}")
            tts = self._create_tts_engine(api_key=api_key)
            self.current_audio_files = tts.generate_all_segments(
                self.current_segments,
                progress_callback=self.signals.progress.emit,
            )

            # Step 4: Export
            self.signals.progress.emit("=== BƯỚC 5: Xuất video cuối cùng ===")
            from video_processor import VideoProcessor
            processor = VideoProcessor()

            output_dir = self.output_dir_input.text().strip() or self.config.get("output_dir", "")
            if not output_dir:
                output_dir = os.path.join(os.path.expanduser("~"), "VideoTranslator_Output")
            os.makedirs(output_dir, exist_ok=True)

            base_name = os.path.splitext(os.path.basename(self.current_video_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}_vi.mp4")

            processor.export_video(
                video_path=self.current_video_path,
                segments=self.current_segments,
                audio_files=self.current_audio_files,
                output_path=output_path,
                font_size=self.font_size_spin.value(),
                keep_original_audio=self.keep_audio_check.isChecked(),
                progress_callback=self.signals.progress.emit,
            )

            self.signals.progress.emit(f"\n✅ HOÀN THÀNH! Video đã xuất: {output_path}")
            self.signals.finished.emit("all")

        except Exception as e:
            self.signals.error.emit(str(e))

    def _on_task_finished(self, task):
        self._set_busy(False)

    def _on_error(self, msg):
        self._set_busy(False)
        self._log(f"❌ LỖI: {msg}")
        QMessageBox.critical(self, "Lỗi", msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Apply dark-ish theme
    app.setStyleSheet("""
        QMainWindow { background-color: #f5f5f5; }
        QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 5px;
                     margin-top: 10px; padding-top: 15px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QPushButton { padding: 6px 16px; border-radius: 4px; border: 1px solid #aaa;
                      background-color: #e8e8e8; }
        QPushButton:hover { background-color: #d0d0d0; }
        QPushButton:disabled { background-color: #f0f0f0; color: #aaa; }
        QLineEdit { padding: 5px; border: 1px solid #ccc; border-radius: 3px; }
        QComboBox { padding: 4px; }
        QTextEdit { border: 1px solid #ccc; border-radius: 3px; background: #1e1e1e; color: #ddd; }
        QProgressBar { border: 1px solid #ccc; border-radius: 3px; text-align: center; }
        QProgressBar::chunk { background-color: #4CAF50; }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
