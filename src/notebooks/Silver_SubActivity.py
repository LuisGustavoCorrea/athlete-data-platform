# Databricks notebook source

from pyspark.sql import functions as F, Window
from delta.tables import DeltaTable
from py_functions_silver import *
from pyspark.sql.functions import current_timestamp
from dataquality_rules_strava import *
from pyspark.sql import Row


BRONZE = "uc_athlete_data.bronze.strava_sub_activity"
CHECKPOINT = "abfss://silver@adlsathlete.dfs.core.windows.net/strava/sub_activity/sub_activity_checkpoint/"

# chave(s) de negócio — mude p/ composto se precisar, ex.: ["activity_id","lap_index"]
BUSINESS_KEYS = ["athlete_id","id"]
# colunas de ordenação para decidir o “vencedor” nos duplicados do micro-lote
ORDER_COLS = ["ingestion_timestamp"]  # adicione "updated_at" se existir

config = get_rules_subactivity()
rules = config["rules"]
reject_table = config["reject_table"]

# COMMAND ----------
# --- Compose (aplica tudo que você mostrou) -----------------------------------

def apply_all_silver_calcs(df: DataFrame,
                           *,
                           start_date_col: str = "start_date",
                           ) -> DataFrame:
    """
    Aplica TODAS as transformações do snippet original.
    Retorna um novo DataFrame com:
      - start_date (date)
    """
    return (
        df
        .transform(lambda d: add_start_date(d, src_col=start_date_col, out_col="start_date"))        
    )

# COMMAND ----------
def upsert_data(microBatchDF, batch):
    microBatchDF.createOrReplaceTempView("sub_activities_microbatch")
    
    sql_query = """
                MERGE INTO uc_athlete_data.silver.strava_sub_activity A
                USING sub_activities_microbatch  B
                ON A.athlete_id = b.athlete_id
                   AND A.ID = B.ID
                   AND A.START_DATE = B.START_DATE
                WHEN NOT MATCHED THEN INSERT * 
                """  

    microBatchDF.sparkSession.sql(sql_query)
# COMMAND ----------
def load_data(microBatchDF, batch):   
    
    microBatchDF = dedupe_microbatch(microBatchDF,BUSINESS_KEYS,ORDER_COLS)
    print("dedup ok ")
    microBatchDF = apply_all_silver_calcs(microBatchDF)
    print("calcs ok ")
    df_clean = assert_quality(microBatchDF,rules,reject_table)
    print("clean ok ")
    df_clean = add_silver_ingestion_time(df_clean)
    upsert_data(df_clean, batch)
    print("upsert ok ")
# COMMAND ----------

bronze_stream = spark.readStream.table(BRONZE)

query = (bronze_stream.writeStream
                 .foreachBatch(load_data)
                 .option("checkpointLocation", CHECKPOINT)
                 .trigger(availableNow=True)
                 .start())
                 
query.awaitTermination()
progress = query.lastProgress

log = Row(
        batchId = progress["batchId"],
        inputRows = progress["numInputRows"],
        outputRows = progress["sink"]["numOutputRows"],
        timestamp = progress["timestamp"]
        )

# print para logs do job
print(f"[Silver] Batch {log.batchId} | In: {log.inputRows} | Out: {log.outputRows} | TS: {log.timestamp}")