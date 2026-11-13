

import pandas as pd
from difflib import get_close_matches

from src.data.load_data import load_experiments


# ==================================================
# 1. Dataset Overview
# ==================================================

def show_overview(df):
    print("\n=== Dataset Overview ===")
    print(f"Experiments: {len(df)}")
    print(f"Investigations: {df['investigation_id'].nunique()}")
    print(f"Fuel Materials: {df['fuel_material'].nunique()}")

    print("\nGravity Distribution:")
    print(df["gravity_condition"].value_counts().to_string())

    print("\nMaterial Categories:")
    print(df["material_category"].value_counts().to_string())


# ==================================================
# 2. Fuel Search
# ==================================================

def search_fuel(df, keyword):
    matches = df[
        df["fuel_material"].str.contains(
            keyword, case=False, na=False, regex=False
        )
    ]["fuel_material"].value_counts()

    print("\n=== Fuel Search Results ===")

    if matches.empty:
        print(f"No fuel found matching: {keyword}")
        return

    for fuel, count in matches.items():
        print(f"{fuel}: {count} experiments")


# ==================================================
# 3. Fuel Statistics
# ==================================================

def analyze_fuel(df, fuel_name):
    selected = df[
        df["fuel_material"].str.lower() == fuel_name.lower()
    ]

    if selected.empty:
        print(f"\nFuel not found: {fuel_name}")
        search_fuel(df, fuel_name)
        return

    print(f"\n=== {fuel_name} Statistics ===")
    print(f"Experiments: {len(selected)}")

    metrics = {
        "Average Burning Rate (mm/s)": "burning_rate_mms",
        "Average Flame Temperature (K)": "flame_temp_k",
        "Average Oxygen (%)": "oxygen_pct",
        "Average Pressure (kPa)": "pressure_kpa",
        "Average Burn Time (s)": "burn_time_s",
    }

    for label, column in metrics.items():
        print(f"{label}: {selected[column].mean():.3f}")

    print("\nGravity Distribution:")
    print(selected["gravity_condition"].value_counts().to_string())

    print("\nExtinction Outcomes:")
    print(selected["extinction_outcome"].value_counts().to_string())


# ==================================================
# 4. Fuel Comparison
# ==================================================

def compare_fuels(df, fuel1, fuel2):
    fuels = [fuel1, fuel2]

    selected = df[
        df["fuel_material"].str.lower().isin(
            [fuel.lower() for fuel in fuels]
        )
    ]

    print(f"\n=== {fuel1} vs {fuel2} ===")

    result = selected.groupby("fuel_material").agg(
        experiments=("experiment_id", "count"),
        avg_burning_rate=("burning_rate_mms", "mean"),
        avg_flame_temp=("flame_temp_k", "mean"),
        avg_oxygen=("oxygen_pct", "mean"),
        avg_pressure=("pressure_kpa", "mean"),
        avg_burn_time=("burn_time_s", "mean"),
    ).round(3)

    print(result.to_string())


# ==================================================
# 5. Burning Rate by Gravity
# ==================================================

def compare_burning_rates(df):
    print("\n=== Burning Rate by Gravity ===")

    result = df.groupby("gravity_condition")[
        "burning_rate_mms"
    ].agg(["count", "mean", "median", "min", "max"]).round(3)

    print(result.to_string())


# ==================================================
# 6. Oxygen vs Extinction
# ==================================================

def analyze_oxygen(df):
    print("\n=== Oxygen vs Extinction ===")

    bins = [0, 10, 15, 18, 21, 25, 100]
    labels = ["0-10%", "10-15%", "15-18%",
              "18-21%", "21-25%", "25%+"]

    data = df.copy()

    data["oxygen_range"] = pd.cut(
        data["oxygen_pct"],
        bins=bins,
        labels=labels,
        right=False
    )

    result = pd.crosstab(
        data["oxygen_range"],
        data["extinction_outcome"],
        normalize="index"
    ) * 100

    if "Extinction" in result.columns:
        print(result[["Extinction"]].round(2).to_string())
    else:
        print("No exact Extinction outcome found.")


# ==================================================
# 7. Extinction Outcomes
# ==================================================

def analyze_outcomes(df):
    print("\n=== Extinction Outcome Distribution ===")

    print(df["extinction_outcome"].value_counts().to_string())

    print("\nOutcome Percentages:")
    percentages = (
        df["extinction_outcome"]
        .value_counts(normalize=True) * 100
    )

    print(percentages.round(2).to_string())


# ==================================================
# 8. Fuel vs Outcomes
# ==================================================

