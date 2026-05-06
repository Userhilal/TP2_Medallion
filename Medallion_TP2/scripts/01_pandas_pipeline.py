from pathlib import Path
import pandas as pd
from minio import Minio

BASE_DIR = Path(__file__).resolve().parents[1]
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True)

client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

# 1. Bronze : upload du CSV brut sans transformation
client.fput_object(
    bucket_name="bronze",
    object_name="ventes/ventes_raw.csv",
    file_path=str(BASE_DIR / "ventes_raw.csv"),
    content_type="text/csv",
)
print("Bronze OK : CSV brut uploadé dans MinIO")

# 2. Silver : récupération + nettoyage
bronze_local = TMP_DIR / "ventes_raw.csv"
client.fget_object("bronze", "ventes/ventes_raw.csv", str(bronze_local))

df = pd.read_csv(bronze_local)
print(f"Lignes brutes : {len(df)}")

# Nettoyage robuste des espaces invisibles dans les colonnes texte
text_cols = ["client_id", "produit", "categorie", "region"]
for col in text_cols:
    df[col] = df[col].astype("string").str.strip()

# Transformer les chaînes vides en valeurs manquantes
for col in text_cols:
    df[col] = df[col].replace("", pd.NA)

# Supprimer les doublons après correction des espaces
before_dedup = len(df)
df = df.drop_duplicates()
print(f"Doublons supprimés : {before_dedup - len(df)}")

# Supprimer les lignes critiques incomplètes
before_nulls = len(df)
df = df.dropna(subset=["client_id", "quantite"])
print(f"Lignes supprimées pour nulls critiques : {before_nulls - len(df)}")

# Types + colonnes dérivées
df["date_commande"] = pd.to_datetime(df["date_commande"])
df["quantite"] = df["quantite"].astype(int)
df["prix_unitaire"] = df["prix_unitaire"].astype(float)
df["montant_total"] = df["quantite"] * df["prix_unitaire"]
df["annee"] = df["date_commande"].dt.year
df["mois"] = df["date_commande"].dt.month

silver_path = TMP_DIR / "silver_ventes_pandas.parquet"
df.to_parquet(silver_path, index=False)
client.fput_object("silver", "ventes/silver_ventes_pandas.parquet", str(silver_path))
print(f"Silver Pandas OK : {len(df)} lignes propres")

# 3. Gold : agrégations métier
gold_region = (
    df.groupby(["region", "categorie"])
    .agg(
        ca_total=("montant_total", "sum"),
        nb_commandes=("id_commande", "count"),
        panier_moyen=("montant_total", "mean"),
    )
    .round(2)
    .reset_index()
    .sort_values("ca_total", ascending=False)
)

gold_mensuel = (
    df.groupby(["annee", "mois"])
    .agg(
        ca_mensuel=("montant_total", "sum"),
        nb_commandes=("id_commande", "count"),
        clients_actifs=("client_id", "nunique"),
    )
    .round(2)
    .reset_index()
    .sort_values(["annee", "mois"])
)

gold_produits = (
    df.groupby(["produit", "categorie"])
    .agg(ca_produit=("montant_total", "sum"), unites_vendues=("quantite", "sum"))
    .round(2)
    .reset_index()
    .sort_values("ca_produit", ascending=False)
)

for name, df_g in [
    ("ca_region", gold_region),
    ("ca_mensuel", gold_mensuel),
    ("top_produits", gold_produits),
]:
    path = TMP_DIR / f"{name}_pandas.parquet"
    df_g.to_parquet(path, index=False)
    client.fput_object("gold", f"ventes/pandas/{name}.parquet", str(path))
    print(f"Gold Pandas OK : ventes/pandas/{name}.parquet")

print("Pipeline Pandas terminé")
print("\nAperçu Gold - CA par région/catégorie")
print(gold_region)
