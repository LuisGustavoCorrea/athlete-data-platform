"""Unit tests for feature transformations."""

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


@pytest.fixture(scope="session")
def spark():
    """Create SparkSession for tests."""
    return SparkSession.builder \
        .appName("test-transformations") \
        .master("local[*]") \
        .getOrCreate()


class TestCalculateTSS:
    """Tests for TSS calculation."""

    def test_tss_positive_for_valid_activity(self, spark):
        """TSS should be positive for valid activities."""
        from src.feature_engineering.transformations import calculate_tss

        data = [("athlete1", 1, 45.0, 5.5)]
        df = spark.createDataFrame(
            data,
            ["athlete_id", "activity_id", "moving_time_min", "pace_min_km"]
        )

        result = calculate_tss(df, threshold_pace=5.0)
        tss = result.select("estimated_tss").collect()[0][0]

        assert tss > 0
        assert tss < 200  # Reasonable range for 45 min run

    def test_tss_zero_for_zero_pace(self, spark):
        """TSS should be zero when pace is zero."""
        from src.feature_engineering.transformations import calculate_tss

        data = [("athlete1", 1, 45.0, 0.0)]
        df = spark.createDataFrame(
            data,
            ["athlete_id", "activity_id", "moving_time_min", "pace_min_km"]
        )

        result = calculate_tss(df, threshold_pace=5.0)
        tss = result.select("estimated_tss").collect()[0][0]

        assert tss == 0

    def test_intensity_factor_increases_with_faster_pace(self, spark):
        """Faster pace (lower min/km) should give higher IF."""
        from src.feature_engineering.transformations import calculate_tss

        data = [
            ("athlete1", 1, 30.0, 4.0),  # Fast
            ("athlete1", 2, 30.0, 6.0),  # Slow
        ]
        df = spark.createDataFrame(
            data,
            ["athlete_id", "activity_id", "moving_time_min", "pace_min_km"]
        )

        result = calculate_tss(df, threshold_pace=5.0)
        ifs = result.orderBy("activity_id").select("intensity_factor").collect()

        fast_if = ifs[0][0]
        slow_if = ifs[1][0]

        assert fast_if > slow_if


class TestCalculateHRZones:
    """Tests for HR zone calculation."""

    def test_hr_zones_sum_to_one(self, spark):
        """Only one zone should be active per row."""
        from src.feature_engineering.transformations import calculate_hr_zones

        data = [
            ("athlete1", 1, 150.0, 200.0, 5.0),  # 75% = zone 3
        ]
        df = spark.createDataFrame(
            data,
            ["athlete_id", "activity_id", "average_heartrate", "max_heartrate", "pace_min_km"]
        )

        result = calculate_hr_zones(df)

        zones = result.select(
            "hr_zone_1_pct", "hr_zone_2_pct", "hr_zone_3_pct",
            "hr_zone_4_pct", "hr_zone_5_pct"
        ).collect()[0]

        zone_sum = sum(zones)
        assert zone_sum == 1.0

    def test_hr_zones_null_when_no_hr(self, spark):
        """HR zones should handle null HR gracefully."""
        from src.feature_engineering.transformations import calculate_hr_zones

        data = [
            ("athlete1", 1, None, None, 5.0),
        ]
        df = spark.createDataFrame(
            data,
            ["athlete_id", "activity_id", "average_heartrate", "max_heartrate", "pace_min_km"]
        )

        result = calculate_hr_zones(df)
        efficiency = result.select("efficiency_index").collect()[0][0]

        assert efficiency is None


class TestCTLATL:
    """Tests for training load calculations."""

    def test_tsb_equals_ctl_minus_atl(self, spark):
        """TSB should be CTL - ATL."""
        from src.feature_engineering.transformations import calculate_ctl_atl

        # Create 50 days of data
        data = [
            ("athlete1", f"2024-01-{i:02d}", float(i * 10))
            for i in range(1, 50)
        ]
        df = spark.createDataFrame(data, ["athlete_id", "activity_date", "daily_tss"])
        df = df.withColumn("activity_date", F.to_date("activity_date"))

        result = calculate_ctl_atl(df)
        row = result.orderBy(F.desc("activity_date")).first()

        expected_tsb = row["ctl_42d"] - row["atl_7d"]
        actual_tsb = row["tsb"]

        assert abs(expected_tsb - actual_tsb) < 0.01

    def test_acwr_calculation(self, spark):
        """ACWR should be ATL / CTL."""
        from src.feature_engineering.transformations import calculate_ctl_atl

        data = [
            ("athlete1", f"2024-01-{i:02d}", 50.0)
            for i in range(1, 50)
        ]
        df = spark.createDataFrame(data, ["athlete_id", "activity_date", "daily_tss"])
        df = df.withColumn("activity_date", F.to_date("activity_date"))

        result = calculate_ctl_atl(df)
        row = result.orderBy(F.desc("activity_date")).first()

        # With constant TSS, ACWR should be close to 1
        assert 0.9 < row["acwr"] < 1.1
