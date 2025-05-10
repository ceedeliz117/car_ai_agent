import re
from pathlib import Path

import pandas as pd


class CatalogService:
    def __init__(self):
        self.catalog_path = (
            Path(__file__).parent.parent.parent / "data" / "sample_caso_ai_engineer.csv"
        )
        self.catalog_df = self._load_catalog()

        bool_columns = ["bluetooth", "car_play"]
        for col in bool_columns:
            if col in self.catalog_df.columns:
                self.catalog_df[col] = (
                    self.catalog_df[col]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .map({"sí": True, "si": True, "no": False})
                    .fillna(False)
                )

    def _load_catalog(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.catalog_path, skipinitialspace=True)
            for col in ["make", "model", "version"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.lower().str.strip()
            print("✅ Catálogo cargado y normalizado correctamente.")
            return df
        except Exception as e:
            print(f"❌ Error cargando catálogo: {e}")
            return pd.DataFrame()
