import re
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


    def search_catalog(self, query: str) -> pd.DataFrame:
        """
        Búsqueda generalizada por todas las columnas relevantes: make, model, version, year, bluetooth, car_play.
        """
        query_lower = query.lower()
        escaped_query = re.escape(query_lower)
        masks = []

        for column in ["make", "model", "version"]:
            if column in self.catalog_df.columns:
                mask = (
                    self.catalog_df[column]
                    .astype(str)
                    .str.lower()
                    .str.contains(escaped_query, na=False, case=False)
                )
                masks.append(mask)

        if query.isdigit() and "year" in self.catalog_df.columns:
            mask_year = (
                self.catalog_df["year"].astype(str).str.contains(escaped_query, na=False)
            )
            masks.append(mask_year)

        if "bluetooth" in self.catalog_df.columns and ("bluetooth" in query_lower):
            mask_bt = (
                self.catalog_df["bluetooth"]
                .astype(str)
                .str.contains("sí", case=False, na=False)
            )
            masks.append(mask_bt)

        if "car_play" in self.catalog_df.columns and (
            "carplay" in query_lower or "car play" in query_lower
        ):
            mask_cp = (
                self.catalog_df["car_play"]
                .astype(str)
                .str.contains("sí", case=False, na=False)
            )
            masks.append(mask_cp)

        if masks:
            combined_mask = masks[0]
            for m in masks[1:]:
                combined_mask = combined_mask | m
            return self.catalog_df[combined_mask]

        return pd.DataFrame()
