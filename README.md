## Shopify AI Command Center

Streamlit dashboard for Shopify-style order CSVs with optional AI executive summaries.

### Run locally

```powershell
uv sync
uv run streamlit run app.py
```

### Secrets (do not commit)

Create/update `.streamlit/secrets.toml` (already gitignored) and add your keys:

- **Gemini**
  - `GEMINI_API_KEY`
  - (optional) `GEMINI_MODEL` (default: `gemini-2.0-flash`)
- **iFlow (qwen3-max)**
  - `IFLOW_API_KEY` (or `XINLIU_API_KEY`)
  - (optional) `IFLOW_MODEL` (default: `qwen3-max`)
  - (optional) `IFLOW_BASE_URL` (default: `https://apis.iflow.cn/v1/chat/completions`)
- **Provider selection**
  - `AI_PROVIDER = "auto" | "gemini" | "iflow"`

### Deploy (Streamlit Cloud)

Generate `requirements.txt`:

```powershell
uv pip compile pyproject.toml -o requirements.txt
```

In Streamlit Cloud, paste the same secrets into the app’s **Advanced settings → Secrets**.
