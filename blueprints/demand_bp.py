from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime
import threading
import uuid
import time
from io import BytesIO # For file download

# Imports from project utils
from utils.data_loading import input_demand_data
# from utils.helpers import handle_nan_values # Assuming handle_nan_values might be more global or in its own util
from utils.plots import generate_area_chart, generate_correlation_plot # If these are used by moved routes

# Import for forecasting (ensure this path is correct relative to how models are structured)
from models.forecasting import Main_forecasting_function


demand_bp = Blueprint('demand', 
                      __name__, 
                      template_folder='../templates', 
                      static_folder='../static',
                      url_prefix='/demand')

# Global job tracking for forecasts - specific to this blueprint
forecast_jobs = {}

# Helper function from app.py (if it's best placed here)
# If handle_nan_values is used by many blueprints, it should be in a central util
def handle_nan_values(obj):
    #Convert NaN values to null for JSON serialization
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: handle_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [handle_nan_values(item) for item in obj]
    return obj

# Helper function moved from app.py
def get_forecast_data_for_sector(scenario_path, sector, from_year, to_year, unit):
    current_app.logger.debug(f"Getting forecast data for sector '{sector}' in path '{scenario_path}' via demand_bp")
    try:
        file_path = os.path.join(scenario_path, f"{sector}.xlsx")
        if not os.path.exists(file_path):
            current_app.logger.warning(f"Sector file not found: {file_path}")
            return None
        
        df = pd.read_excel(file_path, sheet_name='Results')
        if 'Year' not in df.columns:
            current_app.logger.warning(f"'Year' column missing in {file_path}")
            return None
        
        df = df[(df['Year'] >= from_year) & (df['Year'] <= to_year)]
        
        # Unit conversion logic might be needed here if 'unit' param is used
        # For now, assuming data is in the desired unit or conversion is handled elsewhere
        
        return df
    except Exception as e:
        current_app.logger.exception(f"Error getting forecast data for sector {sector} via demand_bp: {e}")
        return None

