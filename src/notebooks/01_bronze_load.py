# Databricks notebook source

from py_auto_loader_class import BronzeLoader

dbutils.widgets.text("1_input_path","")
dbutils.widgets.text("2_output_path","")
dbutils.widgets.text("3_format_file","")
dbutils.widgets.text("4_checkpoint_path","")

input_path = dbutils.widgets.get("1_input_path")
print(f"1_input_path: {input_path}")

output_path = dbutils.widgets.get("2_output_path")
print(f"2_output_path: {output_path}")

format_file = dbutils.widgets.get("3_format_file")
print(f"3_format_file: {format_file}")

checkpoint_path = dbutils.widgets.get("4_checkpoint_path")
print(f"4_checkpoint_path: {checkpoint_path}")

bronze = BronzeLoader(
    input_path=input_path,
    checkpoint_path=checkpoint_path,
    format_file=format_file
    
)

df = bronze.read_autoloader()
if "strava/athlete/" not in input_path:
    df = bronze.get_athlete_id_column(df)

df = bronze.get_ingestion_time_column(df)

bronze.write_to_bronze(
    df,
    output_path=output_path
)