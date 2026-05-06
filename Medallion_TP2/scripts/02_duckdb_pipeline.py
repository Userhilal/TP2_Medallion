from pathlib import Path
import duckdb
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

# Bronze : upload du CSV brut
client.fput_object(
    bucket_name="bronze",
    object_name="ventes/ventes_raw.csv",
    file_path=str(BASE_DIR / "ventes_raw.csv"),
    content_type="text/csv",
)
print("Bronze OK : CSV brut uploadé dans MinIO")

# Télécharger Bronze en local
bronze_local = TMP_DIR / "ventes_raw.csv"
client.fget_object("bronze", "ventes/ventes_raw.csv", str(bronze_local))

con = duckdb.connect()

print("=== Aperçu Bronze ===")
print(con.execute(f"SELECT * FROM read_csv_auto('{bronze_local}') LIMIT 5").df())

print("=== Valeurs nulles critiques ===")
print(con.execute(f"""
    SELECT COUNT(*) - COUNT(client_id) AS nulls_client,
           COUNT(*) - COUNT(quantite) AS nulls_quantite
    FROM read_csv_auto('{bronze_local}')
""").df())

# Silver robuste : TRIM avant DISTINCT pour corriger le doublon 1005 avec espaces
con.execute(f"""
    CREATE OR REPLACE TABLE silver_ventes AS
    SELECT DISTINCT
        id_commande,
        CAST(date_commande AS DATE) AS date_commande,
        TRIM(client_id) AS client_id,
        TRIM(produit) AS produit,
        TRIM(categorie) AS categorie,
        TRIM(region) AS region,
        CAST(quantite AS INTEGER) AS quantite,
        CAST(prix_unitaire AS DOUBLE) AS prix_unitaire,
        CAST(quantite AS INTEGER) * CAST(prix_unitaire AS DOUBLE) AS montant_total,
        YEAR(CAST(date_commande AS DATE)) AS annee,
        MONTH(CAST(date_commande AS DATE)) AS mois
    FROM read_csv_auto('{bronze_local}')
    WHERE client_id IS NOT NULL
      AND quantite IS NOT NULL
""")

n = con.execute("SELECT COUNT(*) FROM silver_ventes").fetchone()[0]
print(f"Silver DuckDB OK : {n} lignes propres")

silver_path = TMP_DIR / "silver_ventes_duckdb.parquet"
con.execute(f"COPY silver_ventes TO '{silver_path}' (FORMAT PARQUET)")
client.fput_object("silver", "ventes/silver_ventes_duckdb.parquet", str(silver_path))

# Gold
con.execute("""
    CREATE OR REPLACE TABLE gold_region AS
    SELECT region, categorie,
           ROUND(SUM(montant_total), 2) AS ca_total,
           COUNT(id_commande) AS nb_commandes,
           ROUND(AVG(montant_total), 2) AS panier_moyen
    FROM silver_ventes
    GROUP BY region, categorie
    ORDER BY ca_total DESC
""")

con.execute("""
    CREATE OR REPLACE TABLE gold_mensuel AS
    SELECT annee, mois,
           ROUND(SUM(montant_total), 2) AS ca_mensuel,
           COUNT(id_commande) AS nb_commandes,
           COUNT(DISTINCT client_id) AS clients_actifs
    FROM silver_ventes
    GROUP BY annee, mois
    ORDER BY annee, mois
""")

con.execute("""
    CREATE OR REPLACE TABLE gold_produits AS
    SELECT produit, categorie,
           ROUND(SUM(montant_total), 2) AS ca_produit,
           SUM(quantite) AS unites_vendues
    FROM silver_ventes
    GROUP BY produit, categorie
    ORDER BY ca_produit DESC
""")

for table, name in [
    ("gold_region", "ca_region"),
    ("gold_mensuel", "ca_mensuel"),
    ("gold_produits", "top_produits"),
]:
    path = TMP_DIR / f"{name}_duckdb.parquet"
    con.execute(f"COPY {table} TO '{path}' (FORMAT PARQUET)")
    client.fput_object("gold", f"ventes/duckdb/{name}.parquet", str(path))
    print(f"Gold DuckDB OK : ventes/duckdb/{name}.parquet")

print("Pipeline DuckDB terminé")
print("\nTop 5 produits")
print(con.execute("SELECT * FROM gold_produits LIMIT 5").df())
