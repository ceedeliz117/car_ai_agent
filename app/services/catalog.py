import re
from pathlib import Path

import pandas as pd

from app.core.utils import extract_price_from_text, normalize_token


class CatalogService:
    def __init__(self):
        self.catalog_path = (
            Path(__file__).parent.parent.parent / "data" / "sample_caso_ai_engineer.csv"
        )
        self.catalog_df = self._load_catalog()

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

    def search_catalog(self, query: str) -> pd.DataFrame:
        query = query.strip().lower()
        tokens = [normalize_token(t) for t in query.split()]
        df = self.catalog_df
        price_value = extract_price_from_text(query)
        if price_value:
            print(f"💰 Se detectó intención de buscar por precio: {price_value}")
            df_price_filtered = self.filter_by_approx_price(df, price_value)
            if not df_price_filtered.empty:
                return df_price_filtered

        mask = pd.Series([True] * len(df))
        matched = False

        print(f"🔍 Analizando tokens: {tokens}")

        for token in tokens:
            token = token.strip().lower()
            escaped_token = re.escape(token)

            # Marca
            if token in df["make"].unique():
                matched = True
                mask &= df["make"].str.contains(escaped_token, na=False)
                print(f"🔎 Filtro por marca: {token}")
                continue

            # Modelo
            if token in df["model"].unique():
                matched = True
                mask &= df["model"].str.contains(escaped_token, na=False)
                print(f"🔎 Filtro por modelo: {token}")
                continue

            # Año
            if token.isdigit() and "year" in df.columns:
                matched = True
                mask &= df["year"].astype(str).str.contains(escaped_token, na=False)
                print(f"🔎 Filtro por año: {token}")
                continue

            # Bluetooth
            if token == "bluetooth" and "bluetooth" in df.columns:
                matched = True
                mask &= df["bluetooth"].str.contains("sí", na=False)
                print(f"🔎 Filtro por característica: bluetooth")
                continue

            # CarPlay
            if token in ["carplay", "car", "play"] and "car_play" in df.columns:
                matched = True
                mask &= df["car_play"].str.contains("sí", na=False)
                print(f"🔎 Filtro por característica: car_play")
                continue

        if matched and mask.any():
            print(f"✅ Autos encontrados: {mask.sum()}")
            return df[mask]

        print(
            "⚠️ No se encontraron coincidencias con filtros estrictos. Realizando búsqueda flexible..."
        )
        return self.search_catalog_fallback(tokens)

    def search_catalog_fallback(self, tokens: list) -> pd.DataFrame:
        """
        Búsqueda flexible por OR si la búsqueda estricta no encontró nada.
        """
        df = self.catalog_df
        combined_mask = pd.Series([False] * len(df))

        for token in tokens:
            token = token.strip().lower()
            escaped_token = re.escape(token)
            print(f"🔍 [Fallback] Token: '{token}'")

            for col in ["make", "model", "version"]:
                if col in df.columns:
                    combined_mask |= df[col].str.contains(escaped_token, na=False)

        print(f"🔧 [Fallback] Coincidencias encontradas: {combined_mask.sum()}")
        return df[combined_mask] if combined_mask.any() else pd.DataFrame()

    def filter_by_approx_price(
        self, df: pd.DataFrame, target_price: int, tolerance: int = 50000
    ) -> pd.DataFrame:
        lower = target_price - tolerance
        upper = target_price + tolerance
        return df[(df["price"] >= lower) & (df["price"] <= upper)]