# Worker function moved from app.py
def run_multiple_forecasts_job(job_id, project_path, data_payload): # Renamed 'data' to 'data_payload'
    current_app.logger.info(f"Starting forecast job {job_id} for project {project_path} via demand_bp")
    job = forecast_jobs[job_id] # Use blueprint-specific job tracking
    job['status'] = 'running'
    
    try:
        scenario_name = data_payload.get('scenarioName')
        target_year = int(data_payload.get('targetYear'))
        exclude_covid = data_payload.get('excludeCovidYears', True)
        sector_configs = data_payload.get('sectorConfigs', {})
        
        current_app.logger.info(f"Job {job_id} config: scenario={scenario_name}, target_year={target_year}, exclude_covid={exclude_covid}, sectors={list(sector_configs.keys())}")
        job['progress'] = 5
        
        demand_input_file_path = f"{project_path}/inputs/input_demand_file.xlsx"
        current_app.logger.debug(f"Loading input data from {demand_input_file_path}")
        
        try:
            # Assuming input_demand_data is correctly imported
            sectors, _, param_dict, sector_data_map, _ = input_demand_data(demand_input_file_path) # Renamed sector_data
        except Exception as e:
            current_app.logger.exception(f"Error loading input data: {e}")
            job['status'] = 'failed'
            job['error'] = f"Failed to load input data: {str(e)}"
            return
        
        start_year = int(param_dict.get('Start_Year', 2006))
        
        for sector_name_key in sector_configs.keys(): # Renamed sector
            if sector_name_key not in sector_data_map:
                current_app.logger.warning(f"Sector {sector_name_key} not found in input data, skipping")
                job['error'] = f"Sector {sector_name_key} not found in input data"
                job['status'] = 'failed'
                return
        
        forecast_dir = f"{project_path}/results/demand_projection/{scenario_name}"
        os.makedirs(forecast_dir, exist_ok=True)
        
        # Main_forecasting_function is imported
        
        sectors_using_existing_data = []
        sectors_forecasted = []
        sectors_with_errors = []
        total_sectors_to_process = len(sector_configs) # Renamed
        
        for idx, (sector_name_key, config) in enumerate(sector_configs.items()):
            if forecast_jobs[job_id]['status'] == 'cancelled':
                current_app.logger.info(f"Job {job_id} was cancelled, stopping processing")
                return
            
            job['currentSector'] = sector_name_key
            job['processedSectors'] = idx
            progress_per_sector = 90 / max(1, total_sectors_to_process)
            current_progress = 5 + int(idx * progress_per_sector)
            job['progress'] = current_progress
            current_app.logger.info(f"Processing sector {sector_name_key} ({idx+1}/{total_sectors_to_process}), progress: {current_progress}%")
            
            try:
                selected_models = config.get('models', ['MLR', 'SLR', 'WAM', 'TimeSeries'])
                base_params = {'target_year': target_year, 'exclude_covid': exclude_covid}
                model_params_config = {} # Renamed
                if 'MLR' in selected_models:
                    independent_vars = config.get('independentVars', [])
                    model_params_config['MLR'] = {'independent_vars': independent_vars}
                if 'WAM' in selected_models:
                    window_size = int(config.get('windowSize', 10))
                    model_params_config['WAM'] = {'window_size': window_size}
                
                if sector_name_key not in sector_data_map:
                    current_app.logger.error(f"Sector {sector_name_key} not in input data, skipping")
                    sectors_with_errors.append(sector_name_key)
                    continue
                
                result = Main_forecasting_function(
                    sector_name_key, 
                    forecast_dir, 
                    sector_data_map[sector_name_key],
                    selected_models=selected_models,
                    model_params=model_params_config,
                    **base_params
                )
                
                if result.get('used_existing_data', False):
                    sectors_using_existing_data.append(sector_name_key)
                else:
                    sectors_forecasted.append(sector_name_key)
            except Exception as e:
                current_app.logger.exception(f"Error processing sector {sector_name_key}: {str(e)}")
                sectors_with_errors.append(sector_name_key)
                continue
            
            job['progress'] = 5 + int((idx + 1) * progress_per_sector)
            job['processedSectors'] = idx + 1
            if forecast_jobs[job_id]['status'] == 'cancelled':
                current_app.logger.info(f"Job {job_id} was cancelled after processing {sector_name_key}")
                return
        
        summary_content = { # Renamed
            'scenario': scenario_name, 'target_year': target_year, 'start_year': start_year,
            'sectors': list(sector_configs.keys()),
            'sectors_with_complete_data': sectors_using_existing_data,
            'sectors_forecasted': sectors_forecasted,
            'sectors_with_errors': sectors_with_errors,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'exclude_covid': exclude_covid,
            'models_used': {s_key: cfg.get('models', ['MLR', 'SLR', 'WAM', 'TimeSeries']) 
                           for s_key, cfg in sector_configs.items()}
        }
        with open(f"{forecast_dir}/summary.json", 'w') as f:
            json.dump(summary_content, f, indent=4)
        
        job['status'] = 'completed'
        job['progress'] = 100
        job['result'] = {
            'scenarioName': scenario_name, 'targetYear': target_year,
            'totalSectors': len(sector_configs),
            'sectorsWithCompleteData': len(sectors_using_existing_data),
            'sectorsForecasted': len(sectors_forecasted),
            'sectorsWithErrors': len(sectors_with_errors),
            'filePath': forecast_dir
        }
        current_app.logger.info(f"Forecast job {job_id} completed successfully via demand_bp")
    except Exception as e:
        current_app.logger.exception(f"Error in forecast job {job_id} (demand_bp): {str(e)}")
        job['status'] = 'failed'
        job['error'] = str(e)

