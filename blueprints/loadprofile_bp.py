from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime
import shutil # For LoadProfileManager's save_uploaded_file
from werkzeug.utils import secure_filename # For LoadProfileManager

# Imports from project utils
from utils.create_load_curve import (
    check_total_demand_data, create_load_curve, load_scenario_data, 
    extract_monthly_patterns_from_excel, get_future_annual_demand
)
# No specific helpers seem to be imported from utils.helpers for these routes in app.py

loadprofile_bp = Blueprint('loadprofile', 
                           __name__, 
                           template_folder='../templates', 
                           static_folder='../static',
                           url_prefix='/load_profile')

# Helper function from app.py (if it's best placed here, or could be in a shared util)
# Re-defining handle_nan_values if it's not globally available.
# If it was moved to a central util, this import should point there.
def handle_nan_values(obj):
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: handle_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [handle_nan_values(item) for item in obj]
    return obj

# ==========================================
# LOAD PROFILE HELPER FUNCTIONS AND CLASS (Moved from app.py)
# ==========================================
class LoadProfileManager:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.inputs_folder = os.path.join(project_path, 'inputs')
        self.results_folder = os.path.join(project_path, 'results')
        self.load_profiles_folder = os.path.join(self.results_folder, 'load_profiles')
        self._ensure_directories()
    
    def _ensure_directories(self):
        os.makedirs(self.inputs_folder, exist_ok=True)
        os.makedirs(self.results_folder, exist_ok=True)
        os.makedirs(self.load_profiles_folder, exist_ok=True)
    
    def get_input_file_path(self) -> str:
        return os.path.join(self.inputs_folder, 'load_curve_template.xlsx')
    
    def check_input_file_exists(self): # Removed type hint Tuple[bool, Optional[str]] for simplicity in BP
        input_file_path = self.get_input_file_path()
        if os.path.exists(input_file_path):
            mod_time = datetime.fromtimestamp(os.path.getmtime(input_file_path))
            return True, mod_time.strftime('%Y-%m-%d %H:%M:%S')
        return False, None
    
    def get_available_years(self): # Removed type hint List[int]
        input_file_path = self.get_input_file_path()
        if not os.path.exists(input_file_path): return []
        try:
            df = pd.read_excel(input_file_path, sheet_name='Past_Hourly_Demand')
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                return sorted(df['date'].dt.year.unique().tolist())
        except Exception as e:
            current_app.logger.error(f"Error reading historical years (LPManager): {e}")
        return []
    
    def get_forecast_scenarios(self): # Removed type hint List[str]
        demand_projection_folder = os.path.join(self.results_folder, 'demand_projection')
        if not os.path.exists(demand_projection_folder): return []
        return [d for d in os.listdir(demand_projection_folder) if os.path.isdir(os.path.join(demand_projection_folder, d))]
    
    def get_generated_profiles(self): # Removed type hint List[Dict[str, Any]]
        profiles = []
        if not os.path.exists(self.load_profiles_folder): return profiles
        for filename in os.listdir(self.load_profiles_folder):
            if filename.endswith('.csv'):
                profile_path = os.path.join(self.load_profiles_folder, filename)
                created_date = datetime.fromtimestamp(os.path.getctime(profile_path))
                profiles.append({
                    'id': filename.replace('.csv', ''),
                    'name': filename.replace('.csv', '').replace('_', ' ').title(),
                    'created': created_date.strftime('%Y-%m-%d'),
                    'path': profile_path})
        profiles.sort(key=lambda x: x['created'], reverse=True)
        return profiles
    
    def save_uploaded_file(self, file) -> bool:
        if not file or not file.filename.endswith('.xlsx'): return False
        temp_path = os.path.join(self.inputs_folder, 'temp_' + secure_filename(file.filename))
        file.save(temp_path)
        valid_file = False
        try:
            with pd.ExcelFile(temp_path) as xls:
                if 'Past_Hourly_Demand' in xls.sheet_names: valid_file = True
                else: current_app.logger.warning("Required sheet 'Past_Hourly_Demand' not found in uploaded file (LPManager)")
        except Exception as e:
            current_app.logger.error(f"Error validating Excel file (LPManager): {e}")
        
        if valid_file:
            file_path = self.get_input_file_path()
            shutil.move(temp_path, file_path)
            current_app.logger.info(f"Saved valid Excel file to {file_path} (LPManager)")
            return True
        else:
            if os.path.exists(temp_path): os.remove(temp_path)
            return False
    
    def generate_profile_id(self, scenario_name, method: str, base_year = None) -> str: # Optional type hints removed
        profile_id_parts = []
        if scenario_name and scenario_name not in ["null", "undefined", ""]:
            profile_id_parts.append(scenario_name)
        else:
            profile_id_parts.append("excel_annual")
        profile_id_parts.append(method)
        if method == 'base_year' and base_year:
            profile_id_parts.append(f"by{base_year}")
        profile_id_parts.append(datetime.now().strftime('%Y%m%d%H%M%S'))
        return "_".join(profile_id_parts)
    
    def get_profile_path(self, profile_id: str) -> str:
        return os.path.join(self.load_profiles_folder, f"{profile_id}.csv")
    
    def load_profile_data(self, profile_id: str): # Optional pd.DataFrame hint removed
        profile_path = self.get_profile_path(profile_id)
        if not os.path.exists(profile_path): return None
        try:
            return pd.read_csv(profile_path)
        except Exception as e:
            current_app.logger.error(f"Error loading profile {profile_id} (LPManager): {e}")
            return None
    
    def get_profile_metadata(self, profile_id: str): # Optional Dict hint removed
        df = self.load_profile_data(profile_id)
        if df is None: return None
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            available_years = sorted(df['timestamp'].dt.year.unique().tolist())
            demand_col = 'demand' if 'demand' in df.columns else 'Demand'
            peak_demand = df[demand_col].max()
            peak_date = df.loc[df[demand_col].idxmax(), 'timestamp']
            avg_demand = df[demand_col].mean()
            min_demand = df[demand_col].min()
            min_date = df.loc[df[demand_col].idxmin(), 'timestamp']
            std_dev = df[demand_col].std()
            load_factor = (avg_demand / peak_demand) * 100 if peak_demand > 0 else 0
            summary = (f"This load profile spans {len(available_years)} years from "
                       f"{available_years[0] if available_years else 'N/A'} to "
                       f"{available_years[-1] if available_years else 'N/A'}. "
                       f"It has an average demand of {avg_demand:.2f} MW with a peak of "
                       f"{peak_demand:.2f} MW, resulting in a load factor of {load_factor:.2f}%.")
            return {
                'profile_id': profile_id, 'available_years': available_years,
                'profile_stats': {
                    'peak_demand': float(peak_demand), 'peak_date': str(peak_date),
                    'avg_demand': float(avg_demand), 'min_demand': float(min_demand),
                    'min_date': str(min_date), 'std_dev': float(std_dev),
                    'load_factor': float(load_factor), 'summary': summary}}
        except Exception as e:
            current_app.logger.error(f"Error calculating metadata for profile {profile_id} (LPManager): {e}")
            return None
            
    def get_profile_year_data(self, profile_id: str, year: int): # Optional List[Dict] hint removed
        df = self.load_profile_data(profile_id)
        if df is None: return None
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            year_df = df[df['timestamp'].dt.year == year]
            if year_df.empty: return []
            demand_col = 'demand' if 'demand' in year_df.columns else 'Demand'
            profile_data = [{'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'), 
                             'demand': float(row[demand_col])} for _, row in year_df.iterrows()]
            return profile_data
        except Exception as e:
            current_app.logger.error(f"Error getting year data for profile {profile_id}, year {year} (LPManager): {e}")
            return None

