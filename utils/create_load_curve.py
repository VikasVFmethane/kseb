# utils/create_load_curve.py
import os
import joblib
import pandas as pd
import numpy as np
from sklearn.discriminant_analysis import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from statsmodels.tsa.seasonal import STL # Assuming this might be used by other parts of your original file
from datetime import datetime, timedelta # Added for year_range default
from typing import Tuple, Optional, Union, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Helper function to get total annual demand (moved from app.py for reusability if needed)
def get_future_annual_demand_lc(project_path_for_inputs_or_results: str, 
                             start_year: int, end_year: int, 
                             forecast_scenario_name: Optional[str],
                             excel_file_path_for_total_demand_sheet: str,
                             total_demand_sheet_name: str = 'Total Demand'
                             ) -> Dict[int, float]:
    annual_demand_data_gwh = {}
    source = "Unknown"
    try:
        if forecast_scenario_name:
            # Construct path to consolidated_results.csv within the specific scenario
            # project_path_for_inputs_or_results is expected to be the root project path here.
            scenario_results_path = os.path.join(project_path_for_inputs_or_results, 'results', 'demand_projection', forecast_scenario_name, 'consolidated_results.csv')
            if os.path.exists(scenario_results_path):
                df_scenario = pd.read_csv(scenario_results_path)
                if 'Year' in df_scenario.columns and 'Total' in df_scenario.columns:
                    for _, row in df_scenario.iterrows():
                        year = int(row['Year'])
                        value_kwh = float(row['Total']) # Assuming Total is in kWh from consolidated_results.csv
                        if start_year <= year <= end_year:
                            annual_demand_data_gwh[year] = value_kwh / 1_000_000 # kWh to GWh
                    source = f"Scenario CSV: {forecast_scenario_name}"
                    if annual_demand_data_gwh: logger.info(f"Loaded annual demand from {source}")
                else:
                    logger.warning(f"'Year' or 'Total' column missing in {scenario_results_path}. Fallback to Excel.")
                    raise ValueError("Scenario CSV invalid format") # Force fallback
            else:
                logger.warning(f"Scenario CSV not found: {scenario_results_path}. Fallback to Excel.")
                raise ValueError("Scenario CSV not found") # Force fallback
        else: # No scenario, must use Excel
            raise ValueError("No forecast scenario provided") # Force fallback

    except Exception as e_scenario:
        logger.info(f"Fallback: Loading annual demand from Excel due to: {e_scenario}")
        if not os.path.exists(excel_file_path_for_total_demand_sheet):
            logger.error(f"Excel for total demand not found: {excel_file_path_for_total_demand_sheet}")
            return annual_demand_data_gwh

        try:
            df_total_demand = pd.read_excel(excel_file_path_for_total_demand_sheet, sheet_name=total_demand_sheet_name)
            # Common column names for financial year and total demand
            year_col = None
            demand_col = None
            if 'financial_year' in df_total_demand.columns: year_col = 'financial_year'
            elif 'Year' in df_total_demand.columns: year_col = 'Year'
            
            if 'Total demand' in df_total_demand.columns: demand_col = 'Total demand' # Assumed GWh
            elif 'Annual_Demand' in df_total_demand.columns: demand_col = 'Annual_Demand' # Assumed GWh

            if year_col and demand_col:
                for _, row in df_total_demand.iterrows():
                    year = int(row[year_col])
                    value_gwh = float(row[demand_col]) # Assuming GWh from this sheet
                    if start_year <= year <= end_year:
                        annual_demand_data_gwh[year] = value_gwh
                source = f"Excel sheet: {total_demand_sheet_name}"
                if annual_demand_data_gwh: logger.info(f"Loaded annual demand from {source}")
            else:
                logger.error(f"Required columns for year or demand missing in Excel sheet '{total_demand_sheet_name}'.")
        except Exception as e_excel:
            logger.error(f"Error reading '{total_demand_sheet_name}' sheet from Excel: {e_excel}")
            
    if not annual_demand_data_gwh:
        logger.warning(f"No annual demand data could be loaded for {start_year}-{end_year} from any source.")
    return annual_demand_data_gwh


def extract_monthly_patterns_from_excel(excel_file_path: str, base_year: int) -> Dict[str, Any]:
    months_ordered = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
    month_mapping_to_name = {
        4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep',
        10: 'Oct', 11: 'Nov', 12: 'Dec', 1: 'Jan', 2: 'Feb', 3: 'Mar'
    }
    
    try:
        historical_demand_df = pd.read_excel(excel_file_path, sheet_name='Past_Hourly_Demand')
    except FileNotFoundError:
        logger.error(f"Excel file not found: {excel_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading 'Past_Hourly_Demand' sheet: {e}")
        raise

    if not all(col in historical_demand_df.columns for col in ['date', 'time', 'demand']):
        raise ValueError("Missing required columns (date, time, demand) in 'Past_Hourly_Demand' sheet.")

    historical_demand_df['datetime'] = pd.to_datetime(
        historical_demand_df['date'].astype(str) + ' ' + historical_demand_df['time'].astype(str)
    )
    
    historical_demand_df['financial_year'] = np.where(
        historical_demand_df['datetime'].dt.month >= 4,
        historical_demand_df['datetime'].dt.year + 1, 
        historical_demand_df['datetime'].dt.year
    )
    
    base_year_data = historical_demand_df[historical_demand_df['financial_year'] == base_year].copy()
    
    if base_year_data.empty:
        logger.warning(f"No data found for financial year {base_year} in {excel_file_path}")
        empty_patterns = {month_name: 0 for month_name in months_ordered}
        return {
            'months': months_ordered,
            'patternData': {
                'Total Demand (GWh)': [0.0]*12, 'Average Demand (MW)': [0.0]*12,
                'Max Demand (MW)': [0.0]*12, 'Load Factor (%)': [0.0]*12,
                'Share of Annual (%)': [0.0]*12
            },
            'yearlyLoadFactor': 0.0
        }

    base_year_data['month_num'] = base_year_data['datetime'].dt.month
    base_year_data['month_name'] = base_year_data['month_num'].map(month_mapping_to_name)
    
    monthly_metrics_list = []
    for month_name_ordered in months_ordered:
        month_data_for_name = base_year_data[base_year_data['month_name'] == month_name_ordered]
        
        if month_data_for_name.empty:
            monthly_metrics_list.append({'month_name': month_name_ordered, 'total_demand_kwh': 0,'avg_demand_kw': 0, 'max_demand_kw': 0})
            continue

        total_demand_kwh = month_data_for_name['demand'].sum() 
        avg_demand_kw = month_data_for_name['demand'].mean()
        max_demand_kw = month_data_for_name['demand'].max()
        monthly_metrics_list.append({'month_name': month_name_ordered, 'total_demand_kwh': total_demand_kwh, 'avg_demand_kw': avg_demand_kw, 'max_demand_kw': max_demand_kw})

    monthly_summary_df = pd.DataFrame(monthly_metrics_list)
    monthly_summary_df['load_factor_percent'] = np.where(monthly_summary_df['max_demand_kw'] > 0, (monthly_summary_df['avg_demand_kw'] / monthly_summary_df['max_demand_kw']) * 100, 0)
    annual_total_kwh = monthly_summary_df['total_demand_kwh'].sum()
    monthly_summary_df['share_of_annual_percent'] = np.where(annual_total_kwh > 0, (monthly_summary_df['total_demand_kwh'] / annual_total_kwh) * 100, 0)

    pattern_data_dict = {
        'Total Demand (GWh)': (monthly_summary_df['total_demand_kwh'] / 1_000_000).round(3).tolist(),
        'Average Demand (MW)': (monthly_summary_df['avg_demand_kw'] / 1_000).round(2).tolist(),
        'Max Demand (MW)': (monthly_summary_df['max_demand_kw'] / 1_000).round(2).tolist(),
        'Load Factor (%)': monthly_summary_df['load_factor_percent'].round(1).tolist(),
        'Share of Annual (%)': monthly_summary_df['share_of_annual_percent'].round(1).tolist()
    }

    overall_avg_demand_kw = base_year_data['demand'].mean()
    overall_max_demand_kw = base_year_data['demand'].max()
    yearly_load_factor = (overall_avg_demand_kw / overall_max_demand_kw * 100) if overall_max_demand_kw > 0 else 0.0
    
    return {'months': months_ordered, 'patternData': pattern_data_dict, 'yearlyLoadFactor': round(yearly_load_factor, 1)}

def check_total_demand_data(excel_file_path: str, total_demand_sheet_name: str = 'Total Demand') -> bool:
    try:
        df = pd.read_excel(excel_file_path, sheet_name=total_demand_sheet_name)
        year_col = 'financial_year' if 'financial_year' in df.columns else 'Year' if 'Year' in df.columns else None
        demand_col = 'Total demand' if 'Total demand' in df.columns else 'Annual_Demand' if 'Annual_Demand' in df.columns else None
        return bool(year_col and demand_col and not df.empty)
    except Exception:
        return False

