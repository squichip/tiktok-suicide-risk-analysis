
import pandas as pd

CSV_PATH = "tiktok_final_analysis.csv"

df = pd.read_csv(CSV_PATH)

# Silinmesini istediğimiz kolonlar
drop_cols = [
    "caption_for_model",
    "transcript_for_model",
    "caption_model",
    "transcript_model"
]

# CSV'de varsa sil
df = df.drop(columns=[c for c in drop_cols if c in df.columns])

# Geri yaz
df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

print("✅ CSV temizlendi. Model ara kolonları silindi.")
print("📌 Kalan kolonlar:")
print(list(df.columns))
