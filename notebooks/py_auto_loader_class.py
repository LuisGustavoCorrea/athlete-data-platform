from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, col
from pyspark.sql import Row
print('start')

class BronzeLoader:
    def __init__(self, input_path, checkpoint_path, format_file):
        self.spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        self.input_path = input_path
        self.checkpoint_path = checkpoint_path
        self.format_file = format_file

    def read_autoloader(self, schema=None):
        df = (self.spark.readStream
              .format("cloudFiles")
              .option("cloudFiles.format", self.format_file)
              .option("cloudFiles.inferColumnTypes", "true")
              .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
              .option("cloudFiles.schemaLocation", self.checkpoint_path)
              .load(self.input_path))
        return df if not schema else df.selectExpr(*schema)

    def standardize_columns(self, df):
        return (df
                .withColumn("athlete_id", col("athlete.id"))
                .withColumn("ingestion_timestamp", current_timestamp()))

    def write_to_bronze(self, df, output_path, await_termination=True):
        query = (df.writeStream
                 .format("delta")
                 .option("checkpointLocation", self.checkpoint_path)
                 .option("mergeSchema", "true")
                 .outputMode("append")
                 .queryName("bronze_loader")  # nome do stream p/ monitorar
                 .trigger(availableNow=True)
                 .start(output_path))
        
        query.awaitTermination()
        progress = query.lastProgress

        log = Row(
            batchId = progress["batchId"],
            inputRows = progress["numInputRows"],
            outputRows = progress["sink"]["numOutputRows"],
            timestamp = progress["timestamp"]
        )

        # print para logs do job
        print(f"[BronzeLoader] Batch {log.batchId} | In: {log.inputRows} | Out: {log.outputRows} | TS: {log.timestamp}")
