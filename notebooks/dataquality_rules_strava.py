# quality_rules/strava_activity.py

def get_rules_activity() -> dict:
    """
    Regras de qualidade para uc_athlete_data.silver.strava_activities.
    Retorna { nome_da_regra: expressão_SQL }.
    """
    return {
        # obrigatórios
        "missing_id":             "id IS NULL",
        "missing_start_date":     "start_date IS NULL",
        "sport_type_missing":     "sport_type IS NULL OR sport_type = ''",

        # distância/tempo básicos
        "neg_distance":           "distance_km < 0",
        "zero_distance_run":      "sport_type = 'Run' AND distance_km = 0",

        # velocidade
        "speed_negative":         "average_speed_kmh < 0",
        "speed_implausible_run":  "sport_type = 'Run' AND average_speed_kmh > 30",

        # pace calculado
        "pace_negative":          "pace_min_km_new < 0",
        "pace_null_when_should":  "moving_time > 0 AND distance_km > 0 AND pace_min_km_new IS NULL",
    }