# Routes
@demand_bp.route('/projection') # Changed from /demand_projection
def demand_projection_route(): # Renamed
    current_app.logger.info("Accessing demand_projection route via demand_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        current_app.logger.warning("No project selected for demand_projection")
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('core.home')) # To core blueprint
    
    demand_input_file_path = f"{current_app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    current_app.logger.debug(f"Looking for input file at {demand_input_file_path}")
    
    if not os.path.exists(demand_input_file_path):
        current_app.logger.warning(f"Input demand file not found at {demand_input_file_path}")
        flash('Input demand file not found. Please upload it first.', 'warning')
        return redirect(url_for('core.home'))
    
    try:
        current_app.logger.debug("Loading input demand data for demand_bp")
        # input_demand_data is imported from utils.data_loading
        sectors, missing_sectors, param_dict, sector_data_map, aggregated_ele = input_demand_data(demand_input_file_path) # Renamed sector_data
        
        # Storing start/end year in app.config might be problematic with blueprints if not careful
        # Consider passing them or accessing param_dict directly in templates/other functions
        # For now, replicating app.py logic:
        current_app.config['START_YEAR'] = param_dict.get('Start_Year')
        current_app.config['END_YEAR'] = param_dict.get('End_Year')

        if not sectors:
            current_app.logger.warning("No sectors found in the input file")
            flash('No sectors found in the input file.', 'warning')
            return redirect(url_for('core.home'))
        
        sector_tables = {}
        for sector_name_key, df_sector in sector_data_map.items(): # Renamed
            sector_tables[sector_name_key] = df_sector.to_html(classes='table table-striped table-hover', index=False)
        aggregated_table = aggregated_ele.to_html(classes='table table-striped table-hover', index=False)
        
        current_app.logger.info("Successfully prepared demand projection data via demand_bp")
        return render_template('demand_projection.html',
                               sectors=sectors,
                               missing_sectors=missing_sectors,
                               param_dict=param_dict,
                               sector_tables=sector_tables,
                               aggregated_table=aggregated_table,
                               chart_data={'sectors': sectors}) # Minimal initial data like in app.py
    except Exception as e:
        current_app.logger.exception(f"Error processing demand projection via demand_bp: {e}")
        flash(f'Error processing demand projection: {str(e)}', 'danger')
        return redirect(url_for('core.home'))

