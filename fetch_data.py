import os
import argparse
import boto3
import json
import pandas as pd
from sqlalchemy import create_engine

DATA_PATH = "data"
os.makedirs(DATA_PATH, exist_ok=True)

def get_db_engine():
    """Fetches RDS credentials and returns a SQLAlchemy Postgres engine."""
    secret_arn = os.environ.get("RDS_SECRET_ARN")
    if not secret_arn:
        raise ValueError("RDS_SECRET_ARN environment variable is not set.")
    
    client = boto3.client('secretsmanager', region_name='eu-north-1')
    secret = json.loads(client.get_secret_value(SecretId=secret_arn)['SecretString'])
    
    # NEW: Override host for local SSM tunnel testing, otherwise default to AWS Secret host
    host = os.environ.get("DB_HOST_OVERRIDE", secret['host'])
    
    user = secret['username']
    password = secret['password']
    port = secret['port']
    dbname = secret['dbname']
    
    engine_str = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(engine_str)

def fetch_data(days, model):
    engine = get_db_engine()
    query = f"""
    SELECT
        to_timestamp(floor((extract('epoch' from recorded_at) / 1800)) * 1800) AS "Time",
        AVG(rh_eq) AS "RHeq",
        AVG(rh_out) AS "RHout",
        AVG(boiler_in_pump_on::int) AS "Pump in",
        AVG(boiler_out_pump_on::int) AS "Pump out",
        AVG(conc_boiler) AS "ConcBoiler",
        AVG(level_tank) AS "TankLevel",
        AVG(conc_absorber) AS "ConcAbsorber",
        AVG(pressure_before_filter) AS "PBF",
        AVG(circ_pump_on::int) AS "CircPump"
    FROM device
    WHERE device_id = '{model}'
      AND recorded_at >= NOW() - INTERVAL '{days} days'
    GROUP BY "Time"
    ORDER BY "Time"
    """
    df = pd.read_sql(query, engine)
    
    if not df.empty:
        df.set_index('Time', inplace=True)
        df = df.resample('30min').asfreq()
        df.reset_index(inplace=True)
        # Format explicitly to match InfluxDB ISO8601 strings
        df['Time'] = df['Time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        
    df.to_csv(os.path.join(DATA_PATH, "exported_data.csv"), index=False)

def fetch_additional_data(days, model):
    engine = get_db_engine()
    
    # --- Uptime Calculation (7 days) ---
    uptime_query = f"""
    SELECT to_timestamp(floor((extract('epoch' from recorded_at) / 3600)) * 3600) AS time_bucket
    FROM device
    WHERE device_id = '{model}' 
      AND recorded_at >= NOW() - INTERVAL '7 days'
      AND rh_eq IS NOT NULL
    GROUP BY time_bucket
    """
    uptime_df = pd.read_sql(uptime_query, engine)
    uptime_percentage = (len(uptime_df) / 168) * 100 if len(uptime_df) > 0 else 0
    
    # --- Hourly Data CSV (Using device_hourly + device tables) ---
    hourly_query = f"""
    SELECT 
        dh.recorded_at AS "Time",
        dh.water_in_hour AS "WaterInHour",
        dh.energy_hour AS "EnergyHour",
        (
            SELECT AVG(rh_in) 
            FROM device d 
            WHERE d.device_id = dh.device_id 
              AND d.recorded_at >= dh.recorded_at 
              AND d.recorded_at < dh.recorded_at + INTERVAL '1 hour'
        ) AS "RHin",
        (
            SELECT AVG(temp_in) 
            FROM device d 
            WHERE d.device_id = dh.device_id 
              AND d.recorded_at >= dh.recorded_at 
              AND d.recorded_at < dh.recorded_at + INTERVAL '1 hour'
        ) AS "TempIn"
    FROM device_hourly dh
    WHERE dh.device_id = '{model}' 
      AND dh.recorded_at >= NOW() - INTERVAL '{days} days'
    ORDER BY dh.recorded_at
    """
    df_hourly = pd.read_sql(hourly_query, engine)
    
    if not df_hourly.empty:
        df_hourly.set_index('Time', inplace=True)
        df_hourly = df_hourly.resample('1h').asfreq().fillna(0)
        df_hourly.reset_index(inplace=True)
        # Format explicitly to match InfluxDB ISO8601 strings
        df_hourly['Time'] = df_hourly['Time'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        
    df_hourly.to_csv(os.path.join(DATA_PATH, f"additional_data_{model}.csv"), index=False)
    
    return uptime_percentage