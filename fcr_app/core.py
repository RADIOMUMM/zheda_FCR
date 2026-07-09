"""
FCR Calculator Core Module
============================================
基于浙大博士论文(2025)方法的FCR计算引擎
包含: CSV加载、10种采食错误类型过滤(FIV/OTV/FRV)、5步体重质控、ADG/ADFI/FCR计算、Excel导出
"""
import pandas as pd
import numpy as np
from datetime import datetime, date
import os, warnings, logging
from dataclasses import dataclass
from typing import Optional, List, Tuple, Callable

warnings.filterwarnings("ignore")
logger = logging.getLogger("FCRCore")

# ============================================================
# 常量
# ============================================================
WEIGHT_UPPER = 180.0       # kg
WEIGHT_LOWER = 25.0        # kg
MIN_RECORDS = 20            # 单猪最少有效记录数
MIN_TEST_DAYS = 30          # 最小测试天数
STAGE_WEIGHT_LOWER = 50.0  # 阶段区间默认下限 (kg)
STAGE_WEIGHT_UPPER = 90.0  # 阶段区间默认上限 (kg)
R2_WARN_THRESHOLD = 0.8    # R² 预警阈值

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
    # 阶段料肉比相关
    stage_adg: Optional[float] = None
    stage_adfi: Optional[float] = None
    stage_fcr: Optional[float] = None
    stage_r_squared: Optional[float] = None
    stage_start_date: Optional[date] = None
    stage_end_date: Optional[date] = None
    stage_start_weight: Optional[float] = None
    stage_end_weight: Optional[float] = None
    stage_total_feed: Optional[float] = None
    stage_chart_path: Optional[str] = None

# ============================================================
# 数据加载 & 合并
# ============================================================
def load_csv(filepath: str) -> pd.DataFrame:
    """加载单个CSV文件"""
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    required = ["animal_number","lifenumber","responder","location",
                "visit_time","duration","state","weight","feed_intake"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"文件 {os.path.basename(filepath)} 缺少必需列: {missing}")
    df["visit_time"] = pd.to_datetime(df["visit_time"])
    df["weight_kg"] = df["weight"].astype(float) / 1000.0
    df["feed_kg"] = df["feed_intake"].astype(float) / 1000.0
    df["date"] = df["visit_time"].dt.date
    df = df.dropna(subset=["lifenumber"])
    # 记录来源文件
    df["_source_file"] = os.path.basename(filepath)
    return df


def load_csv_folder(folder_path: str, progress_callback: Optional[Callable] = None) -> pd.DataFrame:
    """加载文件夹下所有CSV文件并合并"""
    import glob
    csv_files = sorted(glob.glob(os.path.join(folder_path, "*.csv")))
    if not csv_files:
        raise ValueError(f"文件夹 {folder_path} 中未找到CSV文件")
    
    dfs = []
    total = len(csv_files)
    for i, fpath in enumerate(csv_files):
        if progress_callback:
            progress_callback(i + 1, total, os.path.basename(fpath))
        df = load_csv(fpath)
        dfs.append(df)
    
    if not dfs:
        raise ValueError("未能加载任何有效CSV文件")
    
    merged = pd.concat(dfs, ignore_index=True)
    logger.info(f"合并完成: {len(csv_files)} 个文件, {len(merged)} 条记录")
    return merged


# ============================================================
# Step 1: 个体预过滤
# ============================================================
def filter_individual(df: pd.DataFrame, min_age_days: int = 100, max_age_days: int = 200) -> Tuple[pd.DataFrame, List[str]]:
    """
    个体层面预过滤：
    - 入试日龄推算（从最早体重估算），超出范围标记异常
    - 单次异常体重(>180kg或<25kg)记录直接剔除
    - 生成数据完整性备注
    """
    info = []
    if len(df) < 2:
        return df, ["数据不足"]

    days = (df["visit_time"].max() - df["visit_time"].min()).days
    if days < MIN_TEST_DAYS:
        info.append(f"测定日期不足{MIN_TEST_DAYS}天")
    if days < 60:
        info.append("测定日期不足60天")

    # 入试日龄推算（简易估算：体重kg × 2.2 + 15 ≈ 日龄）
    first_wt = df.sort_values("visit_time")["weight_kg"].iloc[0]
    est_age = first_wt * 2.2 + 15
    if est_age < min_age_days or est_age > max_age_days:
        info.append(f"入试日龄约{est_age:.0f}天（体重{first_wt:.1f}kg估算），超出{min_age_days}-{max_age_days}天范围")

    # 单次记录过滤：剔除明显异常的体重值
    df = df[(df["weight_kg"] >= WEIGHT_LOWER) & (df["weight_kg"] <= WEIGHT_UPPER)].copy()
    return df, info


