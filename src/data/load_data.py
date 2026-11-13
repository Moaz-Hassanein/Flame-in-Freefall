
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "canonical_experiments.csv"


def load_experiments():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    return df


def main():
    df = load_experiments()

    print("=" * 50)
    print("FIRE-X | Dataset Loaded Successfully")
    print("=" * 50)

    print(f"Number of experiments: {len(df)}")
    print(f"Number of columns: {len(df.columns)}")

    print("\nDataset Preview:")
    print(df.head().to_string(index=False))


if __name__ == "__main__":
    main()
