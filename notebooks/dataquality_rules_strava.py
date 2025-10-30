# quality_rules/strava_activity.py

def get_rules_activity() -> dict:
    """
    Data Quality Rule for uc_athlete_data.silver.strava_activities.
    Return { Rule_name: expression_SQL }.
    """
    return {
        "rules":{
            # Need To Have
            "missing_id":             "id IS NULL",
            "missing_start_date":     "start_date IS NULL",
            "sport_type_missing":     "sport_type IS NULL OR sport_type = ''",

            # Distance
            "neg_distance":           "distance_km < 0",
            "zero_distance_run":      "sport_type = 'Run' AND distance_km = 0",

            # Speed
            "speed_negative":         "average_speed_kmh < 0",
            "speed_implausible_run":  "sport_type = 'Run' AND average_speed_kmh > 30",

            # pace calculated
            "pace_negative":          "pace_min_km_new < 0",
            "pace_null_when_should":  "moving_time > 0 AND distance_km > 0 AND pace_min_km_new IS NULL",
        },
        "reject_table": "uc_athlete_data.silver_rejects.strava_activities"
    }
    
def get_rules_subactivity() -> dict:
    """
    Data Quality Rule for uc_athlete_data.silver.strava_sub_activity.
    Return { Rule_name: expression_SQL }.
    """
    return {
        "rules":{
            # Need To Have
            "missing_id":             "id IS NULL",
            "missing_start_date":     "athlete_id IS NULL",
            "neg_calories":           "calories < 0"
        },
        "reject_table": "uc_athlete_data.silver_rejects.strava_sub_activity"
    }
    
