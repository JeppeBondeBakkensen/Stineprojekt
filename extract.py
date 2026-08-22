import json

import polars as pl

pl.Config.set_tbl_rows(-1)
pl.Config.set_tbl_cols(-1)
pl.Config.set_fmt_str_lengths(1000)
pl.Config.set_tbl_width_chars(200)


# Importerer dataframe for strom_sheeted
df_strom = pl.read_excel(
    "Oversigt over kontrakter på Spor Strøm forst og Sikring.xlsx",
    sheet_name="Strøm og Materiel",
    engine="openpyxl",
)
# Sørge for at kollonen er striped og er en string
banenr_TIB = pl.col("Banenr. / TIB").cast(pl.String).str.strip_chars()

# Referencenøgle om det er et banenummer eller TIB nummer
referencenogle = (
    pl.when(banenr_TIB == "Banenummer")
    .then(pl.lit("BANENR"))
    .when(banenr_TIB == "TIB")
    .then(pl.lit("TIB"))
    .otherwise(None)
)

# Lave to nye kolonne Referencetype og referenceværdi, som har enten banenummer
# eller TIB som værdi
df_strom = df_strom.with_columns(
    referencenogle.alias("Referencetype"),
    pl.col("Strækningsnummer")
    .cast(pl.String)
    .str.strip_chars()
    .replace("", None)
    .alias("Referenceværdi"),
).drop_nulls(["Referencetype", "Referenceværdi"])

fejlklassificerede_banenumre = [
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

# Fix fejlklassificerede_banenumre
df_strom = df_strom.with_columns(
    pl.when(
        (pl.col("Referencetype") == "TIB")
        & pl.col("Referenceværdi").is_in(fejlklassificerede_banenumre)
    )
    .then(pl.lit("BANENR"))
    .otherwise(pl.col("Referencetype"))
    .alias("Referencetype")
)

# Lave en ny kolonne Referencenøgle som en ny nøgle at joine på med GeoJSON filen
df_strom = df_strom.with_columns(
    pl.concat_str(
        ["Referencetype", "Referenceværdi"],
        separator=":",
    ).alias("Referencenøgle")
)

# GeoJSON

# Importerer GeoJSON filen
with open(
    "Danmarkskort_med_strækninger.geojson",
    encoding="utf-8",
) as file:
    geojson = json.load(file)

properties_df = pl.from_dicts(
    [feature.get("properties", {}) for feature in geojson["features"]]
).with_columns(pl.col("GLOBALID").cast(pl.String).alias("Id"))

# Det er de kolonner fra GeoJSON som skal joines på banenr
banenummer_referencer = (
    properties_df.select(
        "Id",
        "NAVN",
        "HVDSTRK_NAVN",
        "FRA_KM",
        "TIL_KM",
        pl.lit("BANENR").alias("Referencetype"),  # Ny kolonne som hedder Referencetype
        pl.col("BANENR")
        .cast(pl.String)
        .str.strip_chars()
        .replace("", None)
        .alias("Referenceværdi"),
    )
    .drop_nulls(["Referenceværdi"])
    .unique(["Id", "Referencetype", "Referenceværdi"])
)


# Det er de kolonner fra GeoJSON som skal joines på tib nummer
tib_referencer = (
    properties_df.select(
        "Id",
        "NAVN",
        "HVDSTRK_NAVN",
        "FRA_KM",
        "TIL_KM",
        pl.lit("TIB").alias("Referencetype"),
        pl.col("TIB").cast(pl.String).str.split(",").alias("Referenceværdi"),
    )
    .explode("Referenceværdi", empty_as_null=True)
    .with_columns(pl.col("Referenceværdi").str.strip_chars().replace("", None))
    .drop_nulls(["Referenceværdi"])
    .unique(["Id", "Referencetype", "Referenceværdi"])
)

# Kombiner banenummer og tib nummer
geojson_referencer = pl.concat(
    [banenummer_referencer, tib_referencer],
    how="vertical",
).with_columns(
    pl.concat_str(
        ["Referencetype", "Referenceværdi"],
        separator=":",
    ).alias("Referencenøgle")
)

# Join geojson på df_strom
df_geojson_combined = df_strom.join(
    geojson_referencer,
    on=["Referencetype", "Referenceværdi", "Referencenøgle"],
    how="left",
)