def load_scenario_data(project_path: str, scenario_name: str) -> Dict[str, Any]:
    scenario_data: Dict[str, Any] = {'scenario_name': scenario_name}
    consolidated_csv_path = os.path.join(project_path, 'results', 'demand_projection', scenario_name, 'consolidated_results.csv')
    if os.path.exists(consolidated_csv_path):
        try:
            df = pd.read_csv(consolidated_csv_path)
            if 'Year' in df.columns and 'Total' in df.columns:
                # Assuming 'Total' is annual total demand in kWh
                scenario_data['Consolidated Electricity Demand'] = [
                    {'year': int(r['Year']), 'value': float(r['Total'])} for _, r in df.iterrows()
                ]
        except Exception as e:
            logger.error(f"Error reading consolidated_results.csv for scenario {scenario_name}: {e}")
    return scenario_data

def create_load_curve(
    excel_file_path: str,
    base_year: Optional[int] = None,
    scenario_data: Optional[Dict] = None, # Contains scenario_name, optionally Consolidated Electricity Demand
    year_range: Optional[Dict] = None,
    state: str = 'KL', # For holidays, not used in this simplified version
    historical_demand_sheet: str = 'Past_Hourly_Demand',
    total_demand_sheet: str = 'Total Demand',
    max_demand_sheet: str = 'max_demand',
    load_factors_sheet: str = 'load_factors',
    method: str = 'base_year',
    weather_data: Optional[pd.DataFrame] = None,
    apply_constraints: bool = True,
    improved_load_factor: Optional[float] = None,
    future_load_factors: Optional[Dict[int, float]] = None,
    use_excel_load_factors: bool = False,
    use_holidays: bool = False, # Not implemented in detail here
    output_frequency: str = 'hourly'
) -> Optional[pd.DataFrame]:
    logger.info(f"create_load_curve: method={method}, base_year={base_year}, scenario_name={scenario_data.get('scenario_name') if scenario_data else 'N/A'}")
    
    if not os.path.exists(excel_file_path):
        logger.error(f"Excel file not found: {excel_file_path}")
        return None

    if year_range is None:
        current_cal_year = datetime.now().year
        year_range = {'Start_Year': current_cal_year, 'End_Year': current_cal_year + 14}
    
    forecast_start_fy = year_range['Start_Year']
    forecast_end_fy = year_range['End_Year']
    
    try:
        hist_demand_df_raw = pd.read_excel(excel_file_path, sheet_name=historical_demand_sheet)
        hist_demand_df_raw['datetime'] = pd.to_datetime(hist_demand_df_raw['date'].astype(str) + ' ' + hist_demand_df_raw['time'].astype(str))
        # Assuming demand is in kW
        hist_demand_df = hist_demand_df_raw[['datetime', 'demand']].set_index('datetime').resample('H').mean().ffill()
    except Exception as e:
        logger.error(f"Error reading/processing historical demand '{historical_demand_sheet}': {e}")
        return None

    project_root_path = os.path.dirname(os.path.dirname(excel_file_path)) # Get project root from .../inputs/file.xlsx

    future_timestamps = pd.date_range(
        start=f'{forecast_start_fy-1}-04-01 00:00:00',
        end=f'{forecast_end_fy}-03-31 23:00:00', freq='H'
    )
    forecast_df = pd.DataFrame(index=future_timestamps)
    forecast_df['demand_kw'] = 0.0 # Explicitly kW

    if method == 'base_year':
        if base_year is None:
            logger.error("Base year required for 'base_year' method.")
            return None
        
        base_fy_start_dt = pd.Timestamp(f'{base_year-1}-04-01')
        base_fy_end_dt = pd.Timestamp(f'{base_year}-03-31 23:59:59')
        base_year_profile_data = hist_demand_df[(hist_demand_df.index >= base_fy_start_dt) & (hist_demand_df.index <= base_fy_end_dt)].copy()

        if base_year_profile_data.empty or len(base_year_profile_data['demand']) < 8000: # Check for sufficient data
            logger.error(f"Insufficient or no historical data for base FY {base_year}.")
            return None
        
        base_profile_kw_values = base_year_profile_data['demand'].values

        # Get annual totals (in GWh)
        annual_totals_gwh = get_future_annual_demand_lc(
            project_root_path, forecast_start_fy, forecast_end_fy,
            scenario_data.get('scenario_name') if scenario_data else None,
            excel_file_path, total_demand_sheet
        )

        for fy in range(forecast_start_fy, forecast_end_fy + 1):
            fy_dt_start = pd.Timestamp(f'{fy-1}-04-01 00:00:00')
            fy_dt_end = pd.Timestamp(f'{fy}-03-31 23:00:00')
            
            target_gwh = annual_totals_gwh.get(fy, 0)
            if target_gwh == 0:
                logger.warning(f"FY {fy}: Annual total is 0. Hourly profile will be 0.")
                forecast_df.loc[fy_dt_start:fy_dt_end, 'demand_kw'] = 0
                continue

            target_kwh = target_gwh * 1_000_000
            
            # Adapt base profile to current FY's leap status
            is_fy_leap = pd.Timestamp(f'{fy}-02-01').is_leap_year # Feb of FY end year
            hours_in_fy = 8784 if is_fy_leap else 8760
            
            # Simple profile adaptation: use corresponding part of base_profile_kw_values
            # More robust would be to handle leap day specifically if base_profile is non-leap or vice-versa
            adapted_base_profile = base_profile_kw_values[:hours_in_fy]
            if len(adapted_base_profile) < hours_in_fy and len(base_profile_kw_values) > 0 : # If base is shorter (e.g. non-leap and FY is leap)
                adapted_base_profile = np.tile(base_profile_kw_values, (hours_in_fy // len(base_profile_kw_values)) +1 )[:hours_in_fy]


            current_profile_sum_kwh = np.sum(adapted_base_profile) # Sum of kW values (hourly data) is kWh

            if current_profile_sum_kwh == 0:
                logger.warning(f"FY {fy}: Base profile sum is 0. Hourly profile will be 0.")
                forecast_df.loc[fy_dt_start:fy_dt_end, 'demand_kw'] = 0
            else:
                scale_factor = target_kwh / current_profile_sum_kwh
                forecast_df.loc[fy_dt_start:fy_dt_end, 'demand_kw'] = adapted_base_profile * scale_factor
    
    elif method == 'ml_weather':
        logger.warning("ML Weather method not fully implemented. Returning zeros.")
        forecast_df['demand_kw'] = 0.0
    else:
        logger.error(f"Unknown method: {method}")
        return None

    if apply_constraints:
        logger.info("Applying constraints...")
        
        # --- Monthly Peak Demand Constraints ---
        try:
            df_max_demand = pd.read_excel(excel_file_path, sheet_name=max_demand_sheet)
            # Melt the df_max_demand to long format: financial_year, month_name, target_peak_mw
            # Example month columns: 'Apr', 'May', ... 'Mar'
            # Assuming target peaks are in MW
            month_cols = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
            if 'financial_year' in df_max_demand.columns and all(m in df_max_demand.columns for m in month_cols):
                melted_max_demand = df_max_demand.melt(id_vars=['financial_year'], value_vars=month_cols,
                                                       var_name='month_name', value_name='target_peak_mw')
                
                month_name_to_num_map = {name: i+1 for i, name in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])}
                # Correct mapping for financial year perspective
                fy_month_map_num = {'Apr':4, 'May':5, 'Jun':6, 'Jul':7, 'Aug':8, 'Sep':9, 'Oct':10, 'Nov':11, 'Dec':12, 'Jan':1, 'Feb':2, 'Mar':3}
                melted_max_demand['month_num'] = melted_max_demand['month_name'].map(fy_month_map_num)

                for _, row in melted_max_demand.iterrows():
                    fy = int(row['financial_year'])
                    month_num = int(row['month_num'])
                    target_peak_mw = float(row['target_peak_mw'])
                    target_peak_kw = target_peak_mw * 1000

                    if not (forecast_start_fy <= fy <= forecast_end_fy): continue

                    # Determine calendar year for the given financial year and month number
                    # For FY 2025 (Apr 2024 - Mar 2025):
                    # Months 4-12 are in calendar year 2024 (fy - 1)
                    # Months 1-3 are in calendar year 2025 (fy)
                    cal_year = fy -1 if month_num >=4 else fy

                    month_mask = (forecast_df.index.year == cal_year) & (forecast_df.index.month == month_num)
                    month_data_kw = forecast_df.loc[month_mask, 'demand_kw']

                    if not month_data_kw.empty:
                        current_month_max_kw = month_data_kw.max()
                        if current_month_max_kw > target_peak_kw and target_peak_kw > 0 : # Only cap if target is positive
                            logger.info(f"FY {fy}, Month {month_num}: Capping peak from {current_month_max_kw:.2f} kW to target {target_peak_kw:.2f} kW.")
                            forecast_df.loc[month_data_kw[month_data_kw > target_peak_kw].index, 'demand_kw'] = target_peak_kw
                        # Else: current peak is already below or equal to target, or target is non-positive (ignore)
            else:
                logger.warning(f"'{max_demand_sheet}' sheet missing 'financial_year' or month columns. Skipping monthly peak constraints.")
        except Exception as e:
            logger.warning(f"Could not load or process '{max_demand_sheet}' for monthly peak constraints: {e}")


        # --- Yearly Load Factor Constraints ---
        final_year_load_factors_decimal: Dict[int, float] = {} # {fy: lf_decimal}
        if use_excel_load_factors:
            try:
                lf_df_excel = pd.read_excel(excel_file_path, sheet_name=load_factors_sheet)
                if 'financial_year' in lf_df_excel.columns and 'load_factor' in lf_df_excel.columns:
                    for _, r in lf_df_excel.iterrows(): final_year_load_factors_decimal[int(r['financial_year'])] = float(r['load_factor']) / 100.0
                    logger.info(f"Loaded {len(final_year_load_factors_decimal)} LFs from Excel.")
            except Exception as e: logger.warning(f"Could not use LFs from Excel '{load_factors_sheet}': {e}")

        if future_load_factors: # Custom LFs override Excel for those specific years
            for yr, factor_pct in future_load_factors.items(): final_year_load_factors_decimal[int(yr)] = float(factor_pct) / 100.0
            logger.info(f"Applied/Overrode {len(future_load_factors)} custom LFs.")
        
        # Apply year-on-year improvement if rate is given and no specific LF set for a year yet
        if improved_load_factor is not None and improved_load_factor > 0: # Ensure positive improvement rate
            base_lf_for_yoy_improve = None
            last_known_lf_fy = 0
            if final_year_load_factors_decimal: # Use latest explicitly set LF as base
                last_known_lf_fy = max(final_year_load_factors_decimal.keys())
                base_lf_for_yoy_improve = final_year_load_factors_decimal[last_known_lf_fy]
            
            if base_lf_for_yoy_improve is None and base_year: # Fallback to base_year's actual LF
                try:
                    base_patterns = extract_monthly_patterns_from_excel(excel_file_path, base_year)
                    base_lf_for_yoy_improve = base_patterns.get('yearlyLoadFactor', 0.0) / 100.0
                    last_known_lf_fy = base_year 
                except Exception as e_lf_base: logger.warning(f"Could not get base year LF for YoY improvement: {e_lf_base}")

            if base_lf_for_yoy_improve is not None and base_lf_for_yoy_improve > 0:
                logger.info(f"Applying YoY LF improvement of {improved_load_factor}% from base LF {base_lf_for_yoy_improve*100:.1f}% (FY {last_known_lf_fy}).")
                for fy_iter in range(forecast_start_fy, forecast_end_fy + 1):
                    if fy_iter not in final_year_load_factors_decimal: # Only if not explicitly set
                        if fy_iter <= last_known_lf_fy : # For years before/at base of improvement, use that base
                             current_lf = base_lf_for_yoy_improve
                        else:
                            years_since_base_for_improve = fy_iter - last_known_lf_fy
                            current_lf = base_lf_for_yoy_improve * ((1 + improved_load_factor / 100.0) ** years_since_base_for_improve)
                        final_year_load_factors_decimal[fy_iter] = min(current_lf, 0.99) # Cap at 99%
            else: logger.warning("Cannot apply YoY LF improvement: No valid base LF or improvement rate.")

        if final_year_load_factors_decimal:
            for fy_constr, target_lf_dec in final_year_load_factors_decimal.items():
                if not (forecast_start_fy <= fy_constr <= forecast_end_fy): continue

                fy_m = ((forecast_df.index.year == fy_constr - 1) & (forecast_df.index.month >= 4)) | \
                       ((forecast_df.index.year == fy_constr) & (forecast_df.index.month <= 3))
                year_data_kw = forecast_df.loc[fy_m, 'demand_kw']
                if year_data_kw.empty: continue

                current_avg_kw = year_data_kw.mean()
                if target_lf_dec > 0 and current_avg_kw > 0:
                    required_peak_kw = current_avg_kw / target_lf_dec
                    current_max_kw = year_data_kw.max()
                    if current_max_kw > required_peak_kw:
                        logger.info(f"FY {fy_constr}: Target LF {target_lf_dec*100:.1f}%. Shaving peak from {current_max_kw:.2f} to {required_peak_kw:.2f} kW.")
                        forecast_df.loc[year_data_kw[year_data_kw > required_peak_kw].index, 'demand_kw'] = required_peak_kw
                else: logger.warning(f"FY {fy_constr}: Skipping LF constraint (target_lf={target_lf_dec}, avg_demand={current_avg_kw}).")

    if output_frequency != 'hourly':
        logger.info(f"Resampling to {output_frequency}")
        resample_freq_map = {'15min': '15T', 'half_hourly': '30T'}
        if output_frequency in resample_freq_map:
            forecast_df = forecast_df.resample(resample_freq_map[output_frequency]).ffill().bfill()
    
    forecast_df.reset_index(inplace=True)
    forecast_df.rename(columns={'index': 'timestamp', 'demand_kw': 'Demand'}, inplace=True)
    
    forecast_df['Date'] = forecast_df['timestamp'].dt.date
    forecast_df['Time'] = forecast_df['timestamp'].dt.strftime('%H:%M:%S') # Keep as string for CSV
    forecast_df['Year'] = forecast_df['timestamp'].dt.year
    forecast_df['Fiscal_Year'] = np.where(forecast_df['timestamp'].dt.month >= 4, forecast_df['Year'] + 1, forecast_df['Year'])
    
    return forecast_df[['timestamp', 'Demand', 'Date', 'Time', 'Year', 'Fiscal_Year']]
