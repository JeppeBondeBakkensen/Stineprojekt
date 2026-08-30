import json
from pathlib import Path

import polars as pl
import streamlit as st

DATA_DIR = Path(__file__).parent
EXCEL_PATH = DATA_DIR / "Oversigt over kontrakter på Spor Strøm forst og Sikring.xlsx"
GEOJSON_PATH = DATA_DIR / "Danmarkskort_med_strækninger.geojson"
FEJLKLASSIFICEREDE_BANENUMRE = [
    "22",
    "27",
    "79",
    "81",
    "82",
    "83",
    "84",
    "85",
    "86",
    "88",
]
UDFASEREDE_TIB = {"9", "36", "37"}
S_BANE_TIB = {"88", "810", "820", "830", "840", "850", "860", "880"}
ACTIVE_BANENUMBERS = {
    "10",
    "11a",
    "11b",
    "12",
    "13",
    "14",
    "15a",
    "15b",
    "16",
    "19",
    "20",
    "21",
    "22",
    "23a",
    "23b",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "32",
    "33a",
    "33b",
    "34",
    "36",
    "39",
    "40",
    "44",
    "47",
    "49",
    "50",
    "51",
    "54",
    "55",
    "56",
    "70",
    "71",
    "77",
    "78",
    "79",
    "90",
    "91",
    "92",
    "94",
    "95",
    "96",
    "97",
    "98",
    "99",
}
CONTRACT_SHEETS = (
    "Strøm og Materiel",
    "Sikring",
    "Beredskab (interne krav)",
    "Fors, afvanding geoteknik, bro",
)


def normalize_tib(value: object) -> str | None:
    tib = str(value or "").strip()
    if not tib:
        return None
    if tib.isdigit():
        number = int(tib)
        if 600 <= number <= 699:
            return None
        if 1000 <= number <= 1099:
            tib = str(number - 1000)
    return None if tib in UDFASEREDE_TIB else tib


def normalize_tibs(value: object) -> str:
    tibs = []
    for raw_tib in str(value or "").split(","):
        if (tib := normalize_tib(raw_tib)) and tib not in tibs:
            tibs.append(tib)
    return ",".join(tibs)


def is_s_bane(tib_value: object, banenumber: object) -> bool:
    tibs = set(normalize_tibs(tib_value).split(","))
    banenumber_text = str(banenumber or "").strip()
    return bool(tibs & S_BANE_TIB) or (
        banenumber_text.isdigit() and 80 <= int(banenumber_text) <= 89
    )


def is_active_banenumber(value: object) -> bool:
    return str(value or "").strip() in ACTIVE_BANENUMBERS


def clean_excel_line_breaks(dataframe: pl.DataFrame) -> pl.DataFrame:
    return dataframe.with_columns(
        pl.col(pl.String)
        .str.replace_all("_x000D_\n", "\n", literal=True)
        .str.replace_all("_x000D_", "\n", literal=True)
    )


