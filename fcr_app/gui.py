"""
FCR计算工具 GUI主窗口 — v1.2-ui
基于 COFCO 品牌视觉风格的专业桌面界面设计
"""
import sys, os, logging
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import pandas as pd
import numpy as np

from fcr_app.core import (
    load_csv, load_csv_folder, process_pig, batch_process,
    export_summary_excel, export_cleaned_excel, export_stage_summary_excel,
    PigResult, STAGE_WEIGHT_LOWER, STAGE_WEIGHT_UPPER,
)
from fcr_app.chart import plot_weight_curve

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("FCRApp")


# ============================================================
# Design System — QSS Global Stylesheet
# COFCO Brand Color Palette (medium-saturation green)
# ============================================================
APP_STYLESHEET = """
/* ===== Global Base ===== */
QMainWindow, QWidget {
    background-color: #F2F5F3;
    color: #1A2E23;
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
}

/* ===== Header Bar ===== */
QFrame#header_bar {
    background-color: #FFFFFF;
    border-bottom: 3px solid #1B7340;
}
QLabel#app_title {
    color: #1B7340;
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#app_subtitle {
    color: #6B7B73;
    font-size: 11px;
    font-weight: 400;
}
QLabel#version_badge {
    background-color: #E8F5EC;
    color: #1B7340;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 10px;
}

/* ===== Section Cards ===== */
QFrame#section_card {
    background-color: #FFFFFF;
    border: 1px solid #DDE5E0;
    border-radius: 8px;
}
QLabel#section_header {
    color: #1B7340;
    font-size: 13px;
    font-weight: 600;
    padding-bottom: 2px;
}
QFrame#section_separator {
    background-color: #E8EDE9;
    max-height: 1px;
    min-height: 1px;
    border: none;
}

/* ===== Standard Labels ===== */
QLabel {
    color: #3A4A40;
    background: transparent;
}
QLabel#hint_label {
    color: #9AAA9E;
    font-size: 11px;
}
QLabel#info_label {
    color: #3A4A40;
    font-size: 12px;
    background-color: #F8FAF9;
    border: 1px solid #E8EDE9;
    border-radius: 6px;
    padding: 8px 12px;
}

/* ===== LineEdit ===== */
QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #C5D0C8;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1A2E23;
    selection-background-color: #1B7340;
    selection-color: #FFFFFF;
}
QLineEdit:focus {
    border: 1px solid #1B7340;
    background-color: #FCFEFB;
}
QLineEdit::placeholder {
    color: #A8B5AC;
}

/* ===== Buttons ===== */
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #C5D0C8;
    border-radius: 6px;
    padding: 6px 16px;
    color: #3A4A40;
    font-weight: 500;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #EDF5EF;
    border-color: #1B7340;
    color: #1B7340;
}
QPushButton:pressed {
    background-color: #D8EBDD;
}
QPushButton:disabled {
    background-color: #F0F2F1;
    border-color: #E0E5E2;
    color: #A8B5AC;
}

QPushButton#primary_btn {
    background-color: #1B7340;
    border: none;
    border-radius: 6px;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 14px;
    padding: 8px 28px;
    min-height: 24px;
}
QPushButton#primary_btn:hover {
    background-color: #239B54;
}
QPushButton#primary_btn:pressed {
    background-color: #19683B;
}
QPushButton#primary_btn:disabled {
    background-color: #9DC4AB;
    color: #FFFFFF;
}

QPushButton#danger_btn {
    background-color: #C0392B;
    border: none;
    border-radius: 6px;
    color: #FFFFFF;
    font-weight: 600;
    padding: 8px 22px;
    min-height: 22px;
}
QPushButton#danger_btn:hover {
    background-color: #D84B3D;
}
QPushButton#danger_btn:pressed {
    background-color: #A93226;
}
QPushButton#danger_btn:disabled {
    background-color: #D5A8A3;
    color: #FFFFFF;
}

/* ===== DoubleSpinBox ===== */
QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #C5D0C8;
    border-radius: 6px;
    padding: 4px 8px;
    color: #1A2E23;
    min-width: 56px;
    font-weight: 500;
}
QDoubleSpinBox:focus {
    border: 1px solid #1B7340;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #E8F5EC;
    border: none;
    border-radius: 3px;
    width: 18px;
    margin: 1px;
}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #1B7340;
}
QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: #19683B;
}
QDoubleSpinBox::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #1B7340;
    width: 0;
    height: 0;
}
QDoubleSpinBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #1B7340;
    width: 0;
    height: 0;
}
QDoubleSpinBox::up-button:hover QDoubleSpinBox::up-arrow,
QDoubleSpinBox::down-button:hover QDoubleSpinBox::down-arrow {
    border-bottom-color: #FFFFFF;
    border-top-color: #FFFFFF;
}
QDoubleSpinBox:disabled {
    background-color: #F0F2F1;
    border-color: #E0E5E2;
    color: #A8B5AC;
}

/* ===== CheckBox ===== */
QCheckBox {
    spacing: 8px;
    color: #3A4A40;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #C5D0C8;
    border-radius: 4px;
    background-color: #FFFFFF;
}
QCheckBox::indicator:hover {
    border-color: #1B7340;
}
QCheckBox::indicator:checked {
    background-color: #1B7340;
    border-color: #1B7340;
}
QCheckBox::indicator:disabled {
    background-color: #F0F2F1;
    border-color: #E0E5E2;
}

/* ===== ProgressBar ===== */
QProgressBar {
    background-color: #E0E5E2;
    border: none;
    border-radius: 5px;
    text-align: center;
    color: #3A4A40;
    font-size: 11px;
    min-height: 20px;
    max-height: 20px;
}
QProgressBar::chunk {
    background-color: #1B7340;
    border-radius: 5px;
}
QProgressBar#merge_progress {
    background-color: #E0E5E2;
    border: 1px solid #DDE5E0;
    border-radius: 5px;
}
QProgressBar#merge_progress::chunk {
    background-color: #239B54;
    border-radius: 5px;
}

/* ===== TreeWidget ===== */
QTreeWidget {
    background-color: #FFFFFF;
    border: 1px solid #DDE5E0;
    border-radius: 8px;
    padding: 4px;
    alternate-background-color: #F8FAF9;
    outline: none;
}
QTreeWidget::item {
    padding: 5px 2px;
    border: none;
}
QTreeWidget::item:hover {
    background-color: #EDF5EF;
}
QTreeWidget::item:selected {
    background-color: #1B7340;
    color: #FFFFFF;
}
QTreeWidget::branch:has-siblings:!adjoins-item,
QTreeWidget::branch:has-siblings:adjoins-item {
    background: transparent;
}
QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    border-image: none;
    image: none;
    background: transparent;
}
QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {
    border-image: none;
    image: none;
    background: transparent;
}
QHeaderView::section {
    background-color: #F2F5F3;
    border: none;
    padding: 6px;
    font-weight: 600;
    color: #5C6B62;
}

/* ===== PlainTextEdit (Log) ===== */
QPlainTextEdit#log_text {
    background-color: #1B2E23;
    color: #C8E6C9;
    border: 1px solid #2A3A30;
    border-radius: 8px;
    font-family: "Cascadia Code", "Consolas", "JetBrains Mono", "Courier New", monospace;
    font-size: 11px;
    padding: 8px;
    selection-background-color: #1B7340;
    selection-color: #FFFFFF;
}

/* ===== StatusBar ===== */
QStatusBar {
    background-color: #FFFFFF;
    border-top: 1px solid #DDE5E0;
    color: #5C6B62;
    font-size: 12px;
}
QStatusBar::item {
    border: none;
}

/* ===== Splitter Handle ===== */
QSplitter::handle:horizontal {
    background-color: #DDE5E0;
    width: 3px;
    margin: 0 3px;
    border-radius: 1px;
}
QSplitter::handle:horizontal:hover {
    background-color: #1B7340;
}

/* ===== ScrollBar — Vertical ===== */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    background: #C5D0C8;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #1B7340;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

/* ===== ScrollBar — Horizontal ===== */
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #C5D0C8;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #1B7340;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ===== ToolTip ===== */
QToolTip {
    background-color: #1B2E23;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

/* ===== ImageLabel ===== */
QLabel#image_label {
    background-color: #F8FAF9;
    border: 1px solid #DDE5E0;
    border-radius: 8px;
    color: #9AAA9E;
    font-size: 13px;
}
"""


