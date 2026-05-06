from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from minio import Minio

BASE_DIR = Path(__file__).resolve().parents[1]
TMP_DIR = BASE_DIR / "tmp"
OUT_DIR = BASE_DIR / "outputs"
TMP_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
)

# On consomme les résultats Gold produits par Pandas
client.fget_object("gold", "ventes/pandas/ca_region.parquet", str(TMP_DIR / "ca_region.parquet"))
client.fget_object("gold", "ventes/pandas/ca_mensuel.parquet", str(TMP_DIR / "ca_mensuel.parquet"))

region = pd.read_parquet(TMP_DIR / "ca_region.parquet")
mensuel = pd.read_parquet(TMP_DIR / "ca_mensuel.parquet")
mensuel["mois_label"] = mensuel["annee"].astype(str) + "-" + mensuel["mois"].astype(str).str.zfill(2)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

region.groupby("region")["ca_total"].sum().sort_values().plot(kind="barh", ax=axes[0])
axes[0].set_title("CA Total par Région")
axes[0].set_xlabel("CA")

mensuel.plot(x="mois_label", y="ca_mensuel", kind="bar", ax=axes[1], legend=False)
axes[1].set_title("Évolution Mensuelle du CA")
axes[1].set_xlabel("Mois")
axes[1].set_ylabel("CA")
axes[1].tick_params(axis="x", rotation=45)

plt.tight_layout()
out = OUT_DIR / "gold_visualization.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Visualisation sauvegardée : {out}")
