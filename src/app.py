import streamlit as st
from data_extractor import run_data_extractor
from staffing_requirements import run_fte_analysis
from default import main
from Datamart_Daywise_V3 import run_daywise_tool_ver3
import sys
import os

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["What-if analysis","Data Extractor", "Staffing Req Analysis","Datamart-Daywise"])

# Main content based on selection
if page == "What-if analysis":
    st.title("What-If Analysis Tool")
    st.write("Select a scenario to run the analysis.")
    main()

elif page == "Data Extractor":
    st.title("Data Extractor")
    run_data_extractor()

elif page == "Staffing Req Analysis":
    st.title("Staffing Req Analysis")
    run_fte_analysis()

elif page == "Datamart-Daywise":
    st.title("Datamart Daywise")
    run_daywise_tool_ver3()

