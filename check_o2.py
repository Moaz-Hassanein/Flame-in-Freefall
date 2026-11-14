import duckdb
p = r"D:\Flame-in-Freefall\data\processed\experiments.parquet"
q = """
SELECT extinction_outcome, gravity_condition, is_modeled, COUNT(*) AS n
FROM read_parquet(?)
WHERE oxygen_pct >= 30
GROUP BY ALL
ORDER BY n DESC
"""
print(duckdb.execute(q, [p]).df().to_string())
