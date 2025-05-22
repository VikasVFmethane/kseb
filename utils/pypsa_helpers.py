# utils/pypsa_helpers.py
import pandas as pd
import numpy_financial as npf
import numpy as np
import logging

logger = logging.getLogger(__name__)

def find_special_symbols(df, marker):
    markers = []
    for i, row in df.iterrows():
        for j, value in enumerate(row):
            if isinstance(value, str) and value.startswith(marker):
                markers.append((i, j, value[len(marker):].strip()))
    return markers

def extract_table(df, start_row, start_col):
    end_row = start_row + 1
    # Find the end of the table by looking for the first empty cell in the starting column
    # or the end of the DataFrame
    while end_row < len(df) and pd.notnull(df.iloc[end_row, start_col]):
        end_row += 1

    end_col = start_col + 1
    # Find the end of the table by looking for the first empty cell in the header row
    # or the end of the columns
    while end_col < len(df.columns) and pd.notnull(df.iloc[start_row, end_col]): # Check header row
        end_col += 1
    
    # Extract the table, set the first row as header, and reset index
    table_data = df.iloc[start_row:end_row, start_col:end_col].copy()
    if not table_data.empty:
        table_data.columns = table_data.iloc[0]
        table_data = table_data[1:].reset_index(drop=True)
    else: # Handle case where table marker is found but no data follows
        logger.warning(f"Marker found at ({start_row-1}, {start_col}) but no table data extracted.")
        return pd.DataFrame()
        
    return table_data

def extract_tables_by_markers(df, marker_prefix):
    table_markers = find_special_symbols(df, marker_prefix)
    tables = {}
    for r, c, table_name in table_markers:
        logger.info(f"Extracting table '{table_name}' starting at row {r+2}, col {c+1}")
        # Table data starts on the row after the marker and its header
        extracted = extract_table(df, r + 1, c) 
        if not extracted.empty:
            tables[table_name] = extracted
        else:
            logger.warning(f"Could not extract table named '{table_name}' marked with '{marker_prefix}{table_name}'.")
    return tables

def annuity_future_value(rate, nper, pv):
    if pd.isna(rate) or pd.isna(nper) or pd.isna(pv):
        logger.warning(f"NaN input to annuity: rate={rate}, nper={nper}, pv={pv}. Returning 0.")
        return 0
    if nper == 0: 
        logger.warning(f"nper is 0 for annuity calculation with pv={pv}. Returning 0.")
        return 0
    if rate == 0: 
        res = -pv / nper
        logger.debug(f"Rate is 0. Annuity: {-pv}/{nper} = {res}")
        return res
    
    try:
        pmt_val = npf.pmt(rate, nper, pv, fv=0, when='end')
        logger.debug(f"Calculated annuity: rate={rate}, nper={nper}, pv={pv} -> pmt={pmt_val}")
        return pmt_val
    except Exception as e:
        logger.error(f"Error in npf.pmt with rate={rate}, nper={nper}, pv={pv}: {e}")
        return 0 # Or raise error, or return np.nan

def get_excel_column_name(n):
    """Converts a 0-indexed integer n to an Excel column name (A, B, ..., Z, AA, ...)."""
    name = ""
    while n >= 0:
        name = chr(ord('A') + n % 26) + name
        n = n // 26 - 1
    return name