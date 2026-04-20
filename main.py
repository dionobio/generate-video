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
    QGroupBox, QFormLayout, QMessageBox, QFrame, QSlider,
    QDoubleSpinBox, QListWidget, QListWidgetItem, QSplitter,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QUrl, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap, QImage
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

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
        tabs.addTab(self._create_editor_tab(), "Chỉnh sửa Video")
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
        self.tts_provider_combo.addItems([
            "OpenAI (trả phí)",
            "Google (miễn phí)",
            "Edge (miễn phí)",
            "FPT.AI (miễn phí, chuyên Việt)",
        ])
        self.tts_provider_combo.setCurrentText(self.config.get("tts_provider", "Edge (miễn phí)"))
        self.tts_provider_combo.currentTextChanged.connect(self._on_tts_provider_changed)
        opts_row.addWidget(self.tts_provider_combo)

        opts_row.addWidget(QLabel("Giọng đọc:"))
        self.voice_combo = QComboBox()
        opts_row.addWidget(self.voice_combo)

        opts_row.addWidget(QLabel("Tốc độ:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["Chậm", "Bình thường", "Nhanh"])
        saved_speed = self.config.get("tts_speed", "normal")
        speed_display = {"slow": "Chậm", "normal": "Bình thường", "fast": "Nhanh"}
        self.speed_combo.setCurrentText(speed_display.get(saved_speed, "Bình thường"))
        opts_row.addWidget(self.speed_combo)

        # Initialize voice list based on current provider
        self._update_voice_options()
        self._update_speed_visibility()

        opts_row.addWidget(QLabel("Font size:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 60)
        self.font_size_spin.setValue(self.config.get("subtitle_font_size", 24))
        opts_row.addWidget(self.font_size_spin)

        process_layout.addLayout(opts_row)

        # Keep original audio option + subtitle position
        audio_row = QHBoxLayout()
        self.keep_audio_check = QCheckBox("Giữ âm thanh gốc (nhỏ tiếng)")
        self.keep_audio_check.setChecked(False)
        audio_row.addWidget(self.keep_audio_check)

        audio_row.addWidget(QLabel("Vị trí phụ đề:"))
        self.sub_position_spin = QSpinBox()
        self.sub_position_spin.setRange(0, 90)
        self.sub_position_spin.setValue(self.config.get("subtitle_position", 35))
        self.sub_position_spin.setSuffix("% từ đáy")
        self.sub_position_spin.setToolTip(
            "0% = sát đáy video\n"
            "35% = vị trí phụ đề Douyin/TikTok thường gặp\n"
            "50% = giữa video\n"
            "Kéo lên/xuống cho khớp với phụ đề gốc"
        )
        audio_row.addWidget(self.sub_position_spin)

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

    # ========== VIDEO EDITOR TAB ==========

    def _create_editor_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # --- Video source for editing ---
        src_group = QGroupBox("Video nguồn")
        src_layout = QHBoxLayout(src_group)

        self.editor_file_input = QLineEdit()
        self.editor_file_input.setPlaceholderText("Chọn video để chỉnh sửa...")
        self.editor_file_input.setReadOnly(True)
        src_layout.addWidget(self.editor_file_input)

        btn_editor_browse = QPushButton("Chọn File")
        btn_editor_browse.setFixedWidth(100)
        btn_editor_browse.clicked.connect(self._editor_browse_file)
        src_layout.addWidget(btn_editor_browse)

        btn_use_current = QPushButton("Dùng video hiện tại")
        btn_use_current.setFixedWidth(150)
        btn_use_current.clicked.connect(self._editor_use_current_video)
        src_layout.addWidget(btn_use_current)

        layout.addWidget(src_group)

        # --- Video Preview ---
        preview_group = QGroupBox("Xem trước")
        preview_layout = QVBoxLayout(preview_group)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(200)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(self.video_widget)

        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)

        # Playback controls
        ctrl_row = QHBoxLayout()
        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedWidth(70)
        self.btn_play.clicked.connect(self._editor_play_pause)
        ctrl_row.addWidget(self.btn_play)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setFixedWidth(70)
        self.btn_stop.clicked.connect(self._editor_stop)
        ctrl_row.addWidget(self.btn_stop)

        self.editor_seek_slider = QSlider(Qt.Horizontal)
        self.editor_seek_slider.setRange(0, 0)
        self.editor_seek_slider.sliderMoved.connect(self._editor_seek)
        ctrl_row.addWidget(self.editor_seek_slider)

        self.editor_time_label = QLabel("00:00 / 00:00")
        self.editor_time_label.setFixedWidth(120)
        ctrl_row.addWidget(self.editor_time_label)

        preview_layout.addLayout(ctrl_row)

        # Connect media player signals
        self.media_player.positionChanged.connect(self._editor_position_changed)
        self.media_player.durationChanged.connect(self._editor_duration_changed)

        layout.addWidget(preview_group)

        # --- Editing Tools (horizontal sections) ---
        tools_group = QGroupBox("Công cụ chỉnh sửa")
        tools_layout = QVBoxLayout(tools_group)

        # Row 1: Trim
        trim_row = QHBoxLayout()
        trim_row.addWidget(QLabel("Cắt video:"))

        trim_row.addWidget(QLabel("Từ"))
        self.trim_start_spin = QDoubleSpinBox()
        self.trim_start_spin.setRange(0, 99999)
        self.trim_start_spin.setDecimals(1)
        self.trim_start_spin.setSuffix("s")
        self.trim_start_spin.setFixedWidth(90)
        trim_row.addWidget(self.trim_start_spin)

        trim_row.addWidget(QLabel("Đến"))
        self.trim_end_spin = QDoubleSpinBox()
        self.trim_end_spin.setRange(0, 99999)
        self.trim_end_spin.setDecimals(1)
        self.trim_end_spin.setSuffix("s")
        self.trim_end_spin.setFixedWidth(90)
        trim_row.addWidget(self.trim_end_spin)

        self.btn_set_start = QPushButton("Đặt bắt đầu")
        self.btn_set_start.setFixedWidth(100)
        self.btn_set_start.clicked.connect(
            lambda: self.trim_start_spin.setValue(self.media_player.position() / 1000.0)
        )
        trim_row.addWidget(self.btn_set_start)

        self.btn_set_end = QPushButton("Đặt kết thúc")
        self.btn_set_end.setFixedWidth(100)
        self.btn_set_end.clicked.connect(
            lambda: self.trim_end_spin.setValue(self.media_player.position() / 1000.0)
        )
        trim_row.addWidget(self.btn_set_end)

        self.btn_trim = QPushButton("Cắt")
        self.btn_trim.setFixedWidth(70)
        self.btn_trim.clicked.connect(self._editor_trim)
        trim_row.addWidget(self.btn_trim)

        trim_row.addStretch()
        tools_layout.addLayout(trim_row)

        # Row 2: Speed + Crop
        speed_crop_row = QHBoxLayout()

        speed_crop_row.addWidget(QLabel("Tốc độ:"))
        self.editor_speed_spin = QDoubleSpinBox()
        self.editor_speed_spin.setRange(0.25, 4.0)
        self.editor_speed_spin.setDecimals(2)
        self.editor_speed_spin.setSingleStep(0.25)
        self.editor_speed_spin.setValue(1.0)
        self.editor_speed_spin.setSuffix("x")
        self.editor_speed_spin.setFixedWidth(90)
        speed_crop_row.addWidget(self.editor_speed_spin)

        self.btn_speed = QPushButton("Áp dụng")
        self.btn_speed.setFixedWidth(80)
        self.btn_speed.clicked.connect(self._editor_change_speed)
        speed_crop_row.addWidget(self.btn_speed)

        speed_crop_row.addWidget(QLabel("   "))

        speed_crop_row.addWidget(QLabel("Tỷ lệ:"))
        self.crop_ratio_combo = QComboBox()
        self.crop_ratio_combo.addItems(["9:16 (TikTok)", "16:9 (YouTube)", "1:1 (Instagram)", "4:3"])
        self.crop_ratio_combo.setFixedWidth(160)
        speed_crop_row.addWidget(self.crop_ratio_combo)

        self.btn_crop = QPushButton("Crop")
        self.btn_crop.setFixedWidth(70)
        self.btn_crop.clicked.connect(self._editor_crop)
        speed_crop_row.addWidget(self.btn_crop)

        speed_crop_row.addStretch()
        tools_layout.addLayout(speed_crop_row)

        # Row 3: Background music
        music_row = QHBoxLayout()
        music_row.addWidget(QLabel("Nhạc nền:"))

        self.music_file_input = QLineEdit()
        self.music_file_input.setPlaceholderText("Chọn file nhạc (mp3, wav, m4a...)")
        self.music_file_input.setReadOnly(True)
        music_row.addWidget(self.music_file_input)

        btn_music_browse = QPushButton("Chọn")
        btn_music_browse.setFixedWidth(60)
        btn_music_browse.clicked.connect(self._editor_browse_music)
        music_row.addWidget(btn_music_browse)

        music_row.addWidget(QLabel("Vol:"))
        self.music_vol_spin = QDoubleSpinBox()
        self.music_vol_spin.setRange(0.0, 1.0)
        self.music_vol_spin.setDecimals(2)
        self.music_vol_spin.setSingleStep(0.05)
        self.music_vol_spin.setValue(0.3)
        self.music_vol_spin.setFixedWidth(70)
        music_row.addWidget(self.music_vol_spin)

        self.music_keep_original = QCheckBox("Giữ audio gốc")
        self.music_keep_original.setChecked(True)
        music_row.addWidget(self.music_keep_original)

        self.btn_add_music = QPushButton("Thêm nhạc")
        self.btn_add_music.setFixedWidth(90)
        self.btn_add_music.clicked.connect(self._editor_add_music)
        music_row.addWidget(self.btn_add_music)

        tools_layout.addLayout(music_row)

        # Row 4: Watermark
        wm_row = QHBoxLayout()
        wm_row.addWidget(QLabel("Watermark:"))

        self.watermark_file_input = QLineEdit()
        self.watermark_file_input.setPlaceholderText("Chọn ảnh logo (png, jpg...)")
        self.watermark_file_input.setReadOnly(True)
        wm_row.addWidget(self.watermark_file_input)

        btn_wm_browse = QPushButton("Chọn")
        btn_wm_browse.setFixedWidth(60)
        btn_wm_browse.clicked.connect(self._editor_browse_watermark)
        wm_row.addWidget(btn_wm_browse)

        wm_row.addWidget(QLabel("Vị trí:"))
        self.wm_position_combo = QComboBox()
        self.wm_position_combo.addItems([
            "Trên phải", "Trên trái", "Dưới phải", "Dưới trái", "Giữa"
        ])
        self.wm_position_combo.setFixedWidth(100)
        wm_row.addWidget(self.wm_position_combo)

        wm_row.addWidget(QLabel("Opacity:"))
        self.wm_opacity_spin = QDoubleSpinBox()
        self.wm_opacity_spin.setRange(0.1, 1.0)
        self.wm_opacity_spin.setDecimals(1)
        self.wm_opacity_spin.setValue(0.7)
        self.wm_opacity_spin.setFixedWidth(65)
        wm_row.addWidget(self.wm_opacity_spin)

        wm_row.addWidget(QLabel("Size:"))
        self.wm_scale_spin = QDoubleSpinBox()
        self.wm_scale_spin.setRange(0.05, 0.5)
        self.wm_scale_spin.setDecimals(2)
        self.wm_scale_spin.setSingleStep(0.05)
        self.wm_scale_spin.setValue(0.15)
        self.wm_scale_spin.setFixedWidth(65)
        wm_row.addWidget(self.wm_scale_spin)

        self.btn_add_wm = QPushButton("Thêm logo")
        self.btn_add_wm.setFixedWidth(90)
        self.btn_add_wm.clicked.connect(self._editor_add_watermark)
        wm_row.addWidget(self.btn_add_wm)

        tools_layout.addLayout(wm_row)

        # Row 5: Concat
        concat_row = QHBoxLayout()
        concat_row.addWidget(QLabel("Ghép nối:"))

        self.concat_list = QListWidget()
        self.concat_list.setMaximumHeight(60)
        self.concat_list.setToolTip("Danh sách video sẽ được ghép nối theo thứ tự")
        concat_row.addWidget(self.concat_list)

        concat_btn_col = QVBoxLayout()
        btn_concat_add = QPushButton("+")
        btn_concat_add.setFixedWidth(30)
        btn_concat_add.clicked.connect(self._editor_concat_add)
        concat_btn_col.addWidget(btn_concat_add)

        btn_concat_remove = QPushButton("-")
        btn_concat_remove.setFixedWidth(30)
        btn_concat_remove.clicked.connect(self._editor_concat_remove)
        concat_btn_col.addWidget(btn_concat_remove)
        concat_row.addLayout(concat_btn_col)

        self.btn_concat = QPushButton("Ghép video")
        self.btn_concat.setFixedWidth(100)
        self.btn_concat.clicked.connect(self._editor_concat)
        concat_row.addWidget(self.btn_concat)

        tools_layout.addLayout(concat_row)

        layout.addWidget(tools_group)

        # Editor log
        self.editor_log = QTextEdit()
        self.editor_log.setReadOnly(True)
        self.editor_log.setMaximumHeight(80)
        self.editor_log.setFont(QFont("Consolas", 9))
        self.editor_log.setStyleSheet("background: #1e1e1e; color: #ddd; border: 1px solid #ccc; border-radius: 3px;")
        layout.addWidget(self.editor_log)

        return tab

    # --- Editor helper methods ---

    def _editor_log_msg(self, msg):
        self.editor_log.append(msg)
        self.editor_log.verticalScrollBar().setValue(
            self.editor_log.verticalScrollBar().maximum()
        )

    def _editor_browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn Video chỉnh sửa", "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.flv);;All Files (*)",
        )
        if path:
            self.editor_file_input.setText(path)
            self._editor_load_video(path)

    def _editor_use_current_video(self):
        if self.current_video_path and os.path.exists(self.current_video_path):
            self.editor_file_input.setText(self.current_video_path)
            self._editor_load_video(self.current_video_path)
        else:
            QMessageBox.warning(self, "Lỗi", "Chưa có video nào được tải/chọn ở tab Xử lý.")

    def _editor_load_video(self, path):
        """Load video into the preview player."""
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
        self.media_player.pause()
        self._editor_log_msg(f"Đã tải video: {os.path.basename(path)}")
        try:
            from video_editor import VideoEditor
            editor = VideoEditor()
            info = editor.get_video_info(path)
            self._editor_log_msg(
                f"  {info['width']}x{info['height']}, {info['duration']:.1f}s, {info['fps']}fps"
            )
            self.trim_end_spin.setValue(info["duration"])
        except Exception as e:
            self._editor_log_msg(f"  Lỗi đọc thông tin: {e}")

    def _editor_play_pause(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.btn_play.setText("Play")
        else:
            self.media_player.play()
            self.btn_play.setText("Pause")

    def _editor_stop(self):
        self.media_player.stop()
        self.btn_play.setText("Play")

    def _editor_seek(self, position):
        self.media_player.setPosition(position)

    def _editor_position_changed(self, position):
        self.editor_seek_slider.setValue(position)
        current = self._format_ms(position)
        total = self._format_ms(self.media_player.duration())
        self.editor_time_label.setText(f"{current} / {total}")

    def _editor_duration_changed(self, duration):
        self.editor_seek_slider.setRange(0, duration)

    def _format_ms(self, ms):
        """Format milliseconds to MM:SS."""
        s = ms // 1000
        return f"{s // 60:02d}:{s % 60:02d}"

    def _get_editor_video_path(self):
        """Get the current editor video path, validate it exists."""
        path = self.editor_file_input.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn video trước.")
            return None
        return path

    def _get_editor_output_path(self, input_path, suffix):
        """Generate output path for edited video."""
        output_dir = self.output_dir_input.text().strip() or self.config.get("output_dir", "")
        if not output_dir:
            output_dir = os.path.join(os.path.expanduser("~"), "VideoTranslator_Output")
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(input_path))[0]
        return os.path.join(output_dir, f"{base}_{suffix}.mp4")

    # --- Editor actions ---

    def _editor_trim(self):
        path = self._get_editor_video_path()
        if not path:
            return
        start = self.trim_start_spin.value()
        end = self.trim_end_spin.value()
        if end <= start:
            QMessageBox.warning(self, "Lỗi", "Thời gian kết thúc phải lớn hơn bắt đầu.")
            return
        output = self._get_editor_output_path(path, "trimmed")
        self._editor_log_msg(f"Đang cắt video {start:.1f}s -> {end:.1f}s...")
        threading.Thread(target=self._do_editor_task, args=(
            "trim", path, output, {"start_time": start, "end_time": end}
        ), daemon=True).start()

    def _editor_change_speed(self):
        path = self._get_editor_video_path()
        if not path:
            return
        speed = self.editor_speed_spin.value()
        output = self._get_editor_output_path(path, f"speed{speed}x")
        self._editor_log_msg(f"Đang thay đổi tốc độ: {speed}x...")
        threading.Thread(target=self._do_editor_task, args=(
            "speed", path, output, {"speed_factor": speed}
        ), daemon=True).start()

    def _editor_crop(self):
        path = self._get_editor_video_path()
        if not path:
            return
        ratio_text = self.crop_ratio_combo.currentText()
        ratio = ratio_text.split(" ")[0]  # "9:16 (TikTok)" -> "9:16"
        output = self._get_editor_output_path(path, f"crop{ratio.replace(':', 'x')}")
        self._editor_log_msg(f"Đang crop video thành {ratio}...")
        threading.Thread(target=self._do_editor_task, args=(
            "crop", path, output, {"aspect_ratio": ratio}
        ), daemon=True).start()

    def _editor_browse_music(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file nhạc", "",
            "Audio Files (*.mp3 *.wav *.m4a *.aac *.ogg *.flac);;All Files (*)",
        )
        if path:
            self.music_file_input.setText(path)

    def _editor_add_music(self):
        path = self._get_editor_video_path()
        if not path:
            return
        music = self.music_file_input.text().strip()
        if not music or not os.path.exists(music):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file nhạc nền.")
            return
        output = self._get_editor_output_path(path, "music")
        vol = self.music_vol_spin.value()
        keep = self.music_keep_original.isChecked()
        self._editor_log_msg(f"Đang thêm nhạc nền (vol={vol}, giữ gốc={keep})...")
        threading.Thread(target=self._do_editor_task, args=(
            "music", path, output, {
                "music_path": music, "music_volume": vol, "keep_original": keep
            }
        ), daemon=True).start()

    def _editor_browse_watermark(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh watermark/logo", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.svg);;All Files (*)",
        )
        if path:
            self.watermark_file_input.setText(path)

    def _editor_add_watermark(self):
        path = self._get_editor_video_path()
        if not path:
            return
        wm = self.watermark_file_input.text().strip()
        if not wm or not os.path.exists(wm):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn ảnh watermark/logo.")
            return
        pos_map = {
            "Trên phải": "top-right", "Trên trái": "top-left",
            "Dưới phải": "bottom-right", "Dưới trái": "bottom-left",
            "Giữa": "center",
        }
        position = pos_map.get(self.wm_position_combo.currentText(), "top-right")
        opacity = self.wm_opacity_spin.value()
        scale = self.wm_scale_spin.value()
        output = self._get_editor_output_path(path, "watermark")
        self._editor_log_msg(f"Đang thêm watermark ({position})...")
        threading.Thread(target=self._do_editor_task, args=(
            "watermark", path, output, {
                "watermark_path": wm, "position": position,
                "opacity": opacity, "scale": scale,
            }
        ), daemon=True).start()

    def _editor_concat_add(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Thêm video vào danh sách ghép", "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm);;All Files (*)",
        )
        for p in paths:
            item = QListWidgetItem(os.path.basename(p))
            item.setData(Qt.UserRole, p)
            self.concat_list.addItem(item)

    def _editor_concat_remove(self):
        row = self.concat_list.currentRow()
        if row >= 0:
            self.concat_list.takeItem(row)

    def _editor_concat(self):
        count = self.concat_list.count()
        if count < 2:
            QMessageBox.warning(self, "Lỗi", "Cần ít nhất 2 video để ghép nối.")
            return
        paths = []
        for i in range(count):
            item = self.concat_list.item(i)
            paths.append(item.data(Qt.UserRole))

        output_dir = self.output_dir_input.text().strip() or self.config.get("output_dir", "")
        if not output_dir:
            output_dir = os.path.join(os.path.expanduser("~"), "VideoTranslator_Output")
        os.makedirs(output_dir, exist_ok=True)
        output = os.path.join(output_dir, "concat_output.mp4")

        self._editor_log_msg(f"Đang ghép {count} video...")
        threading.Thread(target=self._do_editor_task, args=(
            "concat", None, output, {"input_paths": paths}
        ), daemon=True).start()

    def _do_editor_task(self, task, input_path, output_path, params):
        """Run editor operation in background thread."""
        try:
            from video_editor import VideoEditor
            editor = VideoEditor()

            if task == "trim":
                editor.trim(input_path, output_path,
                            params["start_time"], params["end_time"],
                            progress_callback=self._editor_log_msg)
            elif task == "speed":
                editor.change_speed(input_path, output_path,
                                     params["speed_factor"],
                                     progress_callback=self._editor_log_msg)
            elif task == "crop":
                editor.crop_resize(input_path, output_path,
                                    params["aspect_ratio"],
                                    progress_callback=self._editor_log_msg)
            elif task == "music":
                editor.add_background_music(input_path, params["music_path"],
                                             output_path,
                                             music_volume=params["music_volume"],
                                             keep_original=params["keep_original"],
                                             progress_callback=self._editor_log_msg)
            elif task == "watermark":
                editor.add_watermark(input_path, params["watermark_path"],
                                      output_path,
                                      position=params["position"],
                                      opacity=params["opacity"],
                                      scale=params["scale"],
                                      progress_callback=self._editor_log_msg)
            elif task == "concat":
                editor.concat_videos(params["input_paths"], output_path,
                                      progress_callback=self._editor_log_msg)

            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            self._editor_log_msg(f"Xong! File: {output_path} ({size_mb:.1f} MB)")

            # Auto-load the result into the preview player
            self.editor_file_input.setText(output_path)
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(output_path)))
            self.media_player.pause()

        except Exception as e:
            self._editor_log_msg(f"Lỗi: {e}")

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
            # Auto-detect subtitle position in background
            threading.Thread(
                target=self._detect_sub_position, args=(path,), daemon=True
            ).start()

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục output")
        if d:
            self.output_dir_input.setText(d)

    def _detect_sub_position(self, video_path):
        """Auto-detect original subtitle position and update the spinbox."""
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
        """Show/hide speed combo based on TTS provider (relevant for Edge and FPT.AI)."""
        provider = self.tts_provider_combo.currentText()
        visible = "Edge" in provider or "FPT" in provider
        self.speed_combo.setVisible(visible)
        # Also hide/show the label before it — find the label by traversing layout
        # Speed combo is always present, just hidden when not applicable

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
            # Auto-detect subtitle position
            self._detect_sub_position(path)
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
        elif "FPT" in text:
            return "fptai"
        elif "Edge" in text:
            return "edge"
        return "edge"

    def _get_voice_value(self):
        """Extract the voice/lang value from combo text (strip description)."""
        text = self.voice_combo.currentText()
        # Format: "value (description)" or just "value"
        return text.split(" (")[0].strip()

    def _get_speed_value(self):
        """Get speed value from the speed combo."""
        text = self.speed_combo.currentText()
        speed_map = {"Chậm": "slow", "Bình thường": "normal", "Nhanh": "fast"}
        return speed_map.get(text, "normal")

    def _get_fpt_api_key(self):
        """Get FPT.AI API key."""
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
        """Convert speed setting to Edge TTS rate string."""
        speed = self._get_speed_value()
        rate_map = {"slow": "-20%", "normal": "+0%", "fast": "+20%"}
        return rate_map.get(speed, "+0%")

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

            processor.export_video(
                video_path=self.current_video_path,
                segments=self.current_segments,
                audio_files=self.current_audio_files,
                output_path=output_path,
                font_size=self.font_size_spin.value(),
                keep_original_audio=self.keep_audio_check.isChecked(),
                subtitle_position=self.sub_position_spin.value(),
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

            # Auto-detect subtitle position
            self._detect_sub_position(self.current_video_path)

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
                subtitle_position=self.sub_position_spin.value(),
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
