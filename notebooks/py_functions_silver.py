# src/athlete_utils/silver_transforms.py
from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col, lit, to_timestamp, to_date, when, expr, floor, format_string, date_format
)
from pyspark.sql.functions import round as f_round
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp
from pyspark.sql.window import Window
from pyspark.sql.functions import row_number, col
from pyspark.sql import functions as F


def dedupe_microbatch(df : DataFrame,BUSINESS_KEYS,ORDER_COLS):
    w = Window.partitionBy(*[F.col(c) for c in BUSINESS_KEYS]) \
         .orderBy(*[F.col(c).desc() for c in ORDER_COLS])
    return (df.withColumn("row_id", F.row_number().over(w))
              .filter(F.col("row_id")==1)
              .drop("row_id"))
    
def add_start_date(df: DataFrame,
                   src_col: str = "start_date",
                   out_col: str = "start_date") -> DataFrame:
    """
    Converte ISO8601 (UTC com 'Z') para timestamp e, em seguida, para date.
    """
    return (
        df.withColumn(out_col, to_timestamp(col(src_col), "yyyy-MM-dd'T'HH:mm:ss'Z'"))
          .withColumn(out_col, to_date(col(out_col)))
    )

def add_silver_ingestion(df):
    return df.withColumn('silver_ingestion_timestamp', current_timestamp())

def add_distance_km(df: DataFrame,
                    distance_col: str = "distance",
                    out_col: str = "distance_km",
                    decimals: int = 2) -> DataFrame:
    """
    distance (m) -> km arredondado.
    """
    return df.withColumn(out_col, f_round(col(distance_col) / lit(1000.0), decimals))


def add_average_speed_kmh(df: DataFrame,
                          avg_speed_col: str = "average_speed",
                          out_col: str = "average_speed_kmh",
                          decimals: int = 2) -> DataFrame:
    """
    average_speed (m/s) -> km/h.
    """
    return df.withColumn(out_col, f_round(col(avg_speed_col) * lit(3.6), decimals))


def add_pace_min_km(df: DataFrame,
                    elapsed_time_col: str = "elapsed_time",  # segundos
                    distance_col: str = "distance",          # metros
                    type_col: str = "type",
                    out_col: str = "pace_min_km",
                    decimals: int = 2,
                    only_for_run: bool = True,
                    non_run_value=None) -> DataFrame:
    """
    Pace usando elapsed_time: (min) / km.
    Por padrão calcula apenas para 'Run' (only_for_run=True).
    """
    pace_expr = f_round((col(elapsed_time_col) / lit(60.0)) / (col(distance_col) / lit(1000.0)), decimals)

    if only_for_run:
        return df.withColumn(
            out_col,
            when(col(type_col) == lit("Run"), pace_expr).otherwise(lit(non_run_value))
        )
    else:
        return df.withColumn(out_col, when(col(distance_col) > 0, pace_expr).otherwise(lit(None)))


def add_pace_min_km_moving_time(df: DataFrame,
                                moving_time_col: str = "moving_time",  # segundos
                                distance_col: str = "distance",        # metros
                                type_col: str = "type",
                                out_col: str = "pace_min_km_moving_time",
                                decimals: int = 2,
                                only_for_run: bool = True,
                                non_run_value=None) -> DataFrame:
    """
    Pace usando moving_time: (min) / km.
    """
    pace_expr = f_round((col(moving_time_col) / lit(60.0)) / (col(distance_col) / lit(1000.0)), decimals)

    if only_for_run:
        return df.withColumn(
            out_col,
            when(col(type_col) == lit("Run"), pace_expr).otherwise(lit(non_run_value))
        )
    else:
        return df.withColumn(out_col, when(col(distance_col) > 0, pace_expr).otherwise(lit(None)))


def add_tempo_real(df: DataFrame,
                   seconds_col: str = "moving_time",
                   out_col: str = "tempo_real") -> DataFrame:
    """
    Formata segundos em HH:MM:SS (string). Usa a mesma expressão do seu snippet.
    """
    return df.withColumn(
        out_col,
        expr("format_string('%02d:%02d:%02d', int({s}/3600), int(({s}%3600)/60), int({s}%60))"
             .format(s=seconds_col))
    )


def add_pace_min_km_new(df: DataFrame,
                        moving_time_col: str = "moving_time",  # s
                        distance_col: str = "distance",        # m
                        out_col: str = "pace_min_km_new",
                        decimals: int = 3) -> DataFrame:
    """
    Pace = (moving_time em min) / (distance em km), somente quando distance > 0.
    """
    pace_expr = f_round((col(moving_time_col) / lit(60.0)) / (col(distance_col) / lit(1000.0)), decimals)
    return df.withColumn(out_col, when(col(distance_col) > 0, pace_expr).otherwise(lit(0)))


