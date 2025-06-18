import streamlit as st
import pandas as pd
import numpy as np
import os
from io import BytesIO
import warnings
from streamlit_folium import st_folium
from dateutil import parser


warnings.filterwarnings("ignore")

# Function to process occupancy assumptions
def process_occupancy_assump(file, sheets):
    occ_assumptions_dataframe = pd.DataFrame()
    occ_columns = []

    for sheet in sheets:
        try:
            df = pd.read_excel(file, sheet_name=sheet, header=None)
        except ValueError as e:
            st.error(f"❌ Sheet '{sheet}' not found in the uploaded Excel file. Please check the sheet names and try again.")
            st.stop()
        except Exception as e:
            st.error(f"⚠️ Unexpected error while reading sheet '{sheet}': {e}")
            st.stop()
        if df.empty:
            st.warning(f"⚠️ Sheet '{sheet}' is empty. Skipping this sheet.")
            continue

        # Process the DataFrame
        df = df.iloc[3:, 3:].reset_index(drop=True)
        df = df.T.reset_index(drop=True)
        
        df.columns = df.iloc[0].astype(str) + " " + df.iloc[1].astype(str) + " " + df.iloc[2].astype(str)
        df.columns = df.columns.str.replace("nan", "").str.strip()
        df = df[3:].reset_index(drop=True)
        df["Week Of:"] = pd.to_datetime(df["Week Of:"],format='mixed', dayfirst=True,errors="coerce")

        occ_columns = [col for col in df.columns if "OCC Assumptions" in col]
        occ_df = df[["Week Of:"] + occ_columns]
        occ_assumptions_dataframe = pd.concat([occ_assumptions_dataframe, occ_df], axis=0)
        
    return occ_assumptions_dataframe, occ_columns

# Function to expand weekly occupancy to daily long format
def expand_weekly_occ_to_daily_long(df_weekly):
    df_weekly['Week Of:'] = pd.to_datetime(df_weekly['Week Of:'],format='mixed', dayfirst=True, errors='coerce')
    df_weekly = df_weekly.dropna(subset=['Week Of:'])  # Drop rows where date is not parsable

    df_daily = df_weekly.loc[df_weekly.index.repeat(7)].copy()
    df_daily['Day Offset'] = df_daily.groupby('Week Of:').cumcount()
    df_daily['startDate per day'] = df_daily['Week Of:'] + pd.to_timedelta(df_daily['Day Offset'], unit='D')
    df_daily['startDate per day'] = pd.to_datetime(df_daily['startDate per day'],format='mixed', dayfirst=True,errors='coerce').dt.normalize()

    df_daily = df_daily.drop(columns=['Week Of:', 'Day Offset'])

    df_long = df_daily.melt(id_vars='startDate per day', var_name='Level', value_name='OCC Assumption')
    df_long['startDate per day'] = pd.to_datetime(df_long['startDate per day'],format='mixed', dayfirst=True,errors='coerce').dt.normalize()
    return df_long

# Function to extract level from a string
def extract_level_and_category(input_string):
    start_pos = input_string.find('(')
    end_pos = input_string.find(')', start_pos)
    
    if start_pos != -1 and end_pos != -1:
        l_value = input_string[start_pos + 1:end_pos]
        
        if any(level in l_value for level in ['L3', 'L4', 'L5']):
            level = l_value
        else:
            level = None
        
        if any(category in input_string for category in ['USD', 'Global']):
            category = 'USD' if 'USD' in input_string else 'Global'
        else:
            category = None
        
        return level, category
    else:
        return None, None
       

# Function to convert DataFrame for calls
def convert_df_calls(df):
    df['startDate per day'] = pd.to_datetime(df['startDate per day'],format='mixed', dayfirst=True, errors='coerce')
    raw_float_cols = ['ABNs', 'Calls', 'Q2', 'Loaded AHT', 'ABN %']
    percent_cols = ['Met', 'Missed']
    for col in raw_float_cols:
        df[col] = df[col].astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce')
    for col in percent_cols:
        df[col] = df[col].astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce') / 100.0
    return df

