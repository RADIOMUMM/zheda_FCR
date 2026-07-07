"""
FCR计算工具 GUI主窗口 — v1.1 美化版
=====================================
设计系统: 农科绿主题 (#0F6E56) + 琥珀强调色 (#EF9F27)
布局策略: 卡片式分区 + 渐变标题栏 + 信息层次化展示
"""
import sys, os, logging
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import pandas as pd

from fcr_app.core import load_csv, process_pig, batch_process, export_summary_excel, export_cleaned_excel
from fcr_app.core import load_csv, load_csv_folder, process_pig, batch_process, export_summary_excel, export_cleaned_excel, calc_stage_fcr
from fcr_app.chart import plot_preview, plot_weight_curve, plot_weight_curve_stage

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("FCRApp")

# ============================================================
# QSS Stylesheet — 全局设计令牌
# ============================================================
GLOBAL_QSS = """
/* ===== 基础 ===== */
QMainWindow, QWidget {
    background-color: #F4F5F7;
    color: #2C2C2A;
    font-family: "Microsoft YaHei UI", "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}

/* ===== 卡片容器 ===== */
QFrame#CardFrame {
    background-color: #FFFFFF;
    border-radius: 10px;
    border: 1px solid #E8EAEd;
}

QFrame#CardHeader {
    background-color: #E1F5EE;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border: none;
    min-height: 32px;
}

QLabel#CardTitle {
    color: #085041;
    font-size: 14px;
    font-weight: 700;
    padding-left: 10px;
}

QLabel#CardHint {
    color: #1D9E75;
    font-size: 12px;
    padding-right: 10px;
    font-weight: 500;
}

/* ===== 标题栏 ===== */
QFrame#HeaderBar {
    background-color: #0F6E56;
    border: none;
    min-height: 44px;
    max-height: 44px;
    border-radius: 8px;
}
QLabel#HeaderTitle {
    color: #FFFFFF;
    font-size: 17px;
    font-weight: 700;
    background: transparent;
}
QLabel#HeaderAccent {
    color: #9FE1CB;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}

/* ===== 卡片 ===== */
QFrame#CardFrame {
    background-color: #FFFFFF;
    border-radius: 10px;
    border: 1px solid #E8EAEd;
}

QFrame#CardHeader {
    background-color: #E1F5EE;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border: none;
    min-height: 36px;
}

/* ===== 输入框 ===== */
QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #D3D1C7;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    color: #2C2C2A;
    selection-background-color: #5DCAA5;
    selection-color: #FFFFFF;
}
QLineEdit:focus {
    border: 1.5px solid #1D9E75;
    background-color: #FFFFFF;
}
QLineEdit::placeholder {
    color: #B4B2A9;
}

/* ===== SpinBox ===== */
QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #D3D1C7;
    border-radius: 6px;
    padding: 0px 0px 0px 10px;
    font-size: 13px;
    font-weight: 500;
    color: #2C2C2A;
    selection-background-color: #5DCAA5;
    selection-color: #FFFFFF;
    min-height: 24px;
    max-height: 24px;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #1D9E75;
    background-color: #FFFFFF;
}
/* 上下按钮: 背景纯白, 无横线 */
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    height: 12px;
    border: none;
    border-left: 1px solid #E8EAEd;
    border-top-right-radius: 6px;
    background-color: #FFFFFF;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    height: 12px;
    border: none;
    border-left: 1px solid #E8EAEd;
    border-bottom-right-radius: 6px;
    background-color: #FFFFFF;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #E1F5EE;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: #9FE1CB;
}

/* 上箭头: CSS border 三角 (Windows 上 SVG data URI 在 up-arrow 不可靠) */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #085041;
    background: transparent;
}
QSpinBox::up-button:hover QSpinBox::up-arrow,
QDoubleSpinBox::up-button:hover QDoubleSpinBox::up-arrow {
    border-bottom-color: #0F6E56;
}

/* 下箭头 */
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #085041;
    background: transparent;
}
QSpinBox::down-button:hover QSpinBox::down-arrow,
QDoubleSpinBox::down-button:hover QDoubleSpinBox::down-arrow {
    border-top-color: #0F6E56;
}

/* ===== 按钮 ===== */
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #D3D1C7;
    border-radius: 6px;
    padding: 3px 14px;
    font-size: 13px;
    color: #444441;
    min-height: 24px;
    max-height: 24px;
}
QPushButton:hover {
    background-color: #E1F5EE;
    border-color: #5DCAA5;
    color: #085041;
}
QPushButton:pressed {
    background-color: #9FE1CB;
}
QPushButton:disabled {
    background-color: #F4F5F7;
    color: #B4B2A9;
    border-color: #E8EAEd;
}

QPushButton#PrimaryBtn {
    background-color: #0F6E56;
    border: none;
    border-radius: 6px;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 600;
    min-height: 28px;
    max-height: 28px;
    padding: 3px 20px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #1D9E75;
}
QPushButton#PrimaryBtn:pressed {
    background-color: #085041;
}
QPushButton#PrimaryBtn:disabled {
    background-color: #B4D8CB;
    color: #FFFFFF;
}

QPushButton#DangerBtn {
    background-color: #FFFFFF;
    border: 1.5px solid #E24B4A;
    border-radius: 6px;
    color: #E24B4A;
    font-size: 13px;
    font-weight: 500;
    min-height: 28px;
    max-height: 28px;
    padding: 3px 16px;
}
QPushButton#DangerBtn:hover {
    background-color: #FCEBEB;
}
QPushButton#DangerBtn:pressed {
    background-color: #F7C1C1;
}
QPushButton#DangerBtn:disabled {
    border-color: #F0D5D5;
    color: #C9A0A0;
}

QPushButton#BrowseBtn {
    background-color: #0F6E56;
    border: none;
    border-radius: 6px;
    color: #FFFFFF;
    font-size: 12px;
    padding: 2px 12px;
    min-height: 24px;
    max-height: 24px;
    min-width: 64px;
}
QPushButton#BrowseBtn:hover {
    background-color: #1D9E75;
}
QPushButton#BrowseBtn:pressed {
    background-color: #085041;
}

/* ===== 复选框 ===== */
QCheckBox {
    spacing: 6px;
    font-size: 13px;
    color: #2C2C2A;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1.5px solid #888780;
    background-color: #FFFFFF;
}
QCheckBox::indicator:hover {
    border-color: #1D9E75;
}
QCheckBox::indicator:checked {
    background-color: #0F6E56;
    border: 1.5px solid #0F6E56;
    border-radius: 4px;
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M3 8 L7 12 L13 4' stroke='white' stroke-width='2.2' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
}

/* ===== 列表 ===== */
QListWidget {
    background-color: #FFFFFF;
    border: none;
    border-radius: 0px;
    outline: none;
    font-size: 13px;
}
QListWidget::item {
    padding: 8px 12px;
    border-bottom: 0.5px solid #F1EFE8;
    color: #2C2C2A;
}
QListWidget::item:hover {
    background-color: #F8F9FA;
}
QListWidget::item:selected {
    background-color: #E1F5EE;
    color: #085041;
    border-left: 3px solid #0F6E56;
}
QListWidget::item:selected:hover {
    background-color: #D0EEDF;
}

/* ===== 滚动条 ===== */
QScrollBar:vertical {
    background: #F8F9FA;
    width: 8px;
    border: none;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #D3D1C7;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #888780;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: #F8F9FA;
    height: 8px;
    border: none;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #D3D1C7;
    min-width: 30px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #888780;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ===== 进度条 ===== */
QProgressBar {
    background-color: #F1EFE8;
    border: none;
    border-radius: 6px;
    min-height: 16px;
    max-height: 16px;
    text-align: center;
    font-size: 11px;
    color: #2C2C2A;
}
QProgressBar::chunk {
    background-color: #0F6E56;
    border-radius: 6px;
}

/* ===== 状态栏 ===== */
QStatusBar {
    background-color: #FFFFFF;
    border-top: 1px solid #E8EAEd;
    color: #5F5E5A;
    font-size: 12px;
    min-height: 28px;
}
QStatusBar::item {
    border: none;
}

/* ===== Splitter ===== */
QSplitter::handle {
    background-color: #E8EAEd;
    width: 1px;
}
QSplitter::handle:hover {
    background-color: #5DCAA5;
}

/* ===== 信息标签 ===== */
QLabel#InfoLabel {
    background-color: #F8F9FA;
    border: 1px solid #E8EAEd;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
    color: #444441;
}
QLabel#SectionLabel {
    color: #085041;
    font-size: 13px;
    font-weight: 600;
    min-width: 60px;
}
QLabel#SepLabel {
    color: #0F6E56;
    font-size: 14px;
    font-weight: 700;
}
QLabel#RowLabel {
    color: #085041;
    font-size: 13px;
    font-weight: 600;
    min-width: 80px;
}

/* ===== 对话框 ===== */
QMessageBox {
    background-color: #FFFFFF;
}
QMessageBox QLabel {
    font-size: 13px;
    color: #2C2C2A;
}
"""

