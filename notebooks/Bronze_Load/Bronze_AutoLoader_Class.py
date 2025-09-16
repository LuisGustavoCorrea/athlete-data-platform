# Databricks notebook source
from pyspark.sql.functions import current_timestamp
from pyspark.sql.functions import col

class BronzeLoader:
    def __init__(self, input_path, checkpoint_path, format_file):
        self.input_path = input_path
        self.checkpoint_path = checkpoint_path
        self.format_file = format_file

    def read_autoloader(self, schema=None):
        df = (spark.readStream
              .format("cloudFiles")
              .option("cloudFiles.format", self.format_file)
              .option("cloudFiles.inferColumnTypes", "true")
              .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
              .option("cloudFiles.schemaLocation", self.checkpoint_path)
              .load(self.input_path)
             )
        return df if not schema else df.selectExpr(*schema)

    def standardize_columns(self, df):
        return (df
                .withColumn("athlete_id", col("athlete.id"))
                .withColumn("ingestion_timestamp", current_timestamp())
               )
    
    def write_to_bronze(self, df, output_path):
        return (df.writeStream
              .format("delta")  # <-- aqui muda
              .option("checkpointLocation", self.checkpoint_path)
              .option("mergeSchema", "true")
              .outputMode("append")
              .trigger(availableNow=True)
              .start(output_path)
           )
