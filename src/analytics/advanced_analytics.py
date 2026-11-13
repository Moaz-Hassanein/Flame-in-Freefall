
import pandas as pd
from src.data.load_data import load_experiments



def analyze_oxygen_vs_outcome(df):
    print("\n[1] OXYGEN PERCENTAGE VS EXTINCTION OUTCOME")

    bins = [0, 10, 15, 18, 21, 25, 100]
    labels = ["0-10%", "10-15%", "15-18%", "18-21%", "21-25%", "25%+"]

    data = df.dropna(
        subset=["oxygen_pct", "extinction_outcome"]
    ).copy()

    data["oxygen_range"] = pd.cut(
        data["oxygen_pct"],
        bins=bins,
        labels=labels,
        include_lowest=True
    )

    counts = pd.crosstab(
        data["oxygen_range"],
        data["extinction_outcome"]
    )

    percentages = counts.div(
        counts.sum(axis=1), axis=0
    ) * 100

    print("\nOutcome Percentages (%):")
    print(percentages.round(2).to_string())



def analyze_burning_rate_vs_gravity(df):
    print("\n[2] BURNING RATE VS GRAVITY CONDITION")

    result = (
        df.groupby("gravity_condition")["burning_rate_mms"]
        .agg(["count", "mean", "min", "max"])
        .round(3)
    )

    print(result.to_string())



def analyze_fuel_vs_outcome(df):
    print("\n[3] FUEL MATERIAL VS EXTINCTION OUTCOME")

    fuel_counts = df["fuel_material"].value_counts()
    top_fuels = fuel_counts[fuel_counts >= 10].index

    data = df[df["fuel_material"].isin(top_fuels)]

    counts = pd.crosstab(
        data["fuel_material"],
        data["extinction_outcome"]
    )

    percentages = counts.div(
        counts.sum(axis=1), axis=0
    ) * 100

    print("\nOutcome Percentages by Fuel (%):")
    print(percentages.round(2).to_string())



def main():
    df = load_experiments()

    print("=" * 60)
    print("FIRE-X | ADVANCED ANALYTICS")
    print("=" * 60)

    analyze_oxygen_vs_outcome(df)
    analyze_burning_rate_vs_gravity(df)
    analyze_fuel_vs_outcome(df)

    print("\nADVANCED ANALYSIS COMPLETED")


if __name__ == "__main__":
    main()
