# Databricks notebook source
from pyspark.sql import functions as F, Window
from delta.tables import DeltaTable
from py_functions_silver import *
from pyspark.sql.functions import current_timestamp
from dataquality_rules_strava import get_rules_activity
from pyspark.sql import Row
from functools import partial

BRONZE = "uc_athlete_data.bronze.strava_activities"
target_table = "uc_athlete_data.silver.strava_activities"
key_cols = ["athlete_id", "id", "start_date"]

CHECKPOINT = "abfss://silver@adlsathlete.dfs.core.windows.net/strava/activities/activities_checkpoint/"

# chave(s) de negócio — mude p/ composto se precisar, ex.: ["activity_id","lap_index"]
BUSINESS_KEYS = ["athlete_id","id"]
# colunas de ordenação para decidir o “vencedor” nos duplicados do micro-lote
ORDER_COLS = ["ingestion_timestamp"]  # adicione "updated_at" se existir

config = get_rules_activity()
rules = config["rules"]
reject_table = config["reject_table"]

# COMMAND ----------

# --- Compose (aplica tudo que você mostrou) -----------------------------------

def apply_all_silver_calcs(df: DataFrame,
                           *,
                           type_col: str = "type",
                           distance_col: str = "distance",
                           average_speed_col: str = "average_speed",
                           moving_time_col: str = "moving_time",
                           elapsed_time_col: str = "elapsed_time",
                           start_date_col: str = "start_date",
                           non_run_value_for_pace=0  # para manter igual ao seu snippet
                           ) -> DataFrame:
    """
    Aplica TODAS as transformações do snippet original.
    Retorna um novo DataFrame com:
      - start_date (date)
      - distance_km
      - average_speed_kmh
      - pace_min_km
      - pace_min_km_moving_time
      - tempo_real (HH:MM:SS)
      - pace_min_km_new
      - pace_strava (M:SS)
      - dia_semana
    """
    return (
        df
        .transform(lambda d: add_start_date(d, src_col=start_date_col, out_col="start_date"))
        .transform(lambda d: add_distance_km(d, distance_col=distance_col, out_col="distance_km", decimals=2))
        .transform(lambda d: add_average_speed_kmh(d, avg_speed_col=average_speed_col, out_col="average_speed_kmh", decimals=2))
        .transform(lambda d: add_pace_min_km(d,
                                             elapsed_time_col=elapsed_time_col,
                                             distance_col=distance_col,
                                             type_col=type_col,
                                             out_col="pace_min_km",
                                             decimals=2,
                                             only_for_run=True,
                                             non_run_value=non_run_value_for_pace))
        .transform(lambda d: add_pace_min_km_moving_time(d,
                                                         moving_time_col=moving_time_col,
                                                         distance_col=distance_col,
                                                         type_col=type_col,
                                                         out_col="pace_min_km_moving_time",
                                                         decimals=2,
                                                         only_for_run=True,
                                                         non_run_value=non_run_value_for_pace))
        .transform(lambda d: add_tempo_real(d, seconds_col=moving_time_col, out_col="tempo_real"))
        .transform(lambda d: add_pace_min_km_new(d,
                                                 moving_time_col=moving_time_col,
                                                 distance_col=distance_col,
                                                 out_col="pace_min_km_new",
                                                 decimals=3))
        .transform(lambda d: add_pace_strava(d, pace_min_col="pace_min_km_new", out_col="pace_strava"))
        .transform(lambda d: add_dia_semana(d, date_col="start_date", out_col="dia_semana", pattern="E"))
    )

# COMMAND ----------
def upsert_data(microBatchDF, batch):
    microBatchDF.createOrReplaceTempView("activities_microbatch")
    
    sql_query = """
                MERGE INTO uc_athlete_data.silver.strava_activities A
                USING activities_microbatch B
                ON A.athlete_id = b.athlete_id
                   AND A.ID = B.ID
                   AND A.START_DATE = B.START_DATE
                WHEN NOT MATCHED THEN INSERT * 
                """  

    microBatchDF.sparkSession.sql(sql_query)

# COMMAND ----------
def load_data(microBatchDF, batch):   
    
    microBatchDF = dedupe_microbatch(microBatchDF,BUSINESS_KEYS,ORDER_COLS)
    
    microBatchDF = apply_all_silver_calcs(microBatchDF)
    
    df_clean = assert_quality(microBatchDF,rules,reject_table)
    
    df_clean = add_silver_ingestion_time(df_clean) 
      
    upsert_data(df_clean, batch)
    

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


