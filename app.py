import plotly.express as px
import streamlit as st

from ai_utils import get_ai_insight, send_notification
from data_processor import load_and_process_data


st.set_page_config(page_title="Shopify AI Command Center", layout="wide", page_icon="🛍️")


with st.sidebar:
    st.title("🎛️ Ops Control")
    uploaded_file = st.file_uploader("Upload CSV", type="csv")
    use_demo = st.checkbox("Use Demo Data", value=True)
    ai_provider = st.selectbox(
        "AI Provider",
        options=["Auto", "Gemini", "Qwen3-Max (iFlow)"],
        index=0,
    )
    st.info("💡 Pro Tip: Put your API key in `.streamlit/secrets.toml` (Gemini or iFlow).")


data_source = uploaded_file if uploaded_file else ("shopify_dirty_data.csv" if use_demo else None)
if not data_source:
    st.warning("Please upload a CSV or enable demo data.")
    st.stop()

kpi_data, msg = load_and_process_data(data_source)
if not kpi_data:
    st.error(msg)
    st.stop()


st.title("🛍️ Shopify AI Command Center")
st.caption(f"Data source: {data_source.name if hasattr(data_source, 'name') else data_source}")


c1, c2, c3 = st.columns(3)
c1.metric("💰 Revenue", f"${kpi_data['total_revenue']:,.2f}")
c2.metric("📦 Orders", kpi_data["total_orders"])
c3.metric("📈 AOV", f"${kpi_data['avg_order_value']:.2f}")

st.divider()


chart_left, chart_right = st.columns([2, 1])
with chart_left:
    st.subheader("Daily Sales Trend")
    fig_line = px.line(
        kpi_data["daily_sales"],
        x="Date",
        y="Total_Sales",
        markers=True,
        template="plotly_dark",
    )
    st.plotly_chart(fig_line, width="stretch")

with chart_right:
    st.subheader("Product Mix")
    raw_df = kpi_data["raw_df"]
    prod_sales = raw_df.groupby("Product")["Total_Sales"].sum().reset_index()
    fig_pie = px.pie(prod_sales, values="Total_Sales", names="Product", hole=0.4)
    st.plotly_chart(fig_pie, width="stretch")

st.divider()


st.subheader("🤖 AI Executive Report")

if "ai_report" not in st.session_state:
    st.session_state.ai_report = ""

btn_col, result_col = st.columns([1, 4])
with btn_col:
    if st.button("✨ Generate AI Report", type="primary"):
        with st.spinner("AI is analyzing your data..."):
            provider_key = ai_provider.split(" ", 1)[0].lower()
            if provider_key == "qwen3-max":
                provider_key = "iflow"
            st.session_state.ai_report = get_ai_insight(kpi_data, provider=provider_key)

    if st.session_state.ai_report:
        st.write("")
        if st.button("📨 Send to Slack/Team"):
            if send_notification(st.session_state.ai_report):
                st.toast("✅ Report sent successfully!", icon="🚀")
            else:
                st.error("Failed to send.")

with result_col:
    if st.session_state.ai_report:
        if st.session_state.ai_report.startswith("Error:"):
            st.error(st.session_state.ai_report)
        elif st.session_state.ai_report.startswith(("AI Error:", "Connection Error:", "AI Parse Error:")):
            st.warning(st.session_state.ai_report)
        else:
            st.success("Analysis Complete")
            st.markdown(st.session_state.ai_report)
    else:
        st.info("Click the button to let Gemini analyze your sales performance.")


with st.expander("📄 View cleaned rows"):
    st.dataframe(kpi_data["raw_df"], width="stretch")