@demand_bp.route('/visualization') # Changed from /demand_visualization
def demand_visualization_route(): # Renamed
    current_app.logger.info("Accessing demand_visualization route via demand_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('core.home'))
    try:
        scenarios_path = os.path.join(current_app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection')
        if not os.path.exists(scenarios_path):
            flash('No forecast scenarios found. Please run forecasts first.', 'warning')
            return redirect(url_for('demand.demand_projection_route')) # To this blueprint's route

        scenarios = [d for d in os.listdir(scenarios_path) if os.path.isdir(os.path.join(scenarios_path, d))]
        if not scenarios:
            flash('No forecast scenarios found. Please run forecasts first.', 'warning')
            return redirect(url_for('demand.demand_projection_route'))

        selected_scenario = request.args.get('scenario', scenarios[0])
        sectors_list = [] # Renamed
        start_year_val = 2025 # Renamed
        end_year_val = 2037 # Renamed
        
        scenario_folder_path = os.path.join(scenarios_path, selected_scenario) # Renamed
        sector_files = [f for f in os.listdir(scenario_folder_path) if f.endswith('.xlsx') and not f.startswith('_')]
        
        if sector_files:
            sectors_list = [os.path.splitext(f)[0] for f in sector_files if not os.path.splitext(f)[0].lower() in ['summary', 'consolidated']]
            all_years = []
            for file_item in sector_files: # Renamed
                file_path_item = os.path.join(scenario_folder_path, file_item) # Renamed
                try:
                    xls = pd.ExcelFile(file_path_item)
                    for sheet_name in xls.sheet_names: # Renamed
                        try:
                            df_sheet = pd.read_excel(file_path_item, sheet_name=sheet_name) # Renamed
                            if 'Year' in df_sheet.columns:
                                valid_years = df_sheet['Year'].dropna().apply(lambda x: int(x) if pd.api.types.is_numeric_dtype(type(x)) and not pd.isna(x) else None)
                                valid_years = valid_years[valid_years.notnull()]
                                if not valid_years.empty:
                                    all_years.extend(valid_years.tolist())
                        except Exception as e_sheet: # Renamed
                            current_app.logger.warning(f"Could not read sheet {sheet_name} from {file_item}: {str(e_sheet)}")
                except Exception as e_file: # Renamed
                    current_app.logger.error(f"Error accessing {file_item}: {str(e_file)}")
            
            if all_years:
                start_year_val = int(min(all_years))
                end_year_val = int(max(all_years))
        
        if start_year_val > end_year_val: start_year_val, end_year_val = end_year_val, start_year_val
        if not sectors_list:
            flash('No valid sector data found for this scenario.', 'warning')
            return redirect(url_for('demand.demand_projection_route'))
        
        return render_template('demand_visualization.html',
                               scenarios=scenarios, selected_scenario=selected_scenario,
                               sectors=sectors_list, start_year=start_year_val, end_year=end_year_val,
                               current_project=current_app.config.get('CURRENT_PROJECT'))
    except Exception as e:
        current_app.logger.exception(f"Error loading demand visualization via demand_bp: {e}")
        flash(f'Error loading demand visualization: {str(e)}', 'danger')
        return redirect(url_for('core.home'))

# API Routes
@demand_bp.route('/api/independent_variables/<sector>')
def get_independent_variables_api(sector): # Renamed
    # ... (Logic from app.py, using current_app.logger, current_app.config)
    # Ensure input_demand_data is used correctly
    current_app.logger.info(f"Processing API request for independent_variables/{sector} via demand_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    demand_input_file_path = f"{current_app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    try:
        _, _, _, sector_data_map, _ = input_demand_data(demand_input_file_path)
        if sector not in sector_data_map:
            return jsonify({'status': 'error', 'message': f'Sector {sector} not found'})
        df = sector_data_map[sector]
        variables = df.columns.tolist()
        correlations = {}
        if 'Electricity' in df.select_dtypes(include=['number']).columns:
            for var in variables:
                if var != 'Electricity' and var in df.select_dtypes(include=['number']).columns:
                    correlations[var] = df[var].corr(df['Electricity'])
        return jsonify({'status': 'success', 'variables': variables, 'correlations': handle_nan_values(correlations)})
    except Exception as e:
        current_app.logger.exception(f"Error fetching variables for {sector} via demand_bp: {e}")
        return jsonify({'status': 'error', 'message': f'Error fetching variables: {str(e)}'})

@demand_bp.route('/api/correlation_data/<sector>')
def get_correlation_data_api(sector): # Renamed
    # ... (Logic from app.py, using current_app.logger, current_app.config)
    current_app.logger.info(f"Processing API request for correlation_data/{sector} via demand_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    demand_input_file_path = f"{current_app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    try:
        _, _, _, sector_data_map, aggregated_ele_df = input_demand_data(demand_input_file_path) # Renamed
        df_corr = aggregated_ele_df if sector == 'aggregated' else sector_data_map.get(sector) # Renamed
        if df_corr is None:
            return jsonify({'status': 'error', 'message': f'Sector {sector} not found'})
        
        numeric_df = df_corr.select_dtypes(include=['number'])
        if 'Electricity' not in numeric_df.columns:
            return jsonify({'status': 'success', 'data': {'variables': [], 'correlations': []}})
        
        corr_matrix = numeric_df.corr()
        elec_corr = corr_matrix['Electricity'].drop('Electricity')
        variables = []
        correlations = []
        for var, corr_value in elec_corr.items():
            if pd.isna(corr_value): continue
            corr_abs = abs(corr_value)
            strength = "Strong" if corr_abs >= 0.7 else "Moderate" if corr_abs >= 0.4 else "Weak"
            variables.append(var)
            correlations.append({'value': round(float(corr_value), 2), 'strength': strength})
        
        combined = sorted(list(zip(variables, correlations)), key=lambda x: abs(x[1]['value']), reverse=True)
        sorted_variables = [item[0] for item in combined]
        sorted_correlations = [item[1] for item in combined]
        return jsonify({'status': 'success', 'data': {'variables': sorted_variables, 'correlations': handle_nan_values(sorted_correlations)}})
    except Exception as e:
        current_app.logger.exception(f"Error calculating correlation for {sector} via demand_bp: {e}")
        return jsonify({'status': 'error', 'message': f'Error calculating correlation: {str(e)}'})

@demand_bp.route('/api/chart_data/<sector>')
def get_chart_data_api(sector): # Renamed
    # ... (Logic from app.py, using current_app.logger, current_app.config)
    current_app.logger.info(f"Processing API request for chart_data/{sector} via demand_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    demand_input_file_path = f"{current_app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    try:
        sectors_list_all, _, param_dict_chart, sector_data_map_chart, aggregated_ele_chart = input_demand_data(demand_input_file_path) # Renamed vars
        target_year_chart = int(param_dict_chart.get('End_Year', 2037)) # Renamed
        start_year_chart = int(param_dict_chart.get('Start_Year', 2006)) # Renamed

        # Apply handle_nan_values to relevant dataframes
        aggregated_ele_chart = aggregated_ele_chart.apply(lambda x: x.map(handle_nan_values) if x.dtype == object else x)


        chart_data_resp = {} # Renamed
        if sector == 'aggregated':
            years_agg = aggregated_ele_chart['Year'].tolist() # Renamed
            datasets_agg = [] # Renamed
            for i, s_agg in enumerate(sectors_list_all): # Renamed
                if s_agg in aggregated_ele_chart.columns:
                    r, g, b = (i * 50) % 255, (i * 100) % 255, (i * 150) % 255
                    sector_values_agg = [float(v) if v is not None and not np.isnan(v) else 0 for v in aggregated_ele_chart[s_agg].tolist()] # Renamed
                    datasets_agg.append({
                        'label': s_agg, 'data': sector_values_agg,
                        'backgroundColor': f'rgba({r}, {g}, {b}, 0.7)', 'borderColor': f'rgba({r}, {g}, {b}, 1)'})
            chart_data_resp = {'years': years_agg, 'datasets': datasets_agg}
        else:
            if sector not in sector_data_map_chart:
                return jsonify({'status': 'error', 'message': f'Sector {sector} not found'}), 404
            df_sector_chart = sector_data_map_chart[sector].copy() # Renamed
            df_sector_chart = df_sector_chart.apply(lambda x: x.map(handle_nan_values) if x.dtype == object else x)


            has_complete_data = False
            max_year_data = 0 # Renamed
            if 'Year' in df_sector_chart.columns and 'Electricity' in df_sector_chart.columns:
                valid_data_points = [(y, e) for y, e in zip(df_sector_chart['Year'], df_sector_chart['Electricity']) if e is not None and not np.isnan(e)] # Renamed
                if valid_data_points:
                    max_year_data = max(y for y, _ in valid_data_points)
                    has_complete_data = max_year_data >= target_year_chart
            chart_data_resp = {
                'years': df_sector_chart['Year'].tolist() if 'Year' in df_sector_chart.columns else [],
                'electricity': df_sector_chart['Electricity'].tolist() if 'Electricity' in df_sector_chart.columns else [],
                'hasCompleteData': has_complete_data, 'maxYear': max_year_data,
                'targetYear': target_year_chart, 'startYear': start_year_chart}
        return jsonify({'status': 'success', 'data': handle_nan_values(chart_data_resp)})
    except Exception as e:
        current_app.logger.exception(f"Error fetching chart data for {sector} via demand_bp: {e}")
        return jsonify({'status': 'error', 'message': f'Error fetching chart data: {str(e)}'})

@demand_bp.route('/api/forecast_data/<scenario>')
def get_forecast_data_api(scenario): # Renamed

    current_app.logger.info(f"Processing API request for forecast_data/{scenario} via demand_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    try:
        scenario_path_api = os.path.join(current_app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection', scenario) # Renamed
        if not os.path.exists(scenario_path_api):
            return jsonify({'status': 'error', 'message': f'Scenario {scenario} not found'})
        
        sector_files_api = [f for f in os.listdir(scenario_path_api) if f.endswith('.xlsx') and not f.startswith('_')] # Renamed
        if not sector_files_api:
            return jsonify({'status': 'error', 'message': 'No sector data found for this scenario'})
        
        sector_data_resp = {} # Renamed
        for file_api in sector_files_api: # Renamed
            sector_name_api = os.path.splitext(file_api)[0] # Renamed
            if sector_name_api.lower() in ['summary', 'consolidated']: continue
            file_path_api = os.path.join(scenario_path_api, file_api) # Renamed
            try:
                df_api = pd.read_excel(file_path_api, sheet_name='Results') # Renamed
                if 'Year' not in df_api.columns: continue
                years_api = df_api['Year'].dropna().apply(lambda x: int(x) if pd.api.types.is_numeric_dtype(type(x)) and not pd.isna(x) else None).filter(pd.notna).tolist() # Renamed
                model_data_api = {} # Renamed
                models_list_api = [col for col in df_api.columns if col != 'Year'] # Renamed
                for col_api in models_list_api: # Renamed
                    model_data_api[col_api] = [None if pd.isna(v) else float(v) for v in df_api[col_api].tolist()]
                sector_data_resp[sector_name_api] = {'years': years_api, 'models': models_list_api, **model_data_api}
            except Exception as e_file_api: # Renamed
                current_app.logger.error(f"Error processing {file_api}: {str(e_file_api)}")
        
        if not sector_data_resp:
            return jsonify({'status': 'error', 'message': 'Could not process any sector data'})
        return jsonify({'status': 'success', 'data': handle_nan_values(sector_data_resp)})
    except Exception as e:
        current_app.logger.exception(f"Error fetching forecast data for {scenario} via demand_bp: {e}")
        return jsonify({'status': 'error', 'message': f'Error fetching forecast data: {str(e)}'})

@demand_bp.route('/api/run_forecast', methods=['POST'])
def run_forecast_api(): # Renamed
    # ... (Logic from app.py, using current_app.logger, current_app.config, and blueprint's forecast_jobs)
    current_app.logger.info("Processing API request to run_forecast via demand_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    data_req = request.get_json() # Renamed
    if not data_req:
        return jsonify({'status': 'error', 'message': 'No data provided'})
    
    scenario_name_req = data_req.get('scenarioName') # Renamed
    sector_configs_req = data_req.get('sectorConfigs', {}) # Renamed
    if not scenario_name_req or not data_req.get('targetYear') or not sector_configs_req:
        return jsonify({'status': 'error', 'message': 'Missing required parameters'})
    
    job_id_req = str(uuid.uuid4()) # Renamed
    forecast_jobs[job_id_req] = { # Use BP's forecast_jobs
        'status': 'starting', 'progress': 0, 'currentSector': None,
        'processedSectors': 0, 'totalSectors': len(sector_configs_req),
        'scenarioName': scenario_name_req, 'targetYear': data_req.get('targetYear'),
        'excludeCovidYears': data_req.get('excludeCovidYears', True),
        'start_time': time.time(), 'result': None, 'error': None}
    
    forecast_thread = threading.Thread(target=run_multiple_forecasts_job, 
                                     args=(job_id_req, current_app.config['CURRENT_PROJECT_PATH'], data_req))
    forecast_thread.daemon = True
    forecast_thread.start()
    return jsonify({'status': 'started', 'jobId': job_id_req, 
                    'message': f'Forecast job started for {len(sector_configs_req)} sectors using scenario {scenario_name_req}'})

@demand_bp.route('/api/forecast_status/<job_id>')
def get_forecast_status_api(job_id): # Renamed
    # ... (Logic from app.py, using blueprint's forecast_jobs)
    current_app.logger.info(f"Processing API request for forecast_status/{job_id} via demand_bp")
    if job_id not in forecast_jobs: # Use BP's forecast_jobs
        return jsonify({'status': 'error', 'message': 'Job not found'})
    job_details = forecast_jobs[job_id] # Renamed
    return jsonify({'status': job_details['status'], 'progress': job_details['progress'], 
                    'currentSector': job_details['currentSector'], 
                    'result': job_details['result'] if job_details['status'] == 'completed' else None, 
                    'error': job_details['error'] if job_details['status'] == 'failed' else None})

@demand_bp.route('/api/cancel_forecast/<job_id>', methods=['POST'])
def cancel_forecast_api(job_id): # Renamed
    # ... (Logic from app.py, using blueprint's forecast_jobs)
    current_app.logger.info(f"Processing API request to cancel_forecast/{job_id} via demand_bp")
    if job_id not in forecast_jobs: # Use BP's forecast_jobs
        return jsonify({'status': 'error', 'message': 'Job not found'})
    job_to_cancel = forecast_jobs[job_id] # Renamed
    if job_to_cancel['status'] in ['completed', 'failed', 'cancelled']:
        return jsonify({'status': 'error', 'message': f'Job already {job_to_cancel["status"]}'})
    job_to_cancel['status'] = 'cancelled'
    return jsonify({'status': 'cancelled', 'message': 'Forecast job cancelled'})

@demand_bp.route('/api/scenario_details/<scenario_name>')
def get_scenario_details_api(scenario_name): # Renamed
    # ... (Logic from app.py, using current_app.logger, current_app.config)
    current_app.logger.info(f"Processing API request for scenario_details/{scenario_name} via demand_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    try:
        scenario_folder_api = os.path.join(current_app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection', scenario_name) # Renamed
        if not os.path.exists(scenario_folder_api):
            return jsonify({'status': 'error', 'message': f'Scenario {scenario_name} not found'})
        
        sectors_in_scenario = [] # Renamed
        target_year_meta = 2037 # Renamed
        for filename_meta in os.listdir(scenario_folder_api): # Renamed
            if filename_meta.endswith('.xlsx') and filename_meta != 'aggregated.xlsx':
                sectors_in_scenario.append(filename_meta.replace('.xlsx', ''))
        
        metadata_path_api = os.path.join(scenario_folder_api, 'metadata.json') # Renamed
        if os.path.exists(metadata_path_api):
            with open(metadata_path_api, 'r') as f_meta: # Renamed
                metadata_content = json.load(f_meta) # Renamed
                target_year_meta = metadata_content.get('target_year', 2037)
        else: # Fallback to summary.json
            summary_path_api = os.path.join(scenario_folder_api, 'summary.json') # Renamed
            if os.path.exists(summary_path_api):
                with open(summary_path_api, 'r') as f_summary: # Renamed
                    summary_content_api = json.load(f_summary) # Renamed
                    target_year_meta = summary_content_api.get('target_year', 2037)
        
        return jsonify({'status': 'success', 'scenario_name': scenario_name, 
                        'sectors': sectors_in_scenario, 'target_year': target_year_meta})
    except Exception as e:
        current_app.logger.exception(f"Error processing scenario details for {scenario_name} via demand_bp: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'})

@demand_bp.route('/api/download_comparison_data', methods=['POST'])
def download_comparison_data_api(): # Renamed
    # ... (Logic from app.py, using current_app.logger, current_app.config, and get_forecast_data_for_sector from this BP)
    current_app.logger.info("Processing API request for download_comparison_data via demand_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        return jsonify({"status": "error", "message": "No project loaded."}), 400
    
    data_comp = request.get_json() # Renamed
    scenarios_comp = data_comp.get('scenarios', []) # Renamed
    from_year_comp = int(data_comp.get('fromYear', datetime.now().year - 5)) # Renamed
    to_year_comp = int(data_comp.get('toYear', datetime.now().year + 10)) # Renamed
    unit_comp = data_comp.get('unit', 'TWh') # Renamed
    sector_model_map_comp = data_comp.get('sectorModelMap', {}) # Renamed

    if len(scenarios_comp) < 2:
        return jsonify({"status": "error", "message": "At least two scenarios are required for comparison."}), 400

    consolidated_dfs_comp = [] # Renamed
    for scenario_name_comp in scenarios_comp: # Renamed
        scenario_path_comp = os.path.join(current_app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection', scenario_name_comp) # Renamed
        all_sector_dfs_comp = [] # Renamed
        years_df_comp = pd.DataFrame({'Year': range(from_year_comp, to_year_comp + 1)}) # Renamed

        for sector_comp, model_choice_comp in sector_model_map_comp.items(): # Renamed vars
            # Use the blueprint's get_forecast_data_for_sector
            sector_full_df_comp = get_forecast_data_for_sector(scenario_path_comp, sector_comp, from_year_comp, to_year_comp, unit_comp)
            if sector_full_df_comp is not None and not sector_full_df_comp.empty:
                col_to_use_comp = None # Renamed
                if model_choice_comp in sector_full_df_comp.columns:
                    col_to_use_comp = model_choice_comp
                elif 'Historical' == model_choice_comp and 'Historical' in sector_full_df_comp.columns:
                     col_to_use_comp = 'Historical'
                
                if col_to_use_comp:
                    new_col_name_comp = f"{scenario_name_comp}_{sector_comp}" # Renamed
                    sector_model_data_comp = sector_full_df_comp[['Year', col_to_use_comp]].rename(columns={col_to_use_comp: new_col_name_comp}).copy() # Renamed
                    all_sector_dfs_comp.append(sector_model_data_comp)
        
        if not all_sector_dfs_comp: continue
        scenario_df_comp = years_df_comp.copy() # Renamed
        for df_to_merge_comp in all_sector_dfs_comp: # Renamed
            scenario_df_comp = pd.merge(scenario_df_comp, df_to_merge_comp, on='Year', how='left')
        
        sector_cols_comp = [col for col in scenario_df_comp.columns if col.startswith(f"{scenario_name_comp}_")] # Renamed
        if sector_cols_comp:
            scenario_df_comp[f"{scenario_name_comp}_Total"] = scenario_df_comp[sector_cols_comp].sum(axis=1, skipna=True, min_count=1)
        consolidated_dfs_comp.append(scenario_df_comp)

    if not consolidated_dfs_comp:
        return jsonify({"status": "error", "message": "No data found for selected scenarios."}), 404

    comparison_df_final = consolidated_dfs_comp[0] # Renamed
    for i in range(1, len(consolidated_dfs_comp)):
        cols_to_use_merge = [col for col in consolidated_dfs_comp[i].columns if col != 'Year'] # Renamed
        comparison_df_final = pd.merge(comparison_df_final, consolidated_dfs_comp[i][['Year'] + cols_to_use_merge], on='Year', how='outer')
    
    comparison_df_final = comparison_df_final.fillna(0)
    output_buffer = BytesIO() # Renamed
    comparison_df_final.to_csv(output_buffer, index=False, encoding='utf-8')
    output_buffer.seek(0)
    
    download_filename_comp = f"scenario_comparison_{scenarios_comp[0]}_vs_{scenarios_comp[1]}_{unit_comp}_{from_year_comp}-{to_year_comp}.csv" # Renamed
    return send_file(output_buffer, mimetype='text/csv', as_attachment=True, download_name=download_filename_comp)

@demand_bp.route('/api/save_consolidated_data/<scenario>', methods=['GET'])
def save_consolidated_data_api(scenario): # Renamed
    # ... (Logic from app.py, using current_app.logger, current_app.config, and get_forecast_data_for_sector from this BP)
    current_app.logger.info(f"Processing API request to save consolidated data for scenario {scenario} via demand_bp")
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'})
    try:
        unit_save = request.args.get('unit', 'kWh') # Renamed
        from_year_save = int(request.args.get('from_year', datetime.now().year - 5)) # Renamed
        to_year_save = int(request.args.get('to_year', datetime.now().year + 10)) # Renamed
        model_params_save = {} # Renamed
        for param_key, value_save in request.args.items(): # Renamed vars
            if param_key.startswith('model_'):
                sector_save = param_key.replace('model_', '') # Renamed
                model_params_save[sector_save] = value_save
        
        scenario_path_save = os.path.join(current_app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection', scenario) # Renamed
        if not os.path.exists(scenario_path_save):
            return jsonify({'status': 'error', 'message': f'Scenario {scenario} not found'})
        
        df_save = pd.DataFrame({'Year': range(from_year_save, to_year_save + 1)}) # Renamed
        for sector_iter, model_iter in model_params_save.items(): # Renamed vars
            # Use blueprint's get_forecast_data_for_sector
            sector_df_save = get_forecast_data_for_sector(scenario_path_save, sector_iter, from_year_save, to_year_save, unit_save)
            if sector_df_save is not None and not sector_df_save.empty and model_iter in sector_df_save.columns:
                sector_data_to_merge = sector_df_save[['Year', model_iter]].rename(columns={model_iter: sector_iter}) # Renamed
                df_save = df_save.merge(sector_data_to_merge, on='Year', how='left')
        
        sector_columns_save = [col for col in df_save.columns if col != 'Year'] # Renamed
        if sector_columns_save:
            df_save['Total'] = df_save[sector_columns_save].sum(axis=1)
            file_path_save = os.path.join(scenario_path_save, 'consolidated_results.csv') # Renamed
            df_save.to_csv(file_path_save, index=False)
            return jsonify({'status': 'success', 'message': 'Consolidated data saved successfully', 'file_path': file_path_save})
        else:
            return jsonify({'status': 'error', 'message': 'No sector data found'})
    except Exception as e:
        current_app.logger.exception(f"Error saving consolidated data via demand_bp: {e}")
        return jsonify({'status': 'error', 'message': f'Error saving consolidated data: {str(e)}'})