def add_pace_strava(df: DataFrame,
                    pace_min_col: str = "pace_min_km_new",
                    out_col: str = "pace_strava") -> DataFrame:
    """
    Converte um pace em minutos decimais (ex.: 5.432) para string 'M:SS'.
    Regra: floor em minutos e arredonda os segundos. Se der 60, avança 1 min e zera segundos.
    Implementado com expressões SQL para manter vectorizado.
    """
    # minutos inteiros
    min_int = floor(col(pace_min_col))
    # segundos (arredondados) = round((parte_decimal*60), 0)
    sec_rounded = f_round((col(pace_min_col) - floor(col(pace_min_col))) * lit(60.0), 0).cast("int")

    # se 60, corrige para 59->+1min ou 00
    # vamos normalizar: new_min = min_int + (sec_rounded >= 60 ? 1 : 0); new_sec = (sec_rounded >= 60 ? 0 : sec_rounded)
    new_min = (min_int + when(sec_rounded >= 60, 1).otherwise(0))
    new_sec = when(sec_rounded >= 60, lit(0)).otherwise(sec_rounded)

    return df.withColumn(
        out_col,
        format_string("%d:%02d", new_min, new_sec)
    )


def add_dia_semana(df: DataFrame,
                   date_col: str = "start_date",
                   out_col: str = "dia_semana",
                   pattern: str = "E") -> DataFrame:
    """
    Abreviação do dia da semana com date_format (ex.: Mon/Tue...). 'E' segue locale do runtime.
    """
    return df.withColumn(out_col, date_format(col(date_col), pattern))

def assert_quality(df: DataFrame, rules: dict, reject_table: str):
    # 1) Defina as regras (nome -> condição SQL)
    #rules = get_rules_activity()
    
    # 2) Constrói uma coluna array com TODOS os motivos que baterem
    #    (evita múltiplos scans/union e duplicaçāo na rejects)
    #dfq = df.withColumn("reject_reasons", F.array())  # array<string> inicial
    dfq = df.withColumn("reject_reasons", F.lit(None).cast("array<string>"))
    
    for name, sql_cond in rules.items():
        cond_col = F.expr(sql_cond)
        dfq = dfq.withColumn(
            "reject_reasons",
            F.when(
                cond_col,
                # coalesce para lidar com NULL -> vira [] antes de unir com [name]
                F.array_union(F.coalesce(F.col("reject_reasons"), F.array()), F.array(F.lit(name)))
            ).otherwise(F.col("reject_reasons"))
        )

    # 3) Flag, contador e string consolidada (para leitura humana)
    dfq = (dfq
           .withColumn("reject_reason_count",
                       F.when(F.col("reject_reasons").isNull(), F.lit(0))
                        .otherwise(F.size("reject_reasons")))
           .withColumn("reject_reason",
                       F.when(F.col("reject_reasons").isNull(), F.lit(None).cast("string"))
                        .otherwise(F.array_join("reject_reasons", "|")))
           .withColumn("reject_timestamp", F.current_timestamp())
          )

    # 4) Separa válidos x rejeitos (cada registro entra UMA vez na rejects)
#    df_reject = dfq.filter(F.col("reject_reason_count") > 0 )
#    df_valid  = dfq.filter(F.col("reject_reason_count") == 0).drop("reject_reasons","reject_reason","reject_reason_count","reject_timestamp")
    #display(dfq)
    df_reject = dfq.filter(F.col("reject_reason").isNotNull())
    #display(df_reject)
    df_valid  = dfq.filter(F.col("reject_reason").isNull()).drop("reject_reasons","reject_reason","reject_reason_count","reject_timestamp")

    # 5) Persiste rejects (append) — sem duplicação da mesma linha
    #    Obs: não precisa mergeSchema aqui porque já criamos a tabela com colunas extras.
    has_rejects = df_reject.limit(1).count() > 0

    if has_rejects:  # evita ação pesada; é um job pequeno
        (df_reject
        .write
        .format("delta")        
        .mode("append")
        #.option("checkpointLocation", "/mnt/checkpoints/rejects")
        .option("mergeSchema", "true")
        .saveAsTable(reject_table)
        #.start()
        )
        print(f"⚠️ Rejecteds rows saved on {reject_table}")
    else:
        print(f"Assert Quality OK")        

    return df_valid

def add_silver_ingestion_time(df):
    return (df
            .withColumn("silver_ingestion_timestamp", current_timestamp())
            )