# ============================================================
# Step 2: 采食数据过滤（基于可用数据列，10种错误类型）
# ============================================================
def filter_feed_errors(df: pd.DataFrame) -> pd.DataFrame:
    """
    基于Cassey, Stern, Dekkers (2005) 定义的16种错误类型，
    根据现有CSV数据列（feed_intake、duration）计算可实现的10种错误类型：
      - FIV (3种)：FIV-lo、FIV-hi、FIV-0
      - OTV (2种)：OTV-lo、OTV-hi
      - FRV (5种)：FRV-hi-FIV-lo、FRV-hi-strict、FRV-hi、FRV-0、FRV-lo
    注：LWD/FWD/LTD/FTD (6种) 需要料槽称重的 entry_weight/exit_weight 及
    entry_time/exit_time 字段，当前CSV仅有单次体重和采食量，无法计算。
    """
    df = df.copy().sort_values("visit_time")
    df["feed_error"] = False
    df["feed_remark"] = None
    df["qc_feed_kg"] = np.nan

    fiv = df["feed_intake"].values.astype(float)   # 采食量 (g)
    otv = df["duration"].values.astype(float)       # 采食持续时间 (s)
    frv = np.where(otv > 0, fiv / (otv / 60.0), 0.0)  # 采食速率 (g/min)
    n = len(df)

    errors = []

    # 1-3: FIV 错误（基于 feed_intake / duration）
    errors.append(("FIV-lo", fiv < -20))
    errors.append(("FIV-hi", fiv > 2000))
    errors.append(("FIV-0", (otv == 0) & (np.abs(fiv) > 20)))

    # 4-5: OTV 错误（基于 duration）
    errors.append(("OTV-lo", otv < 0))
    errors.append(("OTV-hi", otv > 3600))

    # 6-10: FRV 错误（基于 FIV/OTV 计算速率）
    small_feed = (fiv > 0) & (fiv < 50)
    errors.append(("FRV-hi-FIV-lo", small_feed & (frv > 500)))
    neg_before = np.zeros(n, dtype=bool)
    if n > 1:
        neg_before[1:] = fiv[:-1] < -20
    errors.append(("FRV-hi-strict", (fiv >= 50) & neg_before & (frv > 110)))
    errors.append(("FRV-hi", (fiv >= 50) & (~neg_before) & (frv > 170)))
    errors.append(("FRV-0", (frv == 0) & (otv > 500)))
    valid_frv = (frv != 0) & (~np.isnan(frv)) & (np.isfinite(frv))
    errors.append(("FRV-lo", valid_frv & (np.abs(frv) <= 2)))

    # 11-16: LWD/FWD/LTD/FTD — 需要料槽 entry/exit 称重数据，当前数据无法计算

    # 标记错误
    for name, mask in errors:
        m = pd.Series(mask, index=df.index).fillna(False)
        df.loc[m, "feed_error"] = True
        for idx in df[m].index:
            old = df.at[idx, "feed_remark"]
            if pd.isna(old):
                df.at[idx, "feed_remark"] = f"采食数据异常：{name}"
            else:
                df.at[idx, "feed_remark"] = str(old) + f"/{name}"

    # 有效采食量：标记错误的行 qc_feed_kg 置为 NaN
    df["qc_feed_kg"] = df["feed_kg"].where(~df["feed_error"], np.nan)
    return df


# ============================================================
# Step 3: 5步体重质控（浙大博士论文核心方法）
# ============================================================
def _fallback_adg(valid: pd.DataFrame):
    """回退方法：用首尾两点或默认值计算ADG参考"""
    if len(valid) >= 2:
        clean = valid.dropna(subset=["weight_kg"])
        if len(clean) >= 2:
            start_wt = clean["weight_kg"].iloc[0]
            start_t = clean["visit_time"].iloc[0]
            end_wt = clean["weight_kg"].iloc[-1]
            days_diff = max((clean["visit_time"].iloc[-1] - start_t).days, 1)
            adg_ref = (end_wt - start_wt) / days_diff
            return adg_ref, start_wt, start_t
    return 0.5, 25.0, valid["visit_time"].min() if len(valid) > 0 else pd.Timestamp.now()


