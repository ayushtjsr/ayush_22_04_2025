import os
import csv
import uuid
import shutil
import zipfile
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, String, Enum, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.declarative import declared_attr
from enum import Enum as PyEnum
import pytz

# Setup paths and app
os.makedirs("data_ayush", exist_ok=True)
os.makedirs("reports_ayush", exist_ok=True)
app = FastAPI(title="Ayush's Restaurant Monitoring API")

# Database setup
DATABASE_URL = "sqlite:///./store-monitoring-data.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enum for status class
class ReportStatus(PyEnum):
    RUNNING = "Running"
    COMPLETE = "Complete"

# Report status table
class Report(Base):
    __tablename__ = "report_status_ayush"

    report_id = Column(String, primary_key=True, index=True)
    status = Column(Enum(ReportStatus), default=ReportStatus.RUNNING)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    report_path = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)

# Helper function to extract data
@app.on_event("startup")
def load_data():
    zip_path = "store-monitoring-data.zip"
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("data_ayush")

# Improved interpolation logic

def calculate_uptime_downtime(status_df, business_hours_df, tz_df, now):
    report_data = []
    status_df['timestamp_utc'] = pd.to_datetime(status_df['timestamp_utc'])

    for store_id, store_status in status_df.groupby("store_id"):
        store_timezone = tz_df[tz_df['store_id'] == store_id]['timezone_str'].values
        tz_str = store_timezone[0] if len(store_timezone) > 0 else 'America/Chicago'
        tz = pytz.timezone(tz_str)

        business_hours = business_hours_df[business_hours_df['store_id'] == store_id]

        def get_intervals(period_hours):
            interval_start = now - timedelta(hours=period_hours)
            intervals = []
            current = interval_start
            while current < now:
                local_time = current.astimezone(tz)
                day = local_time.weekday()
                hours = business_hours[business_hours['dayOfWeek'] == day]
                if hours.empty:
                    intervals.append((current, min(current + timedelta(hours=1), now)))
                else:
                    for _, row in hours.iterrows():
                        start = tz.localize(datetime.combine(local_time.date(), pd.to_datetime(row['start_time_local']).time())).astimezone(pytz.utc)
                        end = tz.localize(datetime.combine(local_time.date(), pd.to_datetime(row['end_time_local']).time())).astimezone(pytz.utc)
                        if start < now and end > interval_start:
                            intervals.append((max(start, interval_start), min(end, now)))
                current += timedelta(days=1)
            return intervals

        def interpolate(intervals):
            total_uptime = total_downtime = 0
            for start, end in intervals:
                subset = store_status[(store_status['timestamp_utc'] >= start) & (store_status['timestamp_utc'] <= end)]
                if subset.empty:
                    continue
                sorted_subset = subset.sort_values('timestamp_utc')
                last_time = start
                for i, row in sorted_subset.iterrows():
                    duration = (row['timestamp_utc'] - last_time).total_seconds() / 60
                    if row['status'] == 'active':
                        total_uptime += duration
                    else:
                        total_downtime += duration
                    last_time = row['timestamp_utc']
                final_duration = (end - last_time).total_seconds() / 60
                if sorted_subset.iloc[-1]['status'] == 'active':
                    total_uptime += final_duration
                else:
                    total_downtime += final_duration
            return total_uptime, total_downtime

        intervals_1h = get_intervals(1)
        intervals_24h = get_intervals(24)
        intervals_7d = get_intervals(24 * 7)

        uptime_1h, downtime_1h = interpolate(intervals_1h)
        uptime_24h, downtime_24h = interpolate(intervals_24h)
        uptime_7d, downtime_7d = interpolate(intervals_7d)

        report_data.append({
            "store_id": store_id,
            "uptime_last_hour": round(uptime_1h, 2),
            "uptime_last_day": round(uptime_24h / 60, 2),
            "update_last_week": round(uptime_7d / 60, 2),
            "downtime_last_hour": round(downtime_1h, 2),
            "downtime_last_day": round(downtime_24h / 60, 2),
            "downtime_last_week": round(downtime_7d / 60, 2),
        })
    return report_data

# Report generation logic

def generate_report(report_id: str):
    session = SessionLocal()
    try:
        status_df = pd.read_csv("store-monitoring-data/store_status.csv")
        hours_df = pd.read_csv("store-monitoring-data/menu_hours.csv")
        tz_df = pd.read_csv("store-monitoring-data/timezones.csv")

        status_df['timestamp_utc'] = pd.to_datetime(status_df['timestamp_utc'])
        now = status_df['timestamp_utc'].max()

        report_data = calculate_uptime_downtime(status_df, hours_df, tz_df, now)

        output_path = f"reports_ayush/{report_id}.csv"
        keys = report_data[0].keys()
        with open(output_path, "w", newline="") as f:
            dict_writer = csv.DictWriter(f, keys)
            dict_writer.writeheader()
            dict_writer.writerows(report_data)

        report = session.query(Report).filter_by(report_id=report_id).first()
        report.status = ReportStatus.COMPLETE
        report.completed_at = datetime.utcnow()
        report.report_path = output_path
        session.commit()
    finally:
        session.close()

@app.post("/trigger_report")
def trigger_report(background_tasks: BackgroundTasks):
    report_id = str(uuid.uuid4())
    session = SessionLocal()
    try:
        new_report = Report(report_id=report_id, status=ReportStatus.RUNNING)
        session.add(new_report)
        session.commit()
    finally:
        session.close()

    background_tasks.add_task(generate_report, report_id)
    return {"report_id": report_id}

@app.get("/get_report")
def get_report(report_id: str):
    session = SessionLocal()
    try:
        report = session.query(Report).filter_by(report_id=report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        if report.status == ReportStatus.RUNNING:
            return {"status": "Running"}
        return FileResponse(path=report.report_path, filename=f"{report_id}.csv", media_type='text/csv')
    finally:
        session.close()
