# Test Project

A Python project using uv, ty, Ruff, pytest, and the Tokyo Night Storm VS Code
theme.

```shell
uv sync
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
```

```shell
uv run streamlit run app.py
```

When `Danmarkskort_med_strækninger.geojson` changes, rebuild the optimized web map:

```shell
uv run python prepare_geojson.py
```
