import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
import csv

def _draw_row(c, y, label, value, label_x=100, value_x=290):
    c.setFont("Helvetica", 12)
    c.setFillColor(HexColor('#000000'))
    c.drawString(label_x, y, label)
    c.drawString(value_x, y, str(value))

def create_rh_in_plot(pref_name, model):
    data_file = f"data/additional_data_{model}.csv"
    timestamps = []
    rh_in_values = []

    if not os.path.exists(data_file):
        return None

    with open(data_file, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        if 'RHin' not in reader.fieldnames:
            return None
            
        for row in reader:
            try:
                dt_str = row['Time'].replace("Z", "")
                timestamps.append(datetime.fromisoformat(dt_str))
                rh_in = row.get('RHin')
                val = float(rh_in) if rh_in and rh_in != 'None' else np.nan
                rh_in_values.append(val)
            except ValueError:
                continue

    if not timestamps:
        return None

    plt.figure(figsize=(10, 5))
    ax = plt.gca()
    ax.set_facecolor('#f7f7f7')
    plt.grid(True, color='#e0e0e0', linestyle='-', linewidth=0.5)
    plt.plot(timestamps, rh_in_values, linestyle='-', color='#1f77b4', linewidth=1.5, label='RH In (%)')
    plt.xlabel("Time", fontsize=10, fontweight="bold")
    plt.ylabel("Relative Humidity In (%)", fontsize=10, fontweight="bold")
    plt.title(f"Incoming Air Humidity (RH In) for {pref_name}", fontsize=12, fontweight="bold")
    plt.xticks(rotation=45)
    plt.tight_layout()

    os.makedirs("plots", exist_ok=True)
    plot_path = f"plots/temp_rh_in_{pref_name}.png"
    plt.savefig(plot_path, dpi=200, bbox_inches='tight')
    plt.close()
    return plot_path

def create_pdf_with_plots(plot_files, summary_data, pref_name, model, output_dir="pdf"):
    os.makedirs(output_dir, exist_ok=True)
    curr_date = datetime.now()
    start_date = curr_date - timedelta(days=7)
    
    date_str = curr_date.strftime("%Y-%m-%d")
    output_filename = f"weekly_{pref_name}_{date_str}.pdf"
    pdf_path = os.path.join(output_dir, output_filename)
    
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter

    logo_path = 'awg_logo.jpg' 
    if os.path.exists(logo_path):
        c.drawImage(logo_path, width - 122, height - 72, width=100, height=50, preserveAspectRatio=True, mask='auto')

    c.setFont("Helvetica-Bold", 18)
    c.drawString(100, 750, f"Report for: {pref_name}")
    
    start_str = start_date.strftime('%d %b %Y')
    end_str = curr_date.strftime('%d %b %Y')
    
    c.setFont("Helvetica", 12)
    # BUG FIXED: Replaced the \n that causes reportlab to crash
    c.drawString(100, 730, f"Period: {start_str} - {end_str}") 

    c.setFont("Helvetica-Bold", 14)
    y = 700
    c.drawString(100, y, "Machine Performance")
    y -= 25

    def get_int(key):
        try: return f"{int(float(summary_data.get(key, '0')))}"
        except: return "0"
            
    def get_float(key):
        try: return f"{float(summary_data.get(key, '0')):.1f}"
        except: return "0.0"

    uptime = get_int('Uptime (%)')
    water = get_int('Total Water Removed (liters)')
    energy = get_int('Total Energy Consumption (kWh)')
    co2 = get_int('Estimated CO2 Savings (kg)')
    rh_avg = get_float('Average RH In (%)')
    temp_avg = get_float('Average Temp In (C)') 

    _draw_row(c, y, "Machine Uptime:", f"{uptime}%")
    y -= 18
    _draw_row(c, y, "Total Water Removed:", f"{water} liters")
    y -= 18
    _draw_row(c, y, "Total Energy Consumption:", f"{energy} kWh")
    y -= 18
    _draw_row(c, y, "Estimated CO2 Savings:", f"{co2} kg")
    y -= 18

    w_avg = get_int('Avg Hourly Water (liters/hr)')
    w_min = get_int('Min Hourly Water (liters/hr)')
    w_max = get_int('Max Hourly Water (liters/hr)')
    
    e_avg = get_int('Avg Hourly Energy (kWh/hr)')
    e_min = get_int('Min Hourly Energy (kWh/hr)')
    e_max = get_int('Max Hourly Energy (kWh/hr)')

    _draw_row(c, y, "Hourly Water (l):", f"Avg {w_avg}, Min {w_min}, Max {w_max}")
    y -= 18
    _draw_row(c, y, "Hourly Energy (kWh):", f"Avg {e_avg}, Min {e_min}, Max {e_max}")
    y -= 18
    _draw_row(c, y, "Average RH In:", f"{rh_avg}%")
    y -= 18 
    _draw_row(c, y, "Average Temp In:", f"{temp_avg} \xb0C")
    y -= 25 

    rh_in_plot_path = create_rh_in_plot(pref_name, model)
    if rh_in_plot_path:
        image_height = 260
        c.drawImage(rh_in_plot_path, 100, y - image_height, width=400, height=image_height, preserveAspectRatio=True, anchor='c')
        y -= (image_height + 20)
        try: os.remove(rh_in_plot_path)
        except OSError: pass

    c.showPage()
    y = 750 
        
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, y, "Hardware Performance")
    y -= 25

    max_image_height = 260
    max_image_width = 400
    image_spacing = 20

    for plot_file in plot_files:
        if os.path.exists(plot_file):
            if y - max_image_height < 50:
                c.showPage()
                y = 750
            c.drawImage(plot_file, 100, y - max_image_height, width=max_image_width, height=max_image_height, preserveAspectRatio=True, anchor='c')
            y -= (max_image_height + image_spacing)
    
    c.save()
    return pdf_path