# ============================================================
# Matplotlib Canvas Embed
# ============================================================
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=8, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor("#FAFBFC")
        super().__init__(self.fig)
        self.setParent(parent)
        self.setStyleSheet("background-color: #FAFBFC; border-radius: 8px;")

    def update_plot(self, result, show_fit=True):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#FAFBFC")
        df = result.cleaned_data
        if df is None or len(df) == 0:
            ax.text(0.5, 0.5, "无数据", ha="center", va="center", fontsize=14, transform=ax.transAxes, color="#888780")
            self.draw()
            return
        import numpy as np, matplotlib.dates as mdates
        valid = df[~df["is_abnormal"] & df["qc_weight_kg"].notna()]
        if len(valid) > 0:
            ax.scatter(valid["visit_time"], valid["qc_weight_kg"], c="#1D9E75", s=25, alpha=0.7, zorder=3, edgecolors="none")
        abnormal = df[df["is_abnormal"] & df["weight_kg"].notna()]
        if len(abnormal) > 0:
            ax.scatter(abnormal["visit_time"], abnormal["weight_kg"], c="#E24B4A", s=15, alpha=0.4, marker="x", zorder=2)
        if show_fit and result.adg is not None and len(valid) >= 3:
            x_min = valid["visit_time"].min()
            x_days = (valid["visit_time"] - x_min).dt.days.values.astype(float)
            y_vals = valid["qc_weight_kg"].values
            A = np.vstack([x_days, np.ones(len(x_days))]).T
            m, c = np.linalg.lstsq(A, y_vals, rcond=None)[0]
            x_fit = np.linspace(0, x_days.max(), 100)
            y_fit = m * x_fit + c
            fit_dates = [x_min + pd.Timedelta(days=int(d)) for d in x_fit]
            ax.plot(fit_dates, y_fit, "-", color="#E24B4A", linewidth=2, zorder=4)
        info = f"{result.lifenumber}  FCR:{result.fcr or '-'}  ADG:{result.adg or '-'}"
        ax.set_title(info, fontsize=12, color="#085041", fontweight="bold")
        ax.set_xlabel("日期", fontsize=11, color="#5F5E5A")
        ax.set_ylabel("体重 (kg)", fontsize=11, color="#5F5E5A")
        ax.tick_params(colors="#5F5E5A", labelsize=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        self.fig.autofmt_xdate()
        ax.grid(True, alpha=0.2, color="#D3D1C7")
        for spine in ax.spines.values():
            spine.set_color("#E8EAEd")
        self.fig.tight_layout()
        self.draw()

# ============================================================
# Worker Thread
# ============================================================
class Worker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, filepath, folder_path, output_dir, min_age, max_age, init_lower, init_upper, stage_lo=30, stage_hi=75, calc_stage=True):
        super().__init__()
        self.filepath = filepath
        self.output_dir = output_dir
        self.min_age = min_age
        self.max_age = max_age
        self.init_lower = init_lower
        self.init_upper = init_upper
        self.folder_path = folder_path
        self.calc_stage = calc_stage
        self.stage_lo = stage_lo
        self.stage_hi = stage_hi
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            fpath = self.folder_path if self.folder_path and os.path.isdir(self.folder_path) else self.filepath
            if os.path.isdir(fpath):
                raw = load_csv_folder(fpath)
            else:
                raw = load_csv(fpath)
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

                result = process_pig(group.copy(), lifenumber, self.min_age, self.max_age, self.init_lower, self.init_upper)
                result.cleaned_data.index = range(len(result.cleaned_data))
                if self.calc_stage:
                    stage_result = calc_stage_fcr(result, self.stage_lo, self.stage_hi)
                    result.stage_fcr = stage_result["fcr"]
                    result.stage_adg = stage_result["adg"]
                    result.stage_data = stage_result

                # 导出清洗数据
                clean_path = os.path.join(self.output_dir, f"01.{lifenumber}_清洗后数据.xlsx")
                export_cleaned_excel(result, clean_path)

                # 导出图片
                img_path = os.path.join(img_dir, f"{lifenumber}.png")
                plot_weight_curve(result, img_path, show_fit=True)
                if self.calc_stage:
                    stage_img = os.path.join(img_dir, f"{lifenumber}_阶段({self.stage_lo:.0f}-{self.stage_hi:.0f}kg).png")
                    plot_weight_curve_stage(result, stage_img, self.stage_lo, self.stage_hi, show_fit=True)
                result.chart_path = img_path

                results.append(result)

            # 导出汇总表
            summary_path = os.path.join(self.output_dir, "02.样本肉料比信息表.xlsx")
            export_summary_excel(results, summary_path)
            if self.calc_stage:
                stage_rows = []
                for r in results:
                    sd = getattr(r, "stage_data", {}) or {}
                    stage_rows.append({
                        "个体批次号": r.lifenumber,
                        "起始时间": str(sd.get("start_date", "")) if sd.get("start_date") else "",
                        "阶段起始体重": sd.get("start_weight"),
                        "终止时间": str(sd.get("end_date", "")) if sd.get("end_date") else "",
                        "阶段终止体重": sd.get("end_weight"),
                        "阶段总采食量": sd.get("total_feed"),
                        "阶段ADG": sd.get("adg"),
                        "阶段ADFI": sd.get("adfi"),
                        "R²": sd.get("r2"),
                        "阶段FCR": sd.get("fcr"),
                        "原始FCR": sd.get("fcr_raw"),
                        "异常": r.is_abnormal,
                    })
                stage_path = os.path.join(self.output_dir, f"02.样本阶段肉料比({self.stage_lo:.0f}-{self.stage_hi:.0f}kg)信息表.xlsx")
                pd.DataFrame(stage_rows).to_excel(stage_path, index=False, engine="openpyxl")

            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