def analyze_fuel_outcomes(df):
    print("\n=== Fuel vs Outcomes ===")

    counts = df.groupby("fuel_material").size()
    valid_fuels = counts[counts >= 10].index

    selected = df[df["fuel_material"].isin(valid_fuels)]

    result = pd.crosstab(
        selected["fuel_material"],
        selected["extinction_outcome"],
        normalize="index"
    ) * 100

    print(result.round(2).to_string())


# ==================================================
# 9. Burning Rate by Fuel
# ==================================================

def analyze_burning_by_fuel(df):
    print("\n=== Burning Rate by Fuel ===")

    result = df.groupby("fuel_material")[
        "burning_rate_mms"
    ].agg(["count", "mean", "median", "min", "max"])

    result = result[result["count"] >= 3]
    result = result.sort_values("mean", ascending=False)

    print(result.round(3).to_string())


# ==================================================
# 10. Gravity Comparison
# ==================================================

def compare_gravity(df, keyword):
    matches = df[
        df["gravity_condition"].str.contains(
            keyword, case=False, na=False, regex=False
        )
    ]

    print(f"\n=== Gravity Search: {keyword} ===")

    if matches.empty:
        print("No matching gravity condition found.")
        print("\nAvailable conditions:")
        print(df["gravity_condition"].unique().tolist())
        return

    result = matches.groupby("gravity_condition").agg(
        experiments=("experiment_id", "count"),
        avg_burning_rate=("burning_rate_mms", "mean"),
        avg_flame_temp=("flame_temp_k", "mean"),
        avg_oxygen=("oxygen_pct", "mean"),
    ).round(3)

    print(result.to_string())


# ==================================================
# 11. Investigation Search
# ==================================================

def search_investigation(df, keyword):
    selected = df[
        df["investigation_id"].astype(str).str.contains(
            keyword, case=False, na=False, regex=False
        )
    ]

    print(f"\n=== Investigation Search: {keyword} ===")

    if selected.empty:
        print("No matching investigation found.")
        return

    columns = [
        "experiment_id",
        "investigation_id",
        "fuel_material",
        "gravity_condition",
        "oxygen_pct",
        "extinction_outcome",
    ]

    print(selected[columns].to_string(index=False))


# ==================================================
# 12. Query Router
# ==================================================

def run_query(question, df):
    question = question.lower().strip()

    if question in ["exit", "quit"]:
        return False

    elif question in ["help", "commands"]:
        show_help()

    elif "search fuel" in question:
        keyword = question.replace("search fuel", "", 1).strip()
        search_fuel(df, keyword)

    elif "analyze fuel" in question:
        fuel = question.replace("analyze fuel", "", 1).strip()
        analyze_fuel(df, fuel)

    elif "compare fuels" in question:
        parts = question.replace("compare fuels", "", 1).strip().split(" vs ")

        if len(parts) == 2:
            compare_fuels(df, parts[0].strip(), parts[1].strip())
        else:
            print("Use: compare fuels Methanol vs Heptane")

    elif "burning rate" in question and "gravity" in question:
        compare_burning_rates(df)

    elif "oxygen" in question:
        analyze_oxygen(df)

    elif "fuel outcomes" in question:
        analyze_fuel_outcomes(df)

    elif "outcomes" in question or "extinction distribution" in question:
        analyze_outcomes(df)

    elif "burning rate" in question and "fuel" in question:
        analyze_burning_by_fuel(df)

    elif "gravity" in question:
        keyword = question.replace("gravity", "").replace(
            "compare", ""
        ).strip()
        compare_gravity(df, keyword)

    elif "investigation" in question:
        keyword = question.replace("search investigation", "").strip()
        search_investigation(df, keyword)

    elif "overview" in question or question == "dataset":
        show_overview(df)

    else:
        print("Unknown query. Type 'help' to see supported queries.")

    return True


# ==================================================
# 13. Help
# ==================================================

def show_help():
    print("""
=== Supported Queries ===

Dataset:
- overview

Fuel:
- search fuel methanol
- analyze fuel methanol
- compare fuels methanol vs heptane
- burning rate by fuel
- fuel outcomes

Gravity:
- burning rate by gravity
- compare gravity microgravity
- compare gravity lunar

Oxygen:
- oxygen vs extinction

Outcomes:
- outcomes
- extinction distribution

Investigation:
- search investigation PSI-159

Other:
- help
- exit
""")


# ==================================================
# 14. Main
# ==================================================

def main():
    df = load_experiments()

    print("=" * 50)
    print("NASA Experiment Query Engine")
    print("=" * 50)

    show_help()

    while True:
        try:
            question = input("\nAsk a question (or type 'exit'): ")

            if not run_query(question, df):
                print("Query Engine stopped.")
                break

        except KeyboardInterrupt:
            print("\nQuery Engine stopped.")
            break

        except Exception as error:
            print(f"\nQuery Error: {error}")


if __name__ == "__main__":
    main()
