# from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
# import os
# import shutil
# from datetime import datetime
# import uuid
# from werkzeug.utils import secure_filename
# import pandas as pd
# import json
# import traceback # Added for better error reporting
# # Import helper functions
# from utils.data_loading import input_demand_data
# from utils.helpers import create_project_structure, validate_project_structure, copy_missing_templates, extract_tables_by_markers
# from utils.plots import generate_area_chart, generate_correlation_plot
# # Import necessary modules
# import threading
# import uuid
# import time
# import json
# from flask import jsonify, request, session
# import numpy as np
# from datetime import datetime
# # Initialize Flask app
# app = Flask(__name__)
# app.secret_key = 'energy_demand_forecasting_secret_key'  # Change in production

# # Configuration
# app.config['UPLOAD_FOLDER'] = 'static/user_uploads'
# app.config['TEMPLATE_FOLDER'] = 'static/templates'
# app.config['ALLOWED_EXTENSIONS'] = {'xlsx'}
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
# app.config['CURRENT_PROJECT'] = None
# app.config['CURRENT_PROJECT_PATH'] = None

# # Ensure upload folders exist
# os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# os.makedirs(app.config['TEMPLATE_FOLDER'], exist_ok=True)
# recent_projects_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'recent_projects')
# os.makedirs(recent_projects_dir, exist_ok=True)
# forecast_jobs = {}


# def save_recent_project(user_id, project_name, project_path):
#     """Save project to recent projects list"""
#     try:
#         # Filename based on user ID
#         filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        
#         # Load existing data or create new
#         if os.path.exists(filename):
#             with open(filename, 'r') as f:
#                 recent_projects = json.load(f)
#         else:
#             recent_projects = []
        
#         # Check if project already exists
#         existing_index = None
#         for i, project in enumerate(recent_projects):
#             if project.get('path') == project_path:
#                 existing_index = i
#                 break
        
#         # Remove if exists
#         if existing_index is not None:
#             recent_projects.pop(existing_index)
        
#         # Add to the beginning
#         recent_projects.insert(0, {
#             'name': project_name,
#             'path': project_path,
#             'last_opened': datetime.now().isoformat(),
#             'timestamp': int(datetime.now().timestamp())
#         })
        
#         # Keep only most recent 10 projects
#         recent_projects = recent_projects[:10]
        
#         # Save back to file
#         with open(filename, 'w') as f:
#             json.dump(recent_projects, f, indent=4)
        
#         return True
#     except Exception as e:
#         print(f"Error saving recent project: {e}")
#         return False

# # Add this endpoint to get recent projects
# @app.route('/api/recent_projects', methods=['GET'])
# def api_recent_projects():
#     user_id = session.get('user_id', 'default_user')
#     try:
#         filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        
#         if not os.path.exists(filename):
#             print(f"Recent projects file not found for user {user_id}")
#             return jsonify({'recent_projects': []})
        
#         with open(filename, 'r') as f:
#             recent_projects = json.load(f)
        
#         print(f"Loaded {len(recent_projects)} recent projects for user {user_id}")
#         return jsonify({'recent_projects': recent_projects})
#     except Exception as e:
#         print(f"Error reading recent projects: {e}")
#         return jsonify({'recent_projects': [], 'error': str(e)})
# @app.route('/api/delete_recent_project', methods=['POST'])
# def api_delete_recent_project():
#     """Delete a project from the recent projects list"""
#     user_id = session.get('user_id', 'default_user')
    
#     try:
#         # Get project path from request
#         data = request.get_json()
#         if not data or 'projectPath' not in data:
#             return jsonify({
#                 'status': 'error',
#                 'message': 'Project path not provided'
#             })
        
#         project_path = data['projectPath']
        
#         # Read existing projects
#         filename = os.path.join(recent_projects_dir, f"{user_id}.json")
#         if not os.path.exists(filename):
#             return jsonify({
#                 'status': 'error',
#                 'message': 'Recent projects file not found'
#             })
        
#         with open(filename, 'r') as f:
#             recent_projects = json.load(f)
        
#         # Find and remove the project
#         found = False
#         for i, project in enumerate(recent_projects):
#             if project.get('path') == project_path:
#                 recent_projects.pop(i)
#                 found = True
#                 break
        
#         if not found:
#             return jsonify({
#                 'status': 'error',
#                 'message': 'Project not found in recent projects'
#             })
        
#         # Save the updated list
#         with open(filename, 'w') as f:
#             json.dump(recent_projects, f, indent=4)
        
#         print(f"Removed project {project_path} from recent projects for user {user_id}")
        
#         return jsonify({
#             'status': 'success',
#             'message': 'Project removed from recent projects'
#         })
    
#     except Exception as e:
#         print(f"Error removing project from recent projects: {e}")
#         import traceback
#         traceback.print_exc()
        
#         return jsonify({
#             'status': 'error',
#             'message': f'Error: {str(e)}'
#         })
# # Helper functions
# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# def get_recent_activities():
#     activities = [
#         {
#             'icon': 'fas fa-chart-line',
#             'title': 'Created forecast for "Energy Scenario 2025"',
#             'time': '2 hours ago',
#             'link': url_for('demand_visualization')
#         },
#         {
#             'icon': 'fas fa-upload',
#             'title': 'Uploaded data for "Regional Analysis"',
#             'time': 'Yesterday',
#             'link': '#'
#         },
#         {
#             'icon': 'fas fa-cogs',
#             'title': 'Ran PyPSA model for "Renewable Integration"',
#             'time': '3 days ago',
#             'link': url_for('modeling_results')
#         }
#     ]
#     return activities

# def create_template_files():
#     pass
# # Add to app.py - Helper function for checking feature usage in templates
# @app.context_processor
# def utility_processor():
#     def is_used(feature_id):
#         # In a real implementation, this would check the database or session
#         # For demo, return True for specific features
#         return feature_id in ['demand-projection', 'load-curve']
#     return dict(is_used=is_used)
# @app.route('/api/independent_variables/<sector>', methods=['GET'])
# def get_independent_variables(sector):
#     """
#     Get available independent variables for the sector with correlation data
#     """
#     if app.config['CURRENT_PROJECT_PATH'] is None:
#         return jsonify({'status': 'error', 'message': 'No project selected'})
    
#     demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
#     if not os.path.exists(demand_input_file_path):
#         return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    
#     try:
#         # Get sector data
#         sectors, _, _, sector_data, _ = input_demand_data(demand_input_file_path)
        
#         if sector not in sector_data:
#             return jsonify({'status': 'error', 'message': f'Sector {sector} not found'})
        
#         # Get the variables for this sector
#         df = sector_data[sector]
#         variables = df.columns.tolist()
        
#         # Calculate correlations with Electricity
#         correlations = {}
#         for var in variables:
#             if var != 'Electricity' and var in df.select_dtypes(include=['number']).columns:
#                 correlations[var] = df[var].corr(df['Electricity'])
        
#         return jsonify({
#             'status': 'success',
#             'variables': variables,
#             'correlations': correlations
#         })
#     except Exception as e:
#         return jsonify({'status': 'error', 'message': f'Error fetching variables: {str(e)}'})

# @app.route('/api/run_forecast', methods=['POST'])
# def run_forecast():
#     """
#     Start a forecast job for all sectors
#     """
#     if app.config['CURRENT_PROJECT_PATH'] is None:
#         return jsonify({'status': 'error', 'message': 'No project selected'})
    
#     # Get request data
#     data = request.get_json()
#     if not data:
#         return jsonify({'status': 'error', 'message': 'No data provided'})
    
#     scenario_name = data.get('scenarioName')
#     target_year = data.get('targetYear')
#     exclude_covid_years = data.get('excludeCovidYears', True)
#     sector_configs = data.get('sectorConfigs', {})
    
#     if not scenario_name or not target_year or not sector_configs:
#         return jsonify({'status': 'error', 'message': 'Missing required parameters'})
    
#     # Create a unique job ID
#     job_id = str(uuid.uuid4())
    
#     # Set up the job in our dictionary
#     forecast_jobs[job_id] = {
#         'status': 'starting',
#         'progress': 0,
#         'currentSector': None,
#         'processedSectors': 0,
#         'totalSectors': len(sector_configs),
#         'scenarioName': scenario_name,
#         'targetYear': target_year,
#         'excludeCovidYears': exclude_covid_years,
#         'start_time': time.time(),
#         'result': None,
#         'error': None
#     }
    
#     # Start the forecast thread
#     forecast_thread = threading.Thread(
#         target=run_multiple_forecasts_job,
#         args=(job_id, app.config['CURRENT_PROJECT_PATH'], data)
#     )
#     forecast_thread.daemon = True
#     forecast_thread.start()
    
#     return jsonify({
#         'status': 'started',
#         'jobId': job_id,
#         'message': f'Forecast job started for {len(sector_configs)} sectors using scenario {scenario_name}'
#     })

# @app.route('/api/forecast_status/<job_id>', methods=['GET'])
# def get_forecast_status(job_id):
#     """
#     Get the status of a forecast job
#     """
#     if job_id not in forecast_jobs:
#         return jsonify({'status': 'error', 'message': 'Job not found'})
    
#     job = forecast_jobs[job_id]
    
#     return jsonify({
#         'status': job['status'],
#         'progress': job['progress'],
#         'currentSector': job['currentSector'],
#         'result': job['result'] if job['status'] == 'completed' else None,
#         'error': job['error'] if job['status'] == 'failed' else None
#     })

# @app.route('/api/cancel_forecast/<job_id>', methods=['POST'])
# def cancel_forecast(job_id):
#     """
#     Cancel a running forecast job
#     """
#     if job_id not in forecast_jobs:
#         return jsonify({'status': 'error', 'message': 'Job not found'})
    
#     job = forecast_jobs[job_id]
    
#     if job['status'] in ['completed', 'failed', 'cancelled']:
#         return jsonify({'status': 'error', 'message': f'Job already {job["status"]}'})
    
#     # Mark the job as cancelled
#     job['status'] = 'cancelled'
    
#     return jsonify({'status': 'cancelled', 'message': 'Forecast job cancelled'})


# def run_multiple_forecasts_job(job_id, project_path, data):
#     """
#     Run forecasts for multiple sectors in a single job, intelligently handling existing data
    
#     Args:
#         job_id (str): The unique identifier for this forecast job
#         project_path (str): Path to the project directory
#         data (dict): Configuration data for the forecast including scenario name, 
#                     target year, and sector-specific configurations
#     """
#     job = forecast_jobs[job_id]
#     job['status'] = 'running'
    
#     try:
#         # Get parameters
#         scenario_name = data.get('scenarioName')
#         target_year = int(data.get('targetYear'))
#         exclude_covid = data.get('excludeCovidYears', True)
#         sector_configs = data.get('sectorConfigs', {})
        
#         print(f"Starting forecast job {job_id} with {len(sector_configs)} sectors: {list(sector_configs.keys())}")
        
#         # Update initial progress
#         job['progress'] = 5
        
#         # Load data
#         demand_input_file_path = f"{project_path}/inputs/input_demand_file.xlsx"
#         sectors, _, param_dict, sector_data, _ = input_demand_data(demand_input_file_path)
        
#         # Get start and end years from parameters
#         start_year = int(param_dict.get('Start_Year', 2006))
        
#         # Validate sectors
#         for sector in sector_configs.keys():
#             if sector not in sector_data:
#                 print(f"Warning: Sector {sector} not found in input data, skipping")
#                 raise ValueError(f"Sector {sector} not found in input data")
        
#         # Prepare forecast directory
#         forecast_dir = f"{project_path}/results/demand_projection/{scenario_name}"
#         os.makedirs(forecast_dir, exist_ok=True)
        
#         # Import the forecasting function from models
#         from models.forecasting import Main_forecasting_function
        
