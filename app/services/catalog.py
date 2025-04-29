from pathlib import Path

import pandas as pd


class CatalogService:
    def __init__(self):
        self.catalog_path = (
            Path(__file__).parent.parent.parent / "data" / "sample_caso_ai_engineer.csv"
        )
        self.catalog_df = self._load_catalog()

    def _load_catalog(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.catalog_path, skipinitialspace=True)
            print("✅ Catálogo cargado correctamente.")
            return df
        except Exception as e:
            print(f"❌ Error cargando catálogo: {e}")
            return pd.DataFrame()

    def search_by_make(self, make: str):
        make_lower = make.lower()
        results = self.catalog_df[self.catalog_df["make"].str.lower() == make_lower]
        return results

    def search_by_model(self, model: str):
        model_lower = model.lower()
        return self.catalog_df[
            self.catalog_df["model"].str.lower().str.contains(model_lower, na=False)
        ]