def filter_bw_5step(df: pd.DataFrame, init_lower: float = 25.0, init_upper: float = 45.0,
                     end_lower: float = 90.0, end_upper: float = 110.0) -> pd.DataFrame:
    """5步体重质控过滤"""
    df = df.copy()
    df["bw_remark"] = None
    df["is_abnormal"] = False
    df["qc_weight_kg"] = np.nan

    # 第1步：粗过滤 + 初测体重下限检查
    s1 = (df["weight_kg"] > WEIGHT_UPPER) | (df["weight_kg"] < WEIGHT_LOWER)
    df.loc[s1, "bw_remark"] = "粗过滤:体重极值"
    df.loc[s1, "is_abnormal"] = True

    # 初测体重范围检查
    df_sorted = df.sort_values("visit_time")
    first_valid = df_sorted[df_sorted["weight_kg"].notna() & ~df_sorted.index.isin(df[s1].index)]
    if len(first_valid) > 0:
        first_wt = first_valid["weight_kg"].iloc[0]
        if first_wt < init_lower or first_wt > init_upper:
            remark = f"初测体重{first_wt:.1f}kg需在{init_lower:.0f}-{init_upper:.0f}kg范围"
            for idx in first_valid.index[:1]:
                old = df.at[idx, "bw_remark"]
                df.at[idx, "bw_remark"] = remark if pd.isna(old) else str(old) + ";" + remark
                df.at[idx, "is_abnormal"] = True

    # 终测体重范围检查
    last_valid = df_sorted[df_sorted["weight_kg"].notna() & ~df_sorted.index.isin(df[s1].index)]
    if len(last_valid) > 0:
        last_wt = last_valid["weight_kg"].iloc[-1]
        if last_wt < end_lower or last_wt > end_upper:
            remark = f"终测体重{last_wt:.1f}kg需在{end_lower:.0f}-{end_upper:.0f}kg范围"
            for idx in last_valid.index[-1:]:
                old = df.at[idx, "bw_remark"]
                df.at[idx, "bw_remark"] = remark if pd.isna(old) else str(old) + ";" + remark
                df.at[idx, "is_abnormal"] = True

    valid = df[~s1].copy()
    if len(valid) == 0:
        df["predicted_weight"] = np.nan
        return df

    # 第2步：计算ADG参考值（使用线性回归，对端点异常值鲁棒）
    x_days = (valid["visit_time"] - valid["visit_time"].min()).dt.days.values.astype(float)
    y_wt = valid["weight_kg"].values
    if len(valid) >= 3 and np.std(x_days) > 1e-6:
        # 线性回归求斜率作为ADG参考，不受首尾异常值影响
        # 剔除无体重值的记录，防止NaN污染回归
        reg_valid = valid.dropna(subset=["weight_kg"])
        if len(reg_valid) >= 3:
            x_r = (reg_valid["visit_time"] - reg_valid["visit_time"].min()).dt.days.values.astype(float)
            y_r = reg_valid["weight_kg"].values
            if np.std(x_r) > 1e-6:
                A = np.vstack([x_r, np.ones(len(x_r))]).T
                m_reg, c_reg = np.linalg.lstsq(A, y_r, rcond=None)[0]
                adg_ref = m_reg
                start_wt = c_reg
                start_t = valid["visit_time"].min()
            else:
                adg_ref, start_wt, start_t = _fallback_adg(valid)
        else:
            adg_ref, start_wt, start_t = _fallback_adg(valid)
    elif len(valid) >= 2:
        # 不足3个点时回退到首尾法
        start_wt = valid["weight_kg"].iloc[0]
        start_t = valid["visit_time"].iloc[0]
        end_wt = valid["weight_kg"].iloc[-1]
        days_diff = max((valid["visit_time"].iloc[-1] - start_t).days, 1)
        adg_ref = (end_wt - start_wt) / days_diff
    else:
        adg_ref = 0.5
        start_wt = valid["weight_kg"].iloc[0] if len(valid) > 0 else 25.0
        start_t = valid["visit_time"].iloc[0] if len(valid) > 0 else valid["visit_time"].min()

    # 第3步：预测体重
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

    # 第5步：按天进行2SD + 7ADG过滤（移除≥3限制）
    for d, grp in clean.groupby("date"):
        if len(grp) < 2:
            continue  # 至少2条才能计算std
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
            # 区分5a和5b的备注
            only_5b = s5b.loc[idx] and not s5a.loc[idx]
            if only_5b:
                remark = "回归偏差较大"
            else:
                remark = "标准差过滤"
            df.at[idx, "bw_remark"] = remark if pd.isna(old) else str(old) + ";" + remark

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
    """计算平均日采食量 — 仅使用未标记采食错误的记录"""
    valid_feed = df[~df["feed_error"]]
    if len(valid_feed) == 0:
        return None
    total = valid_feed["feed_kg"].sum()
    days = max((df["visit_time"].max() - df["visit_time"].min()).days, 1)
    return total / days