def validate_load_profile_form(form_data): # Dict hint removed, Tuple hint removed
    errors = {}
    method = form_data.get('method')
    if not method or method not in ['base_year', 'ml_weather']: errors['method'] = 'Valid method is required'
    if method == 'base_year':
        base_year = form_data.get('base_year')
        if not base_year: errors['base_year'] = 'Base year is required for base year method'
        else:
            try:
                base_year_int = int(base_year)
                if base_year_int < 2000 or base_year_int > datetime.now().year:
                    errors['base_year'] = f'Base year must be between 2000 and {datetime.now().year}'
            except (ValueError, TypeError): errors['base_year'] = 'Base year must be a valid integer'
    try:
        start_year = int(form_data.get('start_year', datetime.now().year))
        end_year = int(form_data.get('end_year', datetime.now().year + 14))
        if start_year >= end_year: errors['year_range'] = 'End year must be greater than start year'
        if end_year - start_year > 50: errors['year_range'] = 'Year range cannot exceed 50 years'
    except (ValueError, TypeError): errors['year_range'] = 'Invalid year range values'
    if form_data.get('output_frequency', 'hourly') not in ['hourly', 'half_hourly', '15min']: errors['output_frequency'] = 'Invalid output frequency'
    if form_data.get('output_unit', 'MW') not in ['MW', 'kW', 'GW']: errors['output_unit'] = 'Invalid output unit'
    if form_data.get('use_improved_load_factors') == 'true':
        lf_improvement = form_data.get('load_factor_improvement')
        if lf_improvement:
            try:
                if not (0 <= float(lf_improvement) <= 10): errors['load_factor_improvement'] = 'Load factor improvement must be between 0 and 10%'
            except (ValueError, TypeError): errors['load_factor_improvement'] = 'Load factor improvement must be a valid number'
    return len(errors) == 0, errors

