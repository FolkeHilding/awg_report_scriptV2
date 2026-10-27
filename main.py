import os
import csv
import re
import boto3
import time
import argparse
from pathlib import Path
from datetime import datetime

# --- NATIVE IMPORTS ---
from fetch_info import get_info_list
from fetch_data import fetch_data, fetch_additional_data
from pdf_gen import create_pdf_with_plots
from send_email import send_email as send_ses_email
from process_pbf import evaluate_pbf
from process_pump import evaluate_pump
from process_rh import evaluate_rh


def cleanup_old_files(directory, days_to_keep):
    print(f"Cleaning up files older than {days_to_keep} days in '{directory}'...")
    time_threshold = time.time() - (days_to_keep * 86400)
    
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return

    for file_path in dir_path.iterdir():
        if file_path.is_file():
            try:
                if file_path.stat().st_mtime < time_threshold:
                    file_path.unlink()
            except FileNotFoundError:
                continue

def modify_prefName(prefName):
    clean_prefName = prefName.replace(" ", "_")
    clean_prefName = re.sub(r'[^\x00-\x7F]+', '', prefName)
    clean_prefName = re.sub(r'[^A-Za-z0-9_]', '', prefName)
    return clean_prefName

def upload_to_s3(test_mode=False):
    """Back up generated files to S3."""
    if test_mode:
        print("⚠️ TEST MODE: Skipping S3 upload to keep test files out of production bucket.")
        return

    bucket_name = "awg-machine-reports-prod"  # <-- Updated to your new bucket!
    s3_client = boto3.client('s3', region_name='eu-north-1')
    directories = ["data", "plots", "logs", "pdf", "reports"]

    print(f"Starting upload to S3 bucket: {bucket_name}...")
    for directory in directories:
        if not os.path.exists(directory):
            continue
        for root, dirs, files in os.walk(directory):
            for file in files:
                local_path = os.path.join(root, file)
                # Ensure correct forward slash formatting for S3 keys regardless of OS
                s3_key = local_path.replace("\\", "/")
                try:
                    s3_client.upload_file(local_path, bucket_name, s3_key)
                    print(f" Uploaded {local_path} to s3://{bucket_name}/{s3_key}")
                except Exception as e:
                    print(f" Failed to upload {local_path}: {e}")
    print("S3 upload complete.")

def write_summary_csv(all_machines_data):
    if not all_machines_data:
        return None
    
    output_dir = "reports"
    os.makedirs(output_dir, exist_ok=True)
    curr_date = datetime.now().strftime("%Y-%m-%d")
    output_filename = os.path.join(output_dir, f"weekly_summary_{curr_date}.csv")
    
    with open(output_filename, "w", newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=all_machines_data[0].keys())
        writer.writeheader()
        writer.writerows(all_machines_data)

    return output_filename

