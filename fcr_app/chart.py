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
from typing import Optional, Tuple

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "PingFang SC", "WenQuanYi Micro Hei"]
plt.rcParams["axes.unicode_minus"] = False


def _aggregate_daily(valid: pd.DataFrame) -> pd.DataFrame:
    """对同一日期的多个体重记录取均值（仅用于回归线计算，不用于散点）"""
    if "date" not in valid.columns:
        valid = valid.copy()
        valid["date"] = valid["visit_time"].dt.date
    daily = valid.groupby("date", as_index=False).agg({
        "visit_time": "first",
        "qc_weight_kg": "mean",
        "weight_kg": "mean",
    })
    daily = daily.sort_values("visit_time")
    return daily


def _split_by_stage(valid_df: pd.DataFrame,
                    stage_lower: Optional[float],
                    stage_upper: Optional[float]) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """将有效数据分为阶段内（高亮）和阶段外（灰色）两组"""
    if stage_lower is None or stage_upper is None:
        return valid_df, None
    in_stage = valid_df[
        (valid_df["qc_weight_kg"] >= stage_lower) &
        (valid_df["qc_weight_kg"] <= stage_upper)
    ]
    out_stage = valid_df[
        (valid_df["qc_weight_kg"] < stage_lower) |
        (valid_df["qc_weight_kg"] > stage_upper)
    ]
    return in_stage, out_stage if len(out_stage) > 0 else None


def _get_adg_line(valid: pd.DataFrame, n_points: int = 300):
    """计算ADG回归线的 X/Y 值（使用每日均值，防止密集日主导回归）"""
    daily = _aggregate_daily(valid)
    x_min = daily["visit_time"].min()
    x_days = (daily["visit_time"] - x_min).dt.days.values.astype(float)
    y_vals = daily["qc_weight_kg"].values
    A = np.vstack([x_days, np.ones(len(x_days))]).T
    m, c = np.linalg.lstsq(A, y_vals, rcond=None)[0]
    x_fit = np.linspace(0, x_days.max(), n_points)
    y_fit = m * x_fit + c
    fit_dates = [x_min + pd.Timedelta(days=d) for d in x_fit]
    return fit_dates, y_fit, m, c


def plot_weight_curve(result, output_path: str, show_fit: bool = True,
                      stage_label: str = "",
                      stage_lower: Optional[float] = None,
                      stage_upper: Optional[float] = None) -> str:
    """绘制体重-日龄拟合曲线图"""
    df = result.cleaned_data
    if df is None or len(df) == 0:
        return None
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5))

    valid = df[~df.get("is_abnormal", False) & df.get("qc_weight_kg").notna()]

    # ---- 有效体重散点（展示全部通过质控的个体记录）----
    if len(valid) > 0:
        in_stage, out_stage = _split_by_stage(valid, stage_lower, stage_upper)

        # 阶段外：灰色（展示全部点，不聚合）
        if out_stage is not None and len(out_stage) > 0:
            ax.scatter(out_stage["visit_time"], out_stage["qc_weight_kg"],
                       c="#cccccc", s=15, alpha=0.5, zorder=2, label="阶段外体重")

        # 阶段内：蓝色高亮
        if in_stage is not None and len(in_stage) > 0:
            ax.scatter(in_stage["visit_time"], in_stage["qc_weight_kg"],
                       c="#3498db", s=25, alpha=0.7, zorder=3, label="阶段内有效体重")
        else:
            # 未启用阶段：全部蓝色
            ax.scatter(valid["visit_time"], valid["qc_weight_kg"],
                       c="#3498db", s=20, alpha=0.6, zorder=3, label="有效体重")

    # ---- 异常体重散点（红叉，展示全部）----
    abnormal = df[df.get("is_abnormal", False) & df["weight_kg"].notna()]
    if len(abnormal) > 0:
        ax.scatter(abnormal["visit_time"], abnormal["weight_kg"],
                   c="#e74c3c", s=20, alpha=0.4, marker="x", zorder=4, label="异常体重")

    # ---- 拟合线（使用每日均值回归，确保客观）----
    if show_fit and result.adg is not None and len(valid) >= 3:
        fit_dates, y_fit, slope, _ = _get_adg_line(valid, n_points=300)
        ax.plot(fit_dates, y_fit, "-", color="#e74c3c", linewidth=2,
                zorder=5, label=f"ADG={result.adg:.4f} kg/d",
                antialiased=True, solid_capstyle="round")

    # ---- 标注信息 ----
    info_lines = [
        f"批次号: {result.lifenumber}",
        f"起止: {result.start_date} ~ {result.end_date}",
        f"体重: {result.start_weight} kg → {result.end_weight} kg",
        f"有效点数: {len(valid)}",
    ]
    if result.adg is not None and result.r_squared is not None:
        info_lines.append(f"ADG: {result.adg:.4f} kg/d  R^2: {result.r_squared:.4f}")
    if result.fcr is not None:
        info_lines.append(f"FCR(料重比): {result.fcr:.3f}")
    if stage_label and result.stage_fcr is not None:
        info_lines.append(f"阶段FCR: {result.stage_fcr:.3f}")
    info_text = "\n".join(info_lines)

    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
            fontsize=11, verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.85))

    # ---- 轴格式 ----
    ax.set_xlabel("日期", fontsize=12)
    ax.set_ylabel("体重 (kg)", fontsize=12)
    title = f"体重-日龄拟合曲线 — {result.lifenumber}"
    if stage_label:
        title += f" {stage_label}"
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    fig.autofmt_xdate()
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_preview(result, show_fit: bool = True,
                 stage_lower: Optional[float] = None,
                 stage_upper: Optional[float] = None) -> matplotlib.figure.Figure:
    """返回matplotlib Figure用于GUI预览"""
    df = result.cleaned_data
    if df is None or len(df) == 0:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "无数据", ha="center", va="center", fontsize=14)
        return fig

    fig, ax = plt.subplots(figsize=(8, 5))

    valid = df[~df.get("is_abnormal", False) & df.get("qc_weight_kg").notna()]
    if len(valid) > 0:
        in_stage, out_stage = _split_by_stage(valid, stage_lower, stage_upper)
        if out_stage is not None and len(out_stage) > 0:
            ax.scatter(out_stage["visit_time"], out_stage["qc_weight_kg"],
                       c="#cccccc", s=12, alpha=0.4, zorder=2)
        if in_stage is not None and len(in_stage) > 0:
            ax.scatter(in_stage["visit_time"], in_stage["qc_weight_kg"],
                       c="#3498db", s=22, alpha=0.7, zorder=3)
        else:
            ax.scatter(valid["visit_time"], valid["qc_weight_kg"],
                       c="#3498db", s=18, alpha=0.6, zorder=3)

    abnormal = df[df.get("is_abnormal", False) & df["weight_kg"].notna()]
    if len(abnormal) > 0:
        ax.scatter(abnormal["visit_time"], abnormal["weight_kg"],
                   c="#e74c3c", s=15, alpha=0.4, marker="x", zorder=4)

    if show_fit and result.adg is not None and len(valid) >= 3:
        fit_dates, y_fit, _, _ = _get_adg_line(valid, n_points=300)
        ax.plot(fit_dates, y_fit, "-", color="#e74c3c", linewidth=2,
                zorder=5, antialiased=True, solid_capstyle="round")

    info = f"{result.lifenumber}  FCR:{result.fcr or '-'}  ADG:{result.adg or '-'}"
    ax.set_title(info, fontsize=12)
    ax.set_xlabel("日期"); ax.set_ylabel("体重 (kg)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig
