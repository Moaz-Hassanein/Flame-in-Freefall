
import os
import requests
import pandas as pd

# NASA PSI API
BASE_URL = "https://psi.nasa.gov/geode-py/ws"
STUDY_ID = "PSI-159"

# File extensions
TABLE_EXTENSIONS = {
    ".csv", ".tsv", ".xlsx", ".xls", ".xlsm", ".ods", ".parquet"
}

TEXT_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".rtf",
    ".md", ".html", ".htm", ".xml", ".json",
    ".pptx", ".ppt"
}

ARCHIVE_EXTENSIONS = {
    ".zip", ".7z", ".tar", ".gz", ".bz2", ".xz"
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff",
    ".bmp", ".gif", ".webp"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".avi", ".mov", ".mkv", ".mpeg"
}


def classify_file(filename):
    ext = os.path.splitext(filename.lower())[1]

    if ext in TABLE_EXTENSIONS:
        return "table"
    elif ext in TEXT_EXTENSIONS:
        return "text_document"
    elif ext in ARCHIVE_EXTENSIONS:
        return "archive"
    elif ext in IMAGE_EXTENSIONS:
        return "image_excluded"
    elif ext in VIDEO_EXTENSIONS:
        return "video_excluded"
    else:
        return "other"


def main():
    print("Fetching PSI-159 metadata...")

    response = requests.get(
        f"{BASE_URL}/repo/investigations/{STUDY_ID}",
        timeout=60
    )
    response.raise_for_status()

    investigation = response.json()
    files = investigation.get("added", [])

    print(f"Total files found: {len(files)}")

    rows = []

    for file_info in files:
        filename = file_info.get("file_name", "")

        if not filename:
            continue

        size = file_info.get("file_size", 0)

        try:
            size = int(size or 0)
        except (ValueError, TypeError):
            size = 0

        rows.append({
            "file_name": filename,
            "extension": os.path.splitext(filename.lower())[1],
            "category": classify_file(filename),
            "file_size_bytes": size,
            "size_mb": round(size / (1024 ** 2), 3),
            "restricted": file_info.get("restricted"),
            "visible": file_info.get("visible"),
            "remote_url": file_info.get("remote_url"),
            "s3_path": file_info.get("s3_path"),
        })

    df = pd.DataFrame(rows)

    # Save complete inventory
    df.to_csv(
        "psi159_full_inventory.csv",
        index=False,
        encoding="utf-8-sig"
    )

    # Save relevant text and table files
    relevant = df[
        df["category"].isin(["table", "text_document"])
    ].copy()

    relevant = relevant.sort_values(
        by=["category", "file_size_bytes"],
        ascending=[True, False]
    )

    relevant.to_csv(
        "psi159_relevant_files.csv",
        index=False,
        encoding="utf-8-sig"
    )

    # Save archives separately
    archives = df[df["category"] == "archive"]

    archives.to_csv(
        "psi159_archives.csv",
        index=False,
        encoding="utf-8-sig"
    )

    # Summary
    print("\n========== FILE INVENTORY SUMMARY ==========")
    print(f"Total files: {len(df)}")

    summary = (
        df.groupby("category")
        .agg(
            file_count=("file_name", "count"),
            total_size_mb=("size_mb", "sum")
        )
        .round(2)
        .sort_values("file_count", ascending=False)
    )

    print("\nFiles by category:")
    print(summary.to_string())

    print("\n========== RELEVANT FILES ==========")
    print(f"Text documents: {(df['category'] == 'text_document').sum()}")
    print(f"Tables: {(df['category'] == 'table').sum()}")
    print(f"Archives: {(df['category'] == 'archive').sum()}")

    print("\nLargest relevant files:")
    print(
        relevant[
            ["file_name", "category", "size_mb"]
        ].head(20).to_string(index=False)
    )

    print("\nGenerated files:")
    print("- psi159_full_inventory.csv")
    print("- psi159_relevant_files.csv")
    print("- psi159_archives.csv")


if __name__ == "__main__":
    main()
