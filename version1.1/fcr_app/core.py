"""
FCR Calculator Core Module
============================================
基于浙大博士论文(2025)方法的FCR计算引擎
包含: CSV加载、16错误类型过滤(基于可用数据)、5步体重质控、ADG/ADFI/FCR计算、Excel导出
"""
import pandas as pd
import numpy as np
import glob, os
from datetime import datetime, date
import os, warnings, logging
from dataclasses import dataclass
from typing import Optional, List, Tuple, Callable

warnings.filterwarnings("ignore")
logger = logging.getLogger("FCRCore")

@dataclass
class PigResult:
    lifenumber: str
    start_date: Optional[date] = None
    start_weight: Optional[float] = None
    end_date: Optional[date] = None
    end_weight: Optional[float] = None
    total_feed: Optional[float] = None
    fcr: Optional[float] = None
    fcr_raw: Optional[float] = None
    adg: Optional[float] = None
    adfi: Optional[float] = None
    r_squared: Optional[float] = None
    fill_info: str = ""
    is_abnormal: str = "否"
    cleaned_data: Optional[pd.DataFrame] = None
    chart_path: Optional[str] = None
    # 阶段料肉比字段（仅在勾选"计算阶段料肉比"时填充）
    stage_fcr: Optional[float] = None
    stage_adg: Optional[float] = None
    stage_data: Optional[dict] = None

# ============================================================
# 数据加载
# ============================================================

# ============================================================
# Folder Input: 批量导入文件夹内所有CSV
# ============================================================
def load_csv_folder(folder_path: str) -> pd.DataFrame:
    """扫描文件夹内所有CSV文件，合并为统一DataFrame"""
    csv_files = glob.glob(os.path.join(folder_path, "*.csv")) + glob.glob(os.path.join(folder_path, "*.CSV"))
    if not csv_files:
        raise FileNotFoundError(f"文件夹中未找到CSV文件: {folder_path}")
    dfs = []
    for f in csv_files:
        try:
            dfs.append(load_csv(f))
        except Exception as e:
            logger.warning(f"跳过文件 {os.path.basename(f)}: {e}")
    if not dfs:
        raise ValueError("所有CSV文件均解析失败")
    result = pd.concat(dfs, ignore_index=True)
    return result

