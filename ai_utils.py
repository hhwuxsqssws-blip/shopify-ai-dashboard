from __future__ import annotations

import json
from typing import Any

import requests
import streamlit as st


def _get_secret(key: str, default: str = "") -> str:
    try:
        value = st.secrets.get(key, default)
    except Exception:
        value = default
    return str(value).strip()


def _parse_int(value: str, default: int) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _parse_float(value: str, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _build_kpi_prompt(kpi_data: dict[str, Any]) -> str:
    return f"""
You are an E-commerce Expert CFO. Analyze this Shopify KPI snapshot:
- Total Revenue: ${kpi_data.get('total_revenue')}
- Total Orders: {kpi_data.get('total_orders')}
- AOV: ${kpi_data.get('avg_order_value')}

Please provide a professional "Weekly Executive Summary" (in English).
Format:
1) 📊 Performance Overview (1 sentence)
2) 🚩 Key Risks (bullet points)
3) 🚀 Actionable Recommendations (bullet points)
Keep it concise and specific.
""".strip()


def _get_ai_insight_gemini(
    kpi_data: dict[str, Any],
    *,
    model: str | None = None,
    timeout_s: float = 20.0,
) -> str:
    api_key = _get_secret("GEMINI_API_KEY")
    if not api_key or "粘贴在这里" in api_key:
        return "Error: Missing GEMINI_API_KEY in `.streamlit/secrets.toml`."

    chosen_model = model or _get_secret("GEMINI_MODEL", "gemini-2.0-flash")
    prompt = _build_kpi_prompt(kpi_data)

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{chosen_model}:generateContent?key={api_key}"
    )
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload),
            timeout=timeout_s,
        )
    except requests.RequestException as e:
        return f"Connection Error: {e}"

    if response.status_code != 200:
        text = response.text
        if len(text) > 800:
            text = text[:800] + "…"
        return f"AI Error: {response.status_code} - {text}"

    try:
        body = response.json()
        return body["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Parse Error: {e} (raw={response.text[:800]})"


def _get_ai_insight_iflow(
    kpi_data: dict[str, Any],
    *,
    model: str | None = None,
    timeout_s: float = 20.0,
) -> str:
    """
    Call iFlow chat completions (OpenAI-compatible).

    Docs example endpoint:
      POST https://apis.iflow.cn/v1/chat/completions

    Secrets:
      - IFLOW_API_KEY (or XINLIU_API_KEY)
      - IFLOW_MODEL (default: qwen3-max)
      - IFLOW_BASE_URL (default: https://apis.iflow.cn/v1/chat/completions)
    """
    api_key = _get_secret("IFLOW_API_KEY") or _get_secret("XINLIU_API_KEY")
    if not api_key:
        return "Error: Missing IFLOW_API_KEY (or XINLIU_API_KEY) in `.streamlit/secrets.toml`."

    url = _get_secret("IFLOW_BASE_URL", "https://apis.iflow.cn/v1/chat/completions")
    chosen_model = model or _get_secret("IFLOW_MODEL", "qwen3-max")

    max_tokens = _parse_int(_get_secret("IFLOW_MAX_TOKENS", "512"), 512)
    temperature = _parse_float(_get_secret("IFLOW_TEMPERATURE", "0.7"), 0.7)
    top_p = _parse_float(_get_secret("IFLOW_TOP_P", "0.7"), 0.7)
    top_k = _parse_int(_get_secret("IFLOW_TOP_K", "50"), 50)
    frequency_penalty = _parse_float(_get_secret("IFLOW_FREQUENCY_PENALTY", "0.5"), 0.5)

    system_msg = "You are an E-commerce Expert CFO. Write concise executive summaries."
    user_msg = _build_kpi_prompt(kpi_data)

    payload: dict[str, Any] = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "frequency_penalty": frequency_penalty,
        "n": 1,
        "response_format": {"type": "text"},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout_s)
    except requests.RequestException as e:
        return f"Connection Error: {e}"

    if response.status_code != 200:
        text = response.text
        if len(text) > 800:
            text = text[:800] + "…"
        return f"AI Error: {response.status_code} - {text}"

    try:
        body = response.json()
        choice0 = body["choices"][0]["message"]
        content = choice0.get("content") or ""
        if content:
            return content
        # Some providers may return reasoning_content only.
        reasoning = choice0.get("reasoning_content") or ""
        return reasoning or "AI Error: Empty response content."
    except Exception as e:
        return f"AI Parse Error: {e} (raw={response.text[:800]})"


def _has_gemini_key() -> bool:
    api_key = _get_secret("GEMINI_API_KEY")
    return bool(api_key and "粘贴在这里" not in api_key)


def _has_iflow_key() -> bool:
    return bool(_get_secret("IFLOW_API_KEY") or _get_secret("XINLIU_API_KEY"))


def get_ai_insight(
    kpi_data: dict[str, Any],
    *,
    provider: str | None = None,
    model: str | None = None,
    timeout_s: float = 20.0,
) -> str:
    """
    Get an English executive summary from the configured provider.

    Provider selection:
      - explicit `provider=...`
      - secrets `AI_PROVIDER` ("auto" | "gemini" | "iflow")
      - auto: use iFlow if IFLOW_API_KEY exists, else Gemini
    """
    chosen = (provider or _get_secret("AI_PROVIDER", "auto")).strip().lower()
    if chosen in {"qwen", "qwen3", "qwen3-max", "iflow"}:
        chosen = "iflow"
    if chosen in {"google", "gemini"}:
        chosen = "gemini"

    if chosen == "auto":
        has_iflow = _has_iflow_key()
        has_gemini = _has_gemini_key()
        if not has_iflow and not has_gemini:
            return (
                "Error: Missing API key. Set GEMINI_API_KEY or IFLOW_API_KEY in "
                "`.streamlit/secrets.toml`."
            )

        if has_iflow:
            chosen = "iflow"
        else:
            chosen = "gemini"

    if chosen == "iflow":
        return _get_ai_insight_iflow(kpi_data, model=model, timeout_s=timeout_s)
    return _get_ai_insight_gemini(kpi_data, model=model, timeout_s=timeout_s)


def send_notification(message: str, *, timeout_s: float = 10.0) -> bool:
    """
    Push a message to Slack/Discord (webhook).

    Secrets:
      - WEBHOOK_URL (optional)
      - WEBHOOK_FORMAT (optional: "slack" or "discord"; default: "slack")
    """
    webhook_url = _get_secret("WEBHOOK_URL")
    if not webhook_url:
        # Local dev: treat as success to avoid blocking the workflow.
        print("⚠️ 未配置 WEBHOOK_URL，模拟发送成功。")
        return True

    fmt = _get_secret("WEBHOOK_FORMAT", "slack").lower()
    if fmt == "discord":
        payload: dict[str, Any] = {"content": message}
    else:
        payload = {"text": message}

    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout_s)
        # Some webhooks return 204 No Content on success.
        if resp.status_code >= 400:
            print(f"发送失败: {resp.status_code} {resp.text[:300]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"发送失败: {e}")
        return False
