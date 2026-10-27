import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import linregress
import numpy as np
import os

def evaluate_pump(pref_name):
    file_path = 'data/exported_data.csv'
    if not os.path.exists(file_path):
        return False
        
    df = pd.read_csv(file_path, parse_dates=['Time'])
    df = df[['Time', 'Pump in', 'Pump out']].dropna()
    df['Difference'] = np.abs(df['Pump in'] - df['Pump out'])

    baseline_period = df[df['Difference'].rolling(window=5*48).std() < 0.5]  
    baseline_mean = baseline_period['Difference'].mean()
    baseline_std = baseline_period['Difference'].std()

    upper_threshold = baseline_mean + 2 * baseline_std
    lower_threshold = baseline_mean - 2 * baseline_std

    os.makedirs('plots', exist_ok=True)
    
    plt.figure(figsize=(14, 7))
    plt.plot(df['Time'], df['Pump in'], label='Pump in', color='blue')
    plt.plot(df['Time'], df['Pump out'], label='Pump out', color='green')
    plt.xlabel('Time')
    plt.ylabel('Values')
    plt.title(f'Pump In and Pump Out Over Time - {pref_name}')
    plt.legend()
    plt.savefig(f'plots/pump_values_overlay_{pref_name}.png')
    plt.close()

    plt.figure(figsize=(14, 7))
    plt.plot(df['Time'], df['Difference'], label='Difference (Pump in - Pump out)', color='purple')
    plt.axhline(baseline_mean, color='blue', linestyle='--', label='Baseline Mean')
    plt.axhline(upper_threshold, color='red', linestyle='--', label='Upper Threshold')
    plt.axhline(lower_threshold, color='orange', linestyle='--', label='Lower Threshold')
    
    window_size = 5 * 48  
    for i in range(window_size, len(df)):
        x_vals = df['Time'].values[i - window_size:i]
        y_vals = df['Difference'].values[i - window_size:i]
        slope, intercept, _, _, _ = linregress(np.arange(window_size, dtype=float), y_vals)
        trend_line = slope * np.arange(window_size, dtype=float) + intercept
        plt.plot(x_vals, trend_line, color='orange', alpha=0.5)

    plt.xlabel('Time')
    plt.ylabel('Difference')
    plt.title(f'Difference Between Pump In and Pump Out - {pref_name}')
    plt.legend()
    plt.savefig(f'plots/pump_difference_{pref_name}.png')
    plt.close()

    df['DeviationCount'] = ((df['Difference'] > upper_threshold) | (df['Difference'] < lower_threshold)).rolling(window=5*48).sum()
    recent_data = df.tail(window_size)
    sustained_deviation = recent_data[recent_data['DeviationCount'] >= window_size]
    
    if not sustained_deviation.empty:
        sustained_deviation.to_csv(f'data/pump_sustained_deviation_{pref_name}.csv', index=False)
        return True
    return False