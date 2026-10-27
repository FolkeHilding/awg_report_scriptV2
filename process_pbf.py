import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import linregress
import numpy as np
import os

def evaluate_pbf(pref_name):
    file_path = 'data/exported_data.csv'
    if not os.path.exists(file_path):
        return False
        
    df = pd.read_csv(file_path, parse_dates=['Time']).dropna()
    filtered_df = df[df['CircPump'] == 1].copy()
    
    if filtered_df.empty:
        return False

    slope_filtered, intercept_filtered, _, _, _ = linregress(range(len(filtered_df)), filtered_df['PBF'])
    
    baseline_period = filtered_df[filtered_df['PBF'].rolling(window=5*48).std() < 0.5]  
    baseline_mean = baseline_period['PBF'].mean()
    baseline_std = baseline_period['PBF'].std()

    upper_threshold = baseline_mean + 2 * baseline_std
    lower_threshold = baseline_mean - 2 * baseline_std

    plt.figure(figsize=(14, 7))
    plt.plot(filtered_df['Time'], filtered_df['PBF'], label='PBF (CircPump = 1)', color='green')
    plt.axhline(baseline_mean, color='blue', linestyle='--', label='Baseline Mean')
    plt.axhline(upper_threshold, color='red', linestyle='--', label='Upper Threshold')
    plt.axhline(lower_threshold, color='black', linestyle='--', label='Lower Threshold')
    
    window_size = 5 * 48  
    for i in range(window_size, len(filtered_df)):
        x_vals = filtered_df['Time'].values[i - window_size:i]
        y_vals = filtered_df['PBF'].values[i - window_size:i]
        slope, intercept, _, _, _ = linregress(np.arange(window_size), y_vals)
        trend_line = slope * np.arange(window_size) + intercept
        plt.plot(x_vals, trend_line, color='orange', alpha=0.5)

    plt.xlabel('Time')
    plt.ylabel('PBF')
    plt.title(f'PBF Over Time with Thresholds - {pref_name}')
    plt.legend()
    
    os.makedirs('plots', exist_ok=True)
    plot_file = f'plots/pbf_predictions_{pref_name}.png'
    plt.savefig(plot_file)
    plt.close()
    
    filtered_df['DeviationCount'] = ((filtered_df['PBF'] > upper_threshold) | (filtered_df['PBF'] < lower_threshold)).rolling(window=5*48).sum()

    recent_data = filtered_df.tail(window_size)
    sustained_deviation = recent_data[recent_data['DeviationCount'] >= window_size]
    
    if not sustained_deviation.empty:
        sustained_deviation.to_csv(f'data/PBF_sustained_deviation_{pref_name}.csv', index=False)
        return True
    return False