#         # Process each sector that needs forecasting
#         sectors_using_existing_data = []
#         sectors_forecasted = []
#         sectors_with_errors = []
        
#         total_sectors = len(sector_configs)
#         print(f"Will process {total_sectors} sectors: {list(sector_configs.keys())}")
        
#         for idx, (sector, config) in enumerate(sector_configs.items()):
#             # Check for cancellation
#             if forecast_jobs[job_id]['status'] == 'cancelled':
#                 print(f"Job {job_id} was cancelled, stopping processing")
#                 return
            
#             # Update progress
#             job['currentSector'] = sector
#             job['processedSectors'] = idx
#             progress_per_sector = 90 / max(1, total_sectors)
#             current_progress = 5 + int(idx * progress_per_sector)
#             job['progress'] = current_progress
            
#             print(f"Processing sector {sector} ({idx+1}/{total_sectors}), progress: {current_progress}%")
            
#             try:
#                 # Get selected models for this sector
#                 selected_models = config.get('models', ['MLR', 'SLR', 'WAM', 'TimeSeries'])
                
#                 print(f"  Models for {sector}: {selected_models}")
                
#                 # Base parameters for all models
#                 base_params = {
#                     'target_year': target_year,
#                     'exclude_covid': exclude_covid
#                 }
                
#                 # Set up model-specific parameters
#                 model_params = {}
#                 if 'MLR' in selected_models:
#                     independent_vars = config.get('independentVars', [])
#                     print(f"  MLR independent variables for {sector}: {independent_vars}")
#                     model_params['MLR'] = {'independent_vars': independent_vars}
                
#                 if 'WAM' in selected_models:
#                     window_size = int(config.get('windowSize', 10))
#                     print(f"  WAM window size for {sector}: {window_size}")
#                     model_params['WAM'] = {'window_size': window_size}
                
#                 # Check if we have valid sector data
#                 if sector not in sector_data:
#                     print(f"Error: Sector {sector} not in input data, skipping")
#                     sectors_with_errors.append(sector)
#                     continue
                
#                 # Run forecast for this sector with all selected models
#                 print(f"  Starting forecast for {sector} with models: {selected_models}")
#                 result = Main_forecasting_function(
#                     sector, 
#                     forecast_dir, 
#                     sector_data[sector],
#                     selected_models=selected_models,
#                     model_params=model_params,
#                     **base_params
#                 )
                
#                 # Track if we used existing data or forecasted
#                 if result.get('used_existing_data', False):
#                     print(f"  Sector {sector} used existing data")
#                     sectors_using_existing_data.append(sector)
#                 else:
#                     print(f"  Sector {sector} forecast completed")
#                     sectors_forecasted.append(sector)
                
#             except Exception as e:
#                 print(f"Error processing sector {sector}: {str(e)}")
#                 import traceback
#                 traceback.print_exc()
#                 sectors_with_errors.append(sector)
                
#                 # Continue processing other sectors despite this error
#                 continue
            
#             # Update progress after each sector
#             sector_progress = 5 + int((idx + 1) * progress_per_sector)
#             job['progress'] = sector_progress
#             job['processedSectors'] = idx + 1
            
#             print(f"  Completed sector {sector}, progress: {sector_progress}%")
            
#             # Check for cancellation again
#             if forecast_jobs[job_id]['status'] == 'cancelled':
#                 print(f"Job {job_id} was cancelled after processing {sector}")
#                 return
        
#         print(f"All sectors processed. Forecasted: {len(sectors_forecasted)}, Used existing: {len(sectors_using_existing_data)}, Errors: {len(sectors_with_errors)}")
        
#         # Generate summary file with metadata
#         summary_data = {
#             'scenario': scenario_name,
#             'target_year': target_year,
#             'start_year': start_year,
#             'sectors': list(sector_configs.keys()),
#             'sectors_with_complete_data': sectors_using_existing_data,
#             'sectors_forecasted': sectors_forecasted,
#             'sectors_with_errors': sectors_with_errors,
#             'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
#             'exclude_covid': exclude_covid,
#             'models_used': {sector: config.get('models', ['MLR', 'SLR', 'WAM', 'TimeSeries']) 
#                            for sector, config in sector_configs.items()}
#         }
        
#         print(f"Writing summary file to {forecast_dir}/summary.json")
#         with open(f"{forecast_dir}/summary.json", 'w') as f:
#             json.dump(summary_data, f, indent=4)
        
#         # Complete the job
#         job['status'] = 'completed'
#         job['progress'] = 100
#         job['result'] = {
#             'scenarioName': scenario_name,
#             'targetYear': target_year,
#             'totalSectors': len(sector_configs),
#             'sectorsWithCompleteData': len(sectors_using_existing_data),
#             'sectorsForecasted': len(sectors_forecasted),
#             'sectorsWithErrors': len(sectors_with_errors),
#             'filePath': forecast_dir
#         }
        
#         print(f"Forecast job {job_id} completed successfully")
        
#     except Exception as e:
#         # Handle errors
#         job['status'] = 'failed'
#         job['error'] = str(e)
#         print(f"Forecast job {job_id} failed: {str(e)}")
#         import traceback
#         traceback.print_exc()
# # Routes
# @app.route('/')
# def home():
#     recent_activities = get_recent_activities()
#     return render_template('home.html', 
#                            recent_activities=recent_activities,
#                            current_project=app.config['CURRENT_PROJECT'])

# @app.route('/demand_projection')
# def demand_projection():
#     if app.config['CURRENT_PROJECT_PATH'] is None:
#         flash('Please select or receberam a project first.', 'warning')
#         return redirect(url_for('home'))
    
#     demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
#     if not os.path.exists(demand_input_file_path):
#         flash('Input demand file not found. Please upload it first.', 'warning')
#         return redirect(url_for('home'))
    
#     try:
#         sectors, missing_sectors, param_dict, sector_data, aggregated_ele = input_demand_data(demand_input_file_path)
        
#         if not sectors:
#             flash('No sectors found in the input file.', 'warning')
#             return redirect(url_for('home'))
        
#         sector_tables = {}
#         chart_data = {'sectors': sectors}  # Minimal initial data

#         # Process sector data
#         for sector, df in sector_data.items():
#             sector_tables[sector] = df.to_html(classes='table table-striped table-hover', index=False)

#         aggregated_table = aggregated_ele.to_html(classes='table table-striped table-hover', index=False)

#         return render_template('demand_projection.html',
#                                sectors=sectors,
#                                missing_sectors=missing_sectors,
#                                param_dict=param_dict,
#                                sector_tables=sector_tables,
#                                aggregated_table=aggregated_table,
#                                chart_data=chart_data)
#     except Exception as e:
#         flash(f'Error processing demand projection: {str(e)}', 'danger')
#         return redirect(url_for('home'))
# def handle_nan_values(obj):
#     """Convert NaN values to null for JSON serialization"""
#     if isinstance(obj, float) and np.isnan(obj):
#         return None
#     elif isinstance(obj, dict):
#         return {k: handle_nan_values(v) for k, v in obj.items()}
#     elif isinstance(obj, list):
#         return [handle_nan_values(item) for item in obj]
#     return obj

# @app.route('/api/correlation_data/<sector>', methods=['GET'])
# def get_correlation_data(sector):
#     """Get correlation data for a specific sector, focusing on Electricity correlations"""
#     if app.config['CURRENT_PROJECT_PATH'] is None:
#         return jsonify({'status': 'error', 'message': 'No project selected'})
    
#     demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
#     if not os.path.exists(demand_input_file_path):
#         return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    
#     try:
#         # Get sector data
#         sectors, _, param_dict, sector_data, aggregated_ele = input_demand_data(demand_input_file_path)
        
#         if sector == 'aggregated':
#             df = aggregated_ele
#         elif sector not in sector_data:
#             return jsonify({'status': 'error', 'message': f'Sector {sector} not found'})
#         else:
#             df = sector_data[sector]
        
#         # Select only numeric columns for correlation analysis
#         numeric_df = df.select_dtypes(include=['number'])
        
#         # Check if Electricity is in the columns
#         if 'Electricity' not in numeric_df.columns:
#             return jsonify({
#                 'status': 'success',
#                 'data': {
#                     'variables': [],
#                     'correlations': []
#                 }
#             })
        
#         # Calculate correlations with Electricity
#         try:
#             corr_matrix = numeric_df.corr()
#             elec_corr = corr_matrix['Electricity'].drop('Electricity')  # Remove self-correlation
            
#             # Prepare data for frontend
#             variables = []
#             correlations = []
            
#             for var, corr_value in elec_corr.items():
#                 if pd.isna(corr_value):
#                     continue
                    
#                 # Get correlation strength
#                 corr_abs = abs(corr_value)
#                 if corr_abs >= 0.7:
#                     strength = "Strong"
#                 elif corr_abs >= 0.4:
#                     strength = "Moderate"
#                 else:
#                     strength = "Weak"
                
#                 variables.append(var)
#                 correlations.append({
#                     'value': round(float(corr_value), 2),
#                     'strength': strength
#                 })
            
#             # Sort by absolute correlation value (descending)
#             combined = list(zip(variables, correlations))
#             sorted_data = sorted(combined, key=lambda x: abs(x[1]['value']), reverse=True)
            
#             sorted_variables = [item[0] for item in sorted_data]
#             sorted_correlations = [item[1] for item in sorted_data]
            
#             return jsonify({
#                 'status': 'success',
#                 'data': {
#                     'variables': sorted_variables,
#                     'correlations': sorted_correlations
#                 }
#             })
#         except Exception as e:
#             import traceback
#             traceback.print_exc()
#             return jsonify({
#                 'status': 'error',
#                 'message': f'Error calculating correlations: {str(e)}'
#             })
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
        
#         return jsonify({
#             'status': 'error',
#             'message': f'Error calculating correlation: {str(e)}'
#         })
# @app.route('/api/chart_data/<sector>', methods=['GET'])
# def get_chart_data(sector):
#     if app.config['CURRENT_PROJECT_PATH'] is None:
#         return jsonify({'status': 'error', 'message': 'No project selected'})
    
#     demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
#     if not os.path.exists(demand_input_file_path):
#         return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    
#     try:
#         sectors, _, param_dict, sector_data, aggregated_ele = input_demand_data(demand_input_file_path)
        
#         # Get target year from parameters
#         target_year = int(param_dict.get('End_Year', 2037))
#         start_year = int(param_dict.get('Start_Year', 2006))
        
#         # Replace NaN values with None for JSON serialization
#         for col in aggregated_ele.columns:
#             aggregated_ele[col] = aggregated_ele[col].replace([np.nan, np.inf, -np.inf], None)
        
#         chart_data = {}
#         if sector == 'aggregated':
#             # Process aggregated data for all sectors
#             years = aggregated_ele['Year'].tolist()
#             datasets = []
            
#             for i, s in enumerate(sectors):
#                 if s in aggregated_ele.columns:
#                     # Generate consistent colors
#                     r = (i * 50) % 255
#                     g = (i * 100) % 255
#                     b = (i * 150) % 255
                    
#                     # Replace None with 0 for chart rendering
#                     sector_data = [float(v) if v is not None else 0 for v in aggregated_ele[s].tolist()]
                    
#                     datasets.append({
#                         'label': s,
#                         'data': sector_data,
#                         'backgroundColor': f'rgba({r}, {g}, {b}, 0.7)',
#                         'borderColor': f'rgba({r}, {g}, {b}, 1)'
#                     })
            
#             chart_data = {
#                 'years': years,
#                 'datasets': datasets
#             }
#         else:
#             if sector not in sector_data:
#                 return jsonify({'status': 'error', 'message': f'Sector {sector} not found'}), 404
            
#             df = sector_data[sector].copy()
            
