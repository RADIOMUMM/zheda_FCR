"""
FCR 计算测试脚本 - 命令行批量计算
用法: python run_test.py <CSV文件路径> [输出目录]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fcr_app.core import load_csv, process_pig, batch_process, export_summary_excel, export_cleaned_excel
from fcr_app.chart import plot_weight_curve

def main():
    if len(sys.argv) < 2:
        print("用法: python run_test.py <CSV文件路径> [输出目录]")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"文件不存在: {csv_path}")
        sys.exit(1)

    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(csv_path), "fcr_test_result")
    os.makedirs(output_dir, exist_ok=True)
    img_dir = os.path.join(output_dir, "03.结果图片")
    os.makedirs(img_dir, exist_ok=True)

    print(f"加载数据: {csv_path}")
    raw = load_csv(csv_path)
    print(f"  共 {len(raw)} 行, {raw['lifenumber'].nunique()} 头猪")

    results = []
    for lifenumber, group in sorted(raw.groupby("lifenumber")):
        print(f"  处理: {lifenumber} ...", end=" ")
        result = process_pig(group.copy(), lifenumber)
        results.append(result)

        # 导出清洗数据
        clean_path = os.path.join(output_dir, f"01.{lifenumber}_清洗后数据.xlsx")
        export_cleaned_excel(result, clean_path)

        # 导出图片
        img_path = os.path.join(img_dir, f"{lifenumber}.png")
        plot_weight_curve(result, img_path, show_fit=True)

        # 打印关键指标
        status = "⚠" if result.is_abnormal != "否" else "✓"
        fcr_str = f"{result.fcr:.3f}" if result.fcr else "N/A"
        adg_str = f"{result.adg:.4f}" if result.adg else "N/A"
        adfi_str = f"{result.adfi:.4f}" if result.adfi else "N/A"
        print(f"{status} FCR={fcr_str}  ADG={adg_str}  ADFI={adfi_str}")

    # 导出汇总表
    summary_path = os.path.join(output_dir, "02.样本肉料比信息表.xlsx")
    export_summary_excel(results, summary_path)
    print(f"\n汇总表: {summary_path}")

    # 统计
    fcr_vals = [r.fcr for r in results if r.fcr is not None]
    adg_vals = [r.adg for r in results if r.adg is not None]
    adfi_vals = [r.adfi for r in results if r.adfi is not None]
    if fcr_vals:
        print(f"FCR: 均值={sum(fcr_vals)/len(fcr_vals):.3f}  "
              f"范围={min(fcr_vals):.3f}~{max(fcr_vals):.3f}  "
              f"样本数={len(fcr_vals)}")
    if adg_vals:
        print(f"ADG: 均值={sum(adg_vals)/len(adg_vals):.4f} kg/d  "
              f"范围={min(adg_vals):.4f}~{max(adg_vals):.4f}")
    if adfi_vals:
        print(f"ADFI:均值={sum(adfi_vals)/len(adfi_vals):.4f} kg/d  "
              f"范围={min(adfi_vals):.4f}~{max(adfi_vals):.4f}")

if __name__ == "__main__":
    main()