def generate_base_year_monthly_patterns(historical_demand: pd.DataFrame, base_year: int) -> pd.DataFrame:
    """
    Generate monthly demand patterns from the base year data.
    
    Parameters:
    -----------
    historical_demand : pd.DataFrame
        Historical demand data
    base_year : int
        Base financial year to use
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with monthly patterns
    """
    # Convert date and add financial year
    historical_demand['date'] = pd.to_datetime(historical_demand['date'])
    historical_demand['financial_year'] = np.where(
        historical_demand['date'].dt.month >= 4,
        historical_demand['date'].dt.year + 1,
        historical_demand['date'].dt.year
    )
    
    # Filter for base year
    base_year_data = historical_demand[historical_demand['financial_year'] == base_year].copy()
    
    if len(base_year_data) == 0:
        logger.warning(f"No data found for financial year {base_year}")
        return pd.DataFrame()
    
    # Add month
    base_year_data['month'] = base_year_data['date'].dt.month
    base_year_data['day'] = base_year_data['date'].dt.day
    
    # Calculate monthly metrics
    monthly_metrics = base_year_data.groupby('month').agg({
        'demand': ['sum', 'mean', 'max', 'min']
    }).reset_index()
    
    # Flatten the MultiIndex columns
    monthly_metrics.columns = ['month', 'total_demand', 'avg_demand', 'max_demand', 'min_demand']
    
    # Calculate load factor for each month
    monthly_metrics['load_factor'] = monthly_metrics['avg_demand'] / monthly_metrics['max_demand'] * 100
    
    # Calculate share of annual demand
    annual_demand = monthly_metrics['total_demand'].sum()
    monthly_metrics['share_of_annual'] = monthly_metrics['total_demand'] / annual_demand * 100
    
    # Create month names for better readability
    month_names = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }
    monthly_metrics['month_name'] = monthly_metrics['month'].map(month_names)
    
    # Reorder to show April-March (financial year)
    fin_year_order = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
    monthly_metrics = monthly_metrics.set_index('month').loc[fin_year_order].reset_index()
    
    # Create a heatmap data structure
    heatmap_data = pd.pivot_table(
        monthly_metrics,
        values=['total_demand', 'avg_demand', 'max_demand', 'load_factor', 'share_of_annual'],
        index=['month_name'],
        aggfunc='first'
    )
    
    # Save to static file for visualization
    heatmap_path = f"static/temp/base_year_{base_year}_patterns.csv"
    os.makedirs(os.path.dirname(heatmap_path), exist_ok=True)
    heatmap_data.to_csv(heatmap_path)
    
    return monthly_metrics


