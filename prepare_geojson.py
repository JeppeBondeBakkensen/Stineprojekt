import json

from rail_data import WEB_GEOJSON_PATH, prepare_geojson


def main() -> None:
    geojson = prepare_geojson()
    with WEB_GEOJSON_PATH.open("w", encoding="utf-8") as file:
        json.dump(geojson, file, ensure_ascii=False, separators=(",", ":"))
    print(
        f"Wrote {len(geojson['features'])} features to {WEB_GEOJSON_PATH.name} "
        f"({WEB_GEOJSON_PATH.stat().st_size / 1_000_000:.2f} MB)"
    )


if __name__ == "__main__":
    main()
