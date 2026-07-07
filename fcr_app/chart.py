"""
图表绘制模块 - 体重-日龄拟合曲线图
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
import os

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "PingFang SC", "WenQuanYi Micro Hei"]
plt.rcParams["axes.unicode_minus"] = False

def plot_weight_curve(result, output_path: str, show_fit: bool = True) -> str:
    """绘制体重-日龄拟合曲线图
    
    参数:
        result: PigResult对象
        output_path: PNG输出路径
        show_fit: 是否显示拟合线
    返回:
        图片路径
    """
    df = result.cleaned_data
    if df is None or len(df) == 0:
        return None
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    # 有效体重散点（通过质控）
    valid = df[~df.get("is_abnormal", False) & df.get("qc_weight_kg").notna()]
    if len(valid) > 0:
        ax.scatter(valid["visit_time"], valid["qc_weight_kg"],
                   c="#3498db", s=30, alpha=0.7, zorder=3, label="有效体重")

    # 异常体重散点（未通过质控）
    abnormal = df[df.get("is_abnormal", False) & df["weight_kg"].notna()]
    if len(abnormal) > 0:
        ax.scatter(abnormal["visit_time"], abnormal["weight_kg"],
                   c="#e74c3c", s=20, alpha=0.4, marker="x", zorder=2, label="异常体重")

    # 拟合线
    if show_fit and result.adg is not None and len(valid) >= 3:
        x_min = valid["visit_time"].min()
        x_days = (valid["visit_time"] - x_min).dt.days
        x_fit = np.linspace(0, x_days.max(), 100)
        start_wt = valid["weight_kg"].iloc[0] if len(valid) > 0 else 0
        # Re-fit properly
        x_vals = x_days.values.astype(float)
        y_vals = valid["qc_weight_kg"].values
        A = np.vstack([x_vals, np.ones(len(x_vals))]).T
        m, c = np.linalg.lstsq(A, y_vals, rcond=None)[0]
        y_fit = m * x_fit + c
        fit_dates = [x_min + pd.Timedelta(days=int(d)) for d in x_fit]
        ax.plot(fit_dates, y_fit, "-", color="#e74c3c", linewidth=2,
                zorder=4, label=f"ADG={result.adg:.4f} kg/d")

    # 标注信息
    info_text = (
        f"批次号: {result.lifenumber}\n"
        f"起止: {result.start_date} ~ {result.end_date}\n"
        f"起始体重: {result.start_weight} kg → 终止: {result.end_weight} kg\n"
    )
    if result.adg is not None:
        info_text += f"ADG: {result.adg:.4f} kg/d  R²: {result.r_squared:.4f}\n"
    if result.fcr is not None:
        info_text += f"FCR(料重比): {result.fcr:.3f}"
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
            fontsize=11, verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.85))

    # 轴标签和格式
    ax.set_xlabel("日期", fontsize=12)
    ax.set_ylabel("体重 (kg)", fontsize=12)
    ax.set_title(f"体重-日龄拟合曲线 — {result.lifenumber}", fontsize=14, fontweight="bold")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    fig.autofmt_xdate()
    ax.legend(loc="lower right", fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path

def plot_preview(result, show_fit: bool = True) -> matplotlib.figure.Figure:
    """返回matplotlib Figure用于GUI预览"""
    df = result.cleaned_data
    if df is None or len(df) == 0:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "无数据", ha="center", va="center", fontsize=14)
        return fig

    fig, ax = plt.subplots(figsize=(8, 5))

    valid = df[~df.get("is_abnormal", False) & df.get("qc_weight_kg").notna()]
    if len(valid) > 0:
        ax.scatter(valid["visit_time"], valid["qc_weight_kg"],
                   c="#3498db", s=25, alpha=0.7, zorder=3)

    abnormal = df[df.get("is_abnormal", False) & df["weight_kg"].notna()]
    if len(abnormal) > 0:
        ax.scatter(abnormal["visit_time"], abnormal["weight_kg"],
                   c="#e74c3c", s=15, alpha=0.4, marker="x", zorder=2)

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
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig
