# utils/pypsa_runner.py
import pandas as pd
import pypsa
import os
from pathlib import Path
import numpy as np
import logging
from .pypsa_helpers import extract_tables_by_markers, annuity_future_value

logger = logging.getLogger(__name__)

# ---- Snapshot Generation ----
def _generate_snapshots_for_year(input_file_path, target_year, snapshot_condition, weightings_freq_hours, base_year_config):
    logger.info(f"Generating snapshots for year {target_year}, condition: '{snapshot_condition}', freq: {weightings_freq_hours}H")
    
    fy_start_date = pd.Timestamp(f'{int(target_year)-1}-04-01 00:00:00')
    fy_end_date   = pd.Timestamp(f'{int(target_year)}-03-31 23:00:00')
    full_year_hourly_index = pd.date_range(start=fy_start_date, end=fy_end_date, freq='H')

    def _resample_index(dt_index, freq_hours):
        if dt_index.empty: return pd.DatetimeIndex([])
        min_dt, max_dt = dt_index.min(), dt_index.max()
        # Create a dummy series on the original fine-grained index to resample
        dummy_series = pd.Series(1, index=dt_index)
        # Origin helps align resampling bins; freq_hours must be int
        resampled = dummy_series.resample(f'{int(freq_hours)}H', origin=min_dt).mean().index
        return resampled[(resampled >= min_dt) & (resampled <= max_dt)] # Ensure within original bounds

    selected_snapshots_for_model = pd.DatetimeIndex([])

    if snapshot_condition == 'All Snapshots':
        selected_snapshots_for_model = _resample_index(full_year_hourly_index, weightings_freq_hours)
    elif snapshot_condition == 'Critical days':
        try:
            df_custom_days = pd.read_excel(input_file_path, sheet_name='Custom days')
            # Determine calendar year for each month to construct dates in the target financial year
            df_custom_days['CalendarYear'] = df_custom_days['Month'].apply(
                lambda m: int(target_year) - 1 if int(m) >= 4 else int(target_year)
            )
            custom_dates = pd.to_datetime(
                {'year': df_custom_days['CalendarYear'], 'month': df_custom_days['Month'], 'day': df_custom_days['Day']}
            )
            hourly_custom_day_snapshots = pd.DatetimeIndex([])
            for date_val in sorted(custom_dates.unique()):
                hourly_custom_day_snapshots = hourly_custom_day_snapshots.union(
                    pd.date_range(start=date_val, periods=24, freq='H')
                )
            selected_snapshots_for_model = _resample_index(hourly_custom_day_snapshots, weightings_freq_hours)
        except Exception as e:
            logger.error(f"Error processing critical days for {target_year}: {e}. Defaulting to all snapshots.")
            selected_snapshots_for_model = _resample_index(full_year_hourly_index, weightings_freq_hours)
    elif snapshot_condition == 'Typical days': # Peak week per month logic
        try:
            demand_excel_df = pd.read_excel(input_file_path, sheet_name='Demand')
            demand_series_full_year = pd.Series(index=full_year_hourly_index, dtype=float)
            if int(target_year) in demand_excel_df.columns:
                demand_series_full_year = pd.Series(demand_excel_df[int(target_year)].iloc[:len(full_year_hourly_index)].values, index=full_year_hourly_index)
            else:
                logger.warning(f"Demand data for year {target_year} not found in Excel. Using base year {base_year_config} demand.")
                demand_series_full_year = pd.Series(demand_excel_df[int(base_year_config)].iloc[:len(full_year_hourly_index)].values, index=full_year_hourly_index)

            temp_df = demand_series_full_year.to_frame('demand')
            temp_df['month_in_fy'] = (temp_df.index.month - 4 + 12) % 12 # 0 (Apr) to 11 (Mar)
            temp_df['week_in_fy'] = temp_df.index.to_series().apply(lambda dt: (dt - fy_start_date).days // 7)

            peak_week_snapshots_list = []
            for _, month_group in temp_df.groupby('month_in_fy'):
                if month_group.empty: continue
                weekly_sum = month_group.groupby('week_in_fy')['demand'].sum()
                if weekly_sum.empty: continue
                peak_week_num = weekly_sum.idxmax()
                peak_week_snapshots_list.extend(month_group[month_group['week_in_fy'] == peak_week_num].index)
            
            if peak_week_snapshots_list:
                selected_snapshots_for_model = _resample_index(pd.DatetimeIndex(peak_week_snapshots_list), weightings_freq_hours)
            else:
                logger.warning(f"No peak weeks identified for {target_year}. Defaulting to all snapshots.")
                selected_snapshots_for_model = _resample_index(full_year_hourly_index, weightings_freq_hours)
        except Exception as e:
            logger.error(f"Error processing typical days for {target_year}: {e}. Defaulting to all snapshots.")
            selected_snapshots_for_model = _resample_index(full_year_hourly_index, weightings_freq_hours)
    else:
        logger.error(f"Unknown snapshot condition: {snapshot_condition}. Defaulting to all snapshots.")
        selected_snapshots_for_model = _resample_index(full_year_hourly_index, weightings_freq_hours)

    logger.info(f"Generated {len(selected_snapshots_for_model)} snapshots for year {target_year} based on '{snapshot_condition}'.")
    return selected_snapshots_for_model, full_year_hourly_index


def _generate_snapshots_for_multiyear(input_file_path, year_list_full, snapshot_condition, weightings_freq_hours, base_year_config):
    logger.info("Generating snapshots for multi-year investment...")
    all_snapshots_data_list = []
    for fy_target in year_list_full:
        fy_target_int = int(fy_target)
        logger.debug(f"Processing multi-year snapshots for FY ending {fy_target_int}")
        
        period_model_snapshots, _ = _generate_snapshots_for_year(
            input_file_path, fy_target_int, snapshot_condition, weightings_freq_hours, base_year_config
        )
        if period_model_snapshots.empty:
            logger.warning(f"No snapshots for FY {fy_target_int} in multi-year setup. Skipping.")
            continue

        # Get demand for these specific model snapshots
        fy_start_date = pd.Timestamp(f'{fy_target_int-1}-04-01 00:00:00')
        fy_end_date   = pd.Timestamp(f'{fy_target_int}-03-31 23:00:00')
        full_fy_hourly_index = pd.date_range(start=fy_start_date, end=fy_end_date, freq='H')
        
        demand_excel_df = pd.read_excel(input_file_path, sheet_name='Demand')
        demand_series_full_fy = pd.Series(index=full_fy_hourly_index, dtype=float)
        if fy_target_int in demand_excel_df.columns:
            demand_series_full_fy = pd.Series(demand_excel_df[fy_target_int].iloc[:len(full_fy_hourly_index)].values, index=full_fy_hourly_index)
        else:
            demand_series_full_fy = pd.Series(demand_excel_df[int(base_year_config)].iloc[:len(full_fy_hourly_index)].values, index=full_fy_hourly_index)
        
        # Align demand to the selected model snapshots for this period
        demand_for_model_snapshots = demand_series_full_fy.reindex(period_model_snapshots).interpolate(method='time').ffill().bfill()

        df_fy_snapshots = pd.DataFrame({
            'snapshots_datetime': period_model_snapshots, # This is already the potentially resampled index
            'demand': demand_for_model_snapshots.values,
            'period_year': fy_target_int # Store the financial year end
        })
        all_snapshots_data_list.append(df_fy_snapshots)

    if not all_snapshots_data_list:
        logger.error("No snapshot data generated for any year in multi-year mode.")
        return pd.DataFrame(columns=['snapshots_datetime', 'demand', 'period_year'])
        
    final_df = pd.concat(all_snapshots_data_list, ignore_index=True)
    logger.info(f"Total snapshots for multi-year setup: {len(final_df)}")
    return final_df

# ---- PyPSA Logic Core ----
def run_pypsa_model_core(job_id, project_path_str, scenario_name, ui_settings_overrides):
    from app import pypsa_jobs # Import here due to potential circularity

    job = pypsa_jobs[job_id]
    job['status'] = 'Processing Inputs'
    job['log'] = ["Model run started...\n"]

    project_path = Path(project_path_str)
    input_file_path = project_path / "inputs" / "pypsa_input_template.xlsx"
    results_base_dir = project_path / "results" / "PyPSA_Modeling"
    scenario_results_dir = results_base_dir / scenario_name
    scenario_results_dir.mkdir(parents=True, exist_ok=True)

    original_cwd = os.getcwd()
    # It's often good practice for PyPSA to run with the results directory as CWD
    # However, ensure all paths are absolute if you do this, or adjust relative paths
    # os.chdir(scenario_results_dir) # Optional: If PyPSA behaves better this way

    try:
        job['log'].append(f"Reading input file: {input_file_path}\n")
        xls = pd.ExcelFile(input_file_path)
        sheet_data = {s: xls.parse(s) for s in xls.sheet_names}

        setting_df_excel = sheet_data.get('Settings')
        if setting_df_excel is None: raise ValueError("Sheet 'Settings' not found.")
        
        settings_main_excel_table = extract_tables_by_markers(setting_df_excel, '~').get('Main_Settings')
        if settings_main_excel_table is None: raise ValueError("Table '~Main_Settings' not found in 'Settings' sheet.")

        def get_setting(key, default_value, df=settings_main_excel_table, overrides=ui_settings_overrides):
            val = overrides.get(key)
            if val is not None:
                job['log'].append(f"UI Override for '{key}': {val}\n")
                # Type casting for known numeric settings
                if key in ['Weightings', 'Base_Year', 'solver_threads'] and val is not None:
                    try: return int(val)
                    except ValueError: return default_value
                return val
            
            row = df[df['Setting'] == key]
            if not row.empty and 'Option' in row.columns and pd.notna(row['Option'].iloc[0]):
                excel_val = row['Option'].iloc[0]
                # Type casting for known numeric settings from Excel
                if key in ['Weightings', 'Base_Year'] and pd.notna(excel_val):
                    try: return int(excel_val)
                    except ValueError: return default_value
                job['log'].append(f"Excel Setting for '{key}': {excel_val}\n")
                return excel_val
            job['log'].append(f"Default for '{key}': {default_value}\n")
            return default_value

        snapshot_condition = get_setting('Run Pypsa Model on', 'All Snapshots')
        weightings_freq_hours = get_setting('Weightings', 1)
        base_year_config = get_setting('Base_Year', 2025)
        multi_year_mode = get_setting('Multi Year Investment', 'No')
        do_generator_clustering = get_setting('Generator Cluster', 'No') == 'Yes'
        
        solver_name_opt = get_setting('solver_name', 'highs', overrides=ui_settings_overrides) # specific override for solver
        solver_options_from_ui = {
            'log_file': str(scenario_results_dir / f'{scenario_name}_solver.log'),
            "threads": get_setting('solver_threads', 0, overrides=ui_settings_overrides),
            "solver": get_setting('highs_solver_type', "simplex", overrides=ui_settings_overrides),
            "parallel": "on" if get_setting('solver_parallel', True, overrides=ui_settings_overrides) else "off",
            "presolve": "on" if get_setting('solver_presolve', True, overrides=ui_settings_overrides) else "off",
            'log_to_console': get_setting('log_to_console_solver', True, overrides=ui_settings_overrides)
        }
        if solver_options_from_ui["solver"] == "pdlp":
             solver_options_from_ui['pdlp_d_gap_tol'] = get_setting('pdlp_gap_tol', 1e-4, overrides=ui_settings_overrides)
        elif solver_options_from_ui["solver"] == "simplex":
             solver_options_from_ui['simplex_strategy'] = get_setting('simplex_strategy', 0, overrides=ui_settings_overrides)


        # --- DataFrames from Excel ---
        generators_base_df = sheet_data.get('Generators', pd.DataFrame())
        buses_df = sheet_data.get('Buses', pd.DataFrame())
        lifetime_df = sheet_data.get('Lifetime', pd.DataFrame())
        fom_df = sheet_data.get('FOM', pd.DataFrame())
        demand_excel_df = sheet_data.get('Demand', pd.DataFrame())
        fuel_cost_df = sheet_data.get('Fuel_cost', pd.DataFrame())
        startupcost_df = sheet_data.get('Startupcost', pd.DataFrame())
        co2_df = sheet_data.get('CO2', pd.DataFrame())
        p_max_pu_excel_df = sheet_data.get('P_max_pu', pd.DataFrame())
        p_min_pu_excel_df = sheet_data.get('P_min_pu', pd.DataFrame())
        capital_cost_df = sheet_data.get('Capital_cost', pd.DataFrame())
        wacc_df = sheet_data.get('wacc', pd.DataFrame())
        new_generators_excel_df = sheet_data.get('New_Generators', pd.DataFrame())
        pipe_line_generators_p_max_df = sheet_data.get('Pipe_Line_Generators_p_max', pd.DataFrame())
        pipe_line_generators_p_min_df = sheet_data.get('Pipe_Line_Generators_p_min', pd.DataFrame())
        new_storage_excel_df = sheet_data.get('New_Storage', pd.DataFrame())
        links_excel_df = sheet_data.get('Links', pd.DataFrame())
        pipe_line_storage_p_min_df = sheet_data.get('Pipe_Line_Storage_p_min', pd.DataFrame())
        # Add new ones from notebook
        committable_settings_df = extract_tables_by_markers(setting_df_excel, '~').get('commitable')
        monthly_constraints_settings_df = extract_tables_by_markers(setting_df_excel, '~').get('Monthly_Constraints')
        battery_cycle_settings_df = extract_tables_by_markers(setting_df_excel, '~').get('Battery_Cycle')
        


        year_list_from_demand = sorted([int(col) for col in demand_excel_df.columns if isinstance(col, (int, float)) and str(int(col)).startswith('20')])
        years_to_simulate = [yr for yr in year_list_from_demand if yr >= base_year_config]

        if not years_to_simulate:
            raise ValueError(f"No years to simulate. Base year {base_year_config}, available demand years: {year_list_from_demand}")
        
        job['log'].append(f"Simulating years: {years_to_simulate}\n")
        job['progress'] = 10
        
        # --- MAIN PYPSA LOGIC ---
        if multi_year_mode == 'No': # Iterative Single Year Runs
            job['status'] = 'Running Single-Year Models'
            previous_year_export_path = None # To carry over capacities

            for idx, current_year in enumerate(years_to_simulate):
                job['current_step'] = f"Processing Year: {current_year}"
                job['log'].append(f"\n--- Processing Year: {current_year} ---\n")

                model_snapshots_index, full_year_hourly_index = _generate_snapshots_for_year(
                    input_file_path, current_year, snapshot_condition, weightings_freq_hours, base_year_config
                )
                if model_snapshots_index.empty:
                    job['log'].append(f"Warning: No snapshots for year {current_year}. Skipping.\n")
                    continue
                
                # Snapshot weighting
                snapshot_duration_hours = weightings_freq_hours # Duration of one model snapshot
                capital_annuity_period_hours = 8760 # Costs are annualized over 8760 hours
                # Weighting for capacity costs: how many actual hours does one model snapshot represent in the annuity calculation.
                snapshot_representativeness_in_year = capital_annuity_period_hours / len(model_snapshots_index) if len(model_snapshots_index) > 0 else 1
                effective_capital_weighting = snapshot_duration_hours * snapshot_representativeness_in_year
                
                job['log'].append(f"Year {current_year}: {len(model_snapshots_index)} snapshots. Effective capital weighting factor per snapshot: {effective_capital_weighting:.2f}\n")


                n = pypsa.Network()
                n.set_snapshots(model_snapshots_index)
                # Operational costs are weighted by the duration of the snapshot (weightings_freq_hours)
                n.snapshot_weightings["objective"] = weightings_freq_hours 
                
                # Prepare P_max_pu and P_min_pu for the current year's snapshots
                p_max_pu_this_year = p_max_pu_excel_df.iloc[:len(full_year_hourly_index)].copy()
                p_max_pu_this_year.index = full_year_hourly_index
                p_max_pu_this_year_aligned = p_max_pu_this_year.reindex(model_snapshots_index).interpolate(method='time').ffill().bfill()

                p_min_pu_this_year = p_min_pu_excel_df.iloc[:len(full_year_hourly_index)].copy()
                p_min_pu_this_year.index = full_year_hourly_index
                p_min_pu_this_year_aligned = p_min_pu_this_year.reindex(model_snapshots_index).interpolate(method='time').ffill().bfill()


                # Add Buses
                if not buses_df.empty: n.import_components_from_dataframe(buses_df, "Bus")
                job['log'].append("Buses added.\n")

                # Add Loads
                demand_series_full_year = pd.Series(index=full_year_hourly_index, dtype=float)
                col_to_use = current_year if current_year in demand_excel_df.columns else base_year_config
                job['log'].append(f"Using demand from year {col_to_use} for simulation year {current_year}.\n")
                demand_series_full_year = pd.Series(demand_excel_df[col_to_use].iloc[:len(full_year_hourly_index)].values, index=full_year_hourly_index)
                load_p_set_aligned = demand_series_full_year.reindex(model_snapshots_index).interpolate(method='time').ffill().bfill()
                n.add("Load", "MainLoad", bus="Main_Bus", p_set=load_p_set_aligned) # Assuming Main_Bus
                job['log'].append("Loads added.\n")

                # Add Carriers
                if not co2_df.empty:
                    for _, car_row in co2_df.iterrows():
                        n.add("Carrier", car_row['TECHNOLOGY'], co2_emissions=car_row['tonnes/MWh'], color=car_row.get('color', '#CCCCCC'))
                job['log'].append("Carriers added.\n")

                # Add Generators (Existing and New)
                current_generators_df = pd.DataFrame()
                if current_year == base_year_config or previous_year_export_path is None:
                    logger.info(f"Using base generators for year {current_year}")
                    current_generators_df = generators_base_df.copy()
                    # Ensure p_nom_extendable column exists and set Market to True
                    if 'p_nom_extendable' not in current_generators_df.columns:
                        current_generators_df['p_nom_extendable'] = False
                    current_generators_df.loc[current_generators_df['carrier'] == 'Market', 'p_nom_extendable'] = True
                else:
                    logger.info(f"Loading generators from previous year ({current_year-1}) results")
                    prev_gens_path = previous_year_export_path / "generators.csv"
                    if prev_gens_path.exists():
                        current_generators_df = pd.read_csv(prev_gens_path)
                        if 'p_nom_opt' in current_generators_df.columns:
                            current_generators_df['p_nom'] = np.maximum(current_generators_df['p_nom'], current_generators_df['p_nom_opt'])
                            current_generators_df = current_generators_df.drop(columns=['p_nom_opt'], errors='ignore')
                        current_generators_df['p_nom_extendable'] = False # Existing are not extendable
                        current_generators_df.loc[current_generators_df['carrier'] == 'Market', 'p_nom_extendable'] = True # Market always extendable
                    else:
                        logger.warning(f"Previous year generator data not found at {prev_gens_path}. Using base for {current_year}.")
                        current_generators_df = generators_base_df.copy()
                        if 'p_nom_extendable' not in current_generators_df.columns: current_generators_df['p_nom_extendable'] = False
                        current_generators_df.loc[current_generators_df['carrier'] == 'Market', 'p_nom_extendable'] = True


                # Add existing generators to network
                for _, gen_row in current_generators_df.iterrows():
                    tech = gen_row['carrier']
                    cap_cost_val = 0
                    if tech in capital_cost_df['carrier'].values:
                        cap_cost_series = capital_cost_df[capital_cost_df['carrier'] == tech][current_year]
                        if not cap_cost_series.empty and pd.notna(cap_cost_series.iloc[0]):
                              wacc_val = wacc_df[current_year].iloc[0] if current_year in wacc_df.columns and not wacc_df[current_year].empty else 0.08 # default wacc
                              life_val = lifetime_df[lifetime_df['carrier'] == tech]['lifetime'].iloc[0]
                              fom_val = fom_df[fom_df['carrier'] == tech]['FOM'].iloc[0]
                              cap_cost_val = float(abs(annuity_future_value(wacc_val, life_val, cap_cost_series.iloc[0])) + fom_val)
                              cap_cost_val = round(cap_cost_val / effective_capital_weighting) if effective_capital_weighting != 0 else 0


                    p_max_pu_series = p_max_pu_this_year_aligned.get(f"{tech}_Outside" if gen_row['bus'] == 'Outside Kerala' and tech in ['Solar', 'Wind'] else tech, pd.Series(1, index=n.snapshots))
                    p_min_pu_series = p_min_pu_this_year_aligned.get(f"{tech}_Outside" if gen_row['bus'] == 'Outside Kerala' and tech in ['Solar', 'Wind'] else tech, pd.Series(0, index=n.snapshots))
                    if gen_row['bus'] == 'Outside Kerala' and tech in ['Solar', 'Wind']: p_min_pu_series = 0 # Override for RE outside

                    n.add("Generator", gen_row['name'],
                          bus=gen_row['bus'], p_nom=gen_row['p_nom'],
                          p_nom_extendable=gen_row.get('p_nom_extendable', False),
                          p_min_pu=p_min_pu_series.tolist(), p_max_pu=p_max_pu_series.tolist(),
                          carrier=tech, marginal_cost=gen_row['marginal_cost'],
                          build_year=gen_row['build_year'], lifetime=gen_row['lifetime'],
                          capital_cost=cap_cost_val,
                          committable=gen_row.get('committable', False),
                          start_up_cost=gen_row.get('start_up_cost', 0), shut_down_cost=gen_row.get('shut_down_cost', 0),
                          min_up_time=gen_row.get('min_up_time', 0), min_down_time=gen_row.get('min_down_time', 0),
                          ramp_limit_up=gen_row.get('ramp_limit_up', 1), ramp_limit_down=gen_row.get('ramp_limit_down', 1))
                job['log'].append("Existing generators processed.\n")

                # Add NEW potential generators for current_year build
                if not new_generators_excel_df.empty:
                    for _, new_gen_row in new_generators_excel_df.iterrows():
                        tech = new_gen_row['carrier']
                        bus_name = new_gen_row['bus']
                        
                        cap_cost_val = 0
                        cap_cost_tech_bus_df = capital_cost_df[(capital_cost_df['carrier'] == tech) & (capital_cost_df['bus'] == bus_name)]

                        if not cap_cost_tech_bus_df.empty and current_year in cap_cost_tech_bus_df.columns and pd.notna(cap_cost_tech_bus_df[current_year].iloc[0]):
                            wacc_val = wacc_df[current_year].iloc[0] if current_year in wacc_df.columns and not wacc_df[current_year].empty else 0.08
                            life_val = lifetime_df[lifetime_df['carrier'] == tech]['lifetime'].iloc[0]
                            fom_val = fom_df[fom_df['carrier'] == tech]['FOM'].iloc[0]
                            cap_cost_val = float(abs(annuity_future_value(wacc_val, life_val, cap_cost_tech_bus_df[current_year].iloc[0])) + fom_val)
                            cap_cost_val = round(cap_cost_val / effective_capital_weighting) if effective_capital_weighting !=0 else 0
                        
                        p_max_pu_series = p_max_pu_this_year_aligned.get(f"{tech}_Outside" if bus_name == 'Outside Kerala' and tech in ['Solar', 'Wind'] else tech, pd.Series(1, index=n.snapshots))
                        p_min_pu_series = p_min_pu_this_year_aligned.get(f"{tech}_Outside" if bus_name == 'Outside Kerala' and tech in ['Solar', 'Wind'] else tech, pd.Series(0, index=n.snapshots))
                        if bus_name == 'Outside Kerala' and tech in ['Solar', 'Wind']: p_min_pu_series = 0


                        p_nom_min_val = pipe_line_generators_p_min_df[
                            (pipe_line_generators_p_min_df["TECHNOLOGY"] == new_gen_row["TECHNOLOGY"]) & 
                            (pipe_line_generators_p_min_df["bus"] == bus_name)][current_year].values[0] if not pipe_line_generators_p_min_df.empty else 0
                        
                        p_nom_max_val = pipe_line_generators_p_max_df[
                            (pipe_line_generators_p_max_df["TECHNOLOGY"] == new_gen_row["TECHNOLOGY"]) &
                            (pipe_line_generators_p_max_df["bus"] == bus_name)][current_year].values[0] if not pipe_line_generators_p_max_df.empty else np.inf
                        
                        job['log'].append(f"Adding new potential: {new_gen_row['TECHNOLOGY']} at {bus_name} for {current_year}. MinCap: {p_nom_min_val}, MaxCap: {p_nom_max_val if p_nom_max_val != np.inf else 'inf'}, CapCost: {cap_cost_val}\n")

                        n.add("Generator", f"{new_gen_row['TECHNOLOGY']} {bus_name} Build{current_year}",
                              bus=bus_name, p_nom_extendable=True, # All new are extendable
                              p_nom_min = p_nom_min_val, p_nom_max = p_nom_max_val,
                              p_min_pu=p_min_pu_series.tolist(), p_max_pu=p_max_pu_series.tolist(),
                              carrier=tech, 
                              marginal_cost=fuel_cost_df[fuel_cost_df['carrier']==tech][current_year].values[0] if not fuel_cost_df[fuel_cost_df['carrier']==tech].empty else 0,
                              build_year=current_year, lifetime=lifetime_df[lifetime_df['carrier'] == tech]['lifetime'].iloc[0],
                              capital_cost=cap_cost_val,
                              # Committable and ramp from new_generators_excel_df
                              committable=new_gen_row.get('committable', False),
                              start_up_cost=startupcost_df[startupcost_df['carrier']==tech][current_year].values[0] if not startupcost_df[startupcost_df['carrier']==tech].empty else 0,
                              shut_down_cost=startupcost_df[startupcost_df['carrier']==tech][current_year].values[0] if not startupcost_df[startupcost_df['carrier']==tech].empty else 0,
                              min_up_time=new_gen_row.get('min_up_time',0), min_down_time=new_gen_row.get('min_down_time',0),
                              ramp_limit_up=new_gen_row.get('ramp_limit_up',1), ramp_limit_down=new_gen_row.get('ramp_limit_down',1)
                              )
                job['log'].append("New potential generators processed.\n")
                
                # Apply retiring logic before clustering
                n = _apply_retiring_logic(n, current_year, base_year_config)
                job['log'].append("Retiring logic applied.\n")

                # Apply generator clustering if enabled
                if do_generator_clustering:
                    n = _apply_generator_clustering(n, p_max_pu_this_year_aligned, p_min_pu_this_year_aligned)
                    job['log'].append("Generator clustering applied.\n")

                #Add Storage (existing from previous, new potential)
                #... similar logic as generators for stores and storage_units ...
                # Store existing storage from previous year (if any)
                if previous_year_export_path:
                    prev_stores_path = previous_year_export_path / "stores.csv"
                    prev_storage_units_path = previous_year_export_path / "storage_units.csv"
                    if prev_stores_path.exists():
                        existing_stores_df = pd.read_csv(prev_stores_path)
                        if 'e_nom_opt' in existing_stores_df.columns:
                            existing_stores_df['e_nom'] = np.maximum(existing_stores_df['e_nom'], existing_stores_df['e_nom_opt'])
                        existing_stores_df['e_nom_extendable'] = False
                        n.import_components_from_dataframe(existing_stores_df.set_index('name'), "Store")
                        job['log'].append(f"Added existing stores from {current_year-1}.\n")
                    if prev_storage_units_path.exists():
                        existing_storage_units_df = pd.read_csv(prev_storage_units_path)
                        if 'p_nom_opt' in existing_storage_units_df.columns:
                             existing_storage_units_df['p_nom'] = np.maximum(existing_storage_units_df['p_nom'], existing_storage_units_df['p_nom_opt'])
                        existing_storage_units_df['p_nom_extendable'] = False
                        n.import_components_from_dataframe(existing_storage_units_df.set_index('name'), "StorageUnit")
                        job['log'].append(f"Added existing storage units from {current_year-1}.\n")
                
                # Add NEW potential storage
                if not new_storage_excel_df.empty:
                    for _, new_store_row in new_storage_excel_df.iterrows():
                        store_tech = new_store_row['TECHNOLOGY'] # Main identifier
                        store_carrier = new_store_row['carrier']
                        store_bus = new_store_row['bus']
                        store_type_excel = new_store_row['Type'] # 'Store' or 'StorageUnit'

                        cap_cost_store_df = capital_cost_df[capital_cost_df['TECHNOLOGY'] == store_tech]
                        cap_cost_val = 0
                        if not cap_cost_store_df.empty and current_year in cap_cost_store_df.columns and pd.notna(cap_cost_store_df[current_year].iloc[0]):
                            wacc_val = wacc_df[current_year].iloc[0] if current_year in wacc_df.columns and not wacc_df[current_year].empty else 0.08
                            life_val = lifetime_df[lifetime_df['TECHNOLOGY'] == store_tech]['lifetime'].iloc[0]
                            # Assuming FOM for storage is also in FOM_df by TECHNOLOGY
                            fom_val = fom_df[fom_df['carrier'] == store_tech]['FOM'].iloc[0] if store_tech in fom_df['carrier'].values else 0
                            cap_cost_val = float(abs(annuity_future_value(wacc_val, life_val, cap_cost_store_df[current_year].iloc[0])) + fom_val)
                            cap_cost_val = round(cap_cost_val / effective_capital_weighting) if effective_capital_weighting != 0 else 0

                        e_nom_min_val_store = pipe_line_storage_p_min_df[
                            (pipe_line_storage_p_min_df["TECHNOLOGY"] == store_tech)][current_year].values[0] if not pipe_line_storage_p_min_df.empty else 0

                        if store_type_excel == 'Store':
                            n.add('Store', f"{store_tech} {store_bus} Build{current_year}",
                                  bus=store_bus, carrier=store_carrier, type=store_type_excel,
                                  e_min_pu=0, e_max_pu=1, capital_cost=cap_cost_val,
                                  e_nom_extendable=True, build_year=current_year,
                                  standing_loss=new_store_row.get('standing_loss', 0.0001), # Example default
                                  lifetime=lifetime_df[lifetime_df['TECHNOLOGY'] == store_tech]['lifetime'].iloc[0],
                                  e_nom_min=e_nom_min_val_store)
                        elif store_type_excel == 'StorageUnit':
                             p_nom_min_val_su = pipe_line_storage_p_min_df[ # Assuming same sheet for p_nom_min of SU
                                (pipe_line_storage_p_min_df["TECHNOLOGY"] == store_tech)][current_year].values[0] if not pipe_line_storage_p_min_df.empty else 0
                             
                             n.add('StorageUnit', f"{store_tech} {store_bus} Build{current_year}",
                                  bus=store_bus, type=store_type_excel, carrier=store_carrier,
                                  p_min_pu=0, p_max_pu=1, capital_cost=cap_cost_val,
                                  p_nom_extendable=True, p_nom_min=p_nom_min_val_su,
                                  marginal_cost=0, build_year=current_year,
                                  max_hours=new_store_row.get('max_hours',6), # Example, take from excel if available
                                  lifetime=lifetime_df[lifetime_df['TECHNOLOGY'] == store_tech]['lifetime'].iloc[0],
                                  efficiency_store=new_store_row.get('efficiency_store', 0.9),
                                  efficiency_dispatch=new_store_row.get('efficiency_dispatch',0.9)
                                  )
                    job['log'].append("New potential storage processed.\n")
                
                # Apply storage retiring
                n = _apply_retiring_logic(n, current_year, base_year_config) # It will apply to stores and SUs
                job['log'].append("Storage retiring logic applied.\n")


                # Add Links
                if not links_excel_df.empty:
                    invertor_setting = get_setting('Storage Charging/Discharging', 'Anytime', df=settings_main_excel_table)
                    for _, link_row in links_excel_df.iterrows():
                        link_p_max_pu_val = link_row['p_max_pu']
                        link_p_min_pu_val = link_row['p_min_pu']
                        if str(link_row['name']).startswith("invertor") and invertor_setting == 'Solar and Non solar hours':
                            solar_hours_start, solar_hours_end = 10, 17 # Example
                            # Create series based on model_snapshots_index
                            is_solar_hour = (model_snapshots_index.hour >= solar_hours_start) & (model_snapshots_index.hour < solar_hours_end)
                            if link_row['type'] == 'charging link': # Charging during solar
                                link_p_max_pu_val = np.where(is_solar_hour, 1, 0).tolist()
                                link_p_min_pu_val = 0
                            else: # Discharging during non-solar
                                link_p_max_pu_val = np.where(is_solar_hour, 0, 1).tolist()
                                link_p_min_pu_val = 0
                        
                        n.add('Link', link_row['name'],
                              bus0=link_row['bus0'], bus1=link_row['bus1'],
                              p_nom=link_row.get('p_nom',0), # Existing links might have p_nom
                              efficiency=link_row['efficiency'],
                              p_max_pu=link_p_max_pu_val, p_min_pu=link_p_min_pu_val,
                              type=link_row.get('type', None),
                              lifetime=link_row.get('lifetime', np.inf), build_year=link_row.get('build_year', base_year_config),
                              p_nom_extendable=link_row.get('p_nom_extendable', False),
                              marginal_cost=link_row.get('marginal_cost',0),
                              capital_cost=link_row.get('capital_cost',0) # Annuity might be needed if extendable
                              )
                job['log'].append("Links added.\n")
                
                # --- Optimization ---
                job['log'].append(f"Optimizing network for year {current_year}...\n")
                n.optimize(solver_name=solver_name_opt, solver_options=solver_options_from_ui)
                job['log'].append("Initial optimization complete.\n")

                # Apply unit commitment if enabled
                if get_setting('Committable', 'No') == 'Yes' and committable_settings_df is not None:
                    job['log'].append("Applying unit commitment logic...\n")
                    n.generators.loc[n.generators.carrier.isin(committable_settings_df[committable_settings_df['Option']=='Yes']['Carrier'].tolist()), 'committable'] = True
                    n.generators.loc[n.generators.carrier.isin(committable_settings_df[committable_settings_df['Option']=='No']['Carrier'].tolist()), 'committable'] = False
                    n.optimize(solver_name=solver_name_opt, solver_options=solver_options_from_ui) # Re-solve
                    job['log'].append("Re-optimization after unit commitment complete.\n")
                
                # Apply network constraints if enabled (monthly, battery cycle)
                # This is tricky as the notebook function `adding_network_constrains_network` itself calls solve.
                # For simplicity here, we might assume constraints should be part of the main solve if possible,
                # or it's a post-processing step that re-solves.
                # If it re-solves, the `p_nom_opt` from the *first* solve should be fixed.
                # For now, let's assume `adding_network_constrains_network` function handles its own solve if needed.
                # The notebook's `adding_network_constrains_network` actually creates a *new* linopy model and adds constraints.
                #This implies it might be for analysis rather than re-optimizing the main PyPSA network state.
                # Let's call it *after* the main PyPSA solve for now, understanding it might need refinement.
                
                _apply_network_constraints(n, sheet_data['Settings'], settings_main_excel_table) # This needs internal solve
                job['log'].append("Network constraints logic applied (if any).\n")


                # --- Export Results ---
                year_results_dir = scenario_results_dir / f"results_{current_year}"
                year_results_dir.mkdir(parents=True, exist_ok=True)
                job['log'].append(f"Exporting results for {current_year} to {year_results_dir}\n")
                
                n.export_to_csv_folder(str(year_results_dir))
                n.export_to_netcdf(str(scenario_results_dir / f"{current_year}_network.nc")) # Save yearly NC file too
                
                previous_year_export_path = year_results_dir
                job['progress'] = 10 + int(((idx + 1) / total_years) * 80)
            
            job['log'].append("All single-year models processed.\n")

        # --- MULTI-YEAR CO-OPTIMIZATION MODES ---
        elif multi_year_mode in ['Only Capacity expansion on multi year', 'All in One multi year']:
            job['status'] = 'Running Multi-Year Model'
            job['current_step'] = "Setting up multi-year network"

            multiyear_snapshots_with_demand = _generate_snapshots_for_multiyear(
                input_file_path, years_to_simulate, snapshot_condition, weightings_freq_hours, base_year_config
            )
            if multiyear_snapshots_with_demand.empty:
                raise ValueError("No snapshots generated for multi-year mode.")

            n = pypsa.Network()
            # Create MultiIndex: (period_year, snapshot_datetime)
            multi_idx = pd.MultiIndex.from_arrays([
                multiyear_snapshots_with_demand['period_year'],
                pd.to_datetime(multiyear_snapshots_with_demand['snapshots_datetime'])
            ], names=['period', 'snapshot_time'])
            n.set_snapshots(multi_idx)
            
            n.investment_periods = years_to_simulate # Financial years
            
            # Investment period weightings (years in each period)
            diff_years = list(np.diff(years_to_simulate)) + [1] # Last period is 1 year long
            n.investment_period_weightings["years"] = pd.Series(diff_years, index=years_to_simulate)

            # Objective weighting (discounting)
            discount_rate = get_setting('Discount Rate', 0.05, df=settings_main_excel_table) # Example default
            current_T = 0
            for period, nyears_in_period in n.investment_period_weightings.years.items():
                discounts = [(1 / (1 + discount_rate) ** t) for t in range(current_T, current_T + int(nyears_in_period))]
                n.investment_period_weightings.at[period, "objective"] = sum(discounts)
                current_T += int(nyears_in_period)
            
            # Snapshot weightings (duration of each snapshot within its operational year)
            n.snapshot_weightings["objective"] = weightings_freq_hours

            job['log'].append(f"Multi-year network snapshots created: {len(n.snapshots)} total.\n")
            job['progress'] = 20

            # Prepare P_max_pu and P_min_pu for all snapshots
            # This needs to tile/repeat the annual profiles across all years in the multi-index
            p_max_pu_multi_aligned = pd.DataFrame(index=n.snapshots)
            p_min_pu_multi_aligned = pd.DataFrame(index=n.snapshots)

            for tech_col in p_max_pu_excel_df.columns:
                if tech_col == 'snapshots': continue
                annual_profile_max = p_max_pu_excel_df[tech_col].iloc[:8760] # Assuming 8760 hourly profile
                annual_profile_min = p_min_pu_excel_df[tech_col].iloc[:8760] if tech_col in p_min_pu_excel_df.columns else pd.Series(0, index=range(8760))
                
                tech_max_series = []
                tech_min_series = []
                for period_year in n.investment_periods:
                    fy_start_date_Snap = pd.Timestamp(f'{int(period_year)-1}-04-01 00:00:00')
                    period_snapshots_this_fy = n.snapshots[n.snapshots.get_level_values('period') == period_year].get_level_values('snapshot_time')
                    
                    # Align annual profile to this FY's start and then to model snapshots
                    aligned_max = pd.Series(annual_profile_max.values, index=pd.date_range(start=fy_start_date_Snap, periods=8760, freq='H'))\
                                      .reindex(period_snapshots_this_fy).interpolate(method='time').ffill().bfill()
                    aligned_min = pd.Series(annual_profile_min.values, index=pd.date_range(start=fy_start_date_Snap, periods=8760, freq='H'))\
                                      .reindex(period_snapshots_this_fy).interpolate(method='time').ffill().bfill()
                    tech_max_series.append(aligned_max)
                    tech_min_series.append(aligned_min)
                
                if tech_max_series: p_max_pu_multi_aligned[tech_col] = pd.concat(tech_max_series)
                if tech_min_series: p_min_pu_multi_aligned[tech_col] = pd.concat(tech_min_series)
            
            job['log'].append("Time-series PU profiles prepared for multi-year.\n")

            # Add Buses, Loads, Carriers (same as single year)
            if not buses_df.empty: n.import_components_from_dataframe(buses_df, "Bus")
            n.add("Load", "MainLoad", bus="Main_Bus", p_set=multiyear_snapshots_with_demand['demand'].values)
            if not co2_df.empty:
                for _, car_row in co2_df.iterrows():
                    n.add("Carrier", car_row['TECHNOLOGY'], co2_emissions=car_row['tonnes/MWh'], color=car_row.get('color', '#CCCCCC'))
            job['log'].append("Buses, Loads, Carriers added for multi-year.\n")

            # Add Generators (Base + New Potential across all years)
            # Base generators (exist from or before the first simulation year)
            base_gens_to_add = generators_base_df[generators_base_df['build_year'] <= years_to_simulate[0]]
            for _, gen_row in base_gens_to_add.iterrows():
                tech = gen_row['carrier']
                # Capital cost for existing is 0, marginal cost is from data
                p_max_pu_series = p_max_pu_multi_aligned.get(f"{tech}_Outside" if gen_row['bus'] == 'Outside Kerala' and tech in ['Solar', 'Wind'] else tech, pd.Series(1, index=n.snapshots))
                p_min_pu_series = p_min_pu_multi_aligned.get(f"{tech}_Outside" if gen_row['bus'] == 'Outside Kerala' and tech in ['Solar', 'Wind'] else tech, pd.Series(0, index=n.snapshots))
                if gen_row['bus'] == 'Outside Kerala' and tech in ['Solar', 'Wind']: p_min_pu_series = 0
                
                n.add("Generator", gen_row['name'], bus=gen_row['bus'], p_nom=gen_row['p_nom'],
                      p_nom_extendable=False, # Existing are not extendable in multi-year by default
                      p_min_pu=p_min_pu_series.tolist(), p_max_pu=p_max_pu_series.tolist(),
                      carrier=tech, marginal_cost=gen_row['marginal_cost'],
                      build_year=gen_row['build_year'], lifetime=gen_row['lifetime'], capital_cost=0,
                      committable=gen_row.get('committable', False), # ... other params
                      start_up_cost=gen_row.get('start_up_cost',0), shut_down_cost=gen_row.get('shut_down_cost',0),
                      min_up_time=gen_row.get('min_up_time',0),min_down_time=gen_row.get('min_down_time',0),
                      ramp_limit_up=gen_row.get('ramp_limit_up',1),ramp_limit_down=gen_row.get('ramp_limit_down',1)
                      )
            job['log'].append("Base generators added for multi-year.\n")

            # New potential generators (can be built in any `year` in `years_to_simulate`)
            if not new_generators_excel_df.empty:
                for current_build_year in years_to_simulate: # Each new generator is considered for build in each period
                    for _, new_gen_row in new_generators_excel_df.iterrows():
                        tech = new_gen_row['carrier']
                        bus_name = new_gen_row['bus']
                        # Capital cost calculation (annuity per year of build)
                        cap_cost_tech_bus_df = capital_cost_df[(capital_cost_df['carrier'] == tech) & (capital_cost_df['bus'] == bus_name)]
                        cap_cost_val = 0
                        if not cap_cost_tech_bus_df.empty and current_build_year in cap_cost_tech_bus_df.columns and pd.notna(cap_cost_tech_bus_df[current_build_year].iloc[0]):
                            wacc_val = wacc_df[current_build_year].iloc[0] if current_build_year in wacc_df.columns and not wacc_df[current_build_year].empty else 0.08
                            life_val = lifetime_df[lifetime_df['carrier'] == tech]['lifetime'].iloc[0]
                            fom_val = fom_df[fom_df['carrier'] == tech]['FOM'].iloc[0] # Assuming FOM is fixed over years here
                            cap_cost_val = float(abs(annuity_future_value(wacc_val, life_val, cap_cost_tech_bus_df[current_build_year].iloc[0])) + fom_val)
                            # No division by capital_weighting here as PyPSA handles it with investment_period_weightings["objective"]

                        p_max_pu_series = p_max_pu_multi_aligned.get(f"{tech}_Outside" if bus_name == 'Outside Kerala' and tech in ['Solar', 'Wind'] else tech, pd.Series(1, index=n.snapshots))
                        p_min_pu_series = p_min_pu_multi_aligned.get(f"{tech}_Outside" if bus_name == 'Outside Kerala' and tech in ['Solar', 'Wind'] else tech, pd.Series(0, index=n.snapshots))
                        if bus_name == 'Outside Kerala' and tech in ['Solar', 'Wind']: p_min_pu_series = 0

                        p_nom_min_val = pipe_line_generators_p_min_df[(pipe_line_generators_p_min_df["TECHNOLOGY"] == new_gen_row["TECHNOLOGY"]) & (pipe_line_generators_p_min_df["bus"] == bus_name)][current_build_year].values[0] if not pipe_line_generators_p_min_df.empty else 0
                        p_nom_max_val = pipe_line_generators_p_max_df[(pipe_line_generators_p_max_df["TECHNOLOGY"] == new_gen_row["TECHNOLOGY"]) & (pipe_line_generators_p_max_df["bus"] == bus_name)][current_build_year].values[0] if not pipe_line_generators_p_max_df.empty else np.inf
                        
                        gen_name = f"{new_gen_row['TECHNOLOGY']} {bus_name} PotentialBuild{current_build_year}"
                        if gen_name not in n.generators.index: # Avoid duplicate definitions across build years if logic implies unique name per (tech,bus)
                            n.add("Generator", gen_name, bus=bus_name, p_nom_extendable=True,
                                  p_nom_min=p_nom_min_val, p_nom_max=p_nom_max_val,
                                  p_min_pu=p_min_pu_series.tolist(), p_max_pu=p_max_pu_series.tolist(),
                                  carrier=tech, 
                                  marginal_cost=fuel_cost_df[fuel_cost_df['carrier']==tech][current_build_year].values[0] if not fuel_cost_df[fuel_cost_df['carrier']==tech].empty else 0,
                                  build_year=current_build_year, lifetime=lifetime_df[lifetime_df['carrier'] == tech]['lifetime'].iloc[0],
                                  capital_cost=cap_cost_val,
                                  committable=new_gen_row.get('committable', False), #... other params
                                  start_up_cost=startupcost_df[startupcost_df['carrier']==tech][current_build_year].values[0] if not startupcost_df[startupcost_df['carrier']==tech].empty else 0,
                                  shut_down_cost=startupcost_df[startupcost_df['carrier']==tech][current_build_year].values[0] if not startupcost_df[startupcost_df['carrier']==tech].empty else 0,
                                  min_up_time=new_gen_row.get('min_up_time',0),min_down_time=new_gen_row.get('min_down_time',0),
                                  ramp_limit_up=new_gen_row.get('ramp_limit_up',1),ramp_limit_down=new_gen_row.get('ramp_limit_down',1)
                                  )
            job['log'].append("New potential generators for multi-year processed.\n")

            # Add Storage (New Potential across all years, existing ones are implicitly part of generators_base_df if modeled as StorageUnit and read)
            if not new_storage_excel_df.empty:
                for current_build_year in years_to_simulate:
                    for _, new_store_row in new_storage_excel_df.iterrows():
                        # ... (similar logic as for new generators, adapting for Store/StorageUnit attributes)
                        store_tech = new_store_row['TECHNOLOGY']
                        store_carrier = new_store_row['carrier']
                        store_bus = new_store_row['bus']
                        store_type_excel = new_store_row['Type']
                        
                        cap_cost_store_df = capital_cost_df[capital_cost_df['TECHNOLOGY'] == store_tech]
                        cap_cost_val = 0
                        if not cap_cost_store_df.empty and current_build_year in cap_cost_store_df.columns and pd.notna(cap_cost_store_df[current_build_year].iloc[0]):
                            wacc_val = wacc_df[current_build_year].iloc[0] if current_build_year in wacc_df.columns and not wacc_df[current_build_year].empty else 0.08
                            life_val = lifetime_df[lifetime_df['TECHNOLOGY'] == store_tech]['lifetime'].iloc[0]
                            fom_val = fom_df[fom_df['carrier'] == store_tech]['FOM'].iloc[0] if store_tech in fom_df['carrier'].values else 0
                            cap_cost_val = float(abs(annuity_future_value(wacc_val, life_val,  cap_cost_store_df[current_build_year].iloc[0] )) + fom_val)

                        e_nom_min_val_store = pipe_line_storage_p_min_df[(pipe_line_storage_p_min_df["TECHNOLOGY"] == store_tech)][current_build_year].values[0] if not pipe_line_storage_p_min_df.empty else 0
                        
                        store_name = f"{store_tech} {store_bus} PotentialBuild{current_build_year}"
                        if store_name not in (n.stores.index if store_type_excel == 'Store' else n.storage_units.index):
                            if store_type_excel == 'Store':
                                n.add('Store', store_name, bus=store_bus, carrier=store_carrier,
                                      e_nom_extendable=True, e_nom_min=e_nom_min_val_store, capital_cost=cap_cost_val,
                                      build_year=current_build_year, lifetime=lifetime_df[lifetime_df['TECHNOLOGY']==store_tech]['lifetime'].iloc[0],
                                      standing_loss=new_store_row.get('standing_loss',0.0001), e_initial=new_store_row.get('e_initial',0.5)*e_nom_min_val_store, # Start half full of min
                                      e_cyclic=new_store_row.get('e_cyclic',True))
                            elif store_type_excel == 'StorageUnit':
                                p_nom_min_val_su = e_nom_min_val_store # Assuming p_nom_min for SU is taken from same sheet for simplicity
                                n.add('StorageUnit', store_name, bus=store_bus, carrier=store_carrier,
                                      p_nom_extendable=True, p_nom_min=p_nom_min_val_su, capital_cost=cap_cost_val,
                                      build_year=current_build_year, lifetime=lifetime_df[lifetime_df['TECHNOLOGY']==store_tech]['lifetime'].iloc[0],
                                      max_hours=new_store_row.get('max_hours',6),
                                      efficiency_store=new_store_row.get('efficiency_store', 0.9),
                                      efficiency_dispatch=new_store_row.get('efficiency_dispatch',0.9),
                                      cyclic_state_of_charge=new_store_row.get('cyclic_state_of_charge',True),
                                      state_of_charge_initial=new_store_row.get('state_of_charge_initial',0.5) * p_nom_min_val_su * new_store_row.get('max_hours',6)
                                      )
            job['log'].append("New potential storage for multi-year processed.\n")


            # Add Links (non-extendable by default in multi-year, unless specified for expansion)
            if not links_excel_df.empty:
                invertor_setting_my = get_setting('Storage Charging/Discharging', 'Anytime', df=settings_main_excel_table)
                for _, link_row in links_excel_df.iterrows():
                    link_p_max_pu_final = link_row['p_max_pu']
                    link_p_min_pu_final = link_row['p_min_pu']
                    if str(link_row['name']).startswith("invertor") and invertor_setting_my == 'Solar and Non solar hours':
                        solar_hours_start, solar_hours_end = 10, 17
                        is_solar_hour_multi = (n.snapshots.get_level_values('snapshot_time').hour >= solar_hours_start) & \
                                              (n.snapshots.get_level_values('snapshot_time').hour < solar_hours_end)
                        if link_row['type'] == 'charging link':
                            link_p_max_pu_final = np.where(is_solar_hour_multi, 1, 0).tolist()
                            link_p_min_pu_final = 0
                        else:
                            link_p_max_pu_final = np.where(is_solar_hour_multi, 0, 1).tolist()
                            link_p_min_pu_final = 0

                    n.add('Link', link_row['name'], bus0=link_row['bus0'], bus1=link_row['bus1'],
                            p_nom=link_row.get('p_nom',0), #If fixed capacity
                            p_nom_extendable=link_row.get('p_nom_extendable', False), # Typically False for basic links in multi-year unless new lines are modeled
                            efficiency=link_row['efficiency'],
                            p_max_pu=link_p_max_pu_final, p_min_pu=link_p_min_pu_final,
                            type=link_row.get('type', None),
                            # For multi-year, capital_cost needs to be annualized for the specific build_year if extendable
                            # If not extendable, capital_cost = 0 as it's existing.
                            capital_cost=link_row.get('capital_cost',0) if not link_row.get('p_nom_extendable', False) else "ANNUALIZED_COST_HERE",
                            lifetime=link_row.get('lifetime', np.inf), build_year=link_row.get('build_year', years_to_simulate[0])) # Default build_year to sim start

            job['log'].append("Links added for multi-year.\n")

            if do_generator_clustering:
                n = _apply_generator_clustering(n, p_max_pu_multi_aligned, p_min_pu_multi_aligned)
                job['log'].append("Generator clustering applied for multi-year.\n")

            if multi_year_mode == 'Only Capacity expansion on multi year':
                # Make existing generators (build_year before first sim year) non-extendable and 'fixed' for their lifetime.
                # Their p_nom is their capacity.
                # This is where the notebook logic `n.generators.loc[n.generators['lifetime'].notnull(), 'lifetime'] += 100`
                # seems to be a way to ensure they operate throughout the horizon if already built.
                # A more PyPSA-idiomatic way is to ensure their p_nom is fixed and p_nom_extendable is False.
                # The annuity cost for these would be sunk.
                job['log'].append("Adjusting for 'Only Capacity Expansion' mode.\n")
                for gen_name in n.generators.index:
                    if n.generators.loc[gen_name, 'build_year'] < years_to_simulate[0]: # Existing at start
                        n.generators.loc[gen_name, 'p_nom_extendable'] = False
                        # Lifetime is already set. If you want them to run forever in model, set lifetime to large number.


            job['log'].append("Optimizing multi-year model...\n")
            job['current_step'] = "Optimizing Multi-Year Model"
            job['progress'] = 60

            n.optimize(multi_investment_periods=True, solver_name=solver_name_opt, solver_options=solver_options_from_ui)
            job['log'].append("Multi-year optimization complete.\n")
            
            # Apply constraints (if applicable after multi-year solve)
            _apply_network_constraints(n, sheet_data['Settings'], settings_main_excel_table)

            job['log'].append(f"Exporting multi-year results to {scenario_results_dir}\n")
            job['current_step'] = "Exporting Multi-Year Results"
            job['progress'] = 90
            
            n.export_to_netcdf(str(scenario_results_dir / f"{scenario_name}_multiyear_network.nc"))
            # For multi-year, export aggregated CSVs, and then loop through periods to export yearly snapshots of components.
            n.export_to_csv_folder(str(scenario_results_dir / "multiyear_aggregated_results"))

            for period_year_export in n.investment_periods:
                period_export_dir = scenario_results_dir / f"results_{period_year_export}"
                period_export_dir.mkdir(exist_ok=True)
                
                # Extract components active in this period for CSV export
                active_gens = n.generators[
                    (n.generators.build_year <= period_year_export) & 
                    (n.generators.build_year + n.generators.lifetime > period_year_export)
                ].copy()
                if 'p_nom_opt' in n.generators.columns: # p_nom_opt is period specific in multi-year
                     active_gens['p_nom_opt_period'] = n.generators_t.p_nom_opt.loc[period_year_export, active_gens.index].values
                
                active_stores = n.stores[
                    (n.stores.build_year <= period_year_export) &
                    (n.stores.build_year + n.stores.lifetime > period_year_export)
                ].copy()
                if 'e_nom_opt' in n.stores.columns:
                     active_stores['e_nom_opt_period'] = n.stores_t.e_nom_opt.loc[period_year_export, active_stores.index].values


                active_storage_units = n.storage_units[
                    (n.storage_units.build_year <= period_year_export) &
                    (n.storage_units.build_year + n.storage_units.lifetime > period_year_export)
                ].copy()
                if 'p_nom_opt' in n.storage_units.columns:
                     active_storage_units['p_nom_opt_period'] = n.storage_units_t.p_nom_opt.loc[period_year_export, active_storage_units.index].values


                active_links = n.links[ # Assuming links might also have build_year/lifetime
                    (n.links.get('build_year', -np.inf) <= period_year_export) &
                    (n.links.get('build_year', -np.inf) + n.links.get('lifetime', np.inf) > period_year_export)
                ].copy()
                # Add p_nom_opt for links if it exists
                if 'p_nom_opt' in n.links.columns:
                    active_links['p_nom_opt_period'] = n.links_t.p_nom_opt.loc[period_year_export, active_links.index].values


                active_gens.to_csv(period_export_dir / "generators.csv")
                active_stores.to_csv(period_export_dir / "stores.csv")
                active_storage_units.to_csv(period_export_dir / "storage_units.csv")
                active_links.to_csv(period_export_dir / "links.csv")
                n.buses.to_csv(period_export_dir / "buses.csv")
                n.loads.to_csv(period_export_dir / "loads.csv")
                # Export snapshot specific data for this period
                snapshots_this_period = n.snapshots[n.snapshots.get_level_values('period') == period_year_export]
                if not snapshots_this_period.empty:
                    n.generators_t.p.loc[snapshots_this_period].to_csv(period_export_dir / "generators-p.csv")
                    n.loads_t.p_set.loc[snapshots_this_period].to_csv(period_export_dir / "loads-p_set.csv")
                    # etc. for other time-series results
                job['log'].append(f"Exported period-specific CSVs for {period_year_export}.\n")
        
        else:
            raise ValueError(f"Unknown Multi Year Investment mode: {multi_year_mode}")

        job['status'] = 'Completed'
        job['progress'] = 100
        job['log'].append(f"PyPSA Model run '{scenario_name}' finished successfully.\n")
        job['result'] = {'message': 'Model run completed.', 'output_folder': str(scenario_results_dir)}
        logger.info(f"Job {job_id} completed.")

    except Exception as e:
        job['status'] = 'Failed'
        job['error'] = str(e)
        job['log'].append(f"CRITICAL ERROR: {str(e)}\n")
        logger.error(f"Job {job_id} failed critically", exc_info=True)
    finally:
        os.chdir(original_cwd) # Change back to original CWD