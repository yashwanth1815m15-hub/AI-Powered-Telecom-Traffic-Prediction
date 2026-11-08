"""
Exploratory Data Analysis (EDA) & Visualization Engine for India Telecom Traffic (2010 - 2024)
Generates publication-grade plots and statistical audits for:
- 03_Visualizations_EDA
- Module 1 Final Teacher Review & Handover
- Student 2 (Visualization & Dashboard) and Student 3 (AI Model Training)
"""

import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Matplotlib headless config
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib_cache'
os.makedirs('/tmp/matplotlib_cache', exist_ok=True)

def generate_eda(
    raw_path: str = None,
    processed_path: str = None,
    output_dir: str = None,
    report_path: str = None
) -> None:
    base_dir = "/Users/yashu/.gemini/antigravity-ide/scratch/module1_preprocessing/Telecom_Traffic_Prediction_Module1"
    raw_path = raw_path or os.path.join(base_dir, "01_Real_Raw_Data/raw_traffic_data.csv")
    processed_path = processed_path or os.path.join(base_dir, "02_Processed_Data/cleaned_traffic_data.csv")
    output_dir = output_dir or os.path.join(base_dir, "03_Visualizations_EDA")
    q_path = os.path.join(base_dir, "01_Real_Raw_Data/india_telecom_traffic_quarterly_2010_2024.csv")
    c_path = os.path.join(base_dir, "01_Real_Raw_Data/india_telecom_circle_traffic_2010_2024.csv")
    brain_dir = "/Users/yashu/.gemini/antigravity/brain/1297abd1-e6d2-4f00-b1b8-734e94a70897"

    os.makedirs(output_dir, exist_ok=True)

    print("\n>>> Generating Official India Telecom EDA Visualizations...")

    # Load datasets
    df_raw = pd.read_csv(raw_path)
    df_proc = pd.read_csv(processed_path)
    df_q = pd.read_csv(q_path) if os.path.exists(q_path) else None
    df_c = pd.read_csv(c_path) if os.path.exists(c_path) else None

    plt.rcParams['font.sans-serif'] = 'Helvetica', 'Arial', 'DejaVu Sans'
    plt.rcParams['axes.edgecolor'] = '#cccccc'
    plt.rcParams['axes.linewidth'] = 0.8

    # 1. 15-Year Data Growth Trajectory
    if df_q is not None:
        fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
        x = range(len(df_q))
        y = df_q['total_wireless_data_traffic_pb']
        ax.plot(x, y, color='#1f77b4', linewidth=2.5, label='Quarterly Wireless Data (Petabytes)')
        ax.fill_between(x, 0, y, color='#1f77b4', alpha=0.15)
        
        ax.axvline(x=26, color='#d62728', linestyle='--', linewidth=1.5)
        ax.text(26.5, 30000, 'Sep 2016:\nCommercial 4G Launch\n(Free VoLTE & Data)', color='#d62728', fontsize=8.5, fontweight='bold')
        
        ax.axvline(x=40, color='#ff7f0e', linestyle='--', linewidth=1.5)
        ax.text(40.5, 45000, 'Mar 2020:\nCOVID-19 Lockdown\n(Work from Home Surge)', color='#ff7f0e', fontsize=8.5, fontweight='bold')

        ax.axvline(x=51, color='#2ca02c', linestyle='--', linewidth=1.5)
        ax.text(51.5, 10000, 'Oct 2022:\nCommercial 5G Rollout', color='#2ca02c', fontsize=8.5, fontweight='bold')

        tick_indices = list(range(0, len(df_q), 4))
        tick_labels = [df_q['quarter'].iloc[i] for i in tick_indices]
        ax.set_xticks(tick_indices)
        ax.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=9)
        ax.set_title('India Total Wireless Data Traffic Growth (2010 - 2024: 15-Year Horizon)\nSource: Telecom Regulatory Authority of India (TRAI)', fontsize=12, fontweight='bold', pad=12)
        ax.set_xlabel('Quarter', fontsize=10, fontweight='bold')
        ax.set_ylabel('Total Data Volume (Petabytes)', fontsize=10, fontweight='bold')
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.legend(loc='upper left', frameon=True)
        plt.tight_layout()
        p1 = os.path.join(output_dir, 'eda_15yr_data_traffic_growth.png')
        plt.savefig(p1)
        if os.path.exists(brain_dir): plt.savefig(os.path.join(brain_dir, '01_india_telecom_15yr_data_traffic_growth.png'))
        plt.close()
        print(f"    [OK] Saved {p1}")

    # 2. Decoupling of Data Traffic vs Voice MOU
    if df_q is not None:
        fig, ax1 = plt.subplots(figsize=(11, 5.5), dpi=150)
        color_data = '#1f77b4'
        color_voice = '#2ca02c'
        ax1.set_xlabel('Year / Quarter', fontsize=10, fontweight='bold')
        ax1.set_ylabel('Wireless Data Traffic (Petabytes)', color=color_data, fontsize=10, fontweight='bold')
        line1 = ax1.plot(x, df_q['total_wireless_data_traffic_pb'], color=color_data, linewidth=2.5, label='Wireless Data Traffic (PB)')
        ax1.tick_params(axis='y', labelcolor=color_data)
        ax1.set_xticks(tick_indices)
        ax1.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=9)

        ax2 = ax1.twinx()
        ax2.set_ylabel('Total Voice Minutes of Usage (Billion MOU)', color=color_voice, fontsize=10, fontweight='bold')
        line2 = ax2.plot(x, df_q['total_voice_mou_billion_min'], color=color_voice, linewidth=2.2, linestyle='-.', label='Voice MOU (Billion Min)')
        ax2.tick_params(axis='y', labelcolor=color_voice)

        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax1.legend(lines, labels, loc='center left', frameon=True)
        plt.title('India Telecom Decoupling: Data Explosion vs Voice Minute Growth\nOfficial TRAI Longitudinal Performance Statistics (2010 - 2024)', fontsize=12, fontweight='bold', pad=12)
        ax1.grid(True, linestyle=':', alpha=0.5)
        plt.tight_layout()
        p2 = os.path.join(output_dir, 'eda_voice_vs_data_traffic_decoupling.png')
        plt.savefig(p2)
        if os.path.exists(brain_dir): plt.savefig(os.path.join(brain_dir, '02_india_voice_vs_data_traffic.png'))
        plt.close()
        print(f"    [OK] Saved {p2}")

    # 3. Technology Transition (2G/3G vs 4G vs 5G Share %)
    if df_q is not None:
        fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
        y_2g = df_q['share_2g_3g_traffic_pct']
        y_4g = df_q['share_4g_traffic_pct']
        y_5g = df_q['share_5g_traffic_pct']
        ax.stackplot(x, y_2g, y_4g, y_5g, labels=['Legacy 2G / 3G', '4G LTE', '5G New Radio (NR)'],
                     colors=['#aec7e8', '#1f77b4', '#ff7f0e'], alpha=0.85)
        ax.set_xticks(tick_indices)
        ax.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=9)
        ax.set_ylim(0, 100)
        ax.set_title('Evolution of Technology Traffic Share in India (2010 - 2024)\n2G/3G Phase-out -> 4G Dominance -> 5G Scaling', fontsize=12, fontweight='bold', pad=12)
        ax.set_xlabel('Quarter', fontsize=10, fontweight='bold')
        ax.set_ylabel('Traffic Share (%)', fontsize=10, fontweight='bold')
        ax.legend(loc='lower left', frameon=True)
        ax.grid(True, linestyle=':', alpha=0.5)
        plt.tight_layout()
        p3 = os.path.join(output_dir, 'eda_technology_transition_2g_to_5g.png')
        plt.savefig(p3)
        if os.path.exists(brain_dir): plt.savefig(os.path.join(brain_dir, '03_india_technology_share_evolution.png'))
        plt.close()
        print(f"    [OK] Saved {p3}")

    # 4. Circle-wise Traffic Distribution Across 22 LSAs
    if df_c is not None:
        df_c_latest = df_c[df_c['quarter'] == '2024-Q4'].sort_values(by='data_traffic_pb', ascending=True)
        fig, ax = plt.subplots(figsize=(10, 7.5), dpi=150)
        category_colors = {
            'Metro': '#d62728',
            'Category-A': '#1f77b4',
            'Category-B': '#2ca02c',
            'Category-C': '#ff7f0e'
        }
        bar_colors = [category_colors[cat] for cat in df_c_latest['circle_category']]
        bars = ax.barh(df_c_latest['circle_name'], df_c_latest['data_traffic_pb'], color=bar_colors, alpha=0.85)
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#d62728', label='Metro Circles (Delhi, Mumbai, Kolkata)'),
            Patch(facecolor='#1f77b4', label='Category A Circles (High Revenue / Tech)'),
            Patch(facecolor='#2ca02c', label='Category B Circles (High Population)'),
            Patch(facecolor='#ff7f0e', label='Category C Circles (Developing / Hilly)')
        ]
        ax.legend(handles=legend_elements, loc='lower right', frameon=True)
        ax.set_title('India Circle-Wise Quarterly Data Traffic Distribution (2024-Q4)\nAcross 22 Telecom Licensed Service Areas (LSAs)', fontsize=12, fontweight='bold', pad=12)
        ax.set_xlabel('Quarterly Wireless Data Usage (Petabytes)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Telecom Circle (LSA)', fontsize=10, fontweight='bold')
        ax.grid(True, linestyle=':', alpha=0.6, axis='x')
        plt.tight_layout()
        p4 = os.path.join(output_dir, 'eda_circle_wise_traffic_distribution.png')
        plt.savefig(p4)
        if os.path.exists(brain_dir): plt.savefig(os.path.join(brain_dir, '04_india_circle_traffic_distribution.png'))
        plt.close()
        print(f"    [OK] Saved {p4}")

    # 5. Feature Correlation Matrix
    fig, ax = plt.subplots(figsize=(8.5, 7), dpi=150)
    cols = ["data_usage", "active_users", "call_volume", "download_traffic", "upload_traffic", "latency", "packet_loss", "bandwidth_utilization"]
    cols_exist = [c for c in cols if c in df_proc.columns]
    corr = df_proc[cols_exist].corr().values
    cax = ax.matshow(corr, cmap='coolwarm', vmin=-1, vmax=1)
    fig.colorbar(cax)
    clean_labels = [c.replace('_', ' ').title() for c in cols_exist]
    ax.set_xticks(range(len(cols_exist)))
    ax.set_yticks(range(len(cols_exist)))
    ax.set_xticklabels(clean_labels, rotation=45, ha='left', fontsize=8.5)
    ax.set_yticklabels(clean_labels, fontsize=8.5)
    for i in range(len(cols_exist)):
        for j in range(len(cols_exist)):
            val = corr[i, j]
            ax.text(j, i, f"{val:.2f}", ha='center', va='center', color='black' if abs(val) < 0.6 else 'white', fontsize=8, fontweight='bold')
    plt.title('Feature Correlation Matrix (India Telemetry & Performance)\nKey Drivers for Downstream AI Forecasting Models', fontsize=11, fontweight='bold', pad=30)
    plt.tight_layout()
    p5 = os.path.join(output_dir, 'eda_correlation_matrix.png')
    plt.savefig(p5)
    if os.path.exists(brain_dir): plt.savefig(os.path.join(brain_dir, '05_india_telecom_correlation_matrix.png'))
    plt.close()
    print(f"    [OK] Saved {p5}")

    # 6. Monthly Seasonality and Long-Term Trend
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
    if 'timestamp' in df_proc.columns:
        df_proc['dt'] = pd.to_datetime(df_proc['timestamp'])
        nat_group = df_proc[df_proc['cell_id'] == 'Cell_004_National_Feed'].sort_values('dt')
        if not nat_group.empty:
            ax.plot(nat_group['dt'], nat_group['data_usage'], color='#9467bd', linewidth=2.2, label='Monthly National Data Volume (TB)')
            if 'rolling_mean_12' in nat_group.columns:
                ax.plot(nat_group['dt'], nat_group['rolling_mean_12'], color='#d62728', linestyle='--', linewidth=2.0, label='12-Month Moving Average Trend')
            ax.set_title('India Monthly Telecom Traffic Trend & 12-Month Seasonality (2010 - 2024)', fontsize=12, fontweight='bold', pad=12)
            ax.set_xlabel('Date (Monthly)', fontsize=10, fontweight='bold')
            ax.set_ylabel('Data Volume (Terabytes)', fontsize=10, fontweight='bold')
            ax.grid(True, linestyle=':', alpha=0.6)
            ax.legend(loc='upper left', frameon=True)
            plt.tight_layout()
            p6 = os.path.join(output_dir, 'eda_monthly_seasonality_and_trend.png')
            plt.savefig(p6)
            plt.close()
            print(f"    [OK] Saved {p6}")

    print("\n[OK] All 6 Official EDA Visualizations generated successfully.")

if __name__ == '__main__':
    generate_eda()
