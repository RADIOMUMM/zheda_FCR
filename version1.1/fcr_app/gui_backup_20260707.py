"""
FCR计算工具 GUI主窗口
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
# Matplotlib Canvas Embed
# ============================================================
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=8, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

    def update_plot(self, result, show_fit=True):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        df = result.cleaned_data
        if df is None or len(df) == 0:
            ax.text(0.5, 0.5, "无数据", ha="center", va="center", fontsize=14, transform=ax.transAxes)
            self.draw()
            return
        import numpy as np, matplotlib.dates as mdates
        valid = df[~df["is_abnormal"] & df["qc_weight_kg"].notna()]
        if len(valid) > 0:
            ax.scatter(valid["visit_time"], valid["qc_weight_kg"], c="#3498db", s=25, alpha=0.7, zorder=3)
        abnormal = df[df["is_abnormal"] & df["weight_kg"].notna()]
        if len(abnormal) > 0:
            ax.scatter(abnormal["visit_time"], abnormal["weight_kg"], c="#e74c3c", s=15, alpha=0.4, marker="x", zorder=2)
        if show_fit and result.adg is not None and len(valid) >= 3:
            x_min = valid["visit_time"].min()
            x_days = (valid["visit_time"] - x_min).dt.days.values.astype(float)
            y_vals = valid["qc_weight_kg"].values
            A = np.vstack([x_days, np.ones(len(x_days))]).T
            m, c = np.linalg.lstsq(A, y_vals, rcond=None)[0]
            x_fit = np.linspace(0, x_days.max(), 100)
            y_fit = m * x_fit + c
            fit_dates = [x_min + pd.Timedelta(days=int(d)) for d in x_fit]
            ax.plot(fit_dates, y_fit, "-", color="#e74c3c", linewidth=2, zorder=4)
        info = f"{result.lifenumber}  FCR:{result.fcr or '-'}  ADG:{result.adg or '-'}"
        ax.set_title(info, fontsize=12)
        ax.set_xlabel("日期"); ax.set_ylabel("体重 (kg)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        self.fig.autofmt_xdate()
        ax.grid(True, alpha=0.3)
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
# Main Window
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FCR 批量计算工具 v1.0")
        self.setMinimumSize(1200, 750)
        self._results = []
        self._current_pig_idx = None
        self._last_output_dir = None
        self._init_ui()

    def _init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Toolbar
        tb1 = QHBoxLayout()
        self.file_edit = QLineEdit(); self.file_edit.setPlaceholderText("选择单个CSV文件...")
        self.btn_browse = QPushButton("浏览文件")
        self.btn_browse.clicked.connect(self._browse_file)
        tb1.addWidget(QLabel("输入文件:")); tb1.addWidget(self.file_edit); tb1.addWidget(self.btn_browse)
        main_layout.addLayout(tb1)
        tb2 = QHBoxLayout()
        self.folder_edit = QLineEdit(); self.folder_edit.setPlaceholderText("选择包含CSV的文件夹...")
        self.btn_folder = QPushButton("浏览文件夹")
        self.btn_folder.clicked.connect(self._browse_folder)
        tb2.addWidget(QLabel("批量输入:")); tb2.addWidget(self.folder_edit); tb2.addWidget(self.btn_folder)
        main_layout.addLayout(tb2)
        # 输入文件与批量输入互斥
        self.file_edit.textChanged.connect(lambda t: self.folder_edit.clear() if t else None)
        self.folder_edit.textChanged.connect(lambda t: self.file_edit.clear() if t else None)
        tb3 = QHBoxLayout()
        self.dir_edit = QLineEdit(); self.dir_edit.setPlaceholderText("输出目录（默认自动生成）...")
        self.btn_dir = QPushButton("浏览目录")
        self.btn_dir.clicked.connect(self._browse_dir)
        tb3.addWidget(QLabel("输出到:")); tb3.addWidget(self.dir_edit); tb3.addWidget(self.btn_dir)
        main_layout.addLayout(tb3)

        # Params
        pb = QHBoxLayout()
        pb.addWidget(QLabel("最小日龄:")); self.spin_min_age = QSpinBox(); self.spin_min_age.setRange(30, 365); self.spin_min_age.setValue(100)
        pb.addWidget(self.spin_min_age)
        pb.addWidget(QLabel("最大日龄:")); self.spin_max_age = QSpinBox(); self.spin_max_age.setRange(30, 365); self.spin_max_age.setValue(200)
        pb.addWidget(self.spin_max_age)
        pb.addWidget(QLabel("初测体重:")); self.spin_init_lo = QDoubleSpinBox(); self.spin_init_lo.setRange(10, 60); self.spin_init_lo.setValue(25); self.spin_init_lo.setSuffix("-"); self.spin_init_lo.setDecimals(0)
        pb.addWidget(self.spin_init_lo)
        self.spin_init_hi = QDoubleSpinBox(); self.spin_init_hi.setRange(20, 100); self.spin_init_hi.setValue(45); self.spin_init_hi.setSuffix(" kg"); self.spin_init_hi.setDecimals(0)
        pb.addWidget(self.spin_init_hi)
        self.chk_stage = QCheckBox("计算阶段料肉比"); self.chk_stage.setChecked(False)
        self.chk_stage.toggled.connect(self._on_stage_toggled)
        pb.addWidget(self.chk_stage)
        self.spin_stage_lo = QDoubleSpinBox(); self.spin_stage_lo.setRange(10, 200); self.spin_stage_lo.setValue(30); self.spin_stage_lo.setSuffix("-"); self.spin_stage_lo.setDecimals(0)
        self.spin_stage_hi = QDoubleSpinBox(); self.spin_stage_hi.setRange(10, 200); self.spin_stage_hi.setValue(75); self.spin_stage_hi.setSuffix(" kg"); self.spin_stage_hi.setDecimals(0)
        pb.addWidget(self.spin_stage_lo)
        pb.addWidget(self.spin_stage_hi)
        self.chk_fit = QCheckBox("显示拟合曲线"); self.chk_fit.setChecked(True)
        self.chk_fit.toggled.connect(self._on_fit_toggled)
        pb.addWidget(self.chk_fit)
        pb.addStretch()
        self.btn_start = QPushButton("开始计算"); self.btn_start.clicked.connect(self._start_calc)
        self.btn_start.setStyleSheet("background:#3498db; color:white; font-weight:bold; padding:6px 20px;")
        pb.addWidget(self.btn_start)
        self.btn_stop = QPushButton("停止"); self.btn_stop.setEnabled(False); self.btn_stop.clicked.connect(self._stop_calc)
        pb.addWidget(self.btn_stop)
        main_layout.addLayout(pb)

        # Splitter: left pig list, right chart
        splitter = QSplitter(Qt.Horizontal)
        self.pig_list = QListWidget()
        self.pig_list.setMinimumWidth(200)
        self.pig_list.currentRowChanged.connect(self._on_pig_selected)
        splitter.addWidget(self.pig_list)

        right_panel = QWidget()
        rl = QVBoxLayout(right_panel)
        self.canvas = MplCanvas(self, width=8, height=5, dpi=100)
        rl.addWidget(self.canvas)
        self.info_label = QLabel("请选择 CSV 文件并开始计算")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("font-size:13px; color:#666;")
        rl.addWidget(self.info_label)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 850])
        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.setStatusBar(self.status_bar)

    def _on_stage_toggled(self, checked):
        if hasattr(self, "_current_pig_idx") and self._current_pig_idx is not None:
            self._on_pig_selected(self._current_pig_idx)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, chr(34) + chr(36873)+chr(25321)+chr(67)+chr(83)+chr(86)+chr(25991)+chr(20214)+chr(22841) + chr(34))
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
        if hasattr(self, "chk_stage") and self.chk_stage.isChecked():
            self.canvas.fig.clear()
            ax = self.canvas.fig.add_subplot(111)
            plot_weight_curve_stage(result, None, self.spin_stage_lo.value(), self.spin_stage_hi.value(), show_fit=self.chk_fit.isChecked(), return_fig=False, ax=ax)
            self.canvas.draw()
        else:
            self.canvas.update_plot(result, show_fit=self.chk_fit.isChecked())
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
        self.info_label.setText("  |  ".join(info_lines))
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
            flag = "⚠" if r.is_abnormal == "异常样本" else ""
            self.pig_list.addItem(f"{flag} {r.lifenumber}  FCR:{r.fcr or '-'}")
        self.pig_list.blockSignals(False)

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
    w = MainWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