# ============================================================
# 阶段料肉比计算（30-70kg区间，可配置）
# ============================================================
def calc_stage_fcr(df_qc: pd.DataFrame, lifenumber: str,
                   stage_lower: float = STAGE_WEIGHT_LOWER,
                   stage_upper: float = STAGE_WEIGHT_UPPER) -> Optional[PigResult]:
    """
    对指定体重区间（如30-70kg）内的数据计算阶段料肉比。
    使用QC后的数据（已标记is_abnormal），筛选通过质控且体重在区间内的记录，
    执行完整的5步质控和FCR计算流程。
    """
    # 先筛选通过质控的记录，再按体重区间过滤
    if "is_abnormal" in df_qc.columns:
        df_qc = df_qc[~df_qc["is_abnormal"]].copy()
        if "qc_weight_kg" in df_qc.columns:
            df_qc = df_qc[df_qc["qc_weight_kg"].notna()].copy()
    stage_df = df_qc[
        (df_qc["weight_kg"] >= stage_lower) & (df_qc["weight_kg"] <= stage_upper)
    ].copy()
    if len(stage_df) < MIN_RECORDS:
        return None

    # 执行完整处理流程
    return process_pig(
        stage_df, lifenumber,
        init_lower=stage_lower, init_upper=stage_upper
    )