# ============================================================
# Stage FCR: 基于已质控数据计算阶段料肉比
# ============================================================
def calc_stage_fcr(result, stage_start: float = 30.0, stage_end: float = 75.0) -> dict:
    """从已质控结果中提取阶段体重范围内的数据，计算阶段FCR"""
    df = result.cleaned_data
    if df is None or len(df) == 0:
        return {"fcr": None, "adg": None, "adfi": None, "r2": None, "rows": 0,
                "total_feed": 0, "fcr_raw": None}
    valid = df[~df["is_abnormal"] & df["qc_weight_kg"].notna()].copy()
    stage = valid[(valid["qc_weight_kg"] >= stage_start) & (valid["qc_weight_kg"] <= stage_end)].copy()
    if len(stage) < 3:
        return {"fcr": None, "adg": None, "adfi": None, "r2": None, "rows": len(stage),
                "total_feed": 0, "fcr_raw": None}
    x = (stage["visit_time"] - stage["visit_time"].min()).dt.days.values.astype(float)
    y = stage["qc_weight_kg"].values
    if np.std(x) < 1e-6:
        return {"fcr": None, "adg": None, "adfi": None, "r2": None, "rows": len(stage),
                "total_feed": 0, "fcr_raw": None}
    A = np.vstack([x, np.ones(len(x))]).T
    m, c = np.linalg.lstsq(A, y, rcond=None)[0]
    y_pred = m * x + c
    ss_res = np.sum((y - y_pred)**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    feed_valid = df[~df["is_abnormal"] & df["qc_feed_kg"].notna() & 
                    (df["qc_weight_kg"] >= stage_start) & (df["qc_weight_kg"] <= stage_end)]
    total_feed = feed_valid["qc_feed_kg"].sum()
    stage_days = max((stage["visit_time"].max() - stage["visit_time"].min()).days, 1)
    adfi = total_feed / stage_days
    fcr = round(adfi / m, 3) if m > 0 else None
    fcr_raw = round(total_feed / (m * stage_days), 3) if m > 0 and stage_days > 0 else None
    return {
        "fcr": round(fcr, 3) if fcr else None,
        "adg": round(m, 4), "adfi": round(adfi, 4), "r2": round(r2, 4),
        "rows": len(stage),
        "start_date": stage["visit_time"].min().date(),
        "end_date": stage["visit_time"].max().date(),
        "start_weight": round(stage["qc_weight_kg"].iloc[0], 1),
        "end_weight": round(stage["qc_weight_kg"].iloc[-1], 1),
        "total_feed": round(total_feed, 3),
        "fcr_raw": round(fcr_raw, 3) if fcr_raw else None,
    }

def load_csv(filepath: str) -> pd.DataFrame:
    """加载CSV文件"""
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    required = ["animal_number","lifenumber","responder","location",
                "visit_time","duration","state","weight","feed_intake"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"缺少必需列: {missing}")
    df["visit_time"] = pd.to_datetime(df["visit_time"])
    df["weight_kg"] = df["weight"].astype(float) / 1000.0
    df["feed_kg"] = df["feed_intake"].astype(float) / 1000.0
    df["date"] = df["visit_time"].dt.date
    df = df.dropna(subset=["lifenumber"])
    return df

# ============================================================
# Step 1: 个体预过滤
# ============================================================
def filter_individual(df: pd.DataFrame, min_age_days: int = 100, max_age_days: int = 200) -> Tuple[pd.DataFrame, List[str]]:
    """
    个体层面预过滤：
    - 初测体重控制在 25±5 kg（20~30 kg），超出则标记为异常
    - 单次异常体重(>180kg或<25kg)记录标记，不删除（保留采食数据用于ADFI）
    - 生成数据完整性备注
    """
    info = []
    if len(df) < 2:
        return df, ["数据不足"]

    days = (df["visit_time"].max() - df["visit_time"].min()).days
    if days < 30:
        info.append("测定日期不足30天")
    if days < 60:
        info.append("测定日期不足60天")

    # 不再物理删除记录，改为在后续 filter_bw_5step 中标记 is_abnormal
    # 保留所有采食数据，确保 ADFI 计算的正确性
    return df, info

# ============================================================
# Step 2: 采食数据过滤（基于可用数据列）
# ============================================================
def filter_feed_errors(df: pd.DataFrame) -> pd.DataFrame:
    """
    根据可用数据列(weight, feed_intake, duration)进行错误过滤。
    仅使用能够从输入数据列计算的错误类型（FIV、OTV、FRV相关），
    不计算需要料槽称重数据的LWD/FWD/LTD/FTD。
    """
    df = df.copy()
    df["feed_error"] = False
    df["feed_remark"] = None
    df["qc_feed_kg"] = np.nan

    fiv = df["feed_intake"].values.astype(float)
    otv = df["duration"].values.astype(float)
    frv = np.where(otv > 0, fiv / (otv / 60.0), 0.0)
    n = len(df)

    errors = []

    # 1-3: FIV 错误
    errors.append(("FIV-lo (负采食量)", fiv < -20))
    errors.append(("FIV-hi (单次采食过高)", fiv > 2000))
    errors.append(("FIV-0 (零时长有采食)", (otv == 0) & (np.abs(fiv) > 20)))

    # 4-5: OTV 错误
    errors.append(("OTV-lo (负数时长)", otv < 0))
    errors.append(("OTV-hi (采食过长)", otv > 3600))

    # 6-10: FRV 错误
    small_feed = (fiv > 0) & (fiv < 50)
    errors.append(("FRV-hi-FIV-lo (小采食量高速率)", small_feed & (frv > 500)))

    # 邻近有负采食量
    neg_before = np.zeros(n, dtype=bool)
    if n > 1:
        neg_before[1:] = fiv[:-1] < -20
    errors.append(("FRV-hi-strict (邻近负值严格判断)", (fiv >= 50) & neg_before & (frv > 110)))
    errors.append(("FRV-hi (高速率)", (fiv >= 50) & (~neg_before) & (frv > 170)))
    errors.append(("FRV-0 (零速率时长长)", (frv == 0) & (otv > 500)))
    valid_frv = (frv != 0) & (~np.isnan(frv)) & (np.isfinite(frv))
    errors.append(("FRV-lo (低速率)", valid_frv & (np.abs(frv) <= 2)))

    # 标记错误
    for name, mask in errors:
        m = pd.Series(mask, index=df.index).fillna(False)
        df.loc[m, "feed_error"] = True
        new_r = "采食数据异常:" + name
        df.loc[m & df["feed_remark"].isna(), "feed_remark"] = new_r
        for idx in df[m & df["feed_remark"].notna()].index:
            df.at[idx, "feed_remark"] = str(df.at[idx, "feed_remark"]) + "," + name

    # 有效采食量：未标记采食错误的记录保留原始采食量，错误的置为NaN
    df["qc_feed_kg"] = df["feed_kg"].copy()
    df.loc[df["feed_error"], "qc_feed_kg"] = np.nan
    return df

# ============================================================
# Step 3: 5步体重质控（浙大博士论文核心方法）
# ============================================================
def filter_bw_5step(df: pd.DataFrame, init_lower: float = 25.0, init_upper: float = 45.0) -> pd.DataFrame:
    """5步体重质控过滤"""
    df = df.copy()
    df["bw_remark"] = None
    df["is_abnormal"] = False
    df["qc_weight_kg"] = np.nan

    # 第1步：粗过滤 + 初测体重下限检查
    s1 = (df["weight_kg"] > 180) | (df["weight_kg"] < 25)
    df.loc[s1, "bw_remark"] = "粗过滤:体重极值"
    df.loc[s1, "is_abnormal"] = True

    # 初测体重下限检查（配置参数 init_weight_min，仅标记备注，不标记记录级is_abnormal）
    df_sorted = df.sort_values("visit_time")
    first_valid = df_sorted[df_sorted["weight_kg"].notna() & ~df_sorted.index.isin(df[s1].index)]
    if len(first_valid) > 0:
        first_wt = first_valid["weight_kg"].iloc[0]
        if first_wt < init_lower or first_wt > init_upper:
            remark = f"初测体重{first_wt:.1f}kg需在{init_lower:.0f}-{init_upper:.0f}kg范围"
            # 标记初测体重异常记录为is_abnormal，不参与ADG回归
            for idx in first_valid.index[:1]:
                old = df.at[idx, "bw_remark"]
                df.at[idx, "bw_remark"] = remark if pd.isna(old) else str(old) + ";" + remark
                df.at[idx, "is_abnormal"] = True

    valid = df[~s1].copy()
    if len(valid) == 0:
        df["predicted_weight"] = np.nan
        return df

    # 第2步：计算ADG参考值
    first_wt_check = valid["weight_kg"].iloc[0]
    first_t_check = valid["visit_time"].iloc[0]
    if len(valid) >= 2 and first_wt_check > init_upper + 10:
        start_wt = valid["weight_kg"].iloc[1]
        start_t = valid["visit_time"].iloc[1]
    else:
        start_wt = first_wt_check
        start_t = first_t_check
    end_wt = valid["weight_kg"].iloc[-1]
    days_diff = max((valid["visit_time"].iloc[-1] - start_t).days, 1)
    adg_ref = (end_wt - start_wt) / days_diff

    # 第3步：预测体重（start_t 已在第2步中确定）
    valid["predicted_wt"] = start_wt + (valid["visit_time"] - start_t).dt.days * adg_ref
    df["predicted_weight"] = np.nan
    df.loc[~s1, "predicted_weight"] = valid["predicted_wt"].values

    # 第4步：预测体重±ADG×21过滤
    s4 = (valid["weight_kg"] - valid["predicted_wt"]).abs() > max(adg_ref * 21, 10)
    for idx in valid[s4].index:
        df.at[idx, "is_abnormal"] = True
        old = df.at[idx, "bw_remark"]
        df.at[idx, "bw_remark"] = "极端错误:预测体重±21*ADG" if pd.isna(old) else str(old) + ";极端错误"

    clean = valid[~s4].copy()
    if len(clean) == 0:
        return df

    # 第5步：按天进行2SD + 7ADG过滤
    for d, grp in clean.groupby("date"):
        if len(grp) < 3:
            continue
        mean_w = grp["weight_kg"].mean()
        std_w = grp["weight_kg"].std()
        if pd.isna(std_w) or std_w == 0:
            continue
        s5a = (grp["weight_kg"] - mean_w).abs() > 2 * std_w
        s5b = (grp["weight_kg"] - mean_w).abs() > adg_ref * 7
        s5 = s5a | s5b
        for idx in grp[s5].index:
            df.at[idx, "is_abnormal"] = True
            old = df.at[idx, "bw_remark"]
            df.at[idx, "bw_remark"] = "回归偏差较大" if pd.isna(old) else str(old) + ";回归偏差较大"

    # 有效体重
    df.loc[~df["is_abnormal"] & df["weight_kg"].notna(), "qc_weight_kg"] = df.loc[~df["is_abnormal"], "weight_kg"]
    return df

# ============================================================
# Step 4-6: ADG / ADFI / FCR
# ============================================================
def calc_adg(df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
    """通过有效体重对日龄做线性回归计算ADG"""
    valid = df[~df["is_abnormal"] & df["qc_weight_kg"].notna()].copy()
    if len(valid) < 3:
        return None, None
    x = (valid["visit_time"] - valid["visit_time"].min()).dt.days.values.astype(float)
    y = valid["qc_weight_kg"].values
    if np.std(x) < 1e-6:
        return None, None
    A = np.vstack([x, np.ones(len(x))]).T
    m, c = np.linalg.lstsq(A, y, rcond=None)[0]
    y_pred = m * x + c
    ss_res = np.sum((y - y_pred)**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return float(m), float(r2)

def calc_adfi(df: pd.DataFrame) -> Optional[float]:
    """计算平均日采食量 — 使用有效（未标记采食错误）采食量总和 / 测试天数"""
    total = df["qc_feed_kg"].sum()
    days = max((df["visit_time"].max() - df["visit_time"].min()).days, 1)
    return total / days

# ============================================================
# 单猪处理流程
# ============================================================
def process_pig(df_raw: pd.DataFrame, lifenumber: str, min_age: int = 100, max_age: int = 200, init_lower: float = 25.0, init_upper: float = 45.0) -> PigResult:
    """完整FCR计算流程"""
    result = PigResult(lifenumber=lifenumber)

    # Step 1: 个体过滤（仅标记不删除，保留所有记录用于ADFI天数计算）
    df, info = filter_individual(df_raw, min_age, max_age)
    result.fill_info = ";".join(info) if info else ""
    # 统计有效体重记录数（剔除体重极值行）
    valid_weight_mask = (df["weight_kg"] >= 25) & (df["weight_kg"] <= 180)
    if valid_weight_mask.sum() < 5:
        result.is_abnormal = "异常样本"
        for col in ["bw_remark","is_abnormal","qc_weight_kg","predicted_weight","feed_error","feed_remark","qc_feed_kg"]:
            if col not in df.columns: df[col] = None
        df["is_abnormal"] = df["is_abnormal"].fillna(False).astype(bool)
        result.cleaned_data = df
        return result

    # 提取起止信息（按时间排序取首尾）
    df_sorted = df.sort_values("visit_time")
    result.start_date = df_sorted["visit_time"].iloc[0].date()
    result.end_date = df_sorted["visit_time"].iloc[-1].date()
    result.start_weight = round(df_sorted["weight_kg"].iloc[0], 1)
    result.end_weight = round(df_sorted["weight_kg"].iloc[-1], 1)

    # Step 2: 采食过滤
    df = filter_feed_errors(df)

    # Step 3: 体重质控
    df = filter_bw_5step(df, init_lower, init_upper)

    # Step 4: ADG
    adg, r2 = calc_adg(df)
    result.adg = round(adg, 4) if adg else None
    result.r_squared = round(r2, 4) if r2 else None

    # Step 5: ADFI
    adfi = calc_adfi(df)
    result.adfi = round(adfi, 4) if adfi and adfi > 0 else None

    # Step 6: FCR = ADFI / ADG (Feed:Gain)
    if adg and adg > 0 and adfi and adfi > 0:
        result.fcr = round(adfi / adg, 3)
    else:
        result.fcr = None

    # 总采食量（有效采食量：排除采食错误记录）
    result.total_feed = round(df["qc_feed_kg"].sum(), 3)

    # 原始FCR = 总体总采食量 / (ADG × 测试天数)  — 需求3.8
    # 使用全部原始采食数据（包含异常记录），ADG为质控后回归ADG
    raw_feed_total = df_raw["feed_intake"].astype(float).sum() / 1000.0
    raw_days = max((df_raw["visit_time"].max() - df_raw["visit_time"].min()).days, 1)
    if adg and adg > 0 and raw_days > 0:
        result.fcr_raw = round(raw_feed_total / (adg * raw_days), 3)

    if result.fcr is None or result.fcr <= 0:
        result.is_abnormal = "异常样本"
    if "初测体重异常" in result.fill_info:
        result.is_abnormal = "异常样本"
    df.index = range(len(df))
    result.cleaned_data = df

    # check init weight range fail -> mark abnormal
    if 'bw_remark' in result.cleaned_data.columns:
        for v in result.cleaned_data['bw_remark'].unique():
            if isinstance(v, str) and '需在' in v:
                result.fill_info = v + ('; ' + result.fill_info if result.fill_info else '')
                result.is_abnormal = '异常样本'
                break
    return result

# ============================================================
# 批量处理
# ============================================================
def batch_process(filepath: str, output_dir: str,
                  progress_callback=None, min_age: int = 100, max_age: int = 200,
                  init_lower: float = 25.0, init_upper: float = 45.0) -> List[PigResult]:
    """批量处理所有猪只"""
    raw = load_csv(filepath)
    os.makedirs(output_dir, exist_ok=True)
    img_dir = os.path.join(output_dir, "03.结果图片")
    os.makedirs(img_dir, exist_ok=True)
    results = []

    pig_groups = list(raw.groupby("lifenumber"))
    total = len(pig_groups)

    for i, (lifenumber, group) in enumerate(pig_groups):
        if progress_callback:
            progress_callback(i + 1, total, lifenumber)
        result = process_pig(group.copy(), lifenumber, min_age, max_age, init_lower, init_upper)
        results.append(result)

    return results

# ============================================================
# Excel导出
# ============================================================
def export_cleaned_excel(result: PigResult, output_path: str):
    """导出单只猪的清洗后数据"""
    df = result.cleaned_data
    if df is None or len(df) == 0:
        return
    out = pd.DataFrame()
    out["animal_number"] = df["animal_number"]
    out["lifenumber"] = df["lifenumber"]
    out["responder"] = df["responder"]
    out["location"] = df["location"]
    out["visit_time"] = df["visit_time"]
    out["duration"] = df["duration"]
    out["state"] = df["state"]
    out["weight"] = df["weight"]
    out["feed_intake"] = df["feed_intake"]
    out["质控后体重数据"] = df.get("qc_weight_kg")
    out["质控后采食量数据"] = df.get("qc_feed_kg")
    out["体重数据备注"] = df.get("bw_remark")
    out["采食数据备注"] = df.get("feed_remark")
    out["predicted_weight"] = df.get("predicted_weight")
    out["_is_abnormal"] = df.get("is_abnormal")
    out.to_excel(output_path, index=False, engine="openpyxl")

def export_summary_excel(results: List[PigResult], output_path: str):
    """导出汇总表"""
    rows = []
    for r in results:
        rows.append({
            "个体批次号": r.lifenumber,
            "起始时间": str(r.start_date) if r.start_date else "",
            "起始重量": r.start_weight,
            "终止时间": str(r.end_date) if r.end_date else "",
            "终止体重": r.end_weight,
            "总采食量": r.total_feed,
            "ADG": r.adg,
            "ADFI": r.adfi,
            "R²": r.r_squared,
            "FCR": r.fcr,
            "原始FCR": r.fcr_raw,
            "是否存在填补数据": r.fill_info,
            "异常": r.is_abnormal,
        })
    pd.DataFrame(rows).to_excel(output_path, index=False, engine="openpyxl")
