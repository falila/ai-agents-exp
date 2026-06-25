import streamlit as st

st.title("Legacy PayWithAgent UI")
st.markdown(
    "The combined legacy dashboard has been retired. "
    "Use the dedicated merchant and consumer dashboards instead."
)

st.markdown("### Run one of the new dashboard entrypoints:")
st.code("streamlit run src/merchant_app.py --server.port 8501")
st.code("streamlit run src/consumer_app.py --server.port 8502")

st.markdown("---")
st.markdown(
    "If you are running this inside Docker, start the services with `docker compose up`. "
    "The merchant dashboard will appear on port 8501 and the consumer dashboard on port 8502."
)