# ============================================================
# 单猪处理流程
# ============================================================
def process_pig(df_raw: pd.DataFrame, lifenumber: str,
                min_age: int = 100, max_age: int = 200,
                init_lower: float = 25.0, init_upper: float = 45.0,
                end_lower: float = 90.0, end_upper: float = 110.0,
                stage_lower: Optional[float] = None,
                stage_upper: Optional[float] = None) -> PigResult:
    """完整FCR计算流程（含原始FCR和阶段料肉比）"""
    result = PigResult(lifenumber=lifenumber)

    # ---- 保存原始数据副本用于原始FCR计算 ----
    raw_copy = df_raw.copy()

    # Step 1: 个体过滤
    df, info = filter_individual(df_raw, min_age, max_age)
    result.fill_info = ";".join([m for m in info if "日龄" not in m]) if info else ""
    if len(df) < MIN_RECORDS:
        result.is_abnormal = "异常样本"
        for col in ["bw_remark","is_abnormal","qc_weight_kg","predicted_weight","feed_error","feed_remark","qc_feed_kg"]:
            if col not in df.columns: df[col] = None
        df["is_abnormal"] = df["is_abnormal"].fillna(False).astype(bool)
        df["qc_feed_kg"] = df.get("qc_feed_kg", np.nan)
        result.cleaned_data = df
        # 原始FCR仍可计算
        _calc_raw_fcr(result, raw_copy)
        return result

    # Step 2: 采食过滤
    df = filter_feed_errors(df)

    # Step 3: 体重质控
    df = filter_bw_5step(df, init_lower, init_upper,
                          end_lower=end_lower, end_upper=end_upper)

    # Step 4: ADG
    adg, r2 = calc_adg(df)
    result.adg = round(adg, 4) if adg else None
    result.r_squared = round(r2, 4) if r2 is not None else None

    # 从质控后的有效记录重新提取起止信息（用回归残差检测离群首尾）
    valid_mask = ~df["is_abnormal"] & df["qc_weight_kg"].notna()
    valid_records = df[valid_mask]
    if len(valid_records) >= 2:
        result.start_date = valid_records["visit_time"].min().date()
        result.end_date = valid_records["visit_time"].max().date()
        valid_sorted = valid_records.sort_values("visit_time")
        # 用线性回归残差检测首尾离群点
        # 对有效数据重新拟合趋势线，残差 > 8kg 视为离群
        start_idx = 0
        end_idx = len(valid_sorted) - 1
        if len(valid_sorted) >= 5:
            x = (valid_sorted["visit_time"] - valid_sorted["visit_time"].iloc[0]).dt.days.values.astype(float)
            y = valid_sorted["qc_weight_kg"].values
            A = np.vstack([x, np.ones(len(x))]).T
            m, c = np.linalg.lstsq(A, y, rcond=None)[0]
            residuals = np.abs(y - (c + x * m))
            # 若首条残差 > 8kg 且比第二条大得多，跳过
            if residuals[0] > 8 and (len(residuals) < 2 or residuals[0] > residuals[1] * 2):
                start_idx = 1
            # 若末条残差 > 8kg 且比倒数第二条大得多，跳过
            if residuals[-1] > 8 and (len(residuals) < 2 or residuals[-1] > residuals[-2] * 2):
                end_idx = len(valid_sorted) - 2
        result.start_weight = round(valid_sorted["qc_weight_kg"].iloc[start_idx], 1)
        result.end_weight = round(valid_sorted["qc_weight_kg"].iloc[end_idx], 1)
    elif len(valid_records) == 1:
        result.start_date = valid_records["visit_time"].iloc[0].date()
        result.end_date = result.start_date
        result.start_weight = round(valid_records["qc_weight_kg"].iloc[0], 1)
        result.end_weight = result.start_weight

    # R² 预警
    if r2 is not None and r2 < R2_WARN_THRESHOLD and result.adg:
        warn = f"ADG拟合R²={r2:.3f}<{R2_WARN_THRESHOLD}"
        result.fill_info = (warn + "; " + result.fill_info) if result.fill_info else warn

    # Step 5: ADFI
    adfi = calc_adfi(df)
    result.adfi = round(adfi, 4) if adfi and adfi > 0 else None

    # Step 6: FCR = ADFI / ADG (Feed:Gain)
    if adg and adg > 0 and adfi and adfi > 0:
        result.fcr = round(adfi / adg, 3)
    else:
        result.fcr = None

    # 总采食量（仅有效采食）
    valid_feed = df[~df["feed_error"]]
    result.total_feed = round(valid_feed["feed_kg"].sum(), 3)

    # 原始FCR（使用原始数据，未经过质控）
    _calc_raw_fcr(result, raw_copy)

    # ---- 异常标记 ----
    if result.fcr is None or result.fcr <= 0:
        result.is_abnormal = "异常样本"

    df.index = range(len(df))
    result.cleaned_data = df

    # ---- 初/终测体重统一检查（使用用户配置的体重范围）----
    weight_notes = []
    if result.start_weight is not None:
        if result.start_weight < init_lower or result.start_weight > init_upper:
            weight_notes.append(
                f"初测体重{result.start_weight:.1f}kg（正常范围{init_lower:.0f}-{init_upper:.0f}kg）")
            result.is_abnormal = '异常样本'
    if result.end_weight is not None:
        if result.end_weight < end_lower or result.end_weight > end_upper:
            weight_notes.append(
                f"终测体重{result.end_weight:.1f}kg（正常范围{end_lower:.0f}-{end_upper:.0f}kg）")
            result.is_abnormal = '异常样本'
    if weight_notes:
        note_str = "; ".join(weight_notes)
        result.fill_info = (note_str + '; ' + result.fill_info) if result.fill_info else note_str

    # ---- 阶段料肉比计算 ----
    if stage_lower is not None and stage_upper is not None:
        stage_result = calc_stage_fcr(df, lifenumber, stage_lower, stage_upper)
        if stage_result:
            result.stage_adg = stage_result.adg
            result.stage_adfi = stage_result.adfi
            result.stage_fcr = stage_result.fcr
            result.stage_r_squared = stage_result.r_squared
            result.stage_start_date = stage_result.start_date
            result.stage_end_date = stage_result.end_date
            result.stage_start_weight = stage_result.start_weight
            result.stage_end_weight = stage_result.end_weight
            result.stage_total_feed = stage_result.total_feed


    return result


