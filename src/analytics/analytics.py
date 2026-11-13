
import pandas as pd
from src.data.load_data import load_experiments


def analyze_dataset():
    df = load_experiments()

    print("\n" + "=" * 55)
    print("FIRE-X | DATA ANALYTICS REPORT")
    print("=" * 55)

    # 1. General Statistics
    print("\n[1] GENERAL STATISTICS")
    print(f"Total experiments: {len(df)}")
    print(f"Fuel materials: {df['fuel_material'].nunique()}")
    print(f"Investigations: {df['investigation_id'].nunique()}")
    print(f"Gravity conditions: {df['gravity_condition'].nunique()}")

    # 2. Gravity Distribution
    print("\n[2] GRAVITY CONDITIONS")
    print(df["gravity_condition"].value_counts().to_string())

    # 3. Fuel Distribution
    print("\n[3] FUEL MATERIALS")
    print(df["fuel_material"].value_counts().to_string())

    # 4. Extinction Outcomes
    print("\n[4] EXTINCTION OUTCOMES")
    print(df["extinction_outcome"].value_counts().to_string())

    # 5. Average Burning Rate by Fuel
    print("\n[5] AVERAGE BURNING RATE BY FUEL")
    print(
        df.groupby("fuel_material")["burning_rate_mms"]
        .agg(["count", "mean", "min", "max"])
        .round(3)
        .to_string()
    )

    # 6. Average Flame Temperature by Gravity
    print("\n[6] AVERAGE FLAME TEMPERATURE BY GRAVITY")
    print(
        df.groupby("gravity_condition")["flame_temp_k"]
        .agg(["count", "mean", "min", "max"])
        .round(2)
        .to_string()
    )

    print("\n" + "=" * 55)
    print("ANALYSIS COMPLETED")
    print("=" * 55)


if __name__ == "__main__":
    analyze_dataset()