#             # Replace NaN with None for JSON
#             for col in df.columns:
#                 df[col] = df[col].replace([np.nan, np.inf, -np.inf], None)
            
#             # Check for data completeness
#             has_complete_data = False
#             max_year = 0
#             if 'Year' in df.columns and 'Electricity' in df.columns:
#                 years_with_data = [(y, e) for y, e in zip(df['Year'], df['Electricity']) if e is not None]
#                 if years_with_data:
#                     max_year = max(y for y, _ in years_with_data)
#                     has_complete_data = max_year >= target_year
            
#             chart_data = {
#                 'years': df['Year'].tolist() if 'Year' in df.columns else [],
#                 'electricity': df['Electricity'].tolist() if 'Electricity' in df.columns else [],
#                 'hasCompleteData': has_complete_data,
#                 'maxYear': max_year,
#                 'targetYear': target_year,
#                 'startYear': start_year
#             }
        
#         return jsonify({'status': 'success', 'data': chart_data})
#     except Exception as e:
#         return jsonify({'status': 'error', 'message': f'Error fetching chart data: {str(e)}'}), 500



# @app.route('/demand_visualization')
# def demand_visualization():
#     """Render the demand visualization page"""
#     if app.config['CURRENT_PROJECT_PATH'] is None:
#         flash('Please select or create a project first.', 'warning')
#         return redirect(url_for('home'))
#     try:
#         # Get available scenarios from results/demand_projection folder
#         scenarios_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection')
#         if not os.path.exists(scenarios_path):
#             flash('No forecast scenarios found. Please run forecasts first.', 'warning')
#             return redirect(url_for('demand_projection'))
        
#         # List directories in demand_projection folder
#         scenarios = [d for d in os.listdir(scenarios_path) 
#                     if os.path.isdir(os.path.join(scenarios_path, d))]
        
#         if not scenarios:
#             flash('No forecast scenarios found. Please run forecasts first.', 'warning')
#             return redirect(url_for('demand_projection'))
        
#         # Get selected scenario from query parameter or use first available
#         selected_scenario = request.args.get('scenario', scenarios[0])
        
#         # Get available sectors and year range
#         sectors = []
#         start_year = 2025  # Default fallback
#         end_year = 2037    # Default fallback
        
#         # Find all sector files
#         scenario_path = os.path.join(scenarios_path, selected_scenario)
#         sector_files = [f for f in os.listdir(scenario_path) 
#                        if f.endswith('.xlsx') and not f.startswith('_')]
        
#         if sector_files:
#             # Get sectors from file names
#             sectors = [os.path.splitext(f)[0] for f in sector_files 
#                       if not os.path.splitext(f)[0].lower() in ['summary', 'consolidated']]
            
#             # Determine year range across all sector files
#             all_years = []
#             for file in sector_files:
#                 file_path = os.path.join(scenario_path, file)
#                 try:
#                     xls = pd.ExcelFile(file_path)
#                     for sheet in xls.sheet_names:
#                         try:
#                             df = pd.read_excel(file_path, sheet_name=sheet)
#                             if 'Year' in df.columns:
#                                 # Filter valid numeric years
#                                 valid_years = df['Year'].dropna().apply(lambda x: int(x) if pd.api.types.is_numeric_dtype(type(x)) and not pd.isna(x) else None)
#                                 valid_years = valid_years[valid_years.notnull()]
#                                 if not valid_years.empty:
#                                     all_years.extend(valid_years.tolist())
#                         except Exception as e:
#                             print(f"Warning: Could not read sheet {sheet} from {file}: {str(e)}")
#                 except Exception as e:
#                     print(f"Error accessing {file}: {str(e)}")
            
#             if all_years:
#                 start_year = int(min(all_years))
#                 end_year = int(max(all_years))
#                 print(f"Determined year range: {start_year} to {end_year}")
#             else:
#                 print("Warning: No valid years found in sector files, using defaults")
#         else:
#             print("Warning: No sector files found in scenario path")

#         # Ensure valid year range
#         if start_year > end_year:
#             start_year, end_year = end_year, start_year
#         if not sectors:
#             flash('No valid sector data found for this scenario.', 'warning')
#             return redirect(url_for('demand_projection'))

#         # Render the template with available data
#         return render_template('demand_visualization.html',
#                              scenarios=scenarios,
#                              selected_scenario=selected_scenario,
#                              sectors=sectors,
#                              start_year=start_year,
#                              end_year=end_year,
#                              current_project=app.config['CURRENT_PROJECT'])

#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         flash(f'Error loading demand visualization: {str(e)}', 'danger')
#         return redirect(url_for('home'))

# @app.route('/api/forecast_data/<scenario>', methods=['GET'])
# def get_forecast_data(scenario):
#     """API endpoint to get forecast data for a specific scenario"""
#     if app.config['CURRENT_PROJECT_PATH'] is None:
#         return jsonify({'status': 'error', 'message': 'No project selected'})
#     try:
#         # Get path to scenario folder
#         scenario_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 
#                                     'results', 'demand_projection', scenario)
        
#         if not os.path.exists(scenario_path):
#             return jsonify({'status': 'error', 'message': f'Scenario {scenario} not found'})
        
#         # Find all sector files
#         sector_files = [f for f in os.listdir(scenario_path) 
#                        if f.endswith('.xlsx') and not f.startswith('_')]
        
#         if not sector_files:
#             return jsonify({'status': 'error', 'message': 'No sector data found for this scenario'})
        
#         # Process each sector file
#         sector_data = {}
        
#         for file in sector_files:
#             sector_name = os.path.splitext(file)[0]
#             if sector_name.lower() in ['summary', 'consolidated']:
#                 continue
                
#             file_path = os.path.join(scenario_path, file)
            
#             try:
#                 # Read the Results sheet
#                 df = pd.read_excel(file_path, sheet_name='Results')
                
#                 # Check for required columns
#                 if 'Year' not in df.columns:
#                     print(f"Warning: 'Year' column missing in {file}")
#                     continue
                
#                 # Extract and validate years
#                 years = df['Year'].dropna().apply(lambda x: int(x) if pd.api.types.is_numeric_dtype(type(x)) and not pd.isna(x) else None)
#                 years = years[years.notnull()].tolist()
#                 print(f"Years for {sector_name}: {years}")
                
#                 # Create model data
#                 model_data = {}
#                 for column in df.columns:
#                     if column != 'Year':
#                         # Replace NaN with None for JSON serialization
#                         model_data[column] = [
#                             None if pd.isna(value) else float(value)
#                             for value in df[column].tolist()
#                         ]
                
#                 # Store data
#                 sector_data[sector_name] = {
#                     'years': years,
#                     **model_data
#                 }
                
#             except Exception as e:
#                 print(f"Error processing {file}: {str(e)}")
#                 continue
        
#         if not sector_data:
#             return jsonify({'status': 'error', 'message': 'Could not process any sector data'})
        
#         return jsonify({
#             'status': 'success',
#             'data': sector_data
#         })
        
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return jsonify({'status': 'error', 'message': f'Error fetching forecast data: {str(e)}'})
# @app.route('/load_profile_creation')
# def load_profile_creation():
#     if not app.config['CURRENT_PROJECT']:
#         flash('Please select or create a project first', 'warning')
#         return redirect(url_for('home'))
        
#     flash('Load Profile Creation module is coming soon!', 'info')
#     return redirect(url_for('home'))

# @app.route('/pypsa_modeling')
# def pypsa_modeling():
#     if not app.config['CURRENT_PROJECT']:
#         flash('Please select or create a project first', 'warning')
#         return redirect(url_for('home'))
        
#     flash('PyPSA Modeling module is coming soon!', 'info')
#     return redirect(url_for('home'))

# @app.route('/modeling_results')
# def modeling_results():
#     if not app.config['CURRENT_PROJECT']:
#         flash('Please select or create a project first', 'warning')
#         return redirect(url_for('home'))
        
#     flash('Modeling Results module is coming soon!', 'info')
#     return redirect(url_for('home'))

# @app.route('/user_guide')
# def user_guide():
#     return render_template('user_guide.html')

# @app.route('/create_project', methods=['POST'])
# def create_project():
#     if request.method != 'POST':
#         return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
#     project_name = request.form.get('projectName')
#     project_location = request.form.get('projectLocation', '')
    
#     if not project_name:
#         return jsonify({'status': 'error', 'message': 'Please provide a project name'})
    
#     if not project_location:
#         return jsonify({'status': 'error', 'message': 'Please select a project location'})
    
#     try:
#         safe_project_name = secure_filename(project_name)
#         if os.path.isabs(project_location):
#             project_path = os.path.join(project_location, safe_project_name)
#         else:
#             project_path = os.path.join(app.config['UPLOAD_FOLDER'], 'projects', project_location, safe_project_name)
        
#         success = create_project_structure(project_path, app.config['TEMPLATE_FOLDER'])
#         if success:
#             print(f"Project created: {project_path} at {datetime.now()}")
            
#             # Save to recent projects
#             user_id = session.get('user_id', 'default_user')
#             save_recent_project(user_id, project_name, project_path)
            
#             app.config['CURRENT_PROJECT'] = project_name
#             app.config['CURRENT_PROJECT_PATH'] = project_path

#             return jsonify({
#                 'status': 'success',
#                 'message': f'Project "{project_name}" created successfully!',
#                 'project_path': project_path
#             })
#         else:
#             return jsonify({
#                 'status': 'error',
#                 'message': 'Failed to create project structure. Check server logs for details.'
#             })
#     except Exception as e:
#         return jsonify({'status': 'error', 'message': f'Error creating project: {str(e)}'})

# @app.route('/validate_project', methods=['POST'])
# def validate_project():
#     if request.method != 'POST':
#         return jsonify({'status': 'error', '即将message': 'Invalid request method'})
    
#     project_path = request.form.get('projectPath')
    
#     if not project_path:
#         return jsonify({'status': 'error', 'message': 'No project path provided'})
    
#     try:
#         if not os.path.exists(project_path):
#             return jsonify({
#                 'status': 'error', 
#                 'message': f'The path "{project_path}" does not exist'
#             })
        
#         validation_result = validate_project_structure(project_path)
#         return jsonify(validation_result)
#     except Exception as e:
#         return jsonify({
#             'status': 'error',
#             'message': f'Error validating project: {str(e)}'
#         })

# @app.route('/load_project', methods=['POST'])
# def load_project():
#     if request.method != 'POST':
#         return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
#     project_path = request.form.get('projectPath')
    
#     if not project_path:
#         return jsonify({'status': 'error use for No project path provided'})
    
#     try:
#         validation_result = validate_project_structure(project_path)
        
#         if validation_result['status'] == 'error':
#             return jsonify(validation_result)
        
#         if validation_result['status'] == 'warning' and validation_result.get('can_fix', False):
#             copy_missing_templates(project_path, validation_result.get('missing_templates', []), app.config['TEMPLATE_FOLDER'])
        
#         project_name = os.path.basename(os.path.normpath(project_path))
#         app.config['CURRENT_PROJECT'] = project_name
#         app.config['CURRENT_PROJECT_PATH'] = project_path
#         user_id = session.get('user_id', 'default_user')
#         save_recent_project(user_id, project_name, project_path)
#         return jsonify({
#             'status': 'success',
#             'message': 'Project loaded successfully',
#             'project_path': project_path,
#             'project_name': project_name
#         })
#     except Exception as e:
#         return jsonify({
#             'status': 'error',
#             'message': f'Error loading project: {str(e)}'
#         })

# @app.route('/download_template/<template_type>')
# def download_template(template_type):
#     templates = {
#         'data_input': 'data_input_template.xlsx',
#         'load_curve': 'load_curve_template.xlsx',
#         'pypsa_input': 'pypsa_input_template.xlsx'
#     }
    