@st.cache_resource(show_spinner="Indlæser kontraktdata...")
def load_combined_data() -> pl.DataFrame:
    """Indlæs og sammenkæd kontrakt- og kortdata én gang."""
    frames = []
    extra_frames = []
    for sheet_name in CONTRACT_SHEETS:
        df_sheet = clean_excel_line_breaks(
            pl.read_excel(
                EXCEL_PATH,
                sheet_name=sheet_name,
                engine="openpyxl",
            )
        )
        if sheet_name == "Strøm og Materiel":
            frames.append(df_sheet.with_columns(pl.lit(sheet_name).alias("Ark")))
        else:
            extra_frames.append(df_sheet.with_columns(pl.lit(sheet_name).alias("Ark")))

    df_strom = pl.concat(frames, how="diagonal_relaxed")
    banenr_tib = pl.col("Banenr. / TIB").cast(pl.String).str.strip_chars()
    referencenoegle = (
        pl.when(banenr_tib == "Banenummer")
        .then(pl.lit("BANENR"))
        .when(banenr_tib == "TIB")
        .then(pl.lit("TIB"))
        .otherwise(None)
    )
    df_strom = (
        df_strom.with_columns(
            referencenoegle.alias("Referencetype"),
            pl.col("Strækningsnummer")
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .alias("Referenceværdi"),
        )
        .drop_nulls(["Referencetype", "Referenceværdi"])
        .with_columns(
            pl.when(
                (pl.col("Referencetype") == "TIB")
                & pl.col("Referenceværdi").is_in(FEJLKLASSIFICEREDE_BANENUMRE)
            )
            .then(pl.lit("BANENR"))
            .otherwise(pl.col("Referencetype"))
            .alias("Referencetype")
        )
        .with_columns(
            pl.when(pl.col("Referencetype") == "TIB")
            .then(
                pl.col("Referenceværdi").map_elements(
                    normalize_tib, return_dtype=pl.String
                )
            )
            .otherwise(pl.col("Referenceværdi"))
            .alias("Referenceværdi")
        )
        .drop_nulls(["Referenceværdi"])
        .filter(
            ~(
                (
                    (pl.col("Referencetype") == "TIB")
                    & pl.col("Referenceværdi").is_in(S_BANE_TIB)
                )
                | (
                    (pl.col("Referencetype") == "BANENR")
                    & pl.col("Referenceværdi")
                    .cast(pl.Int64, strict=False)
                    .is_between(80, 89)
                )
            )
        )
        .filter(
            (pl.col("Referencetype") != "BANENR")
            | pl.col("Referenceværdi").is_in(ACTIVE_BANENUMBERS)
        )
        .with_columns(
            pl.concat_str(["Referencetype", "Referenceværdi"], separator=":").alias(
                "Referencenøgle"
            )
        )
    )

    with GEOJSON_PATH.open(encoding="utf-8") as file:
        geojson = json.load(file)
    properties = pl.from_dicts(
        [
            properties
            for feature in geojson["features"]
            if is_active_banenumber(
                (properties := feature.get("properties", {})).get("BANENR")
            )
            and not is_s_bane(
                properties.get("TIB"),
                properties.get("BANENR"),
            )
        ]
    ).with_columns(pl.col("GLOBALID").cast(pl.String).alias("Id"))

    banenummer_referencer = (
        properties.select(
            "Id",
            "NAVN",
            "HVDSTRK_NAVN",
            "FRA_KM",
            "TIL_KM",
            pl.lit("BANENR").alias("Referencetype"),
            pl.col("BANENR")
            .cast(pl.String)
            .str.strip_chars()
            .replace("", None)
            .alias("Referenceværdi"),
        )
        .drop_nulls(["Referenceværdi"])
        .unique(["Id", "Referencetype", "Referenceværdi"])
    )
    tib_referencer = (
        properties.select(
            "Id",
            "NAVN",
            "HVDSTRK_NAVN",
            "FRA_KM",
            "TIL_KM",
            pl.lit("TIB").alias("Referencetype"),
            pl.col("TIB")
            .map_elements(normalize_tibs, return_dtype=pl.String)
            .str.split(",")
            .alias("Referenceværdi"),
        )
        .explode("Referenceværdi", empty_as_null=True)
        .with_columns(pl.col("Referenceværdi").str.strip_chars().replace("", None))
        .drop_nulls(["Referenceværdi"])
        .unique(["Id", "Referencetype", "Referenceværdi"])
    )
    geojson_referencer = pl.concat(
        [banenummer_referencer, tib_referencer], how="vertical"
    ).with_columns(
        pl.concat_str(["Referencetype", "Referenceværdi"], separator=":").alias(
            "Referencenøgle"
        )
    )
    df_strom = df_strom.join(
        geojson_referencer,
        on=["Referencetype", "Referenceværdi", "Referencenøgle"],
        how="left",
    )
    if extra_frames:
        df_strom = pl.concat([df_strom, *extra_frames], how="diagonal_relaxed")
    return df_strom