# Function to convert DataFrame for FTE
def convert_df_fte(df, lang):
    
    # Let pandas infer the format
    df['startDate per day'] = pd.to_datetime(df['startDate per day'],format='mixed', dayfirst=True, errors='coerce')
    df['startDate per day'] = df['startDate per day'].dt.strftime('%Y-%m-%d')
    
    df['Level'] = df['Agent Type'].astype(str).str[:2]
    df.rename(columns={'Product': 'Req Media', 'Location': 'USD', 'Level': 'Level_ix'}, inplace=True)
    df['Weekly FTEs'] = df['Weekly FTEs'].astype(str).str.replace(',', '', regex=False)
    df['Weekly FTEs'] = pd.to_numeric(df['Weekly FTEs'], errors='coerce')
    df['USD'] = df['USD'].replace('Non-USD', 'Global')
    df['Req Media'] = df['Req Media'].replace('Video Dedicated', 'VIDEO')
    return df

# Function to convert DataFrame for occupancy
def convert_df_occ(df):
    df['startDate per day'] = pd.to_datetime(df['startDate per day'],format='mixed', dayfirst=True, errors='coerce')
    df.rename(columns={'Req. Media': 'Req Media'}, inplace=True)
    df['OCC'] = df['OCC'].astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False)
    df['OCC'] = pd.to_numeric(df['OCC'], errors='coerce')
    return df

# Function to convert DataFrame for hybrid
def convert_df_hybrid(df):
    percent_cols = ['L4 Hybrid Minutes %', 'L5 Hybrid Minutes %']
    for col in percent_cols:
        df[col] = df[col].astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce') / 100.0
    return df

# Function to process CSV files
def process_csv_files(uploaded_fte_file, uploaded_calls_file, uploaded_occ_file, uploaded_hybrid_file, lang):
    df_calls = None
    df_fte = None
    df_hybrid = None
    df_occ = None

    if uploaded_calls_file:
        df_calls = pd.read_csv(uploaded_calls_file)
        df_calls = convert_df_calls(df_calls)
    if uploaded_fte_file:
        df_fte = pd.read_csv(uploaded_fte_file)
        df_fte = convert_df_fte(df_fte, lang)
    if uploaded_hybrid_file:
        df_hybrid = pd.read_csv(uploaded_hybrid_file)
        df_hybrid = convert_df_hybrid(df_hybrid)
    if uploaded_occ_file:
        df_occ = pd.read_csv(uploaded_occ_file)
        df_occ = convert_df_occ(df_occ)

    return df_calls, df_fte, df_hybrid, df_occ

# Function to get hybrid percentages by language
def get_hybrid_percentages_by_language(df_hybrid, language):
    language = language.strip().upper()
    matching_languages = df_hybrid[df_hybrid['Language'].str.upper().str.contains(language, na=False)]

    if matching_languages.empty:
        raise ValueError(f"Language containing '{language}' not found in hybrid data.")
    hybrid_row = matching_languages.iloc[0]
    matched_language = hybrid_row['Language']
    return matched_language, {
        'Language': matched_language,
        'L4 Hybrid Minutes %': float(hybrid_row['L4 Hybrid Minutes %']),
        'L5 Hybrid Minutes %': float(hybrid_row['L5 Hybrid Minutes %'])
    }