def parse_load_factor_form_data(form_data): # Dict hint removed
    load_factor_config = {
        'use_improved_load_factors': form_data.get('use_improved_load_factors') == 'true',
        'load_factor_improvement': None, 'custom_load_factors': None,
        'use_excel_load_factors': form_data.get('use_excel_load_factors') == 'true',
        'use_monthly_excel_load_factors': form_data.get('use_monthly_excel_load_factors') == 'true'}
    lf_improvement_str = form_data.get('load_factor_improvement')
    if lf_improvement_str:
        try: load_factor_config['load_factor_improvement'] = float(lf_improvement_str)
        except (ValueError, TypeError): current_app.logger.warning(f"Invalid load factor improvement value: {lf_improvement_str}")
    custom_lf_json = form_data.get('custom_load_factors')
    if custom_lf_json:
        try: load_factor_config['custom_load_factors'] = {int(k): float(v) for k, v in json.loads(custom_lf_json).items()}
        except (json.JSONDecodeError, ValueError, TypeError) as e: current_app.logger.warning(f"Invalid custom load factors JSON: {e}")
    return load_factor_config

def _handle_file_upload(lp_manager: LoadProfileManager):
    current_app.logger.info("Processing POST request to load_profile_creation via LP_BP")
    if 'profile_file' not in request.files:
        flash('No file uploaded', 'warning')
        return redirect(request.url)
    file = request.files['profile_file']
    if file.filename == '':
        flash('No file selected', 'warning')
        return redirect(request.url)
    if file and file.filename.endswith('.xlsx'):
        if lp_manager.save_uploaded_file(file): flash('File uploaded successfully', 'success')
        else: flash('The Excel file must contain a "Past_Hourly_Demand" sheet', 'danger')
    else: flash('Invalid file format. Please upload an Excel file.', 'danger')
    return redirect(url_for('loadprofile.load_profile_creation_route')) # Point to BP route

def _render_load_profile_page(lp_manager: LoadProfileManager):
    current_app.logger.info("Rendering load profile creation page via LP_BP")
    input_file_exists, input_file_date = lp_manager.check_input_file_exists()
    forecast_scenarios = lp_manager.get_forecast_scenarios()
    available_years = lp_manager.get_available_years() if input_file_exists else []
    generated_profiles = lp_manager.get_generated_profiles()
    return render_template('load_profile.html',
                           input_file_exists=input_file_exists, input_file_date=input_file_date,
                           forecast_scenarios=forecast_scenarios, available_years=available_years,
                           generated_profiles=generated_profiles, current_project=current_app.config.get('CURRENT_PROJECT'))