# ============================================================
# Helper: Create a section card container
# ============================================================
def create_section(title_text):
    """Create a styled section card with header and separator.

    Returns (container_frame, content_layout).
    """
    container = QFrame()
    container.setObjectName("section_card")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(8)

    header = QLabel(title_text)
    header.setObjectName("section_header")
    layout.addWidget(header)

    sep = QFrame()
    sep.setObjectName("section_separator")
    sep.setFixedHeight(1)
    layout.addWidget(sep)

    return container, layout


# ============================================================
# Custom Log Handler — colored output for different log levels
# ============================================================
class QLogHandler(logging.Handler):
    """Logging handler that appends colored HTML to a QPlainTextEdit."""

    LEVEL_COLORS = {
        logging.DEBUG:    "#7A8A7E",
        logging.INFO:     "#C8E6C9",
        logging.WARNING:  "#FFE082",
        logging.ERROR:    "#EF9A9A",
        logging.CRITICAL: "#FF8A80",
    }

    def __init__(self, widget: QPlainTextEdit):
        super().__init__()
        self.widget = widget
        self.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))

    def emit(self, record):
        msg = self.format(record)
        color = self.LEVEL_COLORS.get(record.levelno, "#C8E6C9")
        # Escape HTML special characters
        msg_escaped = (
            msg.replace("&", "&amp;")
               .replace("<", "&lt;")
               .replace(">", "&gt;")
        )
        self.widget.appendHtml(
            f'<span style="color:{color};">{msg_escaped}</span>'
        )


