# import requests
# import pandas as pd
# import os
# import json

# BASE_URL = "https://psi.nasa.gov/geode-py/ws"
# STUDY_ID = "PSI-159"

# response = requests.get(
#     f"{BASE_URL}/repo/investigations/{STUDY_ID}",
#     timeout=60
# )
# response.raise_for_status()

# data = response.json()
# files = data.get("added", [])

# text_extensions = {
#     ".pdf", ".docx", ".doc", ".txt", ".rtf",
#     ".md", ".html", ".htm", ".xml", ".json",
#     ".pptx", ".ppt"
# }

# rows = []

# for item in files:
#     name = item.get("file_name", "")
#     ext = os.path.splitext(name.lower())[1]

#     if ext in text_extensions:
#         size = item.get("file_size", 0)

#         try:
#             size = int(size or 0)
#         except (ValueError, TypeError):
#             size = 0

#         rows.append({
#             "file_name": name,
#             "extension": ext,
#             "size_mb": round(size / (1024 ** 2), 3),
#             "restricted": item.get("restricted"),
#             "visible": item.get("visible"),
#             "remote_url": item.get("remote_url")
#         })

# df = pd.DataFrame(rows)

# print("Total text files:", len(df))

# print("\n========== EXTENSION DISTRIBUTION ==========")
# print(df["extension"].value_counts().to_string())

# print("\n========== LARGEST 30 TEXT FILES ==========")
# print(
#     df.sort_values("size_mb", ascending=False)
#     [["file_name", "extension", "size_mb"]]
#     .head(30)
#     .to_string(index=False)
# )

# # Search likely scientific documents by filename
# keywords = [
#     "report", "publication", "paper", "experiment",
#     "science", "research", "final", "technical",
#     "abstract", "document"
# ]

# mask = df["file_name"].str.lower().apply(
#     lambda name: any(word in name for word in keywords)
# )

# print("\n========== POSSIBLY RELEVANT DOCUMENTS ==========")
# print(
#     df[mask][["file_name", "extension", "size_mb"]]
#     .head(50)
#     .to_string(index=False)
# )

# df.to_csv(
#     "psi159_text_inventory.csv",
#     index=False,
#     encoding="utf-8-sig"
# )

# print("\n========== API PUBLICATIONS ==========")
# print(json.dumps(data.get("publications", []), indent=2))

# print("\nSaved: psi159_text_inventory.csv")


# import pandas as pd
# from collections import Counter

# df = pd.read_csv("psi159_text_inventory.csv")

# for ext in [".txt", ".pdf"]:
#     subset = df[df["extension"] == ext]

#     print("\n" + "=" * 70)
#     print(f"EXTENSION: {ext}")
#     print("Total:", len(subset))

#     print("\nFirst 50 filenames:")
#     for name in subset["file_name"].sort_values().head(50):
#         print(name)

#     # Common filename prefixes
#     prefixes = []

#     for name in subset["file_name"]:
#         parts = name.split("_")
#         if len(parts) >= 3:
#             prefixes.append(parts[2])
#         elif len(parts) >= 2:
#             prefixes.append(parts[1])

#     print("\nCommon filename groups:")
#     for prefix, count in Counter(prefixes).most_common(20):
#         print(f"{prefix}: {count}")


import requests

BASE_URL = "https://psi.nasa.gov/geode-py/ws"
STUDY_ID = "PSI-159"

files_to_inspect = [
    "PSI-159_Raw Data_21088A1_TP.txt",
    "PSI-159_Raw Data_21088A1_ImageComments.txt",
]

for filename in files_to_inspect:
    print("\n" + "=" * 80)
    print("FILE:", filename)

    response = requests.get(
        f"{BASE_URL}/studies/{STUDY_ID}/download",
        params={"file": filename},
        timeout=120
    )
    response.raise_for_status()

    content = response.content.decode(
        "utf-8",
        errors="replace"
    )

    print("\nCONTENT:")
    print(content[:4000])
    print("\nTotal characters:", len(content))