def _calculate_projected_metrics(start_year: int, end_year: int, base_months, base_monthly_shares, 
                               base_monthly_load_factors, future_annual_demands_gwh): # Type hints removed
    projected_data = []
    days_in_month_map = {'Jan': 31, 'Feb': 28, 'Mar': 31, 'Apr': 30, 'May': 31, 'Jun': 30,
                         'Jul': 31, 'Aug': 31, 'Sep': 30, 'Oct': 31, 'Nov': 30, 'Dec': 31}
    for year_fy in range(start_year, end_year + 1):
        annual_total_gwh = future_annual_demands_gwh.get(year_fy, 0)
        if annual_total_gwh == 0: current_app.logger.warning(f"Annual total demand for FY {year_fy} is 0.")
        monthly_metrics_for_year = []
        sum_monthly_avg_demand_mw = 0
        max_monthly_max_demand_mw = 0
        for month_name in base_months:
            share = base_monthly_shares.get(month_name, 0)
            base_lf = base_monthly_load_factors.get(month_name, 0)
            days = days_in_month_map[month_name]
            projected_total_gwh = annual_total_gwh * share
            projected_total_mwh = projected_total_gwh * 1000
            projected_avg_mw = projected_total_mwh / (days * 24) if days > 0 else 0
            projected_max_mw = projected_avg_mw / base_lf if base_lf > 0 else (0 if projected_avg_mw == 0 else float('inf'))
            projected_lf_percent = (projected_avg_mw / projected_max_mw * 100) if projected_max_mw > 0 and projected_max_mw != float('inf') else 0
            monthly_metrics_for_year.append({
                'month': month_name, 'totalDemand_GWh': round(projected_total_gwh, 2),
                'avgDemand_MW': round(projected_avg_mw, 2), 'maxDemand_MW': round(projected_max_mw, 2) if projected_max_mw != float('inf') else 'inf',
                'loadFactor_Percent': round(projected_lf_percent, 1)})
            sum_monthly_avg_demand_mw += projected_avg_mw
            if projected_max_mw != float('inf'): max_monthly_max_demand_mw = max(max_monthly_max_demand_mw, projected_max_mw)
        
        avg_of_monthly_avg_demands = sum_monthly_avg_demand_mw / 12 if sum_monthly_avg_demand_mw > 0 else 0
        yearly_load_factor_percent = (avg_of_monthly_avg_demands / max_monthly_max_demand_mw * 100) if max_monthly_max_demand_mw > 0 else 0
        projected_data.append({'year': year_fy, 'annualTotal_GWh': round(annual_total_gwh, 2),
                               'monthlyData': monthly_metrics_for_year, 
                               'yearlyLoadFactor_Percent': round(yearly_load_factor_percent, 1)})
    return projected_data

def _extract_generation_parameters(form_data): # Dict hint removed
    params = {'method': form_data.get('method'),
              'forecast_scenario_name': form_data.get('forecast_scenario'),
              'base_year': int(form_data['base_year']) if form_data.get('base_year') and form_data['method'] == 'base_year' else None,
              'use_constraints': form_data.get('use_constraints') == 'true',
              'start_year': int(form_data.get('start_year', datetime.now().year)),
              'end_year': int(form_data.get('end_year', datetime.now().year + 14)),
              'output_frequency': form_data.get('output_frequency', 'hourly'),
              'output_unit': form_data.get('output_unit', 'MW')}
    params.update(parse_load_factor_form_data(form_data))
    return params

def _generate_load_profile(input_file_path: str, scenario_data, params): # Optional Dict, Optional pd.DataFrame hints removed
    year_range_dict = {'Start_Year': params['start_year'], 'End_Year': params['end_year']}
    # create_load_curve is imported from utils.create_load_curve
    return create_load_curve(
        excel_file_path=input_file_path, base_year=params.get('base_year'),
        scenario_data=scenario_data, year_range=year_range_dict, method=params['method'],
        apply_constraints=params['use_constraints'],
        improved_load_factor=params.get('load_factor_improvement'),
        future_load_factors=params.get('custom_load_factors'),
        use_excel_load_factors=params.get('use_excel_load_factors', False),
        output_frequency=params['output_frequency'])

def _apply_unit_conversion(df: pd.DataFrame, output_unit: str):
    if 'Demand' not in df.columns: return
    if output_unit == 'kW': df['Demand'] *= 1000
    elif output_unit == 'GW': df['Demand'] /= 1000

# Routes
@loadprofile_bp.route('/', methods=['GET', 'POST']) # Was /load_profile
def load_profile_base_route(): # Renamed
    current_app.logger.info("Accessed /load_profile base route (LP_BP) - redirecting")
    return redirect(url_for('loadprofile.load_profile_creation_route'))

@loadprofile_bp.route('/creation', methods=['GET', 'POST']) # Was /load_profile_creation
def load_profile_creation_route(): # Renamed
    current_app.logger.info("Accessing load_profile_creation route via LP_BP")
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('core.home')) # To core blueprint
    lp_manager = LoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
    try:
        if request.method == 'POST': return _handle_file_upload(lp_manager)
        return _render_load_profile_page(lp_manager)
    except Exception as e:
        current_app.logger.exception(f"Error in load_profile_creation_route (LP_BP): {str(e)}")
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('core.home'))

