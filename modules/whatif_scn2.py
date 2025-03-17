import streamlit as st
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

def load_and_prepare_data(file_path):
    df = pd.read_excel(file_path, sheet_name="Sheet1")
    columns_to_convert = ["Q2", "ABN %", "Loaded AHT", "Met", "Missed"]
    for col in columns_to_convert:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.fillna(0)
    return df

def train_regression_model(df):
    features = ["Q2", "ABN %", "Occ Assumption", "Staffing", "Demand", "Occupancy Rate"]
    target = "Requirement"
    X = df[features]
    y = df[target]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LinearRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"Model Trained: MAE = {mae:.2f}, R2 Score = {r2:.4f}")
    joblib.dump(model, 'model_whatifs')
    return model

def analyze_scenarios(df, model, q2, abn, occ):
    test_data = pd.DataFrame({
        "Q2": q2,
        "ABN %": [abn/100],
        "Occ Assumption": [occ/100],
        "Staffing": [df["Staffing"].median()],
        "Demand": [df["Demand"].median()],
        "Occupancy Rate": [df["Occupancy Rate"].median()],
    })
    fte_prediction = model.predict(test_data)[0]
    return int(fte_prediction)

def fte_impact_of_demand_increase(df, model, q2, abn, occ):
    demand_changes = [5, 10, 15, 20, 25]
    predictions = []
    for change in demand_changes:
        demand_scenario = df["Demand"].median() * (1 + change / 100)
        fte_pred = model.predict(pd.DataFrame({
            "Q2": q2, "ABN %": [abn/100], "Occ Assumption": [occ/100],
            "Staffing": [df["Staffing"].median()], "Demand": [demand_scenario], "Occupancy Rate": [df["Occupancy Rate"].median()]
        }))[0]
        predictions.append((change, int(fte_pred)))
    return predictions

def impact_of_occ_assumption_change(df, model, q2, abn):
    occ_changes = [-10, -5, 0, 5, 10]
    predictions = []
    for change in occ_changes:
        occ_scenario = df["Occ Assumption"].median() * (1 + change / 100)
        fte_pred = model.predict(pd.DataFrame({
            "Q2": q2, "ABN %": [abn/100], "Occ Assumption": occ_scenario,
            "Staffing": [df["Staffing"].median()], "Demand": [df["Demand"].median()], "Occupancy Rate": [df["Occupancy Rate"].median()]
        }))[0]
        predictions.append((change, int(fte_pred)))
    return predictions

st.title("What-If Analysis for FTE Requirements")
st.sidebar.header("User Inputs")

def scn2():

    file_path = st.file_uploader("Upload your Excel file", type=["xlsx"])

    if file_path is not None:
        df = load_and_prepare_data(file_path)
        
        st.header("Filter Data------------------------->")
        # Dropdown filters based on columns
        language = st.selectbox("Select Language", df['Language'].unique())
        req_media = st.selectbox("Select Req Media", df['Req Media'].unique())
        usd = st.selectbox("Select USD", df['USD'].unique())
        level = st.selectbox("Select Level", df['Level'].unique())

        # Filter the DataFrame based on selected values
        df = df[(df['Language'] == language) & (df['Req Media'] == req_media) & 
                     (df['USD'] == usd) & (df['Level'] == level)]
        
        st.header("Output------------------------------>")        
        
        model = train_regression_model(df)
    
        q2 = st.sidebar.slider("Set Q2 Time", min_value=0, max_value=100, value=20, step=1)
        abn = st.sidebar.slider("Set Abandon Rate (%)", min_value=0, max_value=10, value=2, step=1)
        occ = st.sidebar.slider("Set Occupancy Rate (%)", min_value=0, max_value=100, value=80, step=1)
    
        fte_prediction = analyze_scenarios(df, model, q2, abn, occ)
        st.write(f"Predicted FTE based on user inputs: {fte_prediction}")
    
        st.header("FTE Impact of Demand Increase")
        demand_impact = fte_impact_of_demand_increase(df, model, q2, abn, occ)
        for change, fte_pred in demand_impact:
            st.write(f"Demand Increase {change}%: Predicted FTE = {fte_pred}")

        st.header("Impact of OCC Assumption Change")
        occ_impact = impact_of_occ_assumption_change(df, model, q2, abn)
        for change, fte_pred in occ_impact:
            st.write(f"OCC Assumption Change {change}%: Predicted FTE = {fte_pred}")

if __name__ == '__main__':
    scn2()