def prepare_total_demand_from_scenario(scenario_data: Dict, forecast_years: range) -> pd.DataFrame:
    """
    Prepare total demand constraints from scenario data.
    
    Parameters:
    -----------
    scenario_data : Dict
        Scenario data from forecast
    forecast_years : range
        Range of years to forecast
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with yearly total demand targets
    """
    # Extract consolidated demand data
    consolidated_data = scenario_data.get('Consolidated Electricity Demand', [])
    
    # Create DataFrame
    total_demand = pd.DataFrame({
        'financial_year': list(forecast_years),
        'Total demand': [0] * len(forecast_years)
    })
    
    # Fill in values from scenario data
    for year_idx, year in enumerate(forecast_years):
        # Find year in consolidated data
        for data_point in consolidated_data:
            if data_point.get('year') == year:
                total_demand.loc[year_idx, 'Total demand'] = data_point.get('value', 0)
                break
    
    return total_demand


def create_features(df: pd.DataFrame, holidays_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Create time-based features for the input dataframe.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with 'ds' column containing timestamps
    holidays_df : pd.DataFrame, optional
        DataFrame with holiday dates
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with additional time-based features
    """
    df = df.copy()
    if 'ds' not in df.columns:
        if 'datetime' in df.columns:
            df['ds'] = df['datetime']
        elif 'date' in df.columns and 'time' in df.columns:
            df['ds'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
    
    # Extract time components
    df['hour'] = df['ds'].dt.hour
    df['dayofweek'] = df['ds'].dt.dayofweek
    df['month'] = df['ds'].dt.month
    df['year'] = df['ds'].dt.year
    df['day'] = df['ds'].dt.day
    df['financial_year'] = np.where(df['month'] >= 4, df['year'] + 1, df['year'])
    df['is_weekend'] = df['dayofweek'].isin([5, 6]).astype(int)
    df['quarter'] = df['ds'].dt.quarter
    df['dayofyear'] = df['ds'].dt.dayofyear
    df['weekofyear'] = df['ds'].dt.isocalendar().week
    
    # Add day/night features (6am-6pm = day)
    df['is_daytime'] = ((df['hour'] >= 6) & (df['hour'] < 18)).astype(int)
    
    # Add peak hour features (typically 5pm-10pm)
    df['is_peak_hour'] = ((df['hour'] >= 17) & (df['hour'] <= 22)).astype(int)
    
    # Add seasonal features
    seasons = {
        12: 'Winter', 1: 'Winter', 2: 'Winter',
        3: 'Spring', 4: 'Spring', 5: 'Spring',
        6: 'Summer', 7: 'Summer', 8: 'Summer',
        9: 'Fall', 10: 'Fall', 11: 'Fall'
    }
    df['season'] = df['month'].map(seasons)
    
    # Add cyclical features for time components (to capture periodicity)
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['day_sin'] = np.sin(2 * np.pi * df['day'] / 31)
    df['day_cos'] = np.cos(2 * np.pi * df['day'] / 31)
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    df['dayofweek_sin'] = np.sin(2 * np.pi * df['dayofweek'] / 7)
    df['dayofweek_cos'] = np.cos(2 * np.pi * df['dayofweek'] / 7)
    
    # Add holiday features if holidays_df is provided
    if holidays_df is not None and not holidays_df.empty:
        df['is_holiday'] = df['ds'].dt.date.isin(holidays_df['Date'].dt.date).astype(int)
        
        # Add before/after holiday features
        holiday_dates = set(holidays_df['Date'].dt.date)
        
        # Add day before and after holiday
        df['is_day_before_holiday'] = df['ds'].apply(
            lambda x: (x.date() + timedelta(days=1)) in holiday_dates).astype(int)
        df['is_day_after_holiday'] = df['ds'].apply(
            lambda x: (x.date() - timedelta(days=1)) in holiday_dates).astype(int)
    else:
        df['is_holiday'] = 0
        df['is_day_before_holiday'] = 0
        df['is_day_after_holiday'] = 0
    
    return df


def extract_load_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract typical load profiles by month, weekday/weekend, and hour.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with historical demand data
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with load profiles
    """
    # Compute daily totals
    daily_totals = df.groupby(['year', 'month', 'day'])['demand'].sum().reset_index()
    daily_totals.rename(columns={'demand': 'daily_total'}, inplace=True)
    
    # Merge daily totals back to the dataframe
    df = df.merge(daily_totals, on=['year', 'month', 'day'])
    
    # Compute hourly fraction of daily demand
    df['fraction'] = df['demand'] / df['daily_total']
    
    # Handle potential division by zero
    df['fraction'] = df['fraction'].fillna(0).replace([np.inf, -np.inf], 0)
    
    # Calculate different profile types based on available features
    
    # Basic profile by month, is_weekend, and hour
    basic_profiles = df.groupby(['month', 'is_weekend', 'hour'])['fraction'].mean().reset_index()
    
    # Enhanced profiles if more features are available
    enhanced_profiles = None
    if 'season' in df.columns and 'is_holiday' in df.columns:
        # Profiles by season, is_weekend, is_holiday, and hour
        enhanced_profiles = df.groupby(['season', 'is_weekend', 'is_holiday', 'hour'])['fraction'].mean().reset_index()
    
    # If both are available, prefer enhanced profiles for holidays/weekends and basic profiles otherwise
    if enhanced_profiles is not None:
        # Create a merged profile set
        all_combinations = []
        
        # Add basic profiles for non-holidays on weekdays
        for month in range(1, 13):
            for hour in range(24):
                # Get basic profile for this month, hour
                basic_fraction = basic_profiles[
                    (basic_profiles['month'] == month) & 
                    (basic_profiles['is_weekend'] == 0) & 
                    (basic_profiles['hour'] == hour)
                ]['fraction'].values[0] if len(basic_profiles[
                    (basic_profiles['month'] == month) & 
                    (basic_profiles['is_weekend'] == 0) & 
                    (basic_profiles['hour'] == hour)
                ]) > 0 else 1/24
                
                all_combinations.append({
                    'month': month,
                    'is_weekend': 0,
                    'is_holiday': 0,
                    'hour': hour,
                    'fraction': basic_fraction
                })
        
        # Get the season mapping
        seasons = {
            12: 'Winter', 1: 'Winter', 2: 'Winter',
            3: 'Spring', 4: 'Spring', 5: 'Spring',
            6: 'Summer', 7: 'Summer', 8: 'Summer',
            9: 'Fall', 10: 'Fall', 11: 'Fall'
        }
        
        # Add enhanced profiles for holidays and weekends
        for month in range(1, 13):
            season = seasons[month]
            for is_weekend in [0, 1]:
                for is_holiday in [1]:  # Only for holidays
                    for hour in range(24):
                        # Get enhanced profile for this season, weekend status, holiday status, hour
                        enhanced_records = enhanced_profiles[
                            (enhanced_profiles['season'] == season) & 
                            (enhanced_profiles['is_weekend'] == is_weekend) & 
                            (enhanced_profiles['is_holiday'] == is_holiday) & 
                            (enhanced_profiles['hour'] == hour)
                        ]
                        
                        enhanced_fraction = enhanced_records['fraction'].values[0] if len(enhanced_records) > 0 else 1/24
                        
                        # For weekends, use enhanced profiles
                        if is_weekend == 1:
                            all_combinations.append({
                                'month': month,
                                'is_weekend': 1,
                                'is_holiday': 0,  # Use weekend profile for non-holiday weekends
                                'hour': hour,
                                'fraction': enhanced_fraction
                            })
                        
                        # For holidays, use enhanced profiles
                        all_combinations.append({
                            'month': month,
                            'is_weekend': is_weekend,
                            'is_holiday': 1,
                            'hour': hour,
                            'fraction': enhanced_fraction
                        })
        
        # Convert to DataFrame
        merged_profiles = pd.DataFrame(all_combinations)
        
        # Ensure the fractions sum to the expected totals
        for month in range(1, 13):
            for is_weekend in [0, 1]:
                for is_holiday in [0, 1]:
                    filter_mask = (
                        (merged_profiles['month'] == month) & 
                        (merged_profiles['is_weekend'] == is_weekend) & 
                        (merged_profiles['is_holiday'] == is_holiday)
                    )
                    
                    if filter_mask.sum() > 0:
                        # Get the total for this combination
                        total_fraction = merged_profiles.loc[filter_mask, 'fraction'].sum()
                        
                        # Adjust if total is not 1
                        if total_fraction != 0 and total_fraction != 24:
                            merged_profiles.loc[filter_mask, 'fraction'] = (
                                merged_profiles.loc[filter_mask, 'fraction'] / total_fraction
                            )
        
        return merged_profiles
    
    # If enhanced profiles not available, use basic profiles
    return basic_profiles


def forecast_with_stl(df: pd.DataFrame, future_dates: pd.DatetimeIndex, 
                     period: int = 24*365, seasonal_period: int = 13) -> pd.DataFrame:
    """
    Generate base forecast using STL decomposition.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with historical demand data
    future_dates : pd.DatetimeIndex
        DatetimeIndex with future dates for forecasting
    period : int, default 24*365
        Period parameter for STL decomposition
    seasonal_period : int, default 13
        Seasonal parameter for STL decomposition
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with base forecast
    """
    if len(df['demand']) < 24 * 365:
        raise ValueError("Need at least one year of hourly data for STL decomposition.")
    
    # Apply STL decomposition
    stl = STL(df['demand'], period=period, seasonal=seasonal_period)
    result = stl.fit()
    
    # Extract trend and seasonal components
    trend = result.trend.iloc[-1]  # Extend last trend value
    seasonal = result.seasonal.iloc[-24*365:]  # Repeat last year's seasonality
    
    # Create forecast dataframe
    future_df = pd.DataFrame({'ds': future_dates})
    future_df['trend'] = trend
    future_df['seasonal'] = np.tile(seasonal, len(future_df) // len(seasonal) + 1)[:len(future_df)]
    future_df['yhat'] = future_df['trend'] + future_df['seasonal']
    future_df['yhat'] = future_df['yhat'].clip(lower=0)  # Ensure non-negative demand
    
    return future_df


def apply_load_profiles(forecast_df: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    """
    Apply load profiles to the base forecast.
    
    Parameters:
    -----------
    forecast_df : pd.DataFrame
        DataFrame with base forecast
    profiles : pd.DataFrame
        DataFrame with load profiles
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with adjusted forecast
    """
    # Compute daily totals from STL forecast
    daily_totals = forecast_df.groupby(['financial_year', 'month', 'day'])['yhat'].sum().reset_index()
    daily_totals.rename(columns={'yhat': 'yhat_daily'}, inplace=True)
    
    # Merge daily totals back
    forecast_df = forecast_df.merge(daily_totals, on=['financial_year', 'month', 'day'])
    
    # Check if enhanced profiles are available (with is_holiday)
    using_enhanced_profiles = 'is_holiday' in profiles.columns
    
    if using_enhanced_profiles:
        # Merge with load profiles - use appropriate profile based on month, weekend, holiday status
        forecast_df = forecast_df.merge(
            profiles, 
            on=['month', 'is_weekend', 'is_holiday', 'hour'], 
            how='left'
        )
    else:
        # Merge with basic profiles
        forecast_df = forecast_df.merge(
            profiles, 
            on=['month', 'is_weekend', 'hour'], 
            how='left'
        )
    
    # Handle potentially missing profiles
    if forecast_df['fraction'].isna().any():
        logger.warning(f"Missing profiles for {forecast_df['fraction'].isna().sum()} hours. Using mean values.")
        
        # Group by relevant features and fill with group mean
        if using_enhanced_profiles:
            forecast_df['fraction'] = forecast_df.groupby(['month', 'is_weekend', 'is_holiday'])['fraction'].transform(
                lambda x: x.fillna(x.mean() if not pd.isna(x.mean()) else 1/24)
            )
        else:
            forecast_df['fraction'] = forecast_df.groupby(['month', 'is_weekend'])['fraction'].transform(
                lambda x: x.fillna(x.mean() if not pd.isna(x.mean()) else 1/24)
            )
        
        # If still missing, fill with uniform distribution (1/24)
        forecast_df['fraction'] = forecast_df['fraction'].fillna(1/24)
    
    # Adjust hourly demand using daily totals and historical fractions
    forecast_df['yhat'] = forecast_df['fraction'] * forecast_df['yhat_daily']
    
    # Clean up
    forecast_df = forecast_df.drop(columns=['yhat_daily', 'day'])
    
    return forecast_df


def apply_constraints_func(forecast_df: pd.DataFrame, 
                     total_demand: Optional[pd.DataFrame], 
                     max_demand: Optional[pd.DataFrame],
                     year_wise_load_factors: Optional[pd.DataFrame]) -> pd.DataFrame:
    """
    Apply yearly and monthly constraints to the forecast.
    
    Parameters:
    -----------
    forecast_df : pd.DataFrame
        DataFrame with base forecast
    total_demand : pd.DataFrame, optional
        DataFrame with yearly total demand targets
    max_demand : pd.DataFrame, optional
        DataFrame with monthly peak demand targets
    year_wise_load_factors : pd.DataFrame, optional
        DataFrame with yearly load factor targets
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with constrained forecast
    """
    df = forecast_df.copy()
    
    # Scale to yearly totals if total_demand is provided
    if total_demand is not None:
        logger.info("Applying yearly total demand constraints")
        for year_idx, year_row in total_demand.iterrows():
            year = year_row['financial_year']
            target_sum = year_row['Total demand']
            
            mask = df['financial_year'] == year
            if mask.any():
                current_sum = df.loc[mask, 'yhat'].sum()
                if current_sum != 0:
                    scale_factor = target_sum / current_sum
                    df.loc[mask, 'yhat'] *= scale_factor
                elif target_sum != 0:
                    logger.warning(f"Current sum for {year} is 0, cannot scale to target {target_sum}")
    
    # Adjust for monthly peaks if max_demand is provided
    if max_demand is not None:
        logger.info("Applying monthly peak demand constraints")
        
        # Prepare monthly peak demand data
        max_demand_melted = max_demand.melt(
            id_vars=['financial_year'],
            value_vars=['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'],
            var_name='month_name', 
            value_name='max_demand_val'
        )
        
        # Map month names to month numbers
        month_map = {
            'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 
            'Oct': 10, 'Nov': 11, 'Dec': 12, 'Jan': 1, 'Feb': 2, 'Mar': 3
        }
        max_demand_melted['month'] = max_demand_melted['month_name'].map(month_map)
        
        for _, row in max_demand_melted.iterrows():
            year, month, target_max = row['financial_year'], row['month'], row['max_demand_val']
            mask = (df['financial_year'] == year) & (df['month'] == month)
            
            if mask.any():
                current_max = df.loc[mask, 'yhat'].max()
                
                # Only scale up if current_max is below target_max and target_max is positive
                if current_max < target_max and target_max > 0:
                    if current_max != 0:
                        scale_factor = target_max / current_max
                        df.loc[mask, 'yhat'] *= scale_factor
                    else:
                        logger.warning(f"Current max for {year}-{month} is 0, cannot scale to target peak {target_max}")
    
    # Apply load factor constraints if year_wise_load_factors is provided
    if year_wise_load_factors is not None:
        logger.info("Applying yearly load factor constraints")
        
        # Handle forecast years beyond the provided load factors
        if df['financial_year'].max() > year_wise_load_factors['financial_year'].max():
            latest_year = year_wise_load_factors['financial_year'].max()
            latest_load_factor = year_wise_load_factors.loc[
                year_wise_load_factors['financial_year'] == latest_year, 'load_factor'
            ].values[0]
            
            # Filter to keep only years >= df's min financial year
            year_wise_load_factors = year_wise_load_factors[
                year_wise_load_factors['financial_year'] >= df['financial_year'].min()
            ]
            
            # Generate list of missing financial years
            missing_years = list(range(
                latest_year + 1,
                df['financial_year'].max() + 1
            ))
            
            # Create DataFrame for missing years
            missing_data = pd.DataFrame({
                'financial_year': missing_years,
                'load_factor': [latest_load_factor] * len(missing_years)
            })
            
            # Append missing data to year_wise_load_factors
            year_wise_load_factors = pd.concat([year_wise_load_factors, missing_data], ignore_index=True)
        
        # Apply load factor constraints
        for _, lf_row in year_wise_load_factors.iterrows():
            year_to_constrain = lf_row['financial_year']
            target_load_factor = lf_row['load_factor']
            
            year_mask = df['financial_year'] == year_to_constrain
            
            if not year_mask.any():
                continue
            
            # Load factor must be positive
            if target_load_factor <= 0:
                logger.warning(f"Invalid load factor {target_load_factor} for {year_to_constrain}. Skipping.")
                continue
            
            current_yearly_sum = df.loc[year_mask, 'yhat'].sum()
            num_points_in_year = year_mask.sum()
            
            if num_points_in_year == 0:
                continue
            
            # Calculate average demand
            current_average_demand = current_yearly_sum / num_points_in_year if num_points_in_year > 0 else 0
            
            # Calculate maximum allowable peak
            max_allowable_peak = current_average_demand / (target_load_factor/100)
            
            # Cap values exceeding the maximum allowable peak
            condition_to_cap = year_mask & (df['yhat'] > max_allowable_peak)
            df.loc[condition_to_cap, 'yhat'] = max_allowable_peak
    
    return df


def apply_monthly_max_constraints(forecast_df: pd.DataFrame, max_demand: pd.DataFrame) -> pd.DataFrame:
    """
    Apply monthly maximum demand constraints to the forecast.
    
    Parameters:
    -----------
    forecast_df : pd.DataFrame
        DataFrame with forecast
    max_demand : pd.DataFrame
        DataFrame with monthly maximum demand targets
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with adjusted forecast
    """
    df = forecast_df.copy()
    
    # Prepare monthly peak demand data
    max_demand_melted = max_demand.melt(
        id_vars=['financial_year'],
        value_vars=['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'],
        var_name='month_name', 
        value_name='max_demand_val'
    )
    
    # Map month names to month numbers
    month_map = {
        'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 
        'Oct': 10, 'Nov': 11, 'Dec': 12, 'Jan': 1, 'Feb': 2, 'Mar': 3
    }
    max_demand_melted['month'] = max_demand_melted['month_name'].map(month_map)
    
    for _, row in max_demand_melted.iterrows():
        year, month, target_max = row['financial_year'], row['month'], row['max_demand_val']
        mask = (df['financial_year'] == year) & (df['month'] == month)
        
        if mask.any():
            current_max = df.loc[mask, 'yhat'].max()
            
            # Only scale up if current_max is below target_max and target_max is positive
            if current_max < target_max and target_max > 0:
                if current_max != 0:
                    scale_factor = target_max / current_max
                    df.loc[mask, 'yhat'] *= scale_factor
                else:
                    logger.warning(f"Current max for {year}-{month} is 0, cannot scale to target peak {target_max}")
    
    return df


def apply_monthly_avg_constraints(forecast_df: pd.DataFrame, total_demand: pd.DataFrame) -> pd.DataFrame:
    """
    Apply monthly average demand constraints based on the yearly totals.
    
    Parameters:
    -----------
    forecast_df : pd.DataFrame
        DataFrame with forecast
    total_demand : pd.DataFrame
        DataFrame with yearly total demand targets
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with adjusted forecast
    """
    df = forecast_df.copy()
    
    # Calculate monthly shares in the forecast
    monthly_sums = df.groupby(['financial_year', 'month'])['yhat'].sum().reset_index()
    yearly_sums = df.groupby(['financial_year'])['yhat'].sum().reset_index()
    
    # Merge to get yearly totals
    monthly_sums = monthly_sums.merge(yearly_sums, on='financial_year', suffixes=('_month', '_year'))
    
    # Calculate monthly shares
    monthly_sums['share'] = monthly_sums['yhat_month'] / monthly_sums['yhat_year']
    
    # For each year in total_demand, distribute to months based on shares
    for _, year_row in total_demand.iterrows():
        year = year_row['financial_year']
        target_sum = year_row['Total demand']
        
        year_shares = monthly_sums[monthly_sums['financial_year'] == year]
        
        for _, month_row in year_shares.iterrows():
            month = month_row['month']
            share = month_row['share']
            
            # Calculate target for this month
            target_month_sum = target_sum * share
            
            # Calculate current sum for this month
            mask = (df['financial_year'] == year) & (df['month'] == month)
            current_month_sum = df.loc[mask, 'yhat'].sum()
            
            # Apply scaling
            if current_month_sum > 0:
                scale_factor = target_month_sum / current_month_sum
                df.loc[mask, 'yhat'] *= scale_factor
    
    return df


def generate_improved_load_factors(forecast_df: pd.DataFrame, 
                                 base_load_factors: Optional[pd.DataFrame],
                                 improvement_pct: float,
                                 forecast_years: range) -> pd.DataFrame:
    """
    Generate improved load factors for future years based on base load factors
    and a year-on-year improvement percentage.
    
    Parameters:
    -----------
    forecast_df : pd.DataFrame
        DataFrame with forecast
    base_load_factors : pd.DataFrame, optional
        DataFrame with base yearly load factors
    improvement_pct : float
        Year-on-year improvement percentage
    forecast_years : range
        Range of years to forecast
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with improved yearly load factors
    """
    # If no base load factors provided, calculate from forecast
    if base_load_factors is None or len(base_load_factors) == 0:
        # Calculate load factors from forecast
        yearly_stats = forecast_df.groupby('financial_year').agg({
            'yhat': ['mean', 'max']
        }).reset_index()
        
        # Flatten multi-index
        yearly_stats.columns = ['financial_year', 'avg_demand', 'max_demand']
        
        # Calculate load factor
        yearly_stats['load_factor'] = yearly_stats['avg_demand'] / yearly_stats['max_demand'] * 100
        
        # Get base load factor (for first year in forecast or earliest available)
        earliest_year = min(yearly_stats['financial_year'])
        base_load_factor = yearly_stats.loc[yearly_stats['financial_year'] == earliest_year, 'load_factor'].values[0]
    else:
        # Use the last available load factor as base
        base_load_factor = base_load_factors['load_factor'].values[-1]
    
    # Generate improved load factors for all forecast years
    improved_factors = []
    
    for i, year in enumerate(forecast_years):
        # Apply compound improvement
        improved_factor = base_load_factor * (1 + improvement_pct/100) ** i
        
        # Cap at 100% (theoretical maximum)
        improved_factor = min(improved_factor, 100)
        
        improved_factors.append({
            'financial_year': year,
            'load_factor': improved_factor
        })
    
    return pd.DataFrame(improved_factors)


def update_with_custom_load_factors(base_load_factors: Optional[pd.DataFrame],
                                  custom_load_factors: Dict) -> pd.DataFrame:
    """
    Update load factors with custom values for specific years.
    
    Parameters:
    -----------
    base_load_factors : pd.DataFrame, optional
        DataFrame with base yearly load factors
    custom_load_factors : Dict
        Dictionary with {year: load_factor} pairs
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with updated load factors
    """
    # Start with base factors or empty DataFrame
    if base_load_factors is None:
        result = pd.DataFrame(columns=['financial_year', 'load_factor'])
    else:
        result = base_load_factors.copy()
    
    # Add or update custom load factors
    for year, load_factor in custom_load_factors.items():
        year = int(year)
        load_factor = float(load_factor)
        
        # Check if year exists
        if year in result['financial_year'].values:
            # Update existing year
            result.loc[result['financial_year'] == year, 'load_factor'] = load_factor
        else:
            # Add new year
            new_row = pd.DataFrame({
                'financial_year': [year],
                'load_factor': [load_factor]
            })
            result = pd.concat([result, new_row], ignore_index=True)
    
    # Sort by year
    result = result.sort_values('financial_year').reset_index(drop=True)
    
    return result


def prepare_data_for_ml(historical_demand: pd.DataFrame, weather_data: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare data for machine learning model.
    
    Parameters:
    -----------
    historical_demand : pd.DataFrame
        Historical demand data
    weather_data : pd.DataFrame
        Weather data
        
    Returns:
    --------
    pd.DataFrame
        Combined data for ML modeling
    """
    # Process historical demand data
    demand_data = historical_demand.copy()
    demand_data['datetime'] = pd.to_datetime(demand_data['date'].astype(str) + ' ' + demand_data['time'].astype(str))
    demand_data = demand_data[['datetime', 'demand']].set_index('datetime')
    
    # Process weather data
    weather_data = weather_data.copy()
    if 'datetime' not in weather_data.columns:
        if 'date' in weather_data.columns and 'time' in weather_data.columns:
            weather_data['datetime'] = pd.to_datetime(weather_data['date'].astype(str) + ' ' + weather_data['time'].astype(str))
        else:
            raise ValueError("Weather data must have 'datetime' or 'date' and 'time' columns")
    
    weather_data = weather_data.set_index('datetime')
    
    # Merge data on datetime index
    combined_data = demand_data.join(weather_data, how='inner')
    
    # Reset index for easier handling
    combined_data = combined_data.reset_index()
    
    # Create time features
    combined_data['hour'] = combined_data['datetime'].dt.hour
    combined_data['dayofweek'] = combined_data['datetime'].dt.dayofweek
    combined_data['month'] = combined_data['datetime'].dt.month
    combined_data['year'] = combined_data['datetime'].dt.year
    combined_data['day'] = combined_data['datetime'].dt.day
    combined_data['is_weekend'] = combined_data['dayofweek'].isin([5, 6]).astype(int)
    combined_data['hour_sin'] = np.sin(2 * np.pi * combined_data['hour'] / 24)
    combined_data['hour_cos'] = np.cos(2 * np.pi * combined_data['hour'] / 24)
    combined_data['month_sin'] = np.sin(2 * np.pi * combined_data['month'] / 12)
    combined_data['month_cos'] = np.cos(2 * np.pi * combined_data['month'] / 12)
    combined_data['dayofweek_sin'] = np.sin(2 * np.pi * combined_data['dayofweek'] / 7)
    combined_data['dayofweek_cos'] = np.cos(2 * np.pi * combined_data['dayofweek'] / 7)
    
    # Handle missing values
    combined_data = combined_data.fillna(method='ffill')
    
    return combined_data


def train_weather_demand_model(data: pd.DataFrame) -> Any:
    """
    Train a machine learning model for demand forecasting with weather.
    
    Parameters:
    -----------
    data : pd.DataFrame
        Combined data for ML modeling
        
    Returns:
    --------
    Any
        Trained ML model
    """
    # Select features based on available columns
    weather_features = [col for col in data.columns if col.lower() in [
        'temperature', 'temp', 'humidity', 'wind_speed', 'precipitation',
        'dewpoint', 'pressure', 'cloud_cover', 'visibility'
    ]]
    
    time_features = [
        'hour_sin', 'hour_cos', 'month_sin', 'month_cos', 
        'dayofweek_sin', 'dayofweek_cos', 'is_weekend'
    ]
    
    # Combine features
    features = weather_features + time_features
    
    # Ensure all features exist in the data
    features = [f for f in features if f in data.columns]
    
    if len(features) == 0:
        raise ValueError("No valid features found for ML model")
    
    # Split data into train and test sets
    X = data[features]
    y = data['demand']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model (Random Forest)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    # Evaluate model
    logger.info(f"ML Model R² score: {model.score(X_test_scaled, y_test)}")
    
    # Save model and scaler for future use
    model_dir = "models"
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(model, os.path.join(model_dir, "weather_demand_model.joblib"))
    joblib.dump(scaler, os.path.join(model_dir, "weather_demand_scaler.joblib"))
    joblib.dump(features, os.path.join(model_dir, "weather_demand_features.joblib"))
    
    # Return model, scaler, and features as a tuple
    return (model, scaler, features)


def forecast_with_ml_model(model_info: Tuple, data: pd.DataFrame, forecast_years: range) -> pd.DataFrame:
    """
    Generate forecast using ML model.
    
    Parameters:
    -----------
    model_info : Tuple
        Tuple containing (model, scaler, features)
    data : pd.DataFrame
        Combined data for ML modeling
    forecast_years : range
        Range of years to forecast
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with ML-based forecast
    """
    model, scaler, features = model_info
    
    # Create date range for forecast
    start_date = f"{min(forecast_years)-1}-04-01"
    end_date = f"{max(forecast_years)}-03-31 23:00"
    future_dates = pd.date_range(start=start_date, end=end_date, freq='H')
    
    # Create DataFrame for future dates
    future_df = pd.DataFrame({'ds': future_dates})
    
    # Add features
    future_df['hour'] = future_df['ds'].dt.hour
    future_df['dayofweek'] = future_df['ds'].dt.dayofweek
    future_df['month'] = future_df['ds'].dt.month
    future_df['year'] = future_df['ds'].dt.year
    future_df['day'] = future_df['ds'].dt.day
    future_df['is_weekend'] = future_df['dayofweek'].isin([5, 6]).astype(int)
    future_df['hour_sin'] = np.sin(2 * np.pi * future_df['hour'] / 24)
    future_df['hour_cos'] = np.cos(2 * np.pi * future_df['hour'] / 24)
    future_df['month_sin'] = np.sin(2 * np.pi * future_df['month'] / 12)
    future_df['month_cos'] = np.cos(2 * np.pi * future_df['month'] / 12)
    future_df['dayofweek_sin'] = np.sin(2 * np.pi * future_df['dayofweek'] / 7)
    future_df['dayofweek_cos'] = np.cos(2 * np.pi * future_df['dayofweek'] / 7)
    
    # Generate weather features for future dates (synthetic or provided)
    weather_features = [f for f in features if f not in future_df.columns]
    
    if weather_features:
        # Use historical weather patterns to generate future weather
        for feature in weather_features:
            # Get historical values by month and hour
            historical_patterns = data.groupby(['month', 'hour'])[feature].mean().reset_index()
            
            # Merge with future_df
            future_df = future_df.merge(historical_patterns, on=['month', 'hour'], how='left')
            
            # Add random variation (± 10%)
            variation = 0.1
            noise = np.random.normal(1, variation, size=len(future_df))
            future_df[feature] *= noise
    
    # Ensure all required features are available
    missing_features = [f for f in features if f not in future_df.columns]
    if missing_features:
        logger.warning(f"Missing features for ML forecast: {missing_features}")
        # Fill with zeros for now
        for feature in missing_features:
            future_df[feature] = 0
    
    # Generate forecast
    X_future = future_df[features]
    X_future_scaled = scaler.transform(X_future)
    future_df['yhat'] = model.predict(X_future_scaled)
    
    # Ensure non-negative values
    future_df['yhat'] = future_df['yhat'].clip(lower=0)
    
    return future_df


def generate_synthetic_weather_data(historical_demand: pd.DataFrame, forecast_years: range) -> pd.DataFrame:
    """
    Generate synthetic weather data for forecast years.
    
    Parameters:
    -----------
    historical_demand : pd.DataFrame
        Historical demand data
    forecast_years : range
        Range of years to forecast
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with synthetic weather data
    """
    # Create date range for forecast
    start_date = f"{min(forecast_years)-1}-04-01"
    end_date = f"{max(forecast_years)}-03-31 23:00"
    future_dates = pd.date_range(start=start_date, end=end_date, freq='H')
    
    # Create DataFrame for future dates
    weather_df = pd.DataFrame({'datetime': future_dates})
    
    # Add month and hour
    weather_df['month'] = weather_df['datetime'].dt.month
    weather_df['hour'] = weather_df['datetime'].dt.hour
    
    # Generate synthetic temperature data
    # Base temperature by month (northern hemisphere)
    base_temp_by_month = {
        1: 5, 2: 7, 3: 10, 4: 15, 5: 20, 6: 25,
        7: 30, 8: 28, 9: 23, 10: 18, 11: 12, 12: 8
    }
    
    # Daily temperature pattern
    hourly_pattern = {
        0: -3, 1: -3.5, 2: -4, 3: -4.5, 4: -5, 5: -4.5,
        6: -4, 7: -3, 8: -1, 9: 1, 10: 2, 11: 3,
        12: 3.5, 13: 4, 14: 4.5, 15: 4, 16: 3, 17: 2,
        18: 1, 19: 0, 20: -1, 21: -1.5, 22: -2, 23: -2.5
    }
    
    # Generate temperature
    weather_df['temperature'] = weather_df.apply(
        lambda row: base_temp_by_month[row['month']] + hourly_pattern[row['hour']] + np.random.normal(0, 1.5), 
        axis=1
    )
    
    # Generate humidity (inversely related to temperature)
    weather_df['humidity'] = 80 - 0.5 * weather_df['temperature'] + np.random.normal(0, 5, size=len(weather_df))
    weather_df['humidity'] = weather_df['humidity'].clip(10, 100)
    
    # Generate wind speed (more in winter, less in summer)
    seasonal_factor = weather_df['month'].map({
        1: 1.3, 2: 1.2, 3: 1.1, 4: 1, 5: 0.9, 6: 0.8,
        7: 0.7, 8: 0.8, 9: 0.9, 10: 1, 11: 1.1, 12: 1.2
    })
    weather_df['wind_speed'] = 10 * seasonal_factor + np.random.exponential(2, size=len(weather_df))
    
    # Generate cloud cover (more in winter, less in summer)
    weather_df['cloud_cover'] = 50 * seasonal_factor + np.random.normal(0, 20, size=len(weather_df))
    weather_df['cloud_cover'] = weather_df['cloud_cover'].clip(0, 100)
    
    # Drop month and hour columns used for generation
    weather_df = weather_df.drop(columns=['month', 'hour'])
    
    return weather_df


def adjust_output_frequency(forecast: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """
    Adjust the output frequency of the forecast.
    
    Parameters:
    -----------
    forecast : pd.DataFrame
        DataFrame with hourly forecast
    frequency : str
        Output frequency ('hourly', 'half_hourly', or '15min')
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with adjusted frequency
    """
    if frequency == 'hourly':
        # Already hourly, return as is
        return forecast
    
    # Start with the hourly forecast
    result = forecast.copy()
    result = result[['ds', 'yhat']]
    
    if frequency == 'half_hourly':
        # Create half-hourly time points
        half_hours = []
        values = []
        
        for i, row in result.iterrows():
            # Original hour
            half_hours.append(row['ds'])
            values.append(row['yhat'])
            
            # Half hour
            if i < len(result) - 1:
                half_hour = row['ds'] + pd.Timedelta(minutes=30)
                next_value = result.iloc[i+1]['yhat']
                half_hours.append(half_hour)
                values.append((row['yhat'] + next_value) / 2)  # Interpolate
        
        # Create new DataFrame
        result = pd.DataFrame({
            'ds': half_hours,
            'yhat': values
        })
    
    elif frequency == '15min':
        # Create 15-minute time points
        quarter_hours = []
        values = []
        
        for i, row in result.iterrows():
            # Original hour
            quarter_hours.append(row['ds'])
            values.append(row['yhat'])
            
            # 15, 30, 45 minutes
            if i < len(result) - 1:
                next_value = result.iloc[i+1]['yhat']
                for j in range(1, 4):
                    quarter = row['ds'] + pd.Timedelta(minutes=15*j)
                    quarter_hours.append(quarter)
                    # Linear interpolation
                    values.append(row['yhat'] + (next_value - row['yhat']) * (j/4))
        
        # Create new DataFrame
        result = pd.DataFrame({
            'ds': quarter_hours,
            'yhat': values
        })
    
    else:
        raise ValueError(f"Unsupported frequency: {frequency}")
    
    return result


def format_final_output(forecast: pd.DataFrame) -> pd.DataFrame:
    """
    Format the final output DataFrame.
    
    Parameters:
    -----------
    forecast : pd.DataFrame
        DataFrame with forecast
        
    Returns:
    --------
    pd.DataFrame
        Formatted DataFrame for output
    """
    result = forecast.copy()
    result['yhat'] = result['yhat'].round(2)
    result['datetime'] = result['ds']
    result['Demand'] = result['yhat']
    
    if 'ds' in result.columns:
        result['Date'] = result['ds'].dt.date
        result['Time'] = result['ds'].dt.strftime('%H:%M:%S')
        
        # Calculate fiscal year
        if 'month' not in result.columns:
            result['month'] = result['ds'].dt.month
        if 'year' not in result.columns:
            result['year'] = result['ds'].dt.year
        
        result['Fiscal_Year'] = np.where(result['month'] >= 4, result['year'] + 1, result['year'])
        result['Year'] = result['year']
    
    # Select output columns
    output_columns = ['datetime', 'Demand', 'Date', 'Time', 'Fiscal_Year', 'Year']
    output_columns = [col for col in output_columns if col in result.columns]
    
    return result[output_columns]


def validate_forecast(forecast: pd.DataFrame, 
                     total_demand: Optional[pd.DataFrame], 
                     max_demand: Optional[pd.DataFrame]) -> Dict:
    """
    Validate the forecast against the targets.
    
    Parameters:
    -----------
    forecast : pd.DataFrame
        DataFrame with forecasted demand
    total_demand : pd.DataFrame, optional
        DataFrame with yearly total demand targets
    max_demand : pd.DataFrame, optional
        DataFrame with monthly peak demand targets
        
    Returns:
    --------
    Dict
        Dictionary with validation metrics
    """
    validation = {}
    
    # Add financial_year and month columns if not already present
    if 'financial_year' not in forecast.columns:
        forecast['financial_year'] = np.where(forecast['ds'].dt.month >= 4, 
                                             forecast['ds'].dt.year + 1, 
                                             forecast['ds'].dt.year)
    
    if 'month' not in forecast.columns:
        forecast['month'] = forecast['ds'].dt.month
    
    # Validate yearly totals
    if total_demand is not None:
        yearly_sums = forecast.groupby('financial_year')['yhat'].sum()
        
        for year in yearly_sums.index:
            if year in total_demand['financial_year'].values:
                target = total_demand[total_demand['financial_year'] == year]['Total demand'].values[0]
                actual = yearly_sums[year]
                diff_percent = abs(target - actual) / target * 100 if target != 0 else 0
                validation[f'Year_{year}_difference_%'] = diff_percent
    
    # Validate monthly peaks
    if max_demand is not None:
        max_demand_melted = max_demand.melt(
            id_vars=['financial_year'], 
            value_vars=['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'],
            var_name='month_name', 
            value_name='max_demand'
        )
        
        month_map = {
            'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 
            'Oct': 10, 'Nov': 11, 'Dec': 12, 'Jan': 1, 'Feb': 2, 'Mar': 3
        }
        max_demand_melted['month'] = max_demand_melted['month_name'].map(month_map)
        
        for _, row in max_demand_melted.iterrows():
            year, month, target_max = row['financial_year'], row['month'], row['max_demand']
            
            # Get the maximum forecasted demand for this month
            monthly_data = forecast[(forecast['financial_year'] == year) & (forecast['month'] == month)]
            
            if not monthly_data.empty:
                monthly_max = monthly_data['yhat'].max()
                diff = abs(target_max - monthly_max)
                validation[f'Max_{year}_{month}_difference'] = diff
    
    return validation


def log_validation_results(validation_results: Dict) -> None:
    """
    Log validation results.
    
    Parameters:
    -----------
    validation_results : Dict
        Dictionary with validation metrics
    """
    if not validation_results:
        logger.info("No validation metrics available")
        return
    
    logger.info("Validation Results:")
    
    # Log yearly differences
    yearly_diffs = {k: v for k, v in validation_results.items() if k.startswith('Year_')}
    if yearly_diffs:
        logger.info("Yearly Total Demand Differences:")
        for k, v in yearly_diffs.items():
            logger.info(f"  {k}: {v:.2f}%")
    
    # Log monthly peak differences
    monthly_diffs = {k: v for k, v in validation_results.items() if k.startswith('Max_')}
    if monthly_diffs:
        logger.info("Monthly Peak Demand Differences:")
        for k, v in monthly_diffs.items():
            logger.info(f"  {k}: {v:.2f}")


def check_total_demand_data(excel_file_path: str) -> bool:
    """
    Check if the Excel file has valid Total Demand data.
    
    Parameters:
    -----------
    excel_file_path : str
        Path to Excel file
        
    Returns:
    --------
    bool
        True if valid Total Demand data is available, False otherwise
    """
    try:
        # Try to read the Total Demand sheet
        total_demand = pd.read_excel(excel_file_path, sheet_name='Total Demand')
        
        # Check if it has required columns
        if ('financial_year' in total_demand.columns or 'Year' in total_demand.columns) and \
           ('Total demand' in total_demand.columns or 'Annual_Demand' in total_demand.columns):
            return len(total_demand) > 0
        
        return False
    except Exception:
        return False


def load_scenario_data(project_path: str, scenario_name: str) -> Dict:
    """
    Load data from a forecast scenario.
    
    Parameters:
    -----------
    project_path : str
        Path to project directory
    scenario_name : str
        Name of the forecast scenario
        
    Returns:
    --------
    Dict
        Dictionary with scenario data
    """
    scenario_path = os.path.join(project_path, 'results', 'demand_projection', scenario_name)
    consolidated_path = os.path.join(scenario_path, 'consolidated_results.csv')
    
    scenario_data = {}
    
    if os.path.exists(consolidated_path):
        # Read the consolidated CSV
        df = pd.read_csv(consolidated_path)
        
        # Extract data
        if 'Year' in df.columns and 'Total' in df.columns:
            consolidated_data = []
            
            for _, row in df.iterrows():
                consolidated_data.append({
                    'year': row['Year'],
                    'value': row['Total']
                })
            
            scenario_data['Consolidated Electricity Demand'] = consolidated_data
    
    return scenario_data
# Helper function to get total annual demand for future years
def get_future_annual_demand(project_path: str, start_year: int, end_year: int, forecast_scenario: Optional[str]) -> Dict[int, float]:
    annual_demand_data = {}
    try:
        if forecast_scenario:
            scenario_data_loaded = load_scenario_data(project_path, forecast_scenario)
            if scenario_data_loaded and 'Consolidated Electricity Demand' in scenario_data_loaded:
                for item in scenario_data_loaded['Consolidated Electricity Demand']:
                    year = int(item.get('year'))
                    value = float(item.get('value', 0)) # Assuming value is in kWh
                    if start_year <= year <= end_year:
                        annual_demand_data[year] = value / 1_000_000 # Convert kWh to GWh
            else: # Fallback if CSV is not there or not in expected format
                 logger.warning(f"Consolidated data not found or invalid for scenario {forecast_scenario}. Trying Excel.")
                 raise ValueError("Scenario data not found") # Force fallback to excel
        else: # No scenario, try Excel
            raise ValueError("No scenario provided") # Force fallback to excel

    except Exception as e_scenario: # Catch issues with scenario loading or force excel
        logger.info(f"Loading annual demand from Excel due to: {e_scenario}")
        excel_file_path = os.path.join(project_path, 'inputs', 'load_curve_template.xlsx')
        if not os.path.exists(excel_file_path):
            logger.error(f"Load curve template not found at {excel_file_path} for annual demand.")
            return annual_demand_data # Empty

        try:
            # Ensure this sheet name and column names match the user's description
            df_total_demand = pd.read_excel(excel_file_path, sheet_name='Total Demand')
            if 'financial_year' in df_total_demand.columns and 'Total demand' in df_total_demand.columns:
                for _, row in df_total_demand.iterrows():
                    year = int(row['financial_year'])
                    value = float(row['Total demand'])/ 1_000_000  # Convert kWh to GWh
                    if start_year <= year <= end_year:
                        annual_demand_data[year] = value
            else:
                logger.error("'financial_year' or 'Total demand' columns missing in 'Total Demand' sheet.")
        except Exception as e_excel:
            logger.error(f"Error reading 'Total Demand' sheet from Excel: {e_excel}")

    return annual_demand_data
