import streamlit as st
import pandas as pd

from services.apify_service import ApifyService
from services.exporter import ExportService
from utils.formatter import format_results


st.set_page_config(
    page_title="Google Lead Generator",
    page_icon="📍",
    layout="wide"
)

apify = ApifyService()
exporter = ExportService()


st.markdown("""
<style>

.block-container{
    padding-top:2rem;
}

.stButton>button{
    width:100%;
    height:45px;
    font-size:17px;
    font-weight:bold;
}

</style>
""", unsafe_allow_html=True)


st.title("📍 Google Lead Generator")
st.write("Generate Google Maps business leads using Apify.")


st.sidebar.header("Search Parameters")

query = st.sidebar.text_input(
    "Search Query",
    placeholder="Software Companies"
)

location = st.sidebar.text_input(
    "Location",
    placeholder="Chennai"
)

max_results = st.sidebar.number_input(
    "Maximum Results",
    min_value=1,
    max_value=500,
    value=20
)

generate = st.sidebar.button("🚀 Generate Leads")


if generate:

    if not query or not location:
        st.warning("Please enter both Query and Location.")
        st.stop()

    try:

        with st.spinner("Searching Google Maps..."):

            results = apify.run(
                query,
                location,
                max_results
            )

            df = format_results(results)

    except Exception as e:
        st.error(e)
        st.stop()

    total = len(df)
    emails = df["Email"].replace("", pd.NA).count()
    phones = df["Phone"].replace("", pd.NA).count()
    websites = df["Website"].replace("", pd.NA).count()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Leads", total)
    col2.metric("Emails", emails)
    col3.metric("Phones", phones)
    col4.metric("Websites", websites)

    st.divider()

    keyword = st.text_input("Search Leads")

    if keyword:

        filtered_df = df[
            df.astype(str)
            .apply(lambda column: column.str.contains(keyword, case=False, na=False))
            .any(axis=1)
        ]

    else:
        filtered_df = df

    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=600
    )

    files = exporter.export_all(filtered_df)

    col1, col2 = st.columns(2)

    with open(files["csv"], "rb") as file:

        col1.download_button(
            "⬇ Download CSV",
            file,
            "google_leads.csv",
            "text/csv"
        )

    with open(files["excel"], "rb") as file:

        col2.download_button(
            "⬇ Download Excel",
            file,
            "google_leads.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )