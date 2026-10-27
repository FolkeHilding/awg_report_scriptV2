import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import linregress
import numpy as np
import os

def evaluate_rh(pref_name):
    file_path = 'data/exported_data.csv'
    if not os.path.exists(file_path):
        return False
        
    df = pd.read_csv(file_path, parse_dates=['Time'])
    df = df[['Time', 'RHeq', 'RHout', 'CircPump']].dropna()
    filtered_df = df[df['CircPump'] == 1].copy()
    if filtered_df.empty:
        return False
        
    filtered_df['Difference'] = np.abs(filtered_df['RHout'] - filtered_df['RHeq'])

    baseline_period = filtered_df[filtered_df['Difference'].rolling(window=5*48).std() < 0.5]
    baseline_mean = baseline_period['Difference'].mean()
    baseline_std = baseline_period['Difference'].std()

    upper_threshold = baseline_mean + 2 * baseline_std
    lower_threshold = baseline_mean - 2 * baseline_std

    os.makedirs('plots', exist_ok=True)
    
    plt.figure(figsize=(14, 7))
    plt.plot(filtered_df['Time'], filtered_df['RHeq'], label='RHeq', color='blue')
    plt.plot(filtered_df['Time'], filtered_df['RHout'], label='RHout', color='green')
    plt.xlabel('Time')
    plt.ylabel('Values')
    plt.title(f'RHeq and RHout Over Time - {pref_name}')
    plt.legend()
    plt.savefig(f'plots/rh_values_overlay_{pref_name}.png')
    plt.close()

    plt.figure(figsize=(14, 7))
    plt.plot(filtered_df['Time'], filtered_df['Difference'], label='Difference (RHeq - RHout)', color='purple')
    plt.axhline(baseline_mean, color='blue', linestyle='--', label='Baseline Mean')
    plt.axhline(upper_threshold, color='red', linestyle='--', label='Upper Threshold')
    plt.axhline(lower_threshold, color='orange', linestyle='--', label='Lower Threshold')
    
    window_size = 5 * 48
    shorten_by = 55
    for i in range(window_size, len(filtered_df)):
        x_vals = filtered_df['Time'].values[i - window_size:i]
        y_vals = filtered_df['Difference'].values[i - window_size:i]
        if len(y_vals) > shorten_by:
            slope, intercept, _, _, _ = linregress(np.arange(shorten_by, dtype=float), y_vals[-shorten_by:])
            trend_line = slope * np.arange(shorten_by, dtype=float) + intercept
            plt.plot(x_vals[-shorten_by:], trend_line, color='orange', alpha=0.5)

    plt.xlabel('Time')
    plt.ylabel('Difference')
    plt.title(f'Difference Between RHeq and RHout - {pref_name}')
    plt.legend()
    plt.savefig(f'plots/rh_difference_{pref_name}.png')
    plt.close()

    filtered_df['DeviationCount'] = ((filtered_df['Difference'] > upper_threshold) | (filtered_df['Difference'] < lower_threshold)).rolling(window=5*48).sum()
    recent_data = filtered_df.tail(window_size)
    sustained_deviation = recent_data[recent_data['DeviationCount'] >= window_size]

    if not sustained_deviation.empty:
        sustained_deviation.to_csv(f'data/sustained_deviation_{pref_name}.csv', index=False)
        return True
    return False