# Function to convert DataFrame to Excel
def to_excel(df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    output.seek(0)
    return output.read()
    # writer = pd.ExcelWriter(output, engine='xlsxwriter')
    # df.to_excel(writer, index=False, sheet_name='Sheet1')
    # # writer.save()
    # processed_data = output.getvalue()
    # return processed_data

def assign_hybrid_pct(level):
    if level == 'L4 - MSI':
        return lang_hybrid['L4 Hybrid Minutes %']
    elif level == 'L5 - All Call':
        return lang_hybrid['L5 Hybrid Minutes %']
    else:
        return 0.0

def extract_level2(level_str):
    if 'L3' in level_str.upper():
        return 'L3'
    elif 'L4' in level_str.upper():
        return 'L4'
    elif 'L5' in level_str.upper():
        return 'L5'
    else:
        return 'Other'

def extract_after_weekly_planner(text):
    start_pos = text.find('Weekly Planner')
    if start_pos != -1:
        return text[start_pos + len('Weekly Planner'):].strip()
    else:
        return None

    # Streamlit app

def run_daywise_tool():
    global lang_hybrid
    st.title('Datamart Creation - Daywise Data')

    uploaded_fte_file = st.file_uploader("Upload FTE CSV file", type="csv")
    uploaded_calls_file = st.file_uploader("Upload Calls CSV file", type="csv")
    uploaded_occ_file = st.file_uploader("Upload Occupancy CSV file", type="csv")
    uploaded_hybrid_file = st.file_uploader("Upload Hybrid CSV file", type="csv")
    uploaded_wp_file = st.file_uploader("Upload Weekly Planner XLSM file", type="xlsm")

    planner_type = st.multiselect("Select sheets to process", ["1. Weekly Planner OPI USD", "2. Weekly Planner OPI Global", 
                                                            "3. Weekly Planner VRI", "1. Weekly Planner OPI", 
                                                            "2. Weekly Planner VRI", "3. UKD"])
    try:
        if not planner_type:
            st.warning("Please select at least one sheet to process.")
            return
    except Exception as e:
        st.error(f"An error occurred while processing the selected sheets: {e}")
        return
    if st.button('Process Files'):
        if uploaded_wp_file:
            
            sheets = planner_type
            occ_assumptions_dataframe, occ_columns = process_occupancy_assump(uploaded_wp_file, sheets)
                
            if any("VRI" in item for item in sheets):
                
                # Create new columns with Global and USD suffixes
                occ_assumptions_dataframe['Global OCC Assumptions (L4):'] = occ_assumptions_dataframe['OCC Assumptions (L4):']
                occ_assumptions_dataframe['USD OCC Assumptions (L4):'] = occ_assumptions_dataframe['OCC Assumptions (L4):']
                occ_assumptions_dataframe['Global OCC Assumptions (L5):'] = occ_assumptions_dataframe['OCC Assumptions (L5):']
                occ_assumptions_dataframe['USD OCC Assumptions (L5):'] = occ_assumptions_dataframe['OCC Assumptions (L5):']   
                occ_assumptions_dataframe.drop(columns=['OCC Assumptions (L4):', 'OCC Assumptions (L5):'], inplace=True)
                
            df_occ_assump = expand_weekly_occ_to_daily_long(occ_assumptions_dataframe)

            df_occ_assump[['Level', 'USD']] = df_occ_assump['Level'].apply(lambda x: pd.Series(extract_level_and_category(x)))
            
            # Convert list to string       
            xlsm_files_str = uploaded_wp_file.name[:3]
        
            lang = xlsm_files_str

            df_calls, df_fte, df_hybrid, df_occ = process_csv_files(uploaded_fte_file, uploaded_calls_file, 
                                                                    uploaded_occ_file, uploaded_hybrid_file, lang)
            df_fte['Level'] = df_fte['Level_ix'].apply(extract_level2)
            matched_language, lang_hybrid = get_hybrid_percentages_by_language(df_hybrid, lang)
            # Step 1: Filter FTE data for the processing language only
            df_fte_lang = df_fte[df_fte['Language'] == matched_language].copy()
            
            
            # Replace NaN values with zero
            df_fte_lang = df_fte_lang.fillna(0)
            
            # Ensure clean 'Product' column
            df_fte_lang['startDate per day'] = pd.to_datetime(df_fte_lang['startDate per day'],format='mixed', dayfirst=True,errors='coerce')
            
            df_fte_pivoted = df_fte_lang.pivot_table(
                index=['startDate per day', 'USD','Language','Level_ix'],
                columns='Req Media',
                values='Weekly FTEs',
                aggfunc='sum'
            ).reset_index()
            
            df_fte_grouped = df_fte_pivoted.copy()
            
            df_fte_grouped['Hybrid %'] = df_fte_grouped['Level_ix'].apply(assign_hybrid_pct)
            df_fte_grouped.rename(columns={'Level_ix': 'Level'}, inplace=True)

            # Calculate Hybrid FTEs from 'Hybrid' column * Hybrid %
            # Use numpy's where function to handle the conditional logic
            df_fte_grouped['Hybrid FTEs'] = np.where(df_fte_grouped['Hybrid %'] != 0,
                                            df_fte_grouped['Hybrid'] * df_fte_grouped['Hybrid %'],
                                            0)

            # Add hybrid to OPI and Video Dedicated
            df_fte_grouped['Total OPI FTEs'] = df_fte_grouped['OPI'] + df_fte_grouped['Hybrid FTEs']
            df_fte_grouped['Total VRI FTEs'] = df_fte_grouped['VIDEO'] + df_fte_grouped['Hybrid FTEs']

            # Replace NaN values with zero
            df_fte_grouped = df_fte_grouped.fillna(0)


            df_fte_grouped=df_fte_grouped[df_fte_grouped['Total OPI FTEs'] > df_fte_grouped['Total OPI FTEs'].quantile(0.20)]


            # Select only the necessary columns from df_fte_grouped for merging
            df_opi_vri_fte = df_fte_grouped[['startDate per day', 'Language','USD','Level', 'Total OPI FTEs', 'Total VRI FTEs']]

            # Ensure date format consistency in df_calls
            df_calls['startDate per day'] = pd.to_datetime(df_calls['startDate per day'],format='mixed', dayfirst=True, errors='coerce')       
            

            # Merge only OPI/VRI totals into df_calls using common keys
            df_calls_with_fte = pd.merge(
                df_calls,
                df_opi_vri_fte,
                on=['startDate per day','USD', 'Language', 'Level'],
                how='left'
            )

            final_fte_occ_assump = df_calls_with_fte.merge(df_occ_assump, on =['startDate per day', 'Level', 'USD'], how='inner')


            final_fte_occ_assump_occ_rate = final_fte_occ_assump.merge(
                df_occ,
                on=['startDate per day','Language','USD', 'Level', 'Req Media'],
                how='inner'
            )

            final_data = final_fte_occ_assump_occ_rate.copy()

            final_data['OCC Assumption'].fillna(final_data['OCC Assumption'].mean(), inplace=True)
            final_data['OCC'].fillna(final_data['OCC'].mean(), inplace=True)
            final_data["Requirement"] = final_data["Calls"] * final_data['Loaded AHT'] / ((2250 / 7) * final_data["OCC Assumption"])
            final_data.rename(columns={'Total OPI FTEs':'Staffing'}, inplace=True)
            final_data['Demand'] = final_data['Calls'] * final_data['Loaded AHT']
            final_data['Staffing Diff'] = final_data['Staffing'] - final_data['Staffing'].shift(1)
            final_data.rename(columns={"OCC":"Occupancy Rate"}, inplace=True)
            final_data.rename(columns={"OCC Assumption":"Occ Assumption"}, inplace=True)

            final_data = final_data[['startDate per day', 'Language', 'USD', 'Req Media', 'Level', 'ABNs',
                'Calls', 'Q2', 'Loaded AHT', 'ABN %', 'Met', 'Missed','Demand','Occ Assumption',
                                    'Requirement','Staffing','Occupancy Rate','Staffing Diff']]
                    
            # Save the DataFrame to an Excel file
            planner_type_txt=' '.join(planner_type)
            type_data=extract_after_weekly_planner(planner_type_txt)
            
            
            
            
            if 'OPI' in type_data.upper():

                final_data_opi_or_vri = final_data[final_data['Req Media'] == 'OPI']
            else:
                final_data_opi_or_vri = final_data[final_data['Req Media'] == 'VIDEO']  
                
            st.write(final_data_opi_or_vri)                            
             # ✅ Provide download directly
            excel_bytes = to_excel(final_data_opi_or_vri)
            st.download_button(
                label="Download Processed Excel File",
                data=excel_bytes,
                file_name=f'{lang}_{type_data}_output.xlsx',
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("File processed successfully!")  

# if __name__ == "__main__":
#     run_daywise_tool()