#     if template_type not in templates:
#         flash('Template not found', 'danger')
#         return redirect(url_for('home'))
    
#     template_path = os.path.join(app.config['TEMPLATE_FOLDER'], templates[template_type])
    
#     if not os.path.exists(template_path):
#         create_template_files()
#         if not os.path.exists(template_path):
#             flash(f'Template file {templates[template_type]} not found', 'danger')
#             return redirect(url_for('home'))
    
#     return send_file(template_path, as_attachment=True)

# @app.route('/download_user_guide')
# def download_user_guide():
#     guide_path = os.path.join(app.config['TEMPLATE_FOLDER'], 'user_guide.pdf')
    
#     if not os.path.exists(guide_path):
#         flash('User guide PDF not found', 'danger')
#         return redirect(url_for('home'))
        
#     return send_file(guide_path, as_attachment=True)

# @app.route('/download_methodology')
# def download_methodology():
#     methodology_path = os.path.join(app.config['TEMPLATE_FOLDER'], 'methodology.pdf')
    
#     if not os.path.exists(methodology_path):
#         flash('Methodology PDF not found', 'danger')
#         return redirect(url_for('home'))
        
#     return send_file(methodology_path, as_attachment=True)

# @app.route('/tutorials')
# def tutorials():
#     flash('Tutorials page is coming soon!', 'info')
#     return redirect(url_for('home'))

# @app.route('/upload_data', methods=['POST'])
# def upload_data():
#     if request.method == 'POST':
#         if not app.config['CURRENT_PROJECT']:
#             flash('Please select or create a project first', 'warning')
#             return redirect(url_for('home'))
            
#         if 'data_file' not in request.files:
#             flash('No file part', 'danger')
#             return redirect(url_for('home'))
        
#         file = request.files['data_file']
        
#         if file.filename == '':
#             flash('No selected file', 'danger')
#             return redirect(url_for('home'))
        
#         if file and allowed_file(file.filename):
#             filename = secure_filename(file.filename)
#             project_inputs_folder = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'inputs')
#             os.makedirs(project_inputs_folder, exist_ok=True)
#             file_path = os.path.join(project_inputs_folder, filename)
#             file.save(file_path)
#             flash('File uploaded successfully!', 'success')
#             return redirect(url_for('home'))
#         else:
#             flash('Invalid file type. Please upload an Excel (.xlsx) file.', 'danger')
#             return redirect(url_for('home'))

# # Error handlers
# @app.errorhandler(404)
# def page_not_found(e):
#     return render_template('404.html'), 404

# @app.errorhandler(500)
# def internal_server_error(e):
#     return render_template('500.html'), 500

# # API routes
# @app.route('/api/search', methods=['POST'])
# def api_search():
#     query = request.json.get('query', '')
#     results = [
#         {
#             'title': 'Demand Projection',
#             'type': 'Feature',
#             'description': 'Generate sector-wise electricity demand projections',
#             'link': url_for('demand_projection')
#         },
#         {
#             'title': 'Data Input Template',
#             'type': 'Resource',
#             'description': 'Excel template for sector-wise energy demand data',
#             'link': url_for('download_template', template_type='data_input')
#         }
#     ]
#     return jsonify({'results': results})

# #create_template_files()

# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0', port=5000)





