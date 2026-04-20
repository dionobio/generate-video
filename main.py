"""
Video Translator Tool - Main GUI Application
PyQt5 desktop application for downloading, translating, and dubbing videos.
"""

import sys
import os
import threading
import webbrowser

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QComboBox, QSpinBox, QCheckBox, QFileDialog, QTabWidget,
    QGroupBox, QFormLayout, QMessageBox, QFrame, QSlider,
    QDoubleSpinBox, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

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
        self.setMinimumSize(900, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        # Title
        title = QLabel("Video Translator Tool")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Tải video → Chọn chức năng → Xử lý tự động từ đầu đến cuối")
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

        # Download via j2download.com
        j2_row = QHBoxLayout()
        j2_row.addWidget(QLabel("Tải video:"))
        self.btn_j2download = QPushButton("Mở j2download.com để tải video")
        self.btn_j2download.setToolTip(
            "Mở trang j2download.com trong trình duyệt.\n"
            "Dán link video (Douyin, TikTok, YouTube, Bilibili...) vào đó để tải.\n"
            "Sau khi tải xong, chọn file video bên dưới."
        )
        self.btn_j2download.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px 20px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        j2_row.addWidget(self.btn_j2download)
        j2_row.addStretch()
        input_layout.addLayout(j2_row)

        # Local file
        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Chọn video:"))
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Chọn file video đã tải từ máy tính...")
        self.file_path_input.setReadOnly(True)
        file_row.addWidget(self.file_path_input)
        self.btn_browse = QPushButton("Chọn File")
        self.btn_browse.setFixedWidth(120)
        file_row.addWidget(self.btn_browse)
        input_layout.addLayout(file_row)

        layout.addWidget(input_group)

        # --- Feature Selection ---
        features_group = QGroupBox("Chọn chức năng muốn áp dụng")
        features_layout = QVBoxLayout(features_group)

        # Feature 1: Subtitles
        self.chk_subtitles = QCheckBox("Thêm phụ đề dịch")
        self.chk_subtitles.setChecked(True)
        self.chk_subtitles.setFont(QFont("Arial", 10, QFont.Bold))
        self.chk_subtitles.toggled.connect(self._on_subtitle_toggled)
        features_layout.addWidget(self.chk_subtitles)

        # Subtitle options (indented)
        self.subtitle_options = QWidget()
        sub_opts_layout = QHBoxLayout(self.subtitle_options)
        sub_opts_layout.setContentsMargins(30, 0, 0, 5)

        sub_opts_layout.addWidget(QLabel("Font size:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 60)
        self.font_size_spin.setValue(self.config.get("subtitle_font_size", 24))
        self.font_size_spin.setFixedWidth(70)
        sub_opts_layout.addWidget(self.font_size_spin)

        sub_opts_layout.addWidget(QLabel("Vị trí:"))
        self.sub_position_spin = QSpinBox()
        self.sub_position_spin.setRange(0, 90)
        self.sub_position_spin.setValue(self.config.get("subtitle_position", 35))
        self.sub_position_spin.setSuffix("% từ đáy")
        self.sub_position_spin.setFixedWidth(120)
        self.sub_position_spin.setToolTip(
            "0% = sát đáy video\n"
            "35% = vị trí phụ đề Douyin/TikTok thường gặp\n"
            "50% = giữa video"
        )
        sub_opts_layout.addWidget(self.sub_position_spin)
        sub_opts_layout.addStretch()
        features_layout.addWidget(self.subtitle_options)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color: #ddd;")
        features_layout.addWidget(sep1)

        # Feature 2: TTS Voice
        self.chk_tts = QCheckBox("Thêm giọng đọc (TTS)")
        self.chk_tts.setChecked(True)
        self.chk_tts.setFont(QFont("Arial", 10, QFont.Bold))
        self.chk_tts.toggled.connect(self._on_tts_toggled)
        features_layout.addWidget(self.chk_tts)

        # TTS options (indented)
        self.tts_options = QWidget()
        tts_opts_layout = QHBoxLayout(self.tts_options)
        tts_opts_layout.setContentsMargins(30, 0, 0, 5)

        tts_opts_layout.addWidget(QLabel("TTS:"))
        self.tts_provider_combo = QComboBox()
        self.tts_provider_combo.addItems([
            "OpenAI (trả phí)",
            "Google (miễn phí)",
            "Edge (miễn phí)",
            "FPT.AI (miễn phí, chuyên Việt)",
        ])
        self.tts_provider_combo.setCurrentText(self.config.get("tts_provider", "Edge (miễn phí)"))
        self.tts_provider_combo.currentTextChanged.connect(self._on_tts_provider_changed)
        tts_opts_layout.addWidget(self.tts_provider_combo)

        tts_opts_layout.addWidget(QLabel("Giọng:"))
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(180)
        tts_opts_layout.addWidget(self.voice_combo)

        tts_opts_layout.addWidget(QLabel("Tốc độ:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["Chậm", "Bình thường", "Nhanh"])
        saved_speed = self.config.get("tts_speed", "normal")
        speed_display = {"slow": "Chậm", "normal": "Bình thường", "fast": "Nhanh"}
        self.speed_combo.setCurrentText(speed_display.get(saved_speed, "Bình thường"))
        tts_opts_layout.addWidget(self.speed_combo)

        tts_opts_layout.addStretch()
        features_layout.addWidget(self.tts_options)

        # Initialize voice list
        self._update_voice_options()
        self._update_speed_visibility()

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #ddd;")
        features_layout.addWidget(sep2)

        # Feature 3: Original audio
        self.chk_keep_audio = QCheckBox("Giữ âm thanh gốc (mix nhỏ tiếng với giọng đọc)")
        self.chk_keep_audio.setChecked(False)
        self.chk_keep_audio.setFont(QFont("Arial", 10, QFont.Bold))
        self.chk_keep_audio.toggled.connect(self._on_audio_toggled)
        features_layout.addWidget(self.chk_keep_audio)

        # Audio options (indented)
        self.audio_options = QWidget()
        audio_opts_layout = QHBoxLayout(self.audio_options)
        audio_opts_layout.setContentsMargins(30, 0, 0, 5)

        audio_opts_layout.addWidget(QLabel("Âm lượng gốc:"))
        self.original_vol_slider = QSlider(Qt.Horizontal)
        self.original_vol_slider.setRange(0, 100)
        self.original_vol_slider.setValue(10)
        self.original_vol_slider.setFixedWidth(200)
        audio_opts_layout.addWidget(self.original_vol_slider)

        self.vol_label = QLabel("10%")
        self.vol_label.setFixedWidth(40)
        self.original_vol_slider.valueChanged.connect(
            lambda v: self.vol_label.setText(f"{v}%")
        )
        audio_opts_layout.addWidget(self.vol_label)

        audio_opts_layout.addStretch()
        self.audio_options.setVisible(False)
        features_layout.addWidget(self.audio_options)

        # Separator
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet("color: #ddd;")
        features_layout.addWidget(sep3)

        # Feature 4: Whisper settings
        whisper_row = QHBoxLayout()
        whisper_row.addWidget(QLabel("Whisper (trích phụ đề):"))

        self.whisper_mode_combo = QComboBox()
        self.whisper_mode_combo.addItems([
            "API (cloud, không cần torch)",
            "Local (cần cài torch)",
        ])
        self.whisper_mode_combo.setCurrentText(
            self.config.get("whisper_mode", "API (cloud, không cần torch)")
        )
        self.whisper_mode_combo.currentTextChanged.connect(self._on_whisper_mode_changed)
        whisper_row.addWidget(self.whisper_mode_combo)

        whisper_row.addWidget(QLabel("Model:"))
        self.whisper_combo = QComboBox()
        self._update_whisper_model_options()
        whisper_row.addWidget(self.whisper_combo)

        whisper_row.addStretch()
        features_layout.addLayout(whisper_row)

        layout.addWidget(features_group)

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
        self.btn_all.setMinimumHeight(50)
        self.btn_all.setEnabled(False)
        self.btn_all.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:disabled { background-color: #ccc; color: #666; }"
        )
        layout.addWidget(self.btn_all)

        return tab

    # --- Feature toggle handlers ---

    def _on_subtitle_toggled(self, checked):
        self.subtitle_options.setVisible(checked)

    def _on_tts_toggled(self, checked):
        self.tts_options.setVisible(checked)

    def _on_audio_toggled(self, checked):
        self.audio_options.setVisible(checked)

    # ========== SETTINGS TAB ==========

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

        self.fpt_api_key_input = QLineEdit()
        self.fpt_api_key_input.setEchoMode(QLineEdit.Password)
        self.fpt_api_key_input.setText(self.config.get("fpt_api_key", ""))
        self.fpt_api_key_input.setPlaceholderText("FPT.AI API Key (lấy tại https://fpt.ai/tts)")
        form.addRow("FPT.AI API Key:", self.fpt_api_key_input)

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
        self.btn_j2download.clicked.connect(self._on_open_j2download)
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
        url = self.base_url_input.text().strip()
        if not url:
            url = self.config.get("openai_base_url", "")
        return url if url else None

    # --- Actions ---

    def _on_open_j2download(self):
        """Open j2download.com in the default browser for video downloading."""
        webbrowser.open("https://j2download.com/")
        self._log("Đã mở j2download.com trong trình duyệt.")
        self._log("Dán link video vào trang web để tải, sau đó chọn file video bên dưới.")

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
            # Auto-detect subtitle position in background
            if self.chk_subtitles.isChecked():
                threading.Thread(
                    target=self._detect_sub_position, args=(path,), daemon=True
                ).start()

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục output")
        if d:
            self.output_dir_input.setText(d)

    def _detect_sub_position(self, video_path):
        try:
            from video_processor import VideoProcessor
            processor = VideoProcessor()
            pos = processor.detect_subtitle_position(
                video_path,
                progress_callback=self.signals.progress.emit,
            )
            self.sub_position_spin.setValue(pos)
            self.signals.progress.emit(f"Vị trí phụ đề tự động: {pos}% từ đáy")
        except Exception as e:
            self.signals.progress.emit(f"Không thể quét phụ đề gốc: {e}")

    def _on_tts_provider_changed(self, text):
        self._update_voice_options()
        self._update_speed_visibility()

    def _update_voice_options(self):
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
        elif "FPT" in provider:
            self.voice_combo.addItems([
                "banmai (Nữ miền Bắc)",
                "thuminh (Nữ miền Bắc)",
                "leminh (Nam miền Bắc)",
                "myan (Nữ miền Trung)",
                "giahuy (Nam miền Trung)",
                "lannhi (Nữ miền Nam)",
                "lianh (Nữ miền Nam)",
            ])

    def _on_whisper_mode_changed(self, text):
        self._update_whisper_model_options()

    def _update_speed_visibility(self):
        provider = self.tts_provider_combo.currentText()
        visible = "Edge" in provider or "FPT" in provider
        self.speed_combo.setVisible(visible)

    def _update_whisper_model_options(self):
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
        text = self.whisper_mode_combo.currentText()
        return "api" if "API" in text else "local"

    def _save_settings(self):
        self.config["openai_api_key"] = self.api_key_input.text().strip()
        self.config["fpt_api_key"] = self.fpt_api_key_input.text().strip()
        self.config["openai_base_url"] = self.base_url_input.text().strip()
        self.config["openai_model"] = self.model_combo.currentText()
        self.config["tts_model"] = self.tts_model_combo.currentText()
        self.config["tts_provider"] = self.tts_provider_combo.currentText()
        self.config["tts_speed"] = self._get_speed_value()
        self.config["output_dir"] = self.output_dir_input.text().strip()
        self.config["whisper_mode"] = self.whisper_mode_combo.currentText()
        self.config["whisper_model"] = self.whisper_combo.currentText()
        self.config["tts_voice"] = self.voice_combo.currentText()
        self.config["subtitle_font_size"] = self.font_size_spin.value()
        self.config["subtitle_position"] = self.sub_position_spin.value()
        save_config(self.config)
        self._log("Đã lưu cài đặt.")
        QMessageBox.information(self, "Thành công", "Đã lưu cài đặt!")

    def _get_tts_provider_key(self):
        text = self.tts_provider_combo.currentText()
        if "OpenAI" in text:
            return "openai"
        elif "Google" in text:
            return "google"
        elif "FPT" in text:
            return "fptai"
        elif "Edge" in text:
            return "edge"
        return "edge"

    def _get_voice_value(self):
        text = self.voice_combo.currentText()
        return text.split(" (")[0].strip()

    def _get_speed_value(self):
        text = self.speed_combo.currentText()
        speed_map = {"Chậm": "slow", "Bình thường": "normal", "Nhanh": "fast"}
        return speed_map.get(text, "normal")

    def _get_fpt_api_key(self):
        key = self.fpt_api_key_input.text().strip()
        if not key:
            key = self.config.get("fpt_api_key", "")
        if not key:
            QMessageBox.warning(
                self, "Thiếu FPT API Key",
                "Vui lòng nhập FPT.AI API Key trong tab Cài đặt.\n"
                "Đăng ký miễn phí tại: https://fpt.ai/tts"
            )
            return None
        return key

    def _get_edge_rate(self):
        speed = self._get_speed_value()
        rate_map = {"slow": "-20%", "normal": "+0%", "fast": "+20%"}
        return rate_map.get(speed, "+0%")

    def _create_tts_engine(self, api_key=None):
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
            return create_tts_engine(
                "edge",
                voice=voice_value,
                rate=self._get_edge_rate(),
            )
        elif provider == "fptai":
            fpt_key = self.fpt_api_key_input.text().strip() or self.config.get("fpt_api_key", "")
            return create_tts_engine(
                "fptai",
                api_key=fpt_key,
                voice=voice_value,
                speed=self._get_speed_value(),
            )

    # --- Individual step actions ---

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
            for seg in self.current_segments[:3]:
                self.signals.progress.emit(
                    f"  [{seg['text']}] → [{seg.get('translated_text', '')}]"
                )
            if len(self.current_segments) > 3:
                self.signals.progress.emit(f"  ... và {len(self.current_segments) - 3} đoạn khác")
            self.signals.finished.emit("translate")
        except Exception as e:
            self.signals.error.emit(f"Lỗi dịch: {e}")

    def _on_tts(self):
        if not self.current_segments:
            return
        provider = self._get_tts_provider_key()
        api_key = None
        if provider == "openai":
            api_key = self._get_api_key()
            if not api_key:
                return
        elif provider == "fptai":
            fpt_key = self._get_fpt_api_key()
            if not fpt_key:
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

            keep_audio = self.chk_keep_audio.isChecked()
            original_volume = self.original_vol_slider.value() / 100.0 if keep_audio else 0.1

            processor.export_video(
                video_path=self.current_video_path,
                segments=self.current_segments,
                audio_files=self.current_audio_files,
                output_path=output_path,
                font_size=self.font_size_spin.value(),
                keep_original_audio=keep_audio,
                original_audio_volume=original_volume,
                subtitle_position=self.sub_position_spin.value(),
                progress_callback=self.signals.progress.emit,
            )

            self.signals.progress.emit(f"Video đã xuất: {output_path}")
            self.signals.finished.emit("export")
        except Exception as e:
            self.signals.error.emit(f"Lỗi xuất video: {e}")

    # --- Process All (respects feature checkboxes) ---

    def _on_process_all(self):
        if not self.current_video_path:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file video trước.")
            return

        # Check: at least subtitles or TTS must be selected
        if not self.chk_subtitles.isChecked() and not self.chk_tts.isChecked():
            QMessageBox.warning(
                self, "Lỗi",
                "Vui lòng chọn ít nhất một chức năng (phụ đề hoặc giọng đọc)."
            )
            return

        api_key = self._get_api_key()
        if not api_key:
            return

        # Check FPT key if needed
        if self.chk_tts.isChecked() and self._get_tts_provider_key() == "fptai":
            fpt_key = self._get_fpt_api_key()
            if not fpt_key:
                return

        self._set_busy(True)
        threading.Thread(target=self._do_all, args=(api_key,), daemon=True).start()

    def _do_all(self, api_key):
        try:
            want_subtitles = self.chk_subtitles.isChecked()
            want_tts = self.chk_tts.isChecked()
            want_keep_audio = self.chk_keep_audio.isChecked()

            # Step 1: Auto-detect subtitle position
            if want_subtitles:
                self.signals.progress.emit("=== Quét vị trí phụ đề gốc ===")
                self._detect_sub_position(self.current_video_path)

            # Step 2: Extract subtitles (always needed for translation/TTS)
            self.signals.progress.emit("=== BƯỚC 1: Trích xuất phụ đề ===")
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
            self.signals.progress.emit(
                f"Trích xuất xong: {len(self.current_segments)} đoạn (ngôn ngữ: {lang})"
            )

            # Step 3: Translate
            self.signals.progress.emit("=== BƯỚC 2: Dịch sang tiếng Việt ===")
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

            # Step 4: TTS (if selected)
            if want_tts:
                self.signals.progress.emit("=== BƯỚC 3: Tạo giọng đọc tiếng Việt ===")
                provider_name = self.tts_provider_combo.currentText()
                self.signals.progress.emit(f"TTS Engine: {provider_name}")
                tts = self._create_tts_engine(api_key=api_key)
                self.current_audio_files = tts.generate_all_segments(
                    self.current_segments,
                    progress_callback=self.signals.progress.emit,
                )
            else:
                self.current_audio_files = None

            # Step 5: Export video
            self.signals.progress.emit("=== BƯỚC 4: Xuất video cuối cùng ===")
            from video_processor import VideoProcessor
            processor = VideoProcessor()

            output_dir = self.output_dir_input.text().strip() or self.config.get("output_dir", "")
            if not output_dir:
                output_dir = os.path.join(os.path.expanduser("~"), "VideoTranslator_Output")
            os.makedirs(output_dir, exist_ok=True)

            base_name = os.path.splitext(os.path.basename(self.current_video_path))[0]
            output_path = os.path.join(output_dir, f"{base_name}_vi.mp4")

            if want_tts and self.current_audio_files:
                # Full export: subtitles + TTS audio
                original_volume = self.original_vol_slider.value() / 100.0 if want_keep_audio else 0.1
                processor.export_video(
                    video_path=self.current_video_path,
                    segments=self.current_segments,
                    audio_files=self.current_audio_files,
                    output_path=output_path,
                    font_size=self.font_size_spin.value() if want_subtitles else 0,
                    keep_original_audio=want_keep_audio,
                    original_audio_volume=original_volume,
                    subtitle_position=self.sub_position_spin.value(),
                    progress_callback=self.signals.progress.emit,
                )
            elif want_subtitles and not want_tts:
                # Subtitles only, keep original audio
                self.signals.progress.emit("Chỉ thêm phụ đề, giữ nguyên audio gốc...")
                self._export_subtitles_only(processor, output_path)
            else:
                self.signals.progress.emit("Không có chức năng nào được chọn để xuất.")

            self.signals.progress.emit(f"\n✅ HOÀN THÀNH! Video đã xuất: {output_path}")
            self.signals.finished.emit("all")

        except Exception as e:
            self.signals.error.emit(str(e))

    def _export_subtitles_only(self, processor, output_path):
        """Export video with only subtitles burned in, keeping original audio."""
        import subprocess
        import tempfile

        sub_path = tempfile.mktemp(suffix=".ass")
        processor.create_subtitle_file(
            self.current_segments, sub_path,
            self.font_size_spin.value(),
            self.sub_position_spin.value(),
        )

        from video_processor import _escape_filter_path
        sub_filter = f"ass='{_escape_filter_path(sub_path)}'"

        cmd = [
            "ffmpeg", "-y",
            "-i", self.current_video_path,
            "-vf", sub_filter,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"Xuất video thất bại:\n{result.stderr}")

        if os.path.exists(sub_path):
            os.remove(sub_path)

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        self.signals.progress.emit(f"Xuất video xong! ({size_mb:.1f} MB)")

    def _on_task_finished(self, task):
        self._set_busy(False)

    def _on_error(self, msg):
        self._set_busy(False)
        self._log(f"❌ LỖI: {msg}")
        QMessageBox.critical(self, "Lỗi", msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

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
        QCheckBox { spacing: 8px; }
        QCheckBox::indicator { width: 18px; height: 18px; }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