# ============================================================
# Helper: Card Section Builder
# ============================================================
def make_card(title, hint=""):
    """创建卡片容器: 返回 (frame, content_layout)"""
    frame = QFrame()
    frame.setObjectName("CardFrame")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    header = QFrame()
    header.setObjectName("CardHeader")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(12, 4, 12, 4)
    lbl_title = QLabel(title)
    lbl_title.setObjectName("CardTitle")
    header_layout.addWidget(lbl_title)
    header_layout.addStretch()
    if hint:
        lbl_hint = QLabel(hint)
        lbl_hint.setObjectName("CardHint")
        header_layout.addWidget(lbl_hint)
    layout.addWidget(header)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(14, 10, 14, 12)
    content_layout.setSpacing(8)
    layout.addWidget(content)

    return frame, content_layout

# ============================================================
# Main Window
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FCR 批量计算工具 v1.1")
        self.setMinimumSize(1200, 780)
        self._results = []
        self._current_pig_idx = None
        self._last_output_dir = None
        self._init_ui()

    def _init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(10)

        # ===== Header Bar =====
        header = QFrame()
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 0, 18, 0)
        header_layout.setSpacing(0)
        lbl_title = QLabel("FCR 批量计算工具 v1.1")
        lbl_title.setObjectName("HeaderTitle")
        lbl_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        header_layout.addWidget(lbl_title)
        header_layout.addStretch(1)
        # 右侧品牌色块装饰
        accent = QLabel("v1.1")
        accent.setObjectName("HeaderAccent")
        accent.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        header_layout.addWidget(accent)
        main_layout.addWidget(header)

        # ===== Top Row: Input Card + Params Card =====
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # --- Input Card ---
        input_card, input_layout = make_card("数据输入", "选择CSV文件或文件夹")
        input_layout.setSpacing(10)
        # Row 1: Single file
        r1 = QHBoxLayout()
        r1.setSpacing(8)
        lbl1 = QLabel("单文件输入"); lbl1.setObjectName("RowLabel")
        self.file_edit = QLineEdit(); self.file_edit.setPlaceholderText("选择单个CSV文件...")
        self.btn_browse = QPushButton("浏览文件")
        self.btn_browse.setObjectName("BrowseBtn")
        self.btn_browse.clicked.connect(self._browse_file)
        r1.addWidget(lbl1); r1.addWidget(self.file_edit, 1); r1.addWidget(self.btn_browse)
        input_layout.addLayout(r1)
        # Row 2: Folder
        r2 = QHBoxLayout()
        r2.setSpacing(8)
        lbl2 = QLabel("批量文件夹"); lbl2.setObjectName("RowLabel")
        self.folder_edit = QLineEdit(); self.folder_edit.setPlaceholderText("选择包含CSV的文件夹...")
        self.btn_folder = QPushButton("浏览文件夹")
        self.btn_folder.setObjectName("BrowseBtn")
        self.btn_folder.clicked.connect(self._browse_folder)
        r2.addWidget(lbl2); r2.addWidget(self.folder_edit, 1); r2.addWidget(self.btn_folder)
        input_layout.addLayout(r2)
        # Row 3: Output dir
        r3 = QHBoxLayout()
        r3.setSpacing(8)
        lbl3 = QLabel("输出目录"); lbl3.setObjectName("RowLabel")
        self.dir_edit = QLineEdit(); self.dir_edit.setPlaceholderText("输出目录（默认自动生成）...")
        self.btn_dir = QPushButton("浏览目录")
        self.btn_dir.setObjectName("BrowseBtn")
        self.btn_dir.clicked.connect(self._browse_dir)
        r3.addWidget(lbl3); r3.addWidget(self.dir_edit, 1); r3.addWidget(self.btn_dir)
        input_layout.addLayout(r3)
        # 互斥
        self.file_edit.textChanged.connect(lambda t: self.folder_edit.clear() if t else None)
        self.folder_edit.textChanged.connect(lambda t: self.file_edit.clear() if t else None)

        top_row.addWidget(input_card, 1)

        # --- Params Card ---
        params_card, params_layout = make_card("计算参数", "日龄 / 体重 / 阶段设置")
        # Row 1: Age range + weight range
        p1 = QHBoxLayout()
        p1.setSpacing(8)
        lbl_age = QLabel("日龄范围"); lbl_age.setObjectName("RowLabel")
        p1.addWidget(lbl_age)
        self.spin_min_age = QSpinBox(); self.spin_min_age.setRange(30, 365); self.spin_min_age.setValue(100)
        self.spin_min_age.setFixedWidth(76)
        p1.addWidget(self.spin_min_age)
        p1.addSpacing(6)
        self.spin_max_age = QSpinBox(); self.spin_max_age.setRange(30, 365); self.spin_max_age.setValue(200)
        self.spin_max_age.setFixedWidth(76)
        p1.addWidget(self.spin_max_age)
        p1.addSpacing(24)
        lbl_wt = QLabel("初测体重"); lbl_wt.setObjectName("RowLabel")
        p1.addWidget(lbl_wt)
        self.spin_init_lo = QDoubleSpinBox(); self.spin_init_lo.setRange(10, 60); self.spin_init_lo.setValue(25); self.spin_init_lo.setDecimals(0)
        self.spin_init_lo.setSuffix("kg")
        self.spin_init_lo.setFixedWidth(86)
        p1.addWidget(self.spin_init_lo)
        p1.addSpacing(6)
        self.spin_init_hi = QDoubleSpinBox(); self.spin_init_hi.setRange(20, 100); self.spin_init_hi.setValue(45); self.spin_init_hi.setSuffix("kg"); self.spin_init_hi.setDecimals(0)
        self.spin_init_hi.setFixedWidth(86)
        p1.addWidget(self.spin_init_hi)
        p1.addStretch()
        params_layout.addLayout(p1)

        # Row 2: Stage FCR + Fit curve
        p2 = QHBoxLayout()
        p2.setSpacing(8)
        self.chk_stage = QCheckBox("计算阶段料肉比")
        self.chk_stage.setChecked(False)
        self.chk_stage.toggled.connect(self._on_stage_toggled)
        p2.addWidget(self.chk_stage)
        p2.addSpacing(6)
        self.spin_stage_lo = QDoubleSpinBox(); self.spin_stage_lo.setRange(10, 200); self.spin_stage_lo.setValue(30); self.spin_stage_lo.setSuffix("kg"); self.spin_stage_lo.setDecimals(0)
        self.spin_stage_lo.setFixedWidth(86)
        p2.addWidget(self.spin_stage_lo)
        p2.addSpacing(6)
        self.spin_stage_hi = QDoubleSpinBox(); self.spin_stage_hi.setRange(10, 200); self.spin_stage_hi.setValue(75); self.spin_stage_hi.setSuffix("kg"); self.spin_stage_hi.setDecimals(0)
        self.spin_stage_hi.setFixedWidth(86)
        p2.addWidget(self.spin_stage_hi)
        p2.addSpacing(24)
        self.chk_fit = QCheckBox("显示拟合曲线")
        self.chk_fit.setChecked(True)
        self.chk_fit.toggled.connect(self._on_fit_toggled)
        p2.addWidget(self.chk_fit)
        p2.addStretch()
        params_layout.addLayout(p2)

        # Row 3: Buttons
        p3 = QHBoxLayout()
        p3.addStretch()
        self.btn_start = QPushButton("开始计算")
        self.btn_start.setObjectName("PrimaryBtn")
        self.btn_start.clicked.connect(self._start_calc)
        p3.addWidget(self.btn_start)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setObjectName("DangerBtn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_calc)
        p3.addWidget(self.btn_stop)
        params_layout.addLayout(p3)

        top_row.addWidget(params_card, 1)
        main_layout.addLayout(top_row)

        # ===== Splitter: Left pig list, Right chart =====
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # --- Left: Pig List Card ---
        left_card = QFrame()
        left_card.setObjectName("CardFrame")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        left_header = QFrame()
        left_header.setObjectName("CardHeader")
        lh_layout = QHBoxLayout(left_header)
        lh_layout.setContentsMargins(12, 4, 12, 4)
        lbl_left_title = QLabel("猪只列表")
        lbl_left_title.setObjectName("CardTitle")
        lh_layout.addWidget(lbl_left_title)
        lh_layout.addStretch()
        self.lbl_pig_count = QLabel("共 0 头")
        self.lbl_pig_count.setObjectName("CardHint")
        lh_layout.addWidget(self.lbl_pig_count)
        left_layout.addWidget(left_header)

        self.pig_list = QListWidget()
        self.pig_list.setMinimumWidth(200)
        self.pig_list.currentRowChanged.connect(self._on_pig_selected)
        left_layout.addWidget(self.pig_list)
        splitter.addWidget(left_card)

        # --- Right: Chart Card ---
        right_card = QFrame()
        right_card.setObjectName("CardFrame")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_header = QFrame()
        right_header.setObjectName("CardHeader")
        rh_layout = QHBoxLayout(right_header)
        rh_layout.setContentsMargins(12, 4, 12, 4)
        lbl_right_title = QLabel("体重-日龄拟合曲线")
        lbl_right_title.setObjectName("CardTitle")
        rh_layout.addWidget(lbl_right_title)
        rh_layout.addStretch()
        self.lbl_chart_pig = QLabel("")
        self.lbl_chart_pig.setObjectName("CardHint")
        rh_layout.addWidget(self.lbl_chart_pig)
        right_layout.addWidget(right_header)

        chart_content = QWidget()
        chart_layout = QVBoxLayout(chart_content)
        chart_layout.setContentsMargins(10, 10, 10, 10)
        chart_layout.setSpacing(8)
        self.canvas = MplCanvas(self, width=8, height=5, dpi=100)
        chart_layout.addWidget(self.canvas, 1)

        self.info_label = QLabel("请选择 CSV 文件并开始计算")
        self.info_label.setObjectName("InfoLabel")
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.info_label.setWordWrap(True)
        chart_layout.addWidget(self.info_label)
        right_layout.addWidget(chart_content)

        splitter.addWidget(right_card)
        splitter.setSizes([260, 900])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, 1)

        # ===== Status Bar =====
        self.status_bar = QStatusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setTextVisible(True)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _on_stage_toggled(self, checked):
        if hasattr(self, "_current_pig_idx") and self._current_pig_idx is not None:
            self._on_pig_selected(self._current_pig_idx)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择CSV文件夹")
        if path:
            self.folder_edit.setText(path)
            if not self.dir_edit.text():
                self.dir_edit.setText(os.path.join(path, "fcr_results"))

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择CSV文件", "", "CSV文件 (*.csv);;所有文件 (*)")
        if path:
            self.file_edit.setText(path)
            if not self.dir_edit.text():
                default_dir = os.path.join(os.path.dirname(path), "fcr_results")
                self.dir_edit.setText(default_dir)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.dir_edit.setText(path)

    def _on_fit_toggled(self):
        if self._current_pig_idx is not None and self._current_pig_idx < len(self._results):
            result = self._results[self._current_pig_idx]
            if result.cleaned_data is not None:
                self.canvas.update_plot(result, show_fit=self.chk_fit.isChecked())

    def _on_pig_selected(self, idx):
        if idx < 0 or idx >= len(self._results):
            return
        self._current_pig_idx = idx
        result = self._results[idx]
        self.lbl_chart_pig.setText(result.lifenumber)
        if hasattr(self, "chk_stage") and self.chk_stage.isChecked() and getattr(result, "stage_fcr", None) is not None:
            self.canvas.fig.clear()
            ax = self.canvas.fig.add_subplot(111)
            ax.set_facecolor("#FAFBFC")
            plot_weight_curve_stage(result, None, self.spin_stage_lo.value(), self.spin_stage_hi.value(), show_fit=self.chk_fit.isChecked(), return_fig=False, ax=ax)
            self.canvas.draw()
        else:
            self.canvas.update_plot(result, show_fit=self.chk_fit.isChecked())
        info_lines = [
            f"<b style='color:#085041;'>{result.lifenumber}</b>",
            f"<span style='color:#5F5E5A;'>起止: {result.start_date} ~ {result.end_date}</span>",
            f"<span style='color:#5F5E5A;'>体重: {result.start_weight} -> {result.end_weight} kg</span>",
        ]
        metrics = []
        if result.adg:
            metrics.append(f"<span style='color:#0F6E56;font-weight:600;'>ADG: {result.adg:.4f} kg/d</span>")
        if result.r_squared is not None:
            metrics.append(f"<span style='color:#5F5E5A;'>R²: {result.r_squared:.4f}</span>")
        if result.fcr:
            metrics.append(f"<span style='color:#0F6E56;font-weight:600;font-size:14px;'>FCR: {result.fcr:.3f}</span>")
        if result.fill_info:
            metrics.append(f"<span style='color:#E24B4A;'>备注: {result.fill_info}</span>")
        self.info_label.setText("&nbsp;&nbsp;|&nbsp;&nbsp;".join(info_lines) + "<br>" + "&nbsp;&nbsp;|&nbsp;&nbsp;".join(metrics))
        self.status_bar.showMessage(f"选择: {result.lifenumber}", 5000)

    def _start_calc(self):
        filepath = self.file_edit.text().strip()
        folder_path = self.folder_edit.text().strip()
        if not filepath and not folder_path:
            QMessageBox.warning(self, "提示", "请选择CSV文件或文件夹")
            return
        if filepath and not os.path.exists(filepath) and not folder_path:
            QMessageBox.warning(self, "提示", "请选择有效的CSV文件")
            return
        output_dir = self.dir_edit.text().strip()
        if not output_dir:
            base = folder_path if folder_path else os.path.dirname(filepath)
            output_dir = os.path.join(base, "fcr_results")

        self._results = []
        self.pig_list.clear()
        self.lbl_pig_count.setText("共 0 头")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("计算中...")

        self._worker = Worker(filepath, folder_path, output_dir,
                              self.spin_min_age.value(), self.spin_max_age.value(),
                              self.spin_init_lo.value(), self.spin_init_hi.value(),
                              self.spin_stage_lo.value(), self.spin_stage_hi.value(),
                              self.chk_stage.isChecked())
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop_calc(self):
        if hasattr(self, "_worker") and self._worker.isRunning():
            self._worker.cancel()
            self._worker.quit()
            self.status_bar.showMessage("已停止")

    def _on_progress(self, current, total, lifenumber):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_bar.showMessage(f"正在处理 {current}/{total}: {lifenumber}")

    def _on_finished(self, results):
        self._results = results
        self.progress_bar.setVisible(False)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        self.pig_list.blockSignals(True)
        for r in results:
            flag = "⚠ " if r.is_abnormal == "异常样本" else ""
            self.pig_list.addItem(f"{flag}{r.lifenumber}    FCR:{r.fcr or '-'}")
        self.pig_list.blockSignals(False)
        self.lbl_pig_count.setText(f"共 {len(results)} 头")

        fcr_vals = [r.fcr for r in results if r.fcr is not None]
        avg_fcr = f"{np.mean(fcr_vals):.3f}" if fcr_vals else "N/A"
        self.status_bar.showMessage(
            f"完成! 共 {len(results)} 头猪 | FCR均值: {avg_fcr}")

        if results:
            self.pig_list.setCurrentRow(0)

    def _on_error(self, msg):
        self.progress_bar.setVisible(False)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.critical(self, "错误", f"计算失败:\n{msg}")
        self.status_bar.showMessage("计算失败")

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_QSS)

    # 设置默认字体
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)

    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
