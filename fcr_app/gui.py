"""
FCR计算工具 GUI主窗口
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
# 自定义日志处理器
# ============================================================
class QLogHandler(logging.Handler):
    def __init__(self, widget: QPlainTextEdit):
        super().__init__()
        self.widget = widget
        self.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)


# ============================================================
# 图片显示控件（加载已保存的 PNG，自动缩放适应）
# ============================================================
class ImageLabel(QLabel):
    """显示PNG图片，自动缩放保持宽高比"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd;")
        self.setText("请选择 CSV 文件并开始计算")

    def set_image(self, path):
        """加载图片并显示"""
        if path and os.path.exists(path):
            self._pixmap = QPixmap(path)
        else:
            self._pixmap = None
        self._update_display()

    def _update_display(self):
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            super().setPixmap(scaled)
        else:
            self.setText("无图片数据")

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

                # 导出清洗数据
                clean_path = os.path.join(self.output_dir, f"01.{lifenumber}_清洗后数据.xlsx")
                export_cleaned_excel(result, clean_path)

                # 导出主图片（不传递阶段参数，全量绘制）
                img_path = os.path.join(img_dir, f"{lifenumber}.png")
                plot_weight_curve(result, img_path, show_fit=True,
                                  stage_lower=None, stage_upper=None)
                setattr(result, "_full_chart_path", img_path)

                # 导出阶段图片（传递阶段参数，阶段高亮）
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

            # 导出汇总表
            summary_path = os.path.join(self.output_dir, "02.样本肉料比信息表.xlsx")
            export_summary_excel(results, summary_path)

            # 导出阶段汇总表
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
        self._dir_auto_filled = False  # 输出目录是否为自动填充
        self._init_ui()

    def _init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ==================== 工具栏 ====================
        tb = QHBoxLayout()
        self.file_edit = QLineEdit(); self.file_edit.setPlaceholderText("选择CSV文件...")
        self.btn_browse = QPushButton("浏览文件")
        self.btn_browse.clicked.connect(self._browse_file)
        self.dir_edit = QLineEdit(); self.dir_edit.setPlaceholderText("输出目录（默认自动生成）...")
        self.btn_dir = QPushButton("浏览目录")
        self.btn_dir.clicked.connect(self._browse_dir)
        for w in [QLabel("输入文件:"), self.file_edit, self.btn_browse,
                  QLabel("输出到:"), self.dir_edit, self.btn_dir]:
            tb.addWidget(w)
        main_layout.addLayout(tb)

        # ==================== 批量输入 + 参数 ====================
        params_widget = QWidget()
        params_layout = QVBoxLayout(params_widget)
        params_layout.setContentsMargins(0, 2, 0, 2)

        # 批量输入行
        batch_row = QHBoxLayout()
        self.folder_edit = QLineEdit(); self.folder_edit.setPlaceholderText("选择包含CSV的文件夹（批量输入）...")
        self.btn_browse_folder = QPushButton("浏览文件夹")
        self.btn_browse_folder.clicked.connect(self._browse_folder)
        batch_row.addWidget(QLabel("批量输入:"))
        batch_row.addWidget(self.folder_edit)
        batch_row.addWidget(self.btn_browse_folder)
        params_layout.addLayout(batch_row)

        # 参数行
        param_row = QHBoxLayout()
        param_row.addWidget(QLabel("初测体重:"))
        self.spin_init_lo = QDoubleSpinBox(); self.spin_init_lo.setRange(10, 60); self.spin_init_lo.setValue(25); self.spin_init_lo.setDecimals(0)
        param_row.addWidget(self.spin_init_lo)
        param_row.addWidget(QLabel("-"))
        self.spin_init_hi = QDoubleSpinBox(); self.spin_init_hi.setRange(20, 100); self.spin_init_hi.setValue(45); self.spin_init_hi.setSuffix(" kg"); self.spin_init_hi.setDecimals(0)
        param_row.addWidget(self.spin_init_hi)
        param_row.addWidget(QLabel("终测体重:"))
        self.spin_end_lo = QDoubleSpinBox(); self.spin_end_lo.setRange(30, 130); self.spin_end_lo.setValue(90); self.spin_end_lo.setDecimals(0)
        param_row.addWidget(self.spin_end_lo)
        param_row.addWidget(QLabel("-"))
        self.spin_end_hi = QDoubleSpinBox(); self.spin_end_hi.setRange(60, 150); self.spin_end_hi.setValue(110); self.spin_end_hi.setSuffix(" kg"); self.spin_end_hi.setDecimals(0)
        param_row.addWidget(self.spin_end_hi)
        param_row.addStretch()
        params_layout.addLayout(param_row)

        # 操作行
        action_row = QHBoxLayout()
        self.chk_enable_stage = QCheckBox("阶段料肉比计算")
        self.chk_enable_stage.toggled.connect(self._on_stage_toggled)
        action_row.addWidget(self.chk_enable_stage)
        action_row.addWidget(QLabel("区间:"))
        self.spin_stage_lo = QDoubleSpinBox(); self.spin_stage_lo.setRange(10, 100); self.spin_stage_lo.setValue(STAGE_WEIGHT_LOWER); self.spin_stage_lo.setSuffix(" kg")
        action_row.addWidget(self.spin_stage_lo)
        action_row.addWidget(QLabel("-"))
        self.spin_stage_hi = QDoubleSpinBox(); self.spin_stage_hi.setRange(20, 150); self.spin_stage_hi.setValue(STAGE_WEIGHT_UPPER); self.spin_stage_hi.setSuffix(" kg")
        action_row.addWidget(self.spin_stage_hi)
        action_row.addStretch()
        self.chk_fit = QCheckBox("显示拟合曲线"); self.chk_fit.setChecked(True)
        self.chk_fit.toggled.connect(self._on_fit_toggled)
        action_row.addWidget(self.chk_fit)
        self.btn_start = QPushButton("开始计算")
        self.btn_start.clicked.connect(self._start_calc)
        self.btn_start.setStyleSheet("background:#3498db; color:white; font-weight:bold; padding:6px 20px;")
        action_row.addWidget(self.btn_start)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_calc)
        action_row.addWidget(self.btn_stop)
        params_layout.addLayout(action_row)
        main_layout.addWidget(params_widget)

        # ==================== 合并进度条 ====================
        self.merge_progress_bar = QProgressBar()
        self.merge_progress_bar.setRange(0, 100)
        self.merge_progress_bar.setVisible(False)
        self.merge_progress_bar.setFormat("合并文件: %v/%m")
        main_layout.addWidget(self.merge_progress_bar)

        # ==================== Splitter: 左列表(单选) + 右图表 ====================
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)            # 加宽拖动手柄，便于鼠标抓取
        splitter.setChildrenCollapsible(False)  # 防止某侧被完全折叠
        # 左侧：单行选择列表（非复选框）
        self.pig_tree = QTreeWidget()
        self.pig_tree.setMinimumWidth(280)
        self.pig_tree.setHeaderHidden(True)
        self.pig_tree.currentItemChanged.connect(self._on_pig_selected)
        splitter.addWidget(self.pig_tree)

        right_panel = QWidget()
        rl = QVBoxLayout(right_panel)
        self.img_label = ImageLabel(self)
        rl.addWidget(self.img_label)
        # 提示信息
        hint_label = QLabel("💡 图片自动缩放适应窗口")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setStyleSheet("color:#999; font-size:11px;")
        rl.addWidget(hint_label)
        self.info_label = QLabel("请选择 CSV 文件并开始计算")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size:13px; color:#666;")
        rl.addWidget(self.info_label)
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 820])
        main_layout.addWidget(splitter, stretch=3)

        # ==================== 日志面板 ====================
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(500)
        self.log_text.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group, stretch=1)

        log_handler = QLogHandler(self.log_text)
        logging.getLogger("FCRCore").addHandler(log_handler)
        logging.getLogger("FCRApp").addHandler(log_handler)

        # ==================== 状态栏 ====================
        self.status_bar = QStatusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.setStatusBar(self.status_bar)

        self._on_stage_toggled(False)
        logger.info("界面初始化完成")

    # ---------- UI 事件 ----------

    def _auto_fill_dir(self, base_path):
        """自动填充输出目录"""
        ts = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        self.dir_edit.setText(os.path.join(base_path, f"{ts}_fcr_results"))
        self._dir_auto_filled = True

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择CSV文件", "", "CSV文件 (*.csv);;所有文件 (*)")
        if path:
            self.file_edit.setText(path)
            self.folder_edit.clear()
            # 输出目录跟随输入自动填充（除非用户已手动指定）
            if not self.dir_edit.text() or self._dir_auto_filled:
                self._auto_fill_dir(os.path.dirname(path))

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "选择包含CSV的文件夹")
        if path:
            self.folder_edit.setText(path)
            self.file_edit.clear()
            # 输出目录跟随批量输入自动填充（除非用户已手动指定）
            if not self.dir_edit.text() or self._dir_auto_filled:
                self._auto_fill_dir(path)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.dir_edit.setText(path)
            self._dir_auto_filled = False  # 用户手动指定，停止自动跟随

    def _on_stage_toggled(self, checked):
        self.spin_stage_lo.setEnabled(checked)
        self.spin_stage_hi.setEnabled(checked)
        logger.info("阶段料肉比计算已启用" if checked else "阶段料肉比计算已关闭")
        # 切换后刷新当前预览
        if self._current_pig_idx is not None and self._current_pig_idx < len(self._results):
            self._update_preview(self._results[self._current_pig_idx])

    def _on_fit_toggled(self):
        # 图片模式下拟合曲线已固化在PNG中，勾选不影响显示
        # 仅刷新预览（重载当前图片）
        if self._current_pig_idx is not None and self._current_pig_idx < len(self._results):
            self._update_preview(self._results[self._current_pig_idx])

    def _on_pig_selected(self, current, previous):
        """单击树节点 → 预览对应猪只曲线"""
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
        """更新预览区 — 从03.结果图片中加载对应PNG"""
        enable_stage = self.chk_enable_stage.isChecked()

        # 决定显示全期图片还是阶段图片
        if enable_stage and hasattr(result, 'stage_chart_path') and result.stage_chart_path and os.path.exists(result.stage_chart_path):
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
                f"ADG: {result.stage_adg:.4f}")

        self.info_label.setText("  |  ".join(info_lines))

    # ---------- 计算流程 ----------

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
        logger.info(f"开始计算: 输入={'文件夹' if folder_path else '单文件'}, "
                    f"输出={output_dir}, 阶段={enable_stage}")

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
        self.merge_progress_bar.setFormat(f"合并文件: {current}/{total} - {filename}")
        self.status_bar.showMessage(f"正在合并: {current}/{total} - {filename}")

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

        # 构建树形结构：来源文件名 → 个体列表
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
                flag = "⚠ " if r.is_abnormal == "异常样本" else ""
                pig_item = QTreeWidgetItem(file_item,
                    [f"{flag}{r.lifenumber}  FCR:{r.fcr or '-'}"])
                pig_item.setData(0, Qt.UserRole, idx)
            file_item.setExpanded(True)

        self.pig_tree.blockSignals(False)

        fcr_vals = [r.fcr for r in results if r.fcr is not None]
        avg_fcr = f"{np.mean(fcr_vals):.3f}" if fcr_vals else "N/A"
        msg = f"完成! 共 {len(results)} 头猪 | FCR均值: {avg_fcr}"
        self.status_bar.showMessage(msg)
        logger.info(msg)

        if results:
            first_pig = self.pig_tree.topLevelItem(0).child(0) if self.pig_tree.topLevelItemCount() > 0 and self.pig_tree.topLevelItem(0).childCount() > 0 else None
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
    # 全局异常捕获，防止闪退
    def excepthook(exc_type, exc_value, exc_tb):
        import traceback
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical(f"未捕获的异常:\n{msg}")
        QMessageBox.critical(None, "程序错误", f"发生未预期的错误，请查看日志:\n{exc_value}")
    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow(); w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