# ============================================================
# Image Display Widget (loads saved PNG, auto-scales)
# ============================================================
class ImageLabel(QLabel):
    """Display PNG images with auto-scaling and aspect-ratio preservation."""

    EMPTY_TEXT = "等待计算完成后显示结果图片"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self.setObjectName("image_label")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setText(self.EMPTY_TEXT)

    def set_image(self, path):
        """Load and display an image from the given path."""
        if path and os.path.exists(path):
            self._pixmap = QPixmap(path)
            if self._pixmap.isNull():
                self._pixmap = None
        else:
            self._pixmap = None
        self._update_display()

    def _update_display(self):
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            super().setPixmap(scaled)
        else:
            self.setText(self.EMPTY_TEXT)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display()


# ============================================================
# Worker Thread
# ============================================================
class Worker(QThread):
    progress = Signal(int, int, str)
    merge_progress = Signal(int, int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, filepath, folder_path, output_dir,
                 init_lower, init_upper, end_lower, end_upper,
                 enable_stage, stage_lower, stage_upper):
        super().__init__()
        self.filepath = filepath
        self.folder_path = folder_path
        self.output_dir = output_dir
        self.init_lower = init_lower
        self.init_upper = init_upper
        self.end_lower = end_lower
        self.end_upper = end_upper
        self.enable_stage = enable_stage
        self.stage_lower = stage_lower
        self.stage_upper = stage_upper
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self.folder_path:
                logger.info(f"开始加载文件夹: {self.folder_path}")
                raw = load_csv_folder(self.folder_path, self._on_merge_progress)
            else:
                raw = load_csv(self.filepath)

            os.makedirs(self.output_dir, exist_ok=True)
            img_dir = os.path.join(self.output_dir, "03.结果图片")
            os.makedirs(img_dir, exist_ok=True)

            pig_groups = list(raw.groupby("lifenumber"))
            total = len(pig_groups)
            results = []

            for i, (lifenumber, group) in enumerate(pig_groups):
                if self._is_cancelled:
                    return
                self.progress.emit(i + 1, total, lifenumber)

                result = process_pig(group.copy(), lifenumber,
                                     init_lower=self.init_lower, init_upper=self.init_upper,
                                     end_lower=self.end_lower, end_upper=self.end_upper,
                                     stage_lower=(self.stage_lower if self.enable_stage else None),
                                     stage_upper=(self.stage_upper if self.enable_stage else None))
                if result.cleaned_data is not None:
                    result.cleaned_data.index = range(len(result.cleaned_data))

                # Export cleaned data
                clean_path = os.path.join(self.output_dir, f"01.{lifenumber}_清洗后数据.xlsx")
                export_cleaned_excel(result, clean_path)

                # Export main chart (full range)
                img_path = os.path.join(img_dir, f"{lifenumber}.png")
                plot_weight_curve(result, img_path, show_fit=True,
                                  stage_lower=None, stage_upper=None)
                setattr(result, "_full_chart_path", img_path)

                # Export stage chart if enabled
                if self.enable_stage and result.stage_fcr is not None:
                    stage_lbl = f"({self.stage_lower:.0f}-{self.stage_upper:.0f}kg)"
                    stage_path = os.path.join(img_dir,
                                              f"{lifenumber}_阶段{stage_lbl}.png")
                    plot_weight_curve(result, stage_path, show_fit=True,
                                      stage_label=stage_lbl,
                                      stage_lower=self.stage_lower,
                                      stage_upper=self.stage_upper)
                    result.stage_chart_path = stage_path

                results.append(result)

            # Export summary
            summary_path = os.path.join(self.output_dir, "02.样本肉料比信息表.xlsx")
            export_summary_excel(results, summary_path)

            # Export stage summary
            if self.enable_stage:
                stage_summary_path = os.path.join(
                    self.output_dir,
                    f"02.样本阶段肉料比（{self.stage_lower:.0f}-{self.stage_upper:.0f}kg）信息表.xlsx")
                export_stage_summary_excel(results, stage_summary_path,
                                           self.stage_lower, self.stage_upper)

            self.finished.emit(results)
        except Exception as e:
            logger.error(f"计算失败: {e}", exc_info=True)
            self.error.emit(str(e))

    def _on_merge_progress(self, current, total, filename):
        self.merge_progress.emit(current, total, filename)


