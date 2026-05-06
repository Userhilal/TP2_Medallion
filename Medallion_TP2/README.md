# TP2 - Pipeline Medallion avec MinIO, Pandas et DuckDB

Ce dossier contient une réalisation complète du TP2 : Bronze, Silver et Gold avec deux variantes : Pandas et DuckDB.

## Exécution dans GitHub Codespaces

```bash
cd Medallion_TP2
python -m venv venv_tp2
source venv_tp2/bin/activate
pip install -r requirements.txt

docker compose up -d
python scripts/00_create_buckets.py
python scripts/01_pandas_pipeline.py
python scripts/02_duckdb_pipeline.py
python scripts/03_visualisation.py
```

Ouvre ensuite l'interface MinIO :

- URL : http://localhost:9001
- Login : minioadmin
- Mot de passe : minioadmin

Buckets à vérifier : bronze, silver, gold.

## Résultat attendu

- Bronze : `ventes/ventes_raw.csv`
- Silver : `ventes/silver_ventes_pandas.parquet` et `ventes/silver_ventes_duckdb.parquet`
- Gold : tables agrégées dans `ventes/pandas/` et `ventes/duckdb/`
- Visualisation : `outputs/gold_visualization.png`
