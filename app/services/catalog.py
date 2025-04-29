import pandas as pd
from pathlib import Path

class CatalogService:
    def __init__(self):
        self.catalog_path = Path(__file__).parent.parent.parent / "data" / "sample_caso_ai_engineer.csv"
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
        results = self.catalog_df[self.catalog_df['make'].str.lower() == make_lower]
        return results