from io import BytesIO
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
import os
import shutil
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
import pandas as pd
import json
import traceback # Added for better error reporting
# Import helper functions
from utils.data_loading import input_demand_data
from utils.helpers import create_project_structure, validate_project_structure, copy_missing_templates, extract_tables_by_markers
from utils.plots import generate_area_chart, generate_correlation_plot
# Import necessary modules
import threading
import uuid
import time
import json
from flask import jsonify, request, session
import numpy as np
from datetime import datetime
from utils.pypsa_runner import run_pypsa_model_core 
import logging
# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'energy_demand_forecasting_secret_key'  # Change in production
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
# Configuration
app.config['UPLOAD_FOLDER'] = 'static/user_uploads'
app.config['TEMPLATE_FOLDER'] = 'static/templates'
app.config['ALLOWED_EXTENSIONS'] = {'xlsx'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
app.config['CURRENT_PROJECT'] = None
app.config['CURRENT_PROJECT_PATH'] = None

# Ensure upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMPLATE_FOLDER'], exist_ok=True)
recent_projects_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'recent_projects')
os.makedirs(recent_projects_dir, exist_ok=True)
forecast_jobs = {}
pypsa_jobs = {} # For PyPSA model runs
app.config['INPUT_FOLDER'] = os.path.join(app.root_path, 'inputs')
app.config['RESULTS_FOLDER'] = os.path.join(app.root_path, 'results')
os.makedirs(app.config['INPUT_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['RESULTS_FOLDER'], 'load_profiles'), exist_ok=True)
def save_recent_project(user_id, project_name, project_path):
    """Save project to recent projects list"""
    try:
        # Filename based on user ID
        filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        
        # Load existing data or create new
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                recent_projects = json.load(f)
        else:
            recent_projects = []
        
        # Check if project already exists
        existing_index = None
        for i, project in enumerate(recent_projects):
            if project.get('path') == project_path:
                existing_index = i
                break
        
        # Remove if exists
        if existing_index is not None:
            recent_projects.pop(existing_index)
        
        # Add to the beginning
        recent_projects.insert(0, {
            'name': project_name,
            'path': project_path,
            'last_opened': datetime.now().isoformat(),
            'timestamp': int(datetime.now().timestamp())
        })
        
        # Keep only most recent 10 projects
        recent_projects = recent_projects[:10]
        
        # Save back to file
        with open(filename, 'w') as f:
            json.dump(recent_projects, f, indent=4)
        
        return True
    except Exception as e:
        print(f"Error saving recent project: {e}")
        return False

# Add this endpoint to get recent projects
@app.route('/api/recent_projects', methods=['GET'])
def api_recent_projects():
    user_id = session.get('user_id', 'default_user')
    try:
        filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        
        if not os.path.exists(filename):
            print(f"Recent projects file not found for user {user_id}")
            return jsonify({'recent_projects': []})
        
        with open(filename, 'r') as f:
            recent_projects = json.load(f)
        
        print(f"Loaded {len(recent_projects)} recent projects for user {user_id}")
        return jsonify({'recent_projects': recent_projects})
    except Exception as e:
        print(f"Error reading recent projects: {e}")
        return jsonify({'recent_projects': [], 'error': str(e)})
@app.route('/api/delete_recent_project', methods=['POST'])
def api_delete_recent_project():
    """Delete a project from the recent projects list"""
    user_id = session.get('user_id', 'default_user')
    
    try:
        # Get project path from request
        data = request.get_json()
        if not data or 'projectPath' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Project path not provided'
            })
        
        project_path = data['projectPath']
        
        # Read existing projects
        filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        if not os.path.exists(filename):
            return jsonify({
                'status': 'error',
                'message': 'Recent projects file not found'
            })
        
        with open(filename, 'r') as f:
            recent_projects = json.load(f)
        
        # Find and remove the project
        found = False
        for i, project in enumerate(recent_projects):
            if project.get('path') == project_path:
                recent_projects.pop(i)
                found = True
                break
        
        if not found:
            return jsonify({
                'status': 'error',
                'message': 'Project not found in recent projects'
            })
        
        # Save the updated list
        with open(filename, 'w') as f:
            json.dump(recent_projects, f, indent=4)
        
        print(f"Removed project {project_path} from recent projects for user {user_id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Project removed from recent projects'
        })
    
    except Exception as e:
        print(f"Error removing project from recent projects: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        })
# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_recent_activities():
    activities = [
        {
            'icon': 'fas fa-chart-line',
            'title': 'Created forecast for "Energy Scenario 2025"',
            'time': '2 hours ago',
            'link': url_for('demand_visualization')
        },
        {
            'icon': 'fas fa-upload',
            'title': 'Uploaded data for "Regional Analysis"',
            'time': 'Yesterday',
            'link': '#'
        },
        {
            'icon': 'fas fa-cogs',
            'title': 'Ran PyPSA model for "Renewable Integration"',
            'time': '3 days ago',
            'link': url_for('modeling_results')
        }
    ]
    return activities

def create_template_files():
    pass
# Add to app.py - Helper function for checking feature usage in templates
@app.context_processor
def utility_processor():
    def is_used(feature_id):
        # In a real implementation, this would check the database or session
        # For demo, return True for specific features
        return feature_id in ['demand-projection', 'load-curve']
    return dict(is_used=is_used)
@app.route('/api/independent_variables/<sector>', methods=['GET'])
def get_independent_variables(sector):
    """
    Get available independent variables for the sector with correlation data
    """
    if app.config['CURRENT_PROJECT_PATH'] is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    
    try:
        # Get sector data
        sectors, _, _, sector_data, _ = input_demand_data(demand_input_file_path)
        
        if sector not in sector_data:
            return jsonify({'status': 'error', 'message': f'Sector {sector} not found'})
        
        # Get the variables for this sector
        df = sector_data[sector]
        variables = df.columns.tolist()
        
        # Calculate correlations with Electricity
        correlations = {}
        for var in variables:
            if var != 'Electricity' and var in df.select_dtypes(include=['number']).columns:
                correlations[var] = df[var].corr(df['Electricity'])
        
        return jsonify({
            'status': 'success',
            'variables': variables,
            'correlations': correlations
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error fetching variables: {str(e)}'})

@app.route('/api/run_forecast', methods=['POST'])
def run_forecast():
    """
    Start a forecast job for all sectors
    """
    if app.config['CURRENT_PROJECT_PATH'] is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    # Get request data
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'})
    
    scenario_name = data.get('scenarioName')
    target_year = data.get('targetYear')
    exclude_covid_years = data.get('excludeCovidYears', True)
    sector_configs = data.get('sectorConfigs', {})
    
    if not scenario_name or not target_year or not sector_configs:
        return jsonify({'status': 'error', 'message': 'Missing required parameters'})
    
    # Create a unique job ID
    job_id = str(uuid.uuid4())
    
    # Set up the job in our dictionary
    forecast_jobs[job_id] = {
        'status': 'starting',
        'progress': 0,
        'currentSector': None,
        'processedSectors': 0,
        'totalSectors': len(sector_configs),
        'scenarioName': scenario_name,
        'targetYear': target_year,
        'excludeCovidYears': exclude_covid_years,
        'start_time': time.time(),
        'result': None,
        'error': None
    }
    
    # Start the forecast thread
    forecast_thread = threading.Thread(
        target=run_multiple_forecasts_job,
        args=(job_id, app.config['CURRENT_PROJECT_PATH'], data)
    )
    forecast_thread.daemon = True
    forecast_thread.start()
    
    return jsonify({
        'status': 'started',
        'jobId': job_id,
        'message': f'Forecast job started for {len(sector_configs)} sectors using scenario {scenario_name}'
    })

@app.route('/api/forecast_status/<job_id>', methods=['GET'])
def get_forecast_status(job_id):
    """
    Get the status of a forecast job
    """
    if job_id not in forecast_jobs:
        return jsonify({'status': 'error', 'message': 'Job not found'})
    
    job = forecast_jobs[job_id]
    
    return jsonify({
        'status': job['status'],
        'progress': job['progress'],
        'currentSector': job['currentSector'],
        'result': job['result'] if job['status'] == 'completed' else None,
        'error': job['error'] if job['status'] == 'failed' else None
    })

@app.route('/api/cancel_forecast/<job_id>', methods=['POST'])
def cancel_forecast(job_id):
    """
    Cancel a running forecast job
    """
    if job_id not in forecast_jobs:
        return jsonify({'status': 'error', 'message': 'Job not found'})
    
    job = forecast_jobs[job_id]
    
    if job['status'] in ['completed', 'failed', 'cancelled']:
        return jsonify({'status': 'error', 'message': f'Job already {job["status"]}'})
    
    # Mark the job as cancelled
    job['status'] = 'cancelled'
    
    return jsonify({'status': 'cancelled', 'message': 'Forecast job cancelled'})


def run_multiple_forecasts_job(job_id, project_path, data):
    """
    Run forecasts for multiple sectors in a single job, intelligently handling existing data
    
    Args:
        job_id (str): The unique identifier for this forecast job
        project_path (str): Path to the project directory
        data (dict): Configuration data for the forecast including scenario name, 
                    target year, and sector-specific configurations
    """
    job = forecast_jobs[job_id]
    job['status'] = 'running'
    
    try:
        # Get parameters
        scenario_name = data.get('scenarioName')
        target_year = int(data.get('targetYear'))
        exclude_covid = data.get('excludeCovidYears', True)
        sector_configs = data.get('sectorConfigs', {})
        
        print(f"Starting forecast job {job_id} with {len(sector_configs)} sectors: {list(sector_configs.keys())}")
        
        # Update initial progress
        job['progress'] = 5
        
        # Load data
        demand_input_file_path = f"{project_path}/inputs/input_demand_file.xlsx"
        sectors, _, param_dict, sector_data, _ = input_demand_data(demand_input_file_path)
        
        # Get start and end years from parameters
        start_year = int(param_dict.get('Start_Year', 2006))
        
        # Validate sectors
        for sector in sector_configs.keys():
            if sector not in sector_data:
                print(f"Warning: Sector {sector} not found in input data, skipping")
                raise ValueError(f"Sector {sector} not found in input data")
        
        # Prepare forecast directory
        forecast_dir = f"{project_path}/results/demand_projection/{scenario_name}"
        os.makedirs(forecast_dir, exist_ok=True)
        
        # Import the forecasting function from models
        from models.forecasting import Main_forecasting_function
        
        # Process each sector that needs forecasting
        sectors_using_existing_data = []
        sectors_forecasted = []
        sectors_with_errors = []
        
        total_sectors = len(sector_configs)
        print(f"Will process {total_sectors} sectors: {list(sector_configs.keys())}")
        
        for idx, (sector, config) in enumerate(sector_configs.items()):
            # Check for cancellation
            if forecast_jobs[job_id]['status'] == 'cancelled':
                print(f"Job {job_id} was cancelled, stopping processing")
                return
            
            # Update progress
            job['currentSector'] = sector
            job['processedSectors'] = idx
            progress_per_sector = 90 / max(1, total_sectors)
            current_progress = 5 + int(idx * progress_per_sector)
            job['progress'] = current_progress
            
            print(f"Processing sector {sector} ({idx+1}/{total_sectors}), progress: {current_progress}%")
            
            try:
                # Get selected models for this sector
                selected_models = config.get('models', ['MLR', 'SLR', 'WAM', 'TimeSeries'])
                
                print(f"  Models for {sector}: {selected_models}")
                
                # Base parameters for all models
                base_params = {
                    'target_year': target_year,
                    'exclude_covid': exclude_covid
                }
                
                # Set up model-specific parameters
                model_params = {}
                if 'MLR' in selected_models:
                    independent_vars = config.get('independentVars', [])
                    print(f"  MLR independent variables for {sector}: {independent_vars}")
                    model_params['MLR'] = {'independent_vars': independent_vars}
                
                if 'WAM' in selected_models:
                    window_size = int(config.get('windowSize', 10))
                    print(f"  WAM window size for {sector}: {window_size}")
                    model_params['WAM'] = {'window_size': window_size}
                
                # Check if we have valid sector data
                if sector not in sector_data:
                    print(f"Error: Sector {sector} not in input data, skipping")
                    sectors_with_errors.append(sector)
                    continue
                
                # Run forecast for this sector with all selected models
                print(f"  Starting forecast for {sector} with models: {selected_models}")
                result = Main_forecasting_function(
                    sector, 
                    forecast_dir, 
                    sector_data[sector],
                    selected_models=selected_models,
                    model_params=model_params,
                    **base_params
                )
                
                # Track if we used existing data or forecasted
                if result.get('used_existing_data', False):
                    print(f"  Sector {sector} used existing data")
                    sectors_using_existing_data.append(sector)
                else:
                    print(f"  Sector {sector} forecast completed")
                    sectors_forecasted.append(sector)
                
            except Exception as e:
                print(f"Error processing sector {sector}: {str(e)}")
                import traceback
                traceback.print_exc()
                sectors_with_errors.append(sector)
                
                # Continue processing other sectors despite this error
                continue
            
            # Update progress after each sector
            sector_progress = 5 + int((idx + 1) * progress_per_sector)
            job['progress'] = sector_progress
            job['processedSectors'] = idx + 1
            
            print(f"  Completed sector {sector}, progress: {sector_progress}%")
            
            # Check for cancellation again
            if forecast_jobs[job_id]['status'] == 'cancelled':
                print(f"Job {job_id} was cancelled after processing {sector}")
                return
        
        print(f"All sectors processed. Forecasted: {len(sectors_forecasted)}, Used existing: {len(sectors_using_existing_data)}, Errors: {len(sectors_with_errors)}")
        
        # Generate summary file with metadata
        summary_data = {
            'scenario': scenario_name,
            'target_year': target_year,
            'start_year': start_year,
            'sectors': list(sector_configs.keys()),
            'sectors_with_complete_data': sectors_using_existing_data,
            'sectors_forecasted': sectors_forecasted,
            'sectors_with_errors': sectors_with_errors,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'exclude_covid': exclude_covid,
            'models_used': {sector: config.get('models', ['MLR', 'SLR', 'WAM', 'TimeSeries']) 
                           for sector, config in sector_configs.items()}
        }
        
        print(f"Writing summary file to {forecast_dir}/summary.json")
        with open(f"{forecast_dir}/summary.json", 'w') as f:
            json.dump(summary_data, f, indent=4)
        
        # Complete the job
        job['status'] = 'completed'
        job['progress'] = 100
        job['result'] = {
            'scenarioName': scenario_name,
            'targetYear': target_year,
            'totalSectors': len(sector_configs),
            'sectorsWithCompleteData': len(sectors_using_existing_data),
            'sectorsForecasted': len(sectors_forecasted),
            'sectorsWithErrors': len(sectors_with_errors),
            'filePath': forecast_dir
        }
        
        print(f"Forecast job {job_id} completed successfully")
        
    except Exception as e:
        # Handle errors
        job['status'] = 'failed'
        job['error'] = str(e)
        print(f"Forecast job {job_id} failed: {str(e)}")
        import traceback
        traceback.print_exc()
# Routes
@app.route('/')
def home():
    recent_activities = get_recent_activities()
    return render_template('home.html', 
                           recent_activities=recent_activities,
                           current_project=app.config['CURRENT_PROJECT'])

@app.route('/demand_projection')
def demand_projection():
    if app.config['CURRENT_PROJECT_PATH'] is None:
        flash('Please select or receberam a project first.', 'warning')
        return redirect(url_for('home'))
    
    demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        flash('Input demand file not found. Please upload it first.', 'warning')
        return redirect(url_for('home'))
    
    try:
        sectors, missing_sectors, param_dict, sector_data, aggregated_ele = input_demand_data(demand_input_file_path)
        
        if not sectors:
            flash('No sectors found in the input file.', 'warning')
            return redirect(url_for('home'))
        
        sector_tables = {}
        chart_data = {'sectors': sectors}  # Minimal initial data

        # Process sector data
        for sector, df in sector_data.items():
            sector_tables[sector] = df.to_html(classes='table table-striped table-hover', index=False)

        aggregated_table = aggregated_ele.to_html(classes='table table-striped table-hover', index=False)

        return render_template('demand_projection.html',
                               sectors=sectors,
                               missing_sectors=missing_sectors,
                               param_dict=param_dict,
                               sector_tables=sector_tables,
                               aggregated_table=aggregated_table,
                               chart_data=chart_data)
    except Exception as e:
        flash(f'Error processing demand projection: {str(e)}', 'danger')
        return redirect(url_for('home'))
def handle_nan_values(obj):
    """Convert NaN values to null for JSON serialization"""
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: handle_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [handle_nan_values(item) for item in obj]
    return obj

@app.route('/api/correlation_data/<sector>', methods=['GET'])
def get_correlation_data(sector):
    """Get correlation data for a specific sector, focusing on Electricity correlations"""
    if app.config['CURRENT_PROJECT_PATH'] is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    
    try:
        # Get sector data
        sectors, _, param_dict, sector_data, aggregated_ele = input_demand_data(demand_input_file_path)
        
        if sector == 'aggregated':
            df = aggregated_ele
        elif sector not in sector_data:
            return jsonify({'status': 'error', 'message': f'Sector {sector} not found'})
        else:
            df = sector_data[sector]
        
        # Select only numeric columns for correlation analysis
        numeric_df = df.select_dtypes(include=['number'])
        
        # Check if Electricity is in the columns
        if 'Electricity' not in numeric_df.columns:
            return jsonify({
                'status': 'success',
                'data': {
                    'variables': [],
                    'correlations': []
                }
            })
        
        # Calculate correlations with Electricity
        try:
            corr_matrix = numeric_df.corr()
            elec_corr = corr_matrix['Electricity'].drop('Electricity')  # Remove self-correlation
            
            # Prepare data for frontend
            variables = []
            correlations = []
            
            for var, corr_value in elec_corr.items():
                if pd.isna(corr_value):
                    continue
                    
                # Get correlation strength
                corr_abs = abs(corr_value)
                if corr_abs >= 0.7:
                    strength = "Strong"
                elif corr_abs >= 0.4:
                    strength = "Moderate"
                else:
                    strength = "Weak"
                
                variables.append(var)
                correlations.append({
                    'value': round(float(corr_value), 2),
                    'strength': strength
                })
            
            # Sort by absolute correlation value (descending)
            combined = list(zip(variables, correlations))
            sorted_data = sorted(combined, key=lambda x: abs(x[1]['value']), reverse=True)
            
            sorted_variables = [item[0] for item in sorted_data]
            sorted_correlations = [item[1] for item in sorted_data]
            
            return jsonify({
                'status': 'success',
                'data': {
                    'variables': sorted_variables,
                    'correlations': sorted_correlations
                }
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({
                'status': 'error',
                'message': f'Error calculating correlations: {str(e)}'
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'status': 'error',
            'message': f'Error calculating correlation: {str(e)}'
        })
@app.route('/api/chart_data/<sector>', methods=['GET'])
def get_chart_data(sector):
    if app.config['CURRENT_PROJECT_PATH'] is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    
    try:
        sectors, _, param_dict, sector_data, aggregated_ele = input_demand_data(demand_input_file_path)
        
        # Get target year from parameters
        target_year = int(param_dict.get('End_Year', 2037))
        start_year = int(param_dict.get('Start_Year', 2006))
        
        # Replace NaN values with None for JSON serialization
        for col in aggregated_ele.columns:
            aggregated_ele[col] = aggregated_ele[col].replace([np.nan, np.inf, -np.inf], None)
        
        chart_data = {}
        if sector == 'aggregated':
            # Process aggregated data for all sectors
            years = aggregated_ele['Year'].tolist()
            datasets = []
            
            for i, s in enumerate(sectors):
                if s in aggregated_ele.columns:
                    # Generate consistent colors
                    r = (i * 50) % 255
                    g = (i * 100) % 255
                    b = (i * 150) % 255
                    
                    # Replace None with 0 for chart rendering
                    sector_data = [float(v) if v is not None else 0 for v in aggregated_ele[s].tolist()]
                    
                    datasets.append({
                        'label': s,
                        'data': sector_data,
                        'backgroundColor': f'rgba({r}, {g}, {b}, 0.7)',
                        'borderColor': f'rgba({r}, {g}, {b}, 1)'
                    })
            
            chart_data = {
                'years': years,
                'datasets': datasets
            }
        else:
            if sector not in sector_data:
                return jsonify({'status': 'error', 'message': f'Sector {sector} not found'}), 404
            
            df = sector_data[sector].copy()
            
            # Replace NaN with None for JSON
            for col in df.columns:
                df[col] = df[col].replace([np.nan, np.inf, -np.inf], None)
            
            # Check for data completeness
            has_complete_data = False
            max_year = 0
            if 'Year' in df.columns and 'Electricity' in df.columns:
                years_with_data = [(y, e) for y, e in zip(df['Year'], df['Electricity']) if e is not None]
                if years_with_data:
                    max_year = max(y for y, _ in years_with_data)
                    has_complete_data = max_year >= target_year
            
            chart_data = {
                'years': df['Year'].tolist() if 'Year' in df.columns else [],
                'electricity': df['Electricity'].tolist() if 'Electricity' in df.columns else [],
                'hasCompleteData': has_complete_data,
                'maxYear': max_year,
                'targetYear': target_year,
                'startYear': start_year
            }
        
        return jsonify({'status': 'success', 'data': chart_data})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error fetching chart data: {str(e)}'}), 500




@app.route('/demand_visualization')
def demand_visualization():
    if app.config['CURRENT_PROJECT_PATH'] is None:
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('home'))
    try:
        scenarios_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection')
        if not os.path.exists(scenarios_path):
            flash('No forecast scenarios found. Please run forecasts first.', 'warning')
            return redirect(url_for('demand_projection'))
        scenarios = [d for d in os.listdir(scenarios_path) if os.path.isdir(os.path.join(scenarios_path, d))]
        if not scenarios:
            flash('No forecast scenarios found. Please run forecasts first.', 'warning')
            return redirect(url_for('demand_projection'))
        selected_scenario = request.args.get('scenario', scenarios[0])
        sectors = []
        start_year = 2025
        end_year = 2037
        scenario_path = os.path.join(scenarios_path, selected_scenario)
        sector_files = [f for f in os.listdir(scenario_path) if f.endswith('.xlsx') and not f.startswith('_')]
        if sector_files:
            sectors = [os.path.splitext(f)[0] for f in sector_files if not os.path.splitext(f)[0].lower() in ['summary', 'consolidated']]
            all_years = []
            for file in sector_files:
                file_path = os.path.join(scenario_path, file)
                try:
                    xls = pd.ExcelFile(file_path)
                    for sheet in xls.sheet_names:
                        try:
                            df = pd.read_excel(file_path, sheet_name=sheet)
                            if 'Year' in df.columns:
                                valid_years = df['Year'].dropna().apply(lambda x: int(x) if pd.api.types.is_numeric_dtype(type(x)) and not pd.isna(x) else None)
                                valid_years = valid_years[valid_years.notnull()]
                                if not valid_years.empty:
                                    all_years.extend(valid_years.tolist())
                        except Exception as e:
                            print(f"Warning: Could not read sheet {sheet} from {file}: {str(e)}")
                except Exception as e:
                    print(f"Error accessing {file}: {str(e)}")
            if all_years:
                start_year = int(min(all_years))
                end_year = int(max(all_years))
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        if not sectors:
            flash('No valid sector data found for this scenario.', 'warning')
            return redirect(url_for('demand_projection'))
        return render_template('demand_visualization.html',
                               scenarios=scenarios, selected_scenario=selected_scenario,
                               sectors=sectors, start_year=start_year, end_year=end_year,
                               current_project=app.config['CURRENT_PROJECT'])
    except Exception as e:
        flash(f'Error loading demand visualization: {str(e)}', 'danger')
        return redirect(url_for('home'))

@app.route('/api/download_comparison_data', methods=['POST'])
def download_comparison_data():
    if not app.config['CURRENT_PROJECT_PATH']:
        return jsonify({"status": "error", "message": "No project loaded."}), 400

    data = request.get_json()
    scenarios = data.get('scenarios', [])
    from_year = int(data.get('fromYear', datetime.now().year - 5))
    to_year = int(data.get('toYear', datetime.now().year + 10))
    unit = data.get('unit', 'TWh')
    sector_model_map = data.get('sectorModelMap', {})

    if len(scenarios) < 2:
        return jsonify({"status": "error", "message": "At least two scenarios are required for comparison."}), 400

    # Get data for each scenario
    consolidated_dfs = []
    for scenario_name in scenarios:
        scenario_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection', scenario_name)
        
        all_sector_dfs = []
        years_df = pd.DataFrame({'Year': range(from_year, to_year + 1)})

        for sector, model_choice in sector_model_map.items():
            sector_full_df = get_forecast_data_for_sector(scenario_path, sector, from_year, to_year, unit)
            if sector_full_df is not None and not sector_full_df.empty:
                if model_choice in sector_full_df.columns:
                    # Use scenario name as prefix in column name
                    new_col_name = f"{scenario_name}_{sector}"
                    sector_model_data = sector_full_df[['Year', model_choice]].rename(columns={model_choice: new_col_name}).copy()
                    all_sector_dfs.append(sector_model_data)
                elif 'Historical' == model_choice and 'Historical' in sector_full_df.columns:
                    new_col_name = f"{scenario_name}_{sector}"
                    sector_model_data = sector_full_df[['Year', 'Historical']].rename(columns={'Historical': new_col_name}).copy()
                    all_sector_dfs.append(sector_model_data)

        if not all_sector_dfs:
            continue  # Skip this scenario if no data

        # Merge all sectors for this scenario
        scenario_df = years_df.copy()
        for df_to_merge in all_sector_dfs:
            scenario_df = pd.merge(scenario_df, df_to_merge, on='Year', how='left')
        
        # Add total for this scenario
        sector_cols = [col for col in scenario_df.columns if col.startswith(f"{scenario_name}_")]
        if sector_cols:
            scenario_df[f"{scenario_name}_Total"] = scenario_df[sector_cols].sum(axis=1, skipna=True, min_count=1)
        
        consolidated_dfs.append(scenario_df)

    if not consolidated_dfs:
        return jsonify({"status": "error", "message": "No data found for selected scenarios."}), 404

    # Merge all scenario dataframes
    comparison_df = consolidated_dfs[0]
    for i in range(1, len(consolidated_dfs)):
        # Exclude 'Year' from right df as it's already in the left df
        cols_to_use = [col for col in consolidated_dfs[i].columns if col != 'Year']
        comparison_df = pd.merge(comparison_df, consolidated_dfs[i][['Year'] + cols_to_use], on='Year', how='outer')

    # Fill NaNs with 0 for CSV
    comparison_df = comparison_df.fillna(0)

    output = BytesIO()
    comparison_df.to_csv(output, index=False, encoding='utf-8')
    output.seek(0)
    
    download_filename = f"scenario_comparison_{scenarios[0]}_vs_{scenarios[1]}_{unit}_{from_year}-{to_year}.csv"

    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=download_filename)
@app.route('/api/forecast_data/<scenario>', methods=['GET'])
def get_forecast_data(scenario):
    if app.config['CURRENT_PROJECT_PATH'] is None:
        return jsonify({'status': 'error', 'message': 'No project selected'})
    try:
        scenario_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection', scenario)
        if not os.path.exists(scenario_path):
            return jsonify({'status': 'error', 'message': f'Scenario {scenario} not found'})
        sector_files = [f for f in os.listdir(scenario_path) if f.endswith('.xlsx') and not f.startswith('_')]
        if not sector_files:
            return jsonify({'status': 'error', 'message': 'No sector data found for this scenario'})
        sector_data = {}
        for file in sector_files:
            sector_name = os.path.splitext(file)[0]
            if sector_name.lower() in ['summary', 'consolidated']:
                continue
            file_path = os.path.join(scenario_path, file)
            try:
                df = pd.read_excel(file_path, sheet_name='Results')
                if 'Year' not in df.columns:
                    print(f"Warning: 'Year' column missing in {file}")
                    continue
                years = df['Year'].dropna().apply(lambda x: int(x) if pd.api.types.is_numeric_dtype(type(x)) and not pd.isna(x) else None)
                years = years[years.notnull()].tolist()
                model_data = {}
                models = [col for col in df.columns if col != 'Year']  # List available models
                for column in models:
                    model_data[column] = [
                        None if pd.isna(value) else float(value)
                        for value in df[column].tolist()
                    ]
                sector_data[sector_name] = {
                    'years': years,
                    'models': models,  # Add available models
                    **model_data
                }
            except Exception as e:
                print(f"Error processing {file}: {str(e)}")
                continue
        if not sector_data:
            return jsonify({'status': 'error', 'message': 'Could not process any sector data'})
        return jsonify({
            'status': 'success',
            'data': sector_data
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error fetching forecast data: {str(e)}'})
@app.route('/load_profile_creation', methods=['GET', 'POST'])
def load_profile_creation():
    if app.config['CURRENT_PROJECT_PATH'] is None:
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        # Handle file upload
        if 'profile_file' not in request.files:
            flash('No file uploaded', 'warning')
            return redirect(request.url)
            
        file = request.files['profile_file']
        if file.filename == '':
            flash('No file selected', 'warning')
            return redirect(request.url)
            
        if file and file.filename.endswith('.xlsx'):
            # Save file to inputs folder
            file_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'inputs', 'load_curve_template.xlsx')
            file.save(file_path)
            flash('File uploaded successfully', 'success')
            return redirect(url_for('load_profile_creation'))
        else:
            flash('Invalid file format. Please upload an Excel file.', 'danger')
            return redirect(request.url)
    
    # Check if input file exists
    input_file_exists = False
    input_file_date = None
    input_file_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'inputs', 'load_curve_template.xlsx')
    
    if os.path.exists(input_file_path):
        input_file_exists = True
        input_file_date = datetime.fromtimestamp(os.path.getmtime(input_file_path)).strftime('%Y-%m-%d %H:%M:%S')
    
    # Get available forecast scenarios
    forecast_scenarios = []
    results_folder = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results')
    demand_projection_folder = os.path.join(results_folder, 'demand_projection')
    
    if os.path.exists(demand_projection_folder):
        forecast_scenarios = [d for d in os.listdir(demand_projection_folder) 
                            if os.path.isdir(os.path.join(demand_projection_folder, d))]
    
    # Get available years for base year selection
    available_years = []
    if input_file_exists:
        try:
            df = pd.read_excel(input_file_path, sheet_name='Past_Hourly_Demand')
            
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                years = sorted(df['date'].dt.year.unique().tolist())
                available_years = years
        except Exception as e:
            app.logger.error(f"Error reading historical years: {e}")
    
    # Get generated profiles
    generated_profiles = []
    load_profiles_folder = os.path.join(results_folder, 'load_profiles')
    
    if os.path.exists(load_profiles_folder):
        for filename in os.listdir(load_profiles_folder):
            if filename.endswith('.csv'):
                profile_path = os.path.join(load_profiles_folder, filename)
                created_date = datetime.fromtimestamp(os.path.getctime(profile_path)).strftime('%Y-%m-%d')
                
                generated_profiles.append({
                    'id': filename.replace('.csv', ''),
                    'name': filename.replace('.csv', '').replace('_', ' ').title(),
                    'created': created_date,
                    'path': profile_path
                })
    
    return render_template(
        'load_profile.html',
        input_file_exists=input_file_exists,
        input_file_date=input_file_date,
        forecast_scenarios=forecast_scenarios,
        available_years=available_years,
        generated_profiles=generated_profiles,
        current_project=app.config['CURRENT_PROJECT']
    )
# Get available scenarios
def get_available_scenarios():
    scenarios = []
    results_folder = app.config['RESULTS_FOLDER']
    demand_projection_folder = os.path.join(results_folder, 'demand_projection')
    
    if os.path.exists(demand_projection_folder):
        scenarios = [d for d in os.listdir(demand_projection_folder) 
                    if os.path.isdir(os.path.join(demand_projection_folder, d))]
    
    return scenarios

# Get available historical years
def get_available_historical_years():
    years = []
    input_file_path = os.path.join(app.config['INPUT_FOLDER'], 'load_curve_template.xlsx')
    
    if os.path.exists(input_file_path):
        try:
            # Try to read Past_Hourly_Demand sheet
            df = pd.read_excel(input_file_path, sheet_name='Past_Hourly_Demand')
            
            # Extract years from date column
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                years = sorted(df['date'].dt.year.unique().tolist())
        except Exception as e:
            app.logger.error(f"Error reading historical years: {e}")
    
    return years

# Get generated profiles
def get_generated_profiles():
    profiles = []
    results_folder = app.config['RESULTS_FOLDER']
    load_profiles_folder = os.path.join(results_folder, 'load_profiles')
    
    if os.path.exists(load_profiles_folder):
        for filename in os.listdir(load_profiles_folder):
            if filename.endswith('.csv'):
                profile_path = os.path.join(load_profiles_folder, filename)
                created_date = datetime.fromtimestamp(os.path.getctime(profile_path)).strftime('%Y-%m-%d')
                
                profiles.append({
                    'id': filename.replace('.csv', ''),
                    'name': filename.replace('.csv', '').replace('_', ' ').title(),
                    'created': created_date,
                    'path': profile_path
                })
    
    return profiles

# API endpoint to get scenario details
@app.route('/api/scenario_details/<scenario_name>', methods=['GET'])
def get_scenario_details(scenario_name):
    # Get scenario details from results folder
    results_folder = app.config['RESULTS_FOLDER']
    scenario_folder = os.path.join(results_folder, 'demand_projection', scenario_name)
    
    if not os.path.exists(scenario_folder):
        return jsonify({
            'status': 'error',
            'message': f'Scenario {scenario_name} not found'
        })
    
    # Get list of sectors from files in scenario folder
    sectors = []
    target_year = 2037  # Default
    
    for filename in os.listdir(scenario_folder):
        if filename.endswith('.xlsx') and filename != 'aggregated.xlsx':
            sectors.append(filename.replace('.xlsx', ''))
    
    # Try to get target year from metadata file if it exists
    metadata_path = os.path.join(scenario_folder, 'metadata.json')
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                target_year = metadata.get('target_year', 2037)
        except Exception as e:
            app.logger.error(f"Error reading metadata: {e}")
    
    return jsonify({
        'status': 'success',
        'scenario_name': scenario_name,
        'sectors': sectors,
        'target_year': target_year
    })

# API endpoint to generate load profiles
@app.route('/api/generate_load_profiles', methods=['POST'])
def generate_load_profiles():
    # Extract form data
    method = request.form.get('method')
    forecast_scenario = request.form.get('forecast_scenario')
    
    if method == 'base_year':
        base_year = request.form.get('base_year')
        if not base_year:
            return jsonify({
                'status': 'error',
                'message': 'Base year must be selected'
            })
    else:
        weather_data = request.form.get('weather_data')
    
    use_constraints = request.form.get('use_constraints') == 'true'
    
    # Validate inputs
    if not forecast_scenario:
        return jsonify({
            'status': 'error',
            'message': 'Forecast scenario must be selected'
        })
    
    # Process inputs and generate load profiles
    try:
        # In a real implementation, this would process the data using the algorithm
        # For this example, we'll simulate the process
        
        # Create a profile ID based on method and timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        if method == 'base_year':
            profile_id = f"{forecast_scenario}_base_year_{base_year}_{timestamp}"
        else:
            profile_id = f"{forecast_scenario}_ml_weather_{timestamp}"
        
        # Create a CSV file for the profile
        results_folder = app.config['RESULTS_FOLDER']
        load_profiles_folder = os.path.join(results_folder, 'load_profiles')
        
        # Create folder if it doesn't exist
        os.makedirs(load_profiles_folder, exist_ok=True)
        
        # Generate sample data for the profile
        # In a real implementation, this would use the actual algorithm
        # For this example, we'll create a simple sample
        output_path = os.path.join(load_profiles_folder, f"{profile_id}.csv")
        
        # Create sample data
        start_year = int(request.form.get('start_year', 2023))
        end_year = int(request.form.get('end_year', 2037))
        output_frequency = request.form.get('output_frequency', 'hourly')
        output_unit = request.form.get('output_unit', 'MW')
        
        # Generate fake profile data
        generate_sample_profile_data(output_path, start_year, end_year, output_frequency, output_unit)
        
        return jsonify({
            'status': 'success',
            'message': 'Load profiles generated successfully',
            'profile_id': profile_id,
            'details': f'Generated {output_frequency} load profile for years {start_year}-{end_year} in {output_unit}',
            'profiles': get_generated_profiles()
        })
    except Exception as e:
        app.logger.error(f"Error generating load profiles: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error generating load profiles: {str(e)}'
        })

# Generate sample profile data for demonstration
def generate_sample_profile_data(output_path, start_year, end_year, frequency, unit):
    # Create a simple sample dataset
    # In a real implementation, this would use the actual algorithm
    
    # Number of hours per year (regular year)
    hours_per_year = 8760
    
    # Placeholder for data
    data = []
    
    # Generate data for each year
    for year in range(start_year, end_year + 1):
        # Generate hourly data for this year
        for hour in range(hours_per_year):
            # Calculate date and time
            day = hour // 24 + 1
            hour_of_day = hour % 24
            
            # Simple sinusoidal pattern with yearly, weekly, and daily variations
            # Add some randomness and trends
            
            # Day of year effect (seasonal)
            day_of_year = day
            seasonal_factor = 1.0 + 0.3 * np.sin(2 * np.pi * day_of_year / 365)
            
            # Hour of day effect (daily pattern)
            hourly_factor = 1.0 + 0.5 * np.sin(2 * np.pi * (hour_of_day - 10) / 24)
            
            # Random variations
            random_factor = 1.0 + 0.1 * np.random.randn()
            
            # Yearly growth trend
            growth_factor = 1.0 + 0.03 * (year - start_year)
            
            # Combined effect
            demand = 1000 * seasonal_factor * hourly_factor * random_factor * growth_factor
            
            # Format timestamp
            timestamp = f"{year}-{day//30+1:02d}-{day%30+1:02d} {hour_of_day:02d}:00:00"
            
            data.append({
                'timestamp': timestamp,
                'demand': demand
            })
    
    # Create DataFrame and save to CSV
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)

# API endpoint to get load profile metadata
@app.route('/api/load_profile_metadata/<profile_id>', methods=['GET'])
def get_load_profile_metadata(profile_id):
    # Get profile metadata
    results_folder = app.config['RESULTS_FOLDER']
    load_profiles_folder = os.path.join(results_folder, 'load_profiles')
    profile_path = os.path.join(load_profiles_folder, f"{profile_id}.csv")
    
    if not os.path.exists(profile_path):
        return jsonify({
            'status': 'error',
            'message': f'Profile {profile_id} not found'
        })
    
    try:
        # Read profile data
        df = pd.read_csv(profile_path)
        
        # Extract available years
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        available_years = sorted(df['timestamp'].dt.year.unique().tolist())
        
        # Calculate profile statistics
        peak_demand = df['demand'].max()
        peak_date = df.loc[df['demand'].idxmax(), 'timestamp']
        avg_demand = df['demand'].mean()
        min_demand = df['demand'].min()
        min_date = df.loc[df['demand'].idxmin(), 'timestamp']
        std_dev = df['demand'].std()
        load_factor = (avg_demand / peak_demand) * 100 if peak_demand > 0 else 0
        
        # Create a summary
        summary = f"This load profile spans {len(available_years)} years from {available_years[0]} to {available_years[-1]}. " \
                 f"It has an average demand of {avg_demand:.2f} MW with a peak of {peak_demand:.2f} MW, " \
                 f"resulting in a load factor of {load_factor:.2f}%."
        
        return jsonify({
            'status': 'success',
            'profile_id': profile_id,
            'available_years': available_years,
            'profile_stats': {
                'peak_demand': peak_demand,
                'peak_date': peak_date,
                'avg_demand': avg_demand,
                'min_demand': min_demand,
                'min_date': min_date,
                'std_dev': std_dev,
                'load_factor': load_factor,
                'summary': summary
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting profile metadata: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting profile metadata: {str(e)}'
        })

# API endpoint to get load profile data for a specific year
@app.route('/api/load_profile_data/<profile_id>/<year>', methods=['GET'])
def get_load_profile_data(profile_id, year):
    # Get profile data for a specific year
    results_folder = app.config['RESULTS_FOLDER']
    load_profiles_folder = os.path.join(results_folder, 'load_profiles')
    profile_path = os.path.join(load_profiles_folder, f"{profile_id}.csv")
    
    if not os.path.exists(profile_path):
        return jsonify({
            'status': 'error',
            'message': f'Profile {profile_id} not found'
        })
    
    try:
        # Read profile data
        df = pd.read_csv(profile_path)
        
        # Extract data for the specified year
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        year_df = df[df['timestamp'].dt.year == int(year)]
        
        # Convert to list of dictionaries for JSON serialization
        profile_data = []
        for _, row in year_df.iterrows():
            profile_data.append({
                'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'demand': row['demand']
            })
        
        return jsonify({
            'status': 'success',
            'profile_id': profile_id,
            'year': year,
            'profile_data': profile_data
        })
    except Exception as e:
        app.logger.error(f"Error getting profile data: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting profile data: {str(e)}'
        })


@app.route('/pypsa_modeling')
def pypsa_modeling():
    if not app.config['CURRENT_PROJECT']:
        flash('Please select or create a project first', 'warning')
        return redirect(url_for('home'))
    
    # Check if pypsa_input_template.xlsx exists
    input_excel_path = Path(app.config['CURRENT_PROJECT_PATH']) / "inputs" / "pypsa_input_template.xlsx"
    input_file_exists = input_excel_path.exists()
    if not input_file_exists:
        flash('PyPSA input template (pypsa_input_template.xlsx) not found in project inputs folder.', 'warning')
        # Optionally, still render the page but disable run button, or redirect.
        # For now, we'll let the page render and JS can handle UI disabling.

    return render_template('pypsa_modeling.html', 
                           current_project=app.config['CURRENT_PROJECT'],
                           input_file_exists=input_file_exists)

@app.route('/api/get_pypsa_settings_from_excel', methods=['GET'])
def api_get_pypsa_settings_from_excel():
    if not app.config['CURRENT_PROJECT_PATH']:
        return jsonify({'status': 'error', 'message': 'No project selected'})

    input_file_path = Path(app.config['CURRENT_PROJECT_PATH']) / "inputs" / "pypsa_input_template.xlsx"
    if not input_file_path.exists():
        return jsonify({'status': 'error', 'message': 'PyPSA input Excel file not found.'})

    try:
        xls = pd.ExcelFile(input_file_path)

        if 'Settings' not in xls.sheet_names:
            return jsonify({'status': 'error', 'message': "'Settings' sheet not found in the Excel file."})
        
        setting_df_excel = xls.parse('Settings')
        main_settings_table = extract_tables_by_markers(setting_df_excel, '~').get('Main_Settings')
        
        if main_settings_table is None:
            return jsonify({'status': 'error', 'message': "Main_Settings table (marker: ~Main_Settings) not found in 'Settings' sheet."})

        settings_dict = {}
        for _, row in main_settings_table.iterrows():
            if pd.notna(row.get('Setting')) and pd.notna(row.get('Option')):
                # Basic type inference for numbers
                val = row['Option']
                if isinstance(val, (int, float)) and not pd.isna(val) :
                    settings_dict[row['Setting']] = int(val) if val == int(val) else float(val)
                else:
                    settings_dict[row['Setting']] = str(val)
        
        # Specific settings required by UI (add more as needed)
        ui_settings = {
            'Run Pypsa Model on': settings_dict.get('Run Pypsa Model on', 'All Snapshots'),
            'Weightings': int(settings_dict.get('Weightings', 1)),
            'Base_Year': int(settings_dict.get('Base_Year', 2025)),
            'Multi Year Investment': settings_dict.get('Multi Year Investment', 'No'),
            'Generator Cluster': settings_dict.get('Generator Cluster', 'No') == 'Yes',
            # Add other settings you want to expose or default in UI
        }

        return jsonify({'status': 'success', 'settings': ui_settings})
    except Exception as e:
        logger.error(f"Error parsing PyPSA settings from Excel: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Error parsing Excel settings: {str(e)}'})



@app.route('/api/run_pypsa_model', methods=['POST'])
def api_run_pypsa_model():
    # ... (existing code to get project_path, scenario_name) ...
    data = request.get_json()
    scenario_name = data.get('scenarioName')
    ui_settings_overrides = data.get('settings', {}) # Get all settings from UI

    if not scenario_name:
        return jsonify({'status': 'error', 'message': 'Scenario name is required'})

    job_id = str(uuid.uuid4())
    pypsa_jobs[job_id] = {
        'status': 'queued',
        'progress': 0,
        'log': [f"Job {job_id} for scenario '{scenario_name}' queued.\n"],
        'scenario_name': scenario_name,
        'project_path': app.config['CURRENT_PROJECT_PATH'],
        'start_time': datetime.now().isoformat(),
        'current_step': 'Initializing...', # Add current_step
        'result_files': None,
        'error': None
    }
    
    logger.info(f"Queuing PyPSA job {job_id} for scenario: {scenario_name} with UI overrides: {ui_settings_overrides}")

    pypsa_thread = threading.Thread(
        target=run_pypsa_model_core, # Call the refactored function
        args=(job_id, app.config['CURRENT_PROJECT_PATH'], scenario_name, ui_settings_overrides) # Pass overrides
    )
    pypsa_thread.daemon = True
    pypsa_thread.start()

    return jsonify({'status': 'started', 'jobId': job_id, 'message': f'PyPSA model run started for scenario: {scenario_name}'})




@app.route('/api/pypsa_model_status/<job_id>', methods=['GET'])
def api_get_pypsa_model_status(job_id):
    job = pypsa_jobs.get(job_id)
    if not job:
        return jsonify({'status': 'error', 'message': 'Job not found'}), 404
    
    # If completed, scan for result files
    if job['status'] == 'Completed' and job.get('result_files') is None:
        scenario_results_dir = Path(job['project_path']) / "results" / "PyPSA_Modeling" / job['scenario_name']
        if scenario_results_dir.exists():
            job['result_files'] = [f.name for f in scenario_results_dir.iterdir() if f.is_file()]
        else:
            job['result_files'] = []
            
    return jsonify(job)


@app.route('/api/pypsa_scenarios', methods=['GET'])
def api_get_pypsa_scenarios():
    if not app.config['CURRENT_PROJECT_PATH']:
        return jsonify({'status': 'error', 'message': 'No project selected', 'scenarios': []})

    scenarios_dir = Path(app.config['CURRENT_PROJECT_PATH']) / "results" / "PyPSA_Modeling"
    scenarios_data = []

    if scenarios_dir.exists():
        for scenario_path in scenarios_dir.iterdir():
            if scenario_path.is_dir():
                scenario_name = scenario_path.name
                # Basic check for a .nc file or some CSVs to consider it a valid result
                nc_files = list(scenario_path.glob('*.nc'))
                csv_files = list(scenario_path.glob('results_*/generators.csv')) # Example for single year mode
                
                status = "Unknown"
                # Try to find a job for this scenario to get its status
                # This is a simple match by name; more robust would be to store job_id with scenario
                job_found = False
                for job_id, job_info in pypsa_jobs.items():
                    if job_info['scenario_name'] == scenario_name and job_info['project_path'] == app.config['CURRENT_PROJECT_PATH']:
                        status = job_info['status']
                        job_found = True
                        break
                if not job_found and (nc_files or csv_files): # If no active job but files exist, assume completed
                    status = "Completed"

                scenarios_data.append({
                    'name': scenario_name,
                    'path': str(scenario_path),
                    'status': status,
                    'last_modified': datetime.fromtimestamp(scenario_path.stat().st_mtime).isoformat()
                })
    
    scenarios_data.sort(key=lambda x: x['last_modified'], reverse=True)
    return jsonify({'status': 'success', 'scenarios': scenarios_data})

@app.route('/api/download_pypsa_result/<scenario_name>/<path:filename>', methods=['GET'])
def download_pypsa_result_file(scenario_name, filename):
    if not app.config['CURRENT_PROJECT_PATH']:
        flash("No project loaded.", "danger")
        return redirect(url_for('pypsa_modeling'))

    scenario_dir = Path(app.config['CURRENT_PROJECT_PATH']) / "results" / "PyPSA_Modeling" / scenario_name
    
    # Secure the filename - could be a subfolder like "results_2026/generators.csv"
    # Convert filename from URL path to OS-specific path
    parts = filename.split('/')
    safe_parts = [secure_filename(part) for part in parts]
    file_to_download_path = scenario_dir.joinpath(*safe_parts)

    if file_to_download_path.is_file() and file_to_download_path.resolve().is_relative_to(scenario_dir.resolve()):
        return send_file(str(file_to_download_path.resolve()), as_attachment=True)
    else:
        flash(f"File not found or access denied: {filename}", "danger")
        return redirect(url_for('pypsa_modeling'))




@app.route('/modeling_results')
def modeling_results():
    if not app.config['CURRENT_PROJECT']:
        flash('Please select or create a project first', 'warning')
        return redirect(url_for('home'))
        
    flash('Modeling Results module is coming soon!', 'info')
    return redirect(url_for('home'))

@app.route('/user_guide')
def user_guide():
    return render_template('user_guide.html')

@app.route('/create_project', methods=['POST'])
def create_project():
    if request.method != 'POST':
        return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
    project_name = request.form.get('projectName')
    project_location = request.form.get('projectLocation', '')
    
    if not project_name:
        return jsonify({'status': 'error', 'message': 'Please provide a project name'})
    
    if not project_location:
        return jsonify({'status': 'error', 'message': 'Please select a project location'})
    
    try:
        safe_project_name = secure_filename(project_name)
        if os.path.isabs(project_location):
            project_path = os.path.join(project_location, safe_project_name)
        else:
            project_path = os.path.join(app.config['UPLOAD_FOLDER'], 'projects', project_location, safe_project_name)
        
        success = create_project_structure(project_path, app.config['TEMPLATE_FOLDER'])
        if success:
            print(f"Project created: {project_path} at {datetime.now()}")
            
            # Save to recent projects
            user_id = session.get('user_id', 'default_user')
            save_recent_project(user_id, project_name, project_path)
            
            app.config['CURRENT_PROJECT'] = project_name
            app.config['CURRENT_PROJECT_PATH'] = project_path

            return jsonify({
                'status': 'success',
                'message': f'Project "{project_name}" created successfully!',
                'project_path': project_path
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to create project structure. Check server logs for details.'
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error creating project: {str(e)}'})

@app.route('/validate_project', methods=['POST'])
def validate_project():
    if request.method != 'POST':
        return jsonify({'status': 'error', '即将message': 'Invalid request method'})
    
    project_path = request.form.get('projectPath')
    
    if not project_path:
        return jsonify({'status': 'error', 'message': 'No project path provided'})
    
    try:
        if not os.path.exists(project_path):
            return jsonify({
                'status': 'error', 
                'message': f'The path "{project_path}" does not exist'
            })
        
        validation_result = validate_project_structure(project_path)
        return jsonify(validation_result)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error validating project: {str(e)}'
        })

@app.route('/load_project', methods=['POST'])
def load_project():
    if request.method != 'POST':
        return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
    project_path = request.form.get('projectPath')
    
    if not project_path:
        return jsonify({'status': 'error use for No project path provided'})
    
    try:
        validation_result = validate_project_structure(project_path)
        
        if validation_result['status'] == 'error':
            return jsonify(validation_result)
        
        if validation_result['status'] == 'warning' and validation_result.get('can_fix', False):
            copy_missing_templates(project_path, validation_result.get('missing_templates', []), app.config['TEMPLATE_FOLDER'])
        
        project_name = os.path.basename(os.path.normpath(project_path))
        app.config['CURRENT_PROJECT'] = project_name
        app.config['CURRENT_PROJECT_PATH'] = project_path
        user_id = session.get('user_id', 'default_user')
        save_recent_project(user_id, project_name, project_path)
        return jsonify({
            'status': 'success',
            'message': 'Project loaded successfully',
            'project_path': project_path,
            'project_name': project_name
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error loading project: {str(e)}'
        })

@app.route('/download_template/<template_type>')
def download_template(template_type):
    templates = {
        'data_input': 'data_input_template.xlsx',
        'load_curve': 'load_curve_template.xlsx',
        'pypsa_input': 'pypsa_input_template.xlsx'
    }
    
    if template_type not in templates:
        flash('Template not found', 'danger')
        return redirect(url_for('home'))
    
    template_path = os.path.join(app.config['TEMPLATE_FOLDER'], templates[template_type])
    
    if not os.path.exists(template_path):
        create_template_files()
        if not os.path.exists(template_path):
            flash(f'Template file {templates[template_type]} not found', 'danger')
            return redirect(url_for('home'))
    
    return send_file(template_path, as_attachment=True)

@app.route('/download_user_guide')
def download_user_guide():
    guide_path = os.path.join(app.config['TEMPLATE_FOLDER'], 'user_guide.pdf')
    
    if not os.path.exists(guide_path):
        flash('User guide PDF not found', 'danger')
        return redirect(url_for('home'))
        
    return send_file(guide_path, as_attachment=True)

@app.route('/download_methodology')
def download_methodology():
    methodology_path = os.path.join(app.config['TEMPLATE_FOLDER'], 'methodology.pdf')
    
    if not os.path.exists(methodology_path):
        flash('Methodology PDF not found', 'danger')
        return redirect(url_for('home'))
        
    return send_file(methodology_path, as_attachment=True)

@app.route('/tutorials')
def tutorials():
    flash('Tutorials page is coming soon!', 'info')
    return redirect(url_for('home'))

@app.route('/upload_data', methods=['POST'])
def upload_data():
    if request.method == 'POST':
        if not app.config['CURRENT_PROJECT']:
            flash('Please select or create a project first', 'warning')
            return redirect(url_for('home'))
            
        if 'data_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(url_for('home'))
        
        file = request.files['data_file']
        
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(url_for('home'))
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            project_inputs_folder = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'inputs')
            os.makedirs(project_inputs_folder, exist_ok=True)
            file_path = os.path.join(project_inputs_folder, filename)
            file.save(file_path)
            flash('File uploaded successfully!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid file type. Please upload an Excel (.xlsx) file.', 'danger')
            return redirect(url_for('home'))

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# API routes
@app.route('/api/search', methods=['POST'])
def api_search():
    query = request.json.get('query', '')
    results = [
        {
            'title': 'Demand Projection',
            'type': 'Feature',
            'description': 'Generate sector-wise electricity demand projections',
            'link': url_for('demand_projection')
        },
        {
            'title': 'Data Input Template',
            'type': 'Resource',
            'description': 'Excel template for sector-wise energy demand data',
            'link': url_for('download_template', template_type='data_input')
        }
    ]
    return jsonify({'results': results})

#create_template_files()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)