# ============================================================
# Main Window
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FCR 批量计算工具 v1.2")
        self.setMinimumSize(1200, 800)
        self._results = []
        self._current_pig_idx = None
        self._dir_auto_filled = False
        self._init_ui()

    # --------------------------------------------------------
    # UI Construction
    # --------------------------------------------------------
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # ==================== Header Bar ====================
        header = QFrame()
        header.setObjectName("header_bar")
        header.setFixedHeight(52)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 8, 16, 8)

        # Left: title + subtitle
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        self._title_label = QLabel("FCR 批量计算工具")
        self._title_label.setObjectName("app_title")
        subtitle = QLabel("Feed Conversion Ratio Calculator")
        subtitle.setObjectName("app_subtitle")
        title_col.addWidget(self._title_label)
        title_col.addWidget(subtitle)
        h_layout.addLayout(title_col)
        h_layout.addStretch()

        # Right: version badge
        ver = QLabel("v1.2")
        ver.setObjectName("version_badge")
        ver.setAlignment(Qt.AlignCenter)
        h_layout.addWidget(ver)
        main_layout.addWidget(header)

        # ==================== Data Input Section ====================
        input_card, input_layout = create_section("数据输入")

        # Row 1: file input + output dir
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(QLabel("输入文件:"))
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("选择单个 CSV 文件...")
        self.file_edit.setMinimumWidth(220)
        row1.addWidget(self.file_edit, stretch=3)
        self.btn_browse = QPushButton("浏览文件")
        self.btn_browse.clicked.connect(self._browse_file)
        row1.addWidget(self.btn_browse)
        row1.addSpacing(16)
        row1.addWidget(QLabel("输出目录:"))
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("默认自动生成...")
        self.dir_edit.setMinimumWidth(160)
        row1.addWidget(self.dir_edit, stretch=2)
        self.btn_dir = QPushButton("浏览目录")
        self.btn_dir.clicked.connect(self._browse_dir)
        row1.addWidget(self.btn_dir)
        input_layout.addLayout(row1)

        # Row 2: batch folder input
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("批量输入:"))
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("选择包含 CSV 的文件夹（批量模式）...")
        self.folder_edit.setMinimumWidth(220)
        row2.addWidget(self.folder_edit, stretch=5)
        self.btn_browse_folder = QPushButton("浏览文件夹")
        self.btn_browse_folder.clicked.connect(self._browse_folder)
        row2.addWidget(self.btn_browse_folder)
        input_layout.addLayout(row2)

        main_layout.addWidget(input_card)

        # ==================== Parameters Section ====================
        param_card, param_layout = create_section("计算参数")

        # Row 1: weight ranges
        prow1 = QHBoxLayout()
        prow1.setSpacing(8)
        prow1.addWidget(QLabel("初测体重:"))
        self.spin_init_lo = QDoubleSpinBox()
        self.spin_init_lo.setRange(10, 60)
        self.spin_init_lo.setValue(25)
        self.spin_init_lo.setDecimals(0)
        prow1.addWidget(self.spin_init_lo)
        dash1 = QLabel("–")
        dash1.setFixedWidth(10)
        dash1.setAlignment(Qt.AlignCenter)
        prow1.addWidget(dash1)
        self.spin_init_hi = QDoubleSpinBox()
        self.spin_init_hi.setRange(20, 100)
        self.spin_init_hi.setValue(45)
        self.spin_init_hi.setSuffix(" kg")
        self.spin_init_hi.setDecimals(0)
        prow1.addWidget(self.spin_init_hi)
        prow1.addSpacing(20)
        prow1.addWidget(QLabel("终测体重:"))
        self.spin_end_lo = QDoubleSpinBox()
        self.spin_end_lo.setRange(30, 130)
        self.spin_end_lo.setValue(90)
        self.spin_end_lo.setDecimals(0)
        prow1.addWidget(self.spin_end_lo)
        dash2 = QLabel("–")
        dash2.setFixedWidth(10)
        dash2.setAlignment(Qt.AlignCenter)
        prow1.addWidget(dash2)
        self.spin_end_hi = QDoubleSpinBox()
        self.spin_end_hi.setRange(60, 150)
        self.spin_end_hi.setValue(110)
        self.spin_end_hi.setSuffix(" kg")
        self.spin_end_hi.setDecimals(0)
        prow1.addWidget(self.spin_end_hi)
        prow1.addStretch()
        param_layout.addLayout(prow1)

        # Row 2: stage + fit + action buttons
        prow2 = QHBoxLayout()
        prow2.setSpacing(8)
        self.chk_enable_stage = QCheckBox("阶段料肉比计算")
        self.chk_enable_stage.toggled.connect(self._on_stage_toggled)
        prow2.addWidget(self.chk_enable_stage)
        prow2.addWidget(QLabel("区间:"))
        self.spin_stage_lo = QDoubleSpinBox()
        self.spin_stage_lo.setRange(10, 100)
        self.spin_stage_lo.setValue(STAGE_WEIGHT_LOWER)
        self.spin_stage_lo.setSuffix(" kg")
        self.spin_stage_lo.setDecimals(0)
        prow2.addWidget(self.spin_stage_lo)
        dash3 = QLabel("–")
        dash3.setFixedWidth(10)
        dash3.setAlignment(Qt.AlignCenter)
        prow2.addWidget(dash3)
        self.spin_stage_hi = QDoubleSpinBox()
        self.spin_stage_hi.setRange(20, 150)
        self.spin_stage_hi.setValue(STAGE_WEIGHT_UPPER)
        self.spin_stage_hi.setSuffix(" kg")
        self.spin_stage_hi.setDecimals(0)
        prow2.addWidget(self.spin_stage_hi)
        prow2.addStretch()
        self.chk_fit = QCheckBox("显示拟合曲线")
        self.chk_fit.setChecked(True)
        self.chk_fit.toggled.connect(self._on_fit_toggled)
        prow2.addWidget(self.chk_fit)
        prow2.addSpacing(16)
        self.btn_start = QPushButton("开始计算")
        self.btn_start.setObjectName("primary_btn")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self._start_calc)
        prow2.addWidget(self.btn_start)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setObjectName("danger_btn")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_calc)
        prow2.addWidget(self.btn_stop)
        param_layout.addLayout(prow2)

        main_layout.addWidget(param_card)

        # ==================== Merge Progress Bar ====================
        self.merge_progress_bar = QProgressBar()
        self.merge_progress_bar.setObjectName("merge_progress")
        self.merge_progress_bar.setRange(0, 100)
        self.merge_progress_bar.setVisible(False)
        self.merge_progress_bar.setFormat("合并文件: %v/%m")
        self.merge_progress_bar.setFixedHeight(22)
        main_layout.addWidget(self.merge_progress_bar)

        # ==================== Splitter: Tree + Image Preview ====================
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)

        # --- Left: pig tree ---
        tree_container = QFrame()
        tree_container.setObjectName("section_card")
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(8, 8, 8, 8)
        tree_layout.setSpacing(4)
        tree_header = QLabel("猪只列表")
        tree_header.setObjectName("section_header")
        tree_layout.addWidget(tree_header)
        self.pig_tree = QTreeWidget()
        self.pig_tree.setMinimumWidth(260)
        self.pig_tree.setHeaderHidden(True)
        self.pig_tree.setAlternatingRowColors(True)
        self.pig_tree.currentItemChanged.connect(self._on_pig_selected)
        tree_layout.addWidget(self.pig_tree)
        splitter.addWidget(tree_container)

        # --- Right: image preview ---
        right_container = QFrame()
        right_container.setObjectName("section_card")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(4)
        right_header = QLabel("体重曲线预览")
        right_header.setObjectName("section_header")
        right_layout.addWidget(right_header)
        self.img_label = ImageLabel(self)
        right_layout.addWidget(self.img_label, stretch=1)
        hint_label = QLabel("图片自动缩放适应窗口  ·  点击左侧列表切换猪只")
        hint_label.setObjectName("hint_label")
        hint_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(hint_label)
        self.info_label = QLabel("请选择 CSV 文件并开始计算")
        self.info_label.setObjectName("info_label")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label)
        splitter.addWidget(right_container)
        splitter.setSizes([280, 820])
        main_layout.addWidget(splitter, stretch=3)

        # ==================== Log Panel ====================
        log_card, log_layout = create_section("处理日志")
        self.log_text = QPlainTextEdit()
        self.log_text.setObjectName("log_text")
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(500)
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_card, stretch=1)

        log_handler = QLogHandler(self.log_text)
        logging.getLogger("FCRCore").addHandler(log_handler)
        logging.getLogger("FCRApp").addHandler(log_handler)

        # ==================== Status Bar ====================
        self.status_bar = QStatusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.setStatusBar(self.status_bar)

        # ==================== Initialize state ====================
        self._on_stage_toggled(False)
        logger.info("界面初始化完成")

    # --------------------------------------------------------
    # UI Events
    # --------------------------------------------------------

    def _auto_fill_dir(self, base_path):
        """Auto-fill the output directory based on input path."""
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        self.dir_edit.setText(os.path.join(base_path, f"{ts}_fcr_results"))
        self._dir_auto_filled = True

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择CSV文件", "", "CSV文件 (*.csv);;所有文件 (*)"
        )
        if path:
            self.file_edit.setText(path)
            self.folder_edit.clear()
            if not self.dir_edit.text() or self._dir_auto_filled:
                self._auto_fill_dir(os.path.dirname(path))

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择包含CSV的文件夹")
        if path:
            self.folder_edit.setText(path)
            self.file_edit.clear()
            if not self.dir_edit.text() or self._dir_auto_filled:
                self._auto_fill_dir(path)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.dir_edit.setText(path)
            self._dir_auto_filled = False

    def _on_stage_toggled(self, checked):
        self.spin_stage_lo.setEnabled(checked)
        self.spin_stage_hi.setEnabled(checked)
        logger.info("阶段料肉比计算已启用" if checked else "阶段料肉比计算已关闭")
        if self._current_pig_idx is not None and self._current_pig_idx < len(self._results):
            self._update_preview(self._results[self._current_pig_idx])

    def _on_fit_toggled(self):
        if self._current_pig_idx is not None and self._current_pig_idx < len(self._results):
            self._update_preview(self._results[self._current_pig_idx])

    def _on_pig_selected(self, current, previous):
        """Tree item click -> preview corresponding pig curve."""
        if current is None:
            return
        idx = current.data(0, Qt.UserRole)
        if idx is None or idx < 0 or idx >= len(self._results):
            return
        self._current_pig_idx = idx
        result = self._results[idx]
        self._update_preview(result)
        self.status_bar.showMessage(f"选择: {result.lifenumber}", 5000)

    def _update_preview(self, result):
        """Update the preview area — load PNG from output directory."""
        enable_stage = self.chk_enable_stage.isChecked()

        # Determine which image to show (stage or full)
        if enable_stage and hasattr(result, 'stage_chart_path') \
           and result.stage_chart_path and os.path.exists(result.stage_chart_path):
            img_path = result.stage_chart_path
        else:
            full_path = getattr(result, '_full_chart_path', None)
            img_path = full_path if full_path and os.path.exists(full_path) else None

        self.img_label.set_image(img_path)

        info_lines = [
            f"批次号: {result.lifenumber}",
            f"起止: {result.start_date} ~ {result.end_date}",
            f"体重: {result.start_weight} → {result.end_weight} kg",
        ]
        if result.adg:
            info_lines.append(f"ADG: {result.adg:.4f} kg/d  R²: {result.r_squared:.4f}")
        if result.fcr:
            info_lines.append(f"FCR(料重比): {result.fcr:.3f}")
        if result.fill_info:
            info_lines.append(f"备注: {result.fill_info}")
        stage_lo = self.spin_stage_lo.value() if enable_stage else None
        stage_hi = self.spin_stage_hi.value() if enable_stage else None
        if enable_stage and result.stage_fcr is not None:
            info_lines.append(
                f"阶段FCR({stage_lo:.0f}-{stage_hi:.0f}kg): {result.stage_fcr:.3f}  "
                f"ADG: {result.stage_adg:.4f}"
            )

        self.info_label.setText("  |  ".join(info_lines))

    # --------------------------------------------------------
    # Calculation Flow
    # --------------------------------------------------------

    def _start_calc(self):
        filepath = self.file_edit.text().strip()
        folder_path = self.folder_edit.text().strip()

        if not folder_path and (not filepath or not os.path.exists(filepath)):
            QMessageBox.warning(self, "提示", "请选择有效的CSV文件或包含CSV的文件夹")
            return
        if folder_path and not os.path.isdir(folder_path):
            QMessageBox.warning(self, "提示", "请选择有效的文件夹路径")
            return

        output_dir = self.dir_edit.text().strip()
        if not output_dir:
            ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
            base = folder_path if folder_path else os.path.dirname(filepath)
            output_dir = os.path.join(base, f"{ts}_fcr_results")

        enable_stage = self.chk_enable_stage.isChecked()

        self._results = []
        self.pig_tree.blockSignals(True)
        self.pig_tree.clear()
        self.pig_tree.blockSignals(False)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.merge_progress_bar.setVisible(bool(folder_path))
        self.merge_progress_bar.setValue(0)
        self.status_bar.showMessage("计算中...")
        logger.info(
            f"开始计算: 输入={'文件夹' if folder_path else '单文件'}, "
            f"输出={output_dir}, 阶段={enable_stage}"
        )

        self._worker = Worker(
            filepath, folder_path, output_dir,
            self.spin_init_lo.value(), self.spin_init_hi.value(),
            self.spin_end_lo.value(), self.spin_end_hi.value(),
            enable_stage,
            self.spin_stage_lo.value(), self.spin_stage_hi.value(),
        )
        self._worker.merge_progress.connect(self._on_merge_progress)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop_calc(self):
        if hasattr(self, "_worker") and self._worker.isRunning():
            self._worker.cancel()
            self._worker.quit()
            self.status_bar.showMessage("已停止")
            logger.info("用户手动停止计算")

    def _on_merge_progress(self, current, total, filename):
        self.merge_progress_bar.setMaximum(total)
        self.merge_progress_bar.setValue(current)
        self.merge_progress_bar.setFormat(f"合并文件: {current}/{total} — {filename}")
        self.status_bar.showMessage(f"正在合并: {current}/{total} — {filename}")

    def _on_progress(self, current, total, lifenumber):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_bar.showMessage(f"正在处理 {current}/{total}: {lifenumber}")

    def _on_finished(self, results):
        self._results = results
        self.progress_bar.setVisible(False)
        self.merge_progress_bar.setVisible(False)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        # Build tree structure: source file -> pig list
        self.pig_tree.blockSignals(True)
        self.pig_tree.clear()
        from collections import OrderedDict
        file_groups = OrderedDict()
        for idx, r in enumerate(results):
            src_name = "(unknown)"
            if r.cleaned_data is not None and "_source_file" in r.cleaned_data.columns:
                srcs = r.cleaned_data["_source_file"].dropna().unique()
                if len(srcs) > 0:
                    src_name = srcs[0]
            file_groups.setdefault(src_name, []).append(idx)

        for fname, indices in file_groups.items():
            file_item = QTreeWidgetItem(self.pig_tree, [fname])
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsSelectable)
            font = file_item.font(0)
            font.setBold(True)
            file_item.setFont(0, font)
            for idx in indices:
                r = results[idx]
                flag = "  ⚠  " if r.is_abnormal == "异常样本" else "  "
                pig_item = QTreeWidgetItem(
                    file_item,
                    [f"{flag}{r.lifenumber}  FCR:{r.fcr or '-'}"]
                )
                pig_item.setData(0, Qt.UserRole, idx)
            file_item.setExpanded(True)

        self.pig_tree.blockSignals(False)

        fcr_vals = [r.fcr for r in results if r.fcr is not None]
        avg_fcr = f"{np.mean(fcr_vals):.3f}" if fcr_vals else "N/A"
        msg = f"完成! 共 {len(results)} 头猪 | FCR均值: {avg_fcr}"
        self.status_bar.showMessage(msg)
        logger.info(msg)

        if results:
            first_pig = (
                self.pig_tree.topLevelItem(0).child(0)
                if self.pig_tree.topLevelItemCount() > 0
                and self.pig_tree.topLevelItem(0).childCount() > 0
                else None
            )
            if first_pig:
                self.pig_tree.setCurrentItem(first_pig)
                self._current_pig_idx = 0
                self._update_preview(results[0])

    def _on_error(self, msg):
        self.progress_bar.setVisible(False)
        self.merge_progress_bar.setVisible(False)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.critical(self, "错误", f"计算失败:\n{msg}")
        self.status_bar.showMessage("计算失败")
        logger.error(f"计算失败: {msg}")


def main():
    # Global exception handler to prevent silent crashes
    def excepthook(exc_type, exc_value, exc_tb):
        import traceback
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical(f"未捕获的异常:\n{msg}")
        QMessageBox.critical(None, "程序错误",
                             f"发生未预期的错误，请查看日志:\n{exc_value}")

    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