def _calc_raw_fcr(result: PigResult, raw_df: pd.DataFrame):
    """使用原始数据（未经过任何质控过滤）计算原始FCR"""
    sorted_raw = raw_df.sort_values("visit_time").dropna(subset=["weight_kg"])
    if len(sorted_raw) < 2:
        result.fcr_raw = None
        return
    total_feed_kg = sorted_raw["feed_kg"].sum()
    first_wt = sorted_raw["weight_kg"].iloc[0]
    last_wt = sorted_raw["weight_kg"].iloc[-1]
    weight_gain_kg = last_wt - first_wt
    if weight_gain_kg > 0 and total_feed_kg > 0:
        result.fcr_raw = round(total_feed_kg / weight_gain_kg, 3)
    else:
        result.fcr_raw = None


# ============================================================
# 批量处理
# ============================================================
def batch_process(filepath: str, output_dir: str,
                  progress_callback=None,
                  init_lower: float = 25.0, init_upper: float = 45.0,
                  end_lower: float = 90.0, end_upper: float = 110.0,
                  stage_lower: Optional[float] = None,
                  stage_upper: Optional[float] = None) -> List[PigResult]:
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
        result = process_pig(group.copy(), lifenumber,
                             init_lower=init_lower, init_upper=init_upper,
                             end_lower=end_lower, end_upper=end_upper,
                             stage_lower=stage_lower, stage_upper=stage_upper)
        results.append(result)

    return results


# ============================================================
# 防文件冲突
# ============================================================
def _safe_path(filepath: str) -> str:
    """如果文件已存在，自动添加时间戳后缀"""
    if not os.path.exists(filepath):
        return filepath
    base, ext = os.path.splitext(filepath)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_{ts}{ext}"


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
    out.to_excel(_safe_path(output_path), index=False, engine="openpyxl")


def _build_summary_row(r: PigResult) -> dict:
    """构建汇总表的一行数据"""
    return {
        "个体批次号": r.lifenumber,
        "起始时间": str(r.start_date) if r.start_date else "",
        "起始重量": r.start_weight,
        "终止时间": str(r.end_date) if r.end_date else "",
        "终止体重": r.end_weight,
        "总采食量": r.total_feed,
        "FCR": r.fcr,
        "原始FCR": r.fcr_raw,
        "异常详情": r.fill_info,
        "异常": r.is_abnormal,
    }


def export_summary_excel(results: List[PigResult], output_path: str):
    """导出汇总表（10列，符合需求文档4.3节）"""
    rows = [_build_summary_row(r) for r in results]
    pd.DataFrame(rows).to_excel(_safe_path(output_path), index=False, engine="openpyxl")


def export_stage_summary_excel(results: List[PigResult], output_path: str,
                                stage_lower: float = STAGE_WEIGHT_LOWER,
                                stage_upper: float = STAGE_WEIGHT_UPPER):
    """导出阶段料肉比汇总表 — 与主汇总表列数一致"""
    rows = []
    for r in results:
        if r.stage_fcr is None:
            continue
        # 用阶段数据覆盖，列名与主表一致
        row = _build_summary_row(r)
        row["起始时间"] = str(r.stage_start_date) if r.stage_start_date else ""
        row["起始重量"] = r.stage_start_weight
        row["终止时间"] = str(r.stage_end_date) if r.stage_end_date else ""
        row["终止体重"] = r.stage_end_weight
        row["总采食量"] = r.stage_total_feed
        row["FCR"] = r.stage_fcr
        row["原始FCR"] = r.fcr_raw  # 原始FCR全局不变
        # 标记阶段区间
        if r.fill_info:
            row["异常详情"] = f"阶段({stage_lower:.0f}-{stage_upper:.0f}kg);" + r.fill_info
        else:
            row["异常详情"] = f"阶段({stage_lower:.0f}-{stage_upper:.0f}kg)"
        rows.append(row)
    if rows:
        pd.DataFrame(rows).to_excel(_safe_path(output_path), index=False, engine="openpyxl")