# API Routes
@loadprofile_bp.route('/api/projected_future_metrics/<int:base_year>/<int:start_year>/<int:end_year>', methods=['GET'])
def get_projected_future_metrics_api(base_year: int, start_year: int, end_year: int): # Renamed
    current_app.logger.info(f"API call: projected_future_metrics for base_year={base_year}, range={start_year}-{end_year} (LP_BP)")
    if not current_app.config.get('CURRENT_PROJECT_PATH'): return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    if start_year >= end_year: return jsonify({'status': 'error', 'message': 'End year must be greater than start year'}), 400
    if end_year - start_year > 50: return jsonify({'status': 'error', 'message': 'Year range cannot exceed 50 years'}), 400
    
    lp_manager = LoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
    excel_file_path = lp_manager.get_input_file_path()
    if not os.path.exists(excel_file_path): return jsonify({'status': 'error', 'message': 'Load curve input Excel file not found.'}), 404
    
    try:
        forecast_scenario = request.args.get('forecast_scenario')
        # extract_monthly_patterns_from_excel and get_future_annual_demand are imported
        base_year_patterns = extract_monthly_patterns_from_excel(excel_file_path, base_year)
        base_months = base_year_patterns['months']
        raw_shares = base_year_patterns['patternData'].get('Share of Annual (%)', [0]*12)
        raw_load_factors = base_year_patterns['patternData'].get('Load Factor (%)', [0]*12)
        base_monthly_shares = {m: float(s)/100.0 if s is not None else 0 for m, s in zip(base_months, raw_shares)}
        base_monthly_load_factors = {m: float(lf)/100.0 if lf is not None else 0 for m, lf in zip(base_months, raw_load_factors)}
        
        scenario_name = forecast_scenario if forecast_scenario and forecast_scenario not in ["null", "undefined"] else None
        future_annual_demands_gwh = get_future_annual_demand(current_app.config['CURRENT_PROJECT_PATH'], start_year, end_year, scenario_name)
        if not future_annual_demands_gwh: current_app.logger.warning(f"No future annual demand data for {start_year}-{end_year} (scenario: {scenario_name})")
            
        projected_data = _calculate_projected_metrics(start_year, end_year, base_months, base_monthly_shares, base_monthly_load_factors, future_annual_demands_gwh)
        return jsonify({'status': 'success', 'data': handle_nan_values(projected_data), 'baseYearMonths': base_months})
    except Exception as e:
        current_app.logger.exception(f"Error in get_projected_future_metrics_api (LP_BP): {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@loadprofile_bp.route('/api/monthly_patterns/<int:base_year>', methods=['GET'])
def get_monthly_patterns_api(base_year: int): # Renamed
    current_app.logger.info(f"Processing request for monthly patterns for year {base_year} (LP_BP)")
    if not current_app.config.get('CURRENT_PROJECT_PATH'): return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    if not (2000 <= base_year <= datetime.now().year): return jsonify({'status': 'error', 'message': f'Base year must be between 2000 and {datetime.now().year}'}), 400
    
    lp_manager = LoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
    input_file_path = lp_manager.get_input_file_path()
    if not os.path.exists(input_file_path): return jsonify({'status': 'error', 'message': 'Input file not found'}), 404
    
    try:
        patterns = extract_monthly_patterns_from_excel(input_file_path, base_year)
        return jsonify({'status': 'success', 'months': patterns['months'], 
                        'patternData': handle_nan_values(patterns['patternData']), 
                        'yearlyLoadFactor': handle_nan_values(patterns.get('yearlyLoadFactor', 0)),
                        'calculatedFromExcel': True})
    except Exception as e:
        current_app.logger.exception(f"Error generating monthly patterns (LP_BP): {e}")
        return jsonify({'status': 'error', 'message': f'Error generating monthly patterns: {str(e)}'}), 500

@loadprofile_bp.route('/api/generate_load_profiles', methods=['POST'])
def generate_load_profiles_api(): # Renamed
    current_app.logger.info("Processing API request to generate_load_profiles via LP_BP")
    if not current_app.config.get('CURRENT_PROJECT_PATH'): return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    try:
        lp_manager = LoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        input_file_path = lp_manager.get_input_file_path()
        if not os.path.exists(input_file_path): return jsonify({'status': 'error', 'message': 'Load curve template file not found'}), 404
        
        form_data = dict(request.form)
        is_valid, validation_errors = validate_load_profile_form(form_data)
        if not is_valid: return jsonify({'status': 'error', 'message': f'Validation errors: {"; ".join(validation_errors.values())}'}), 400
        
        generation_params = _extract_generation_parameters(form_data)
        scenario_data = None
        scenario_name = generation_params['forecast_scenario_name']
        if scenario_name and scenario_name not in ["null", "undefined", ""]:
            scenario_data = load_scenario_data(current_app.config['CURRENT_PROJECT_PATH'], scenario_name) # Imported function
        
        # check_total_demand_data is imported
        if not check_total_demand_data(input_file_path) and not (scenario_data and scenario_data.get('Consolidated Electricity Demand')):
            if not scenario_name or scenario_name in ["null", "undefined", ""]:
                return jsonify({'status': 'error', 'message': 'Please select a forecast scenario or provide Total Demand data in Excel.'}), 400
        
        profile_id = lp_manager.generate_profile_id(scenario_name, generation_params['method'], generation_params.get('base_year'))
        output_path = lp_manager.get_profile_path(profile_id)
        load_forecast_df = _generate_load_profile(input_file_path, scenario_data, generation_params)
        
        if load_forecast_df is None or load_forecast_df.empty:
            return jsonify({'status': 'error', 'message': 'Failed to generate load profile. Result was empty.'}), 500
        
        _apply_unit_conversion(load_forecast_df, generation_params['output_unit'])
        load_forecast_df.to_csv(output_path, index=False)
        generated_profiles = lp_manager.get_generated_profiles()
        
        return jsonify({'status': 'success', 'message': 'Load profiles generated successfully!', 
                        'profile_id': profile_id, 
                        'details': f'Generated {generation_params["output_frequency"]} load profile for years {generation_params["start_year"]}-{generation_params["end_year"]} in {generation_params["output_unit"]}.', 
                        'profiles': handle_nan_values(generated_profiles)})
    except Exception as e:
        current_app.logger.exception(f"Error in generate_load_profiles_api (LP_BP): {e}")
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500

@loadprofile_bp.route('/api/metadata/<profile_id>', methods=['GET']) # Was /api/load_profile_metadata/
def get_load_profile_metadata_api(profile_id): # Renamed
    current_app.logger.info(f"Processing API request for load_profile_metadata/{profile_id} via LP_BP")
    if not current_app.config.get('CURRENT_PROJECT_PATH'): return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    if not profile_id or not profile_id.strip(): return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
    try:
        lp_manager = LoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        metadata = lp_manager.get_profile_metadata(profile_id)
        if metadata is None: return jsonify({'status': 'error', 'message': f'Profile {profile_id} not found'}), 404
        return jsonify({'status': 'success', **handle_nan_values(metadata)})
    except Exception as e:
        current_app.logger.exception(f"Error getting profile metadata for {profile_id} (LP_BP): {e}")
        return jsonify({'status': 'error', 'message': f'Error getting profile metadata: {str(e)}'}), 500

@loadprofile_bp.route('/api/data/<profile_id>/<year>', methods=['GET']) # Was /api/load_profile_data/
def get_load_profile_data_api(profile_id, year): # Renamed
    current_app.logger.info(f"Processing API request for load_profile_data/{profile_id}/{year} via LP_BP")
    if not current_app.config.get('CURRENT_PROJECT_PATH'): return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    if not profile_id or not profile_id.strip(): return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
    try:
        year_int = int(year)
        if not (2000 <= year_int <= 2100): return jsonify({'status': 'error', 'message': 'Invalid year'}), 400
    except (ValueError, TypeError): return jsonify({'status': 'error', 'message': 'Year must be a valid integer'}), 400
    
    try:
        lp_manager = LoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        profile_data = lp_manager.get_profile_year_data(profile_id, year_int)
        if profile_data is None: return jsonify({'status': 'error', 'message': f'Profile {profile_id} not found'}), 404
        return jsonify({'status': 'success', 'profile_id': profile_id, 'year': year, 
                        'profile_data': handle_nan_values(profile_data)})
    except Exception as e:
        current_app.logger.exception(f"Error getting profile data for {profile_id}/{year} (LP_BP): {e}")
        return jsonify({'status': 'error', 'message': f'Error getting profile data: {str(e)}'}), 500