def summarize_csv_data(csv_file, pref_name, uptime_percentage, model):
    water_in_hour, energy_hour, rh_in_values, temp_in_values = [], [], [], []

    with open(csv_file, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row.get("WaterInHour"):
                try: water_in_hour.append(float(row["WaterInHour"]))
                except ValueError: pass
            if row.get("EnergyHour"):
                try: energy_hour.append(float(row["EnergyHour"]))
                except ValueError: pass
            if row.get("RHin"):
                try:
                    val = float(row["RHin"])
                    if val > 0: rh_in_values.append(val)
                except ValueError: pass
            if row.get("TempIn"):
                try:
                    val = float(row["TempIn"])
                    if val != 0: temp_in_values.append(val)
                except ValueError: pass

    total_water = sum(water_in_hour) if water_in_hour else 0
    total_energy = sum(energy_hour) if energy_hour else 0
    avg_rh = sum(rh_in_values) / len(rh_in_values) if rh_in_values else 0
    avg_temp = sum(temp_in_values) / len(temp_in_values) if temp_in_values else 0
    co2 = (total_water * 4 - total_energy) * 0.309 if total_water > 0 else 0

    water_summary = {"average": total_water/len(water_in_hour) if water_in_hour else 0, "min": min(water_in_hour) if water_in_hour else 0, "max": max(water_in_hour) if water_in_hour else 0}
    energy_summary = {"average": total_energy/len(energy_hour) if energy_hour else 0, "min": min(energy_hour) if energy_hour else 0, "max": max(energy_hour) if energy_hour else 0}

    summary_text = (
        f"Weekly Report for: {pref_name}\n"
        f"--------------------------------------\n"
        f"Machine Uptime: {uptime_percentage:.2f}%\n"
        f"Total Water Removed: {total_water:.2f} liters\n"
        f"Total Energy Consumption: {total_energy:.2f} kWh\n"
        f"Estimated CO2 Savings: {co2:.2f} kg\n\n"
        f"Average RH In: {avg_rh:.2f}%\n"
        f"Average Temp In: {avg_temp:.2f} C\n" 
    )
    
    summary_data = {
        "Machine": pref_name,
        "Model": model,
        "Uptime (%)": f"{uptime_percentage:.2f}",
        "Total Water Removed (liters)": f"{total_water:.2f}",
        "Total Energy Consumption (kWh)": f"{total_energy:.2f}",
        "Estimated CO2 Savings (kg)": f"{co2:.2f}",
        "Average RH In (%)": f"{avg_rh:.2f}",
        "Average Temp In (C)": f"{avg_temp:.2f}", 
        "Avg Hourly Water (liters/hr)": f"{water_summary['average']:.2f}",
        "Min Hourly Water (liters/hr)": f"{water_summary['min']:.2f}",
        "Max Hourly Water (liters/hr)": f"{water_summary['max']:.2f}",
        "Avg Hourly Energy (kWh/hr)": f"{energy_summary['average']:.2f}",
        "Min Hourly Energy (kWh/hr)": f"{energy_summary['min']:.2f}",
        "Max Hourly Energy (kWh/hr)": f"{energy_summary['max']:.2f}",
    }
    return summary_text, summary_data

def daily_run(days, model, pref_name, receiver_emails):
    fetch_data(days, model)
    
    # Process alerts natively
    plot_files = []
    if evaluate_pbf(pref_name):
        plot_files.append(f"plots/pbf_predictions_{pref_name}.png")
    if evaluate_pump(pref_name):
        plot_files.extend([f"plots/pump_values_overlay_{pref_name}.png", f"plots/pump_difference_{pref_name}.png"])
    if evaluate_rh(pref_name):
        plot_files.extend([f"plots/rh_values_overlay_{pref_name}.png", f"plots/rh_difference_{pref_name}.png"])

    if plot_files:
        for plot in plot_files:
            send_ses_email(receiver_emails, "System Alert", f"The model: {pref_name} raised an alert.", plot)

def weekly_run(model, pref_name, receiver_emails):
    cleanup_old_files(directory="pdf/", days_to_keep=30)
    
    fetch_data(7, model)
    evaluate_pbf(pref_name)
    evaluate_pump(pref_name)
    evaluate_rh(pref_name)

    plot_files = [
        f"plots/pbf_predictions_{pref_name}.png",
        f"plots/pump_values_overlay_{pref_name}.png",
        f"plots/pump_difference_{pref_name}.png",
        f"plots/rh_values_overlay_{pref_name}.png",
        f"plots/rh_difference_{pref_name}.png"
    ]

    # Native Uptime variable returned straight from fetch_data.py
    uptime = fetch_additional_data(7, model)
    
    summary_text, summary_data = summarize_csv_data(f"data/additional_data_{model}.csv", pref_name, uptime, model)
    pdf_path = create_pdf_with_plots(plot_files, summary_data, pref_name, model)
    
    send_ses_email(receiver_emails, "Weekly Report: Plots and Summary", summary_text, pdf_path)
    return summary_data

def main(days, weekly, test_model=None, test_email=None):
    combined_list = get_info_list()
    all_machines_summary = []
    
    # Base summary recipients
    summary_recipients = ["folke.hilding@airwatergreen.com", "david.johansson@airwatergreen.com", "Johan.jonsson@airwatergreen.com"] 
    
    # Intercept summary emails if testing
    if test_email:
        print(f"\n TEST MODE: Diverting Final Summary Email")
        print(f"   Original: {summary_recipients}")
        print(f"   Diverted to: [{test_email}]\n")
        summary_recipients = [test_email]

    for item in combined_list:
        if isinstance(item, str) and item.strip().upper().startswith('NEXTV'):
            components = item.split(', ')
            model = components[0]
            
            # If testing a single model, skip the rest
            if test_model and model != test_model:
                continue

            pref_name = components[1]
            real_emails = components[2:]
            clean_prefName = modify_prefName(pref_name)

            # Intercept machine-specific emails if testing
            active_emails = real_emails
            if test_email:
                print(f"   TEST MODE ({model}): Diverting emails")
                print(f"   Original: {real_emails}")
                print(f"   Diverted to: [{test_email}]")
                active_emails = [test_email]

            if weekly:
                data = weekly_run(model, clean_prefName, active_emails)
                if data: all_machines_summary.append(data)
            else:
                daily_run(days, model, clean_prefName, active_emails)

    if weekly:
        csv_filepath = write_summary_csv(all_machines_summary)
        if csv_filepath: 
            send_ses_email(summary_recipients, f"Weekly Machine Performance Summary - {datetime.now().strftime('%Y-%m-%d')}", "Please find the weekly machine performance summary attached.", csv_filepath)
            
    # If a test_email is provided, we assume test mode and skip pushing to S3
    is_test_mode = bool(test_email or test_model)
    upload_to_s3(test_mode=is_test_mode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--weekly", action="store_true")
    parser.add_argument("--test_model", type=str, help="Run a test for a single model ID")
    parser.add_argument("--test_email", type=str, help="Divert ALL emails to this address for testing")
    args = parser.parse_args()

    main(args.days, args.weekly, args.test_model, args.test_email)