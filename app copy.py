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
import traceback
import logging
import threading
import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
from utils.create_load_curve import (
    check_total_demand_data, create_load_curve, load_scenario_data, 
    extract_monthly_patterns_from_excel, get_future_annual_demand
)

# Set up logging configuration
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Application starting")

# Import helper functions
try:
    from utils.data_loading import input_demand_data
    from utils.helpers import create_project_structure, validate_project_structure, copy_missing_templates, extract_tables_by_markers
    from utils.plots import generate_area_chart, generate_correlation_plot
    from utils.pypsa_runner import run_pypsa_model_core
    from utils.features_manager import *
    
    # For the forecasting function that will be imported later
    from models.forecasting import Main_forecasting_function
    
    from statsmodels.tsa.seasonal import STL
    from sklearn.linear_model import LinearRegression
    import holidays
    
    logger.info("Successfully imported utility modules")
except ImportError as e:
    logger.critical(f"Failed to import required modules: {e}")
    # We'll let the application start and handle specific import errors at runtime

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'energy_demand_forecasting_secret_key'  # Change in production

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

# Global job tracking
forecast_jobs = {}
pypsa_jobs = {}

# Initialize feature manager
from flask import current_app, g

def init_feature_manager(app):
    app.feature_manager = FeatureManager(app)
    
    @app.context_processor
    def feature_processor():
        def is_used(feature_id):
            """Check if a feature is enabled for the current project"""
            project_path = app.config.get('CURRENT_PROJECT_PATH')
            return app.feature_manager.is_feature_enabled(feature_id, project_path)
        
        def get_enabled_features():
            """Get a list of all enabled features for the current project"""
            project_path = app.config.get('CURRENT_PROJECT_PATH')
            return app.feature_manager.get_enabled_features(project_path)
        
        return dict(is_used=is_used, get_enabled_features=get_enabled_features)
    
    return app.feature_manager

# Initialize the feature manager
feature_manager = init_feature_manager(app)

# Configuration validation function
def validate_app_config():
    """Validate critical configuration settings"""
    logger.info("Validating application configuration")
    
    required_config = [
        'UPLOAD_FOLDER',
        'TEMPLATE_FOLDER',
        'ALLOWED_EXTENSIONS',
    ]
    
    optional_but_important = [
        'CURRENT_PROJECT',
        'CURRENT_PROJECT_PATH',
    ]
    
    # Check required config
    missing = [key for key in required_config if key not in app.config or not app.config[key]]
    if missing:
        logger.critical(f"Missing required configuration keys: {missing}")
    
    # Log status of important config
    for key in optional_but_important:
        if key not in app.config or not app.config[key]:
            logger.warning(f"Configuration key '{key}' is not set")
        else:
            logger.debug(f"Configuration '{key}' = '{app.config[key]}'")
    
    # Check that folders exist
    for key in ['UPLOAD_FOLDER', 'TEMPLATE_FOLDER']:
        if key in app.config and app.config[key]:
            folder = app.config[key]
            if not os.path.exists(folder):
                logger.warning(f"Folder for {key} does not exist: {folder}")
                try:
                    os.makedirs(folder, exist_ok=True)
                    logger.info(f"Created missing folder: {folder}")
                except Exception as e:
                    logger.error(f"Failed to create folder {folder}: {str(e)}")

# Call validation at startup
validate_app_config()

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def allowed_file(filename):
    """Check if a file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_recent_activities():
    """Get recent user activities (placeholder for actual implementation)"""
    logger.debug("Fetching recent activities")
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
    """Create template files if they don't exist"""
    logger.info("Creating template files if needed")
    try:
        # Implementation would go here
        pass
    except Exception as e:
        logger.error(f"Error creating template files: {e}")

def save_recent_project(user_id, project_name, project_path):
    """Save project to recent projects list"""
    logger.info(f"Saving recent project: '{project_name}' at '{project_path}' for user '{user_id}'")
    try:
        # Filename based on user ID
        filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        
        # Load existing data or create new
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                recent_projects = json.load(f)
                logger.debug(f"Loaded {len(recent_projects)} existing recent projects")
        else:
            recent_projects = []
            logger.debug("No existing recent projects file, creating new")
        
        # Check if project already exists
        existing_index = None
        for i, project in enumerate(recent_projects):
            if project.get('path') == project_path:
                existing_index = i
                break
        
        # Remove if exists
        if existing_index is not None:
            logger.debug(f"Project already exists at index {existing_index}, removing")
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
        
        logger.info(f"Successfully saved recent project for user {user_id}")
        return True
    except Exception as e:
        logger.exception(f"Error saving recent project: {e}")
        return False

def get_forecast_data_for_sector(scenario_path, sector, from_year, to_year, unit):
    """Helper function to get forecast data for a specific sector"""
    logger.debug(f"Getting forecast data for sector '{sector}' in path '{scenario_path}'")
    try:
        file_path = os.path.join(scenario_path, f"{sector}.xlsx")
        if not os.path.exists(file_path):
            logger.warning(f"Sector file not found: {file_path}")
            return None
        
        df = pd.read_excel(file_path, sheet_name='Results')
        if 'Year' not in df.columns:
            logger.warning(f"'Year' column missing in {file_path}")
            return None
        
        # Filter years
        df = df[(df['Year'] >= from_year) & (df['Year'] <= to_year)]
        
        # Convert units if needed
        if unit != 'TWh' and 'unit_conversion' in df.columns:
            # Implement unit conversion logic
            pass
        
        return df
    except Exception as e:
        logger.exception(f"Error getting forecast data for sector {sector}: {e}")
        return None

def handle_nan_values(obj):
    """Convert NaN values to null for JSON serialization"""
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: handle_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [handle_nan_values(item) for item in obj]
    return obj

# ==========================================
# LOAD PROFILE HELPER FUNCTIONS
# ==========================================

class LoadProfileManager:
    """Manager class for load profile operations"""
    
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.inputs_folder = os.path.join(project_path, 'inputs')
        self.results_folder = os.path.join(project_path, 'results')
        self.load_profiles_folder = os.path.join(self.results_folder, 'load_profiles')
        self.pypsa_results_folder=os.path.join(self.results_folder, 'Pypsa_results')
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        os.makedirs(self.inputs_folder, exist_ok=True)
        os.makedirs(self.results_folder, exist_ok=True)
        os.makedirs(self.load_profiles_folder, exist_ok=True)
    
    def get_input_file_path(self) -> str:
        """Get the path to the load curve template file"""
        return os.path.join(self.inputs_folder, 'load_curve_template.xlsx')
    
    def check_input_file_exists(self) -> Tuple[bool, Optional[str]]:
        """Check if input file exists and return its modification date"""
        input_file_path = self.get_input_file_path()
        if os.path.exists(input_file_path):
            mod_time = datetime.fromtimestamp(os.path.getmtime(input_file_path))
            return True, mod_time.strftime('%Y-%m-%d %H:%M:%S')
        return False, None
    
    def get_available_years(self) -> List[int]:
        """Get available years from historical data"""
        input_file_path = self.get_input_file_path()
        if not os.path.exists(input_file_path):
            return []
        
        try:
            df = pd.read_excel(input_file_path, sheet_name='Past_Hourly_Demand')
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                years = sorted(df['date'].dt.year.unique().tolist())
                return years
        except Exception as e:
            logger.error(f"Error reading historical years: {e}")
        
        return []
    
    def get_forecast_scenarios(self) -> List[str]:
        """Get available forecast scenarios"""
        demand_projection_folder = os.path.join(self.results_folder, 'demand_projection')
        if not os.path.exists(demand_projection_folder):
            return []
        
        scenarios = [
            d for d in os.listdir(demand_projection_folder) 
            if os.path.isdir(os.path.join(demand_projection_folder, d))
        ]
        return scenarios
    
    def get_generated_profiles(self) -> List[Dict[str, Any]]:
        """Get list of generated load profiles"""
        profiles = []
        if not os.path.exists(self.load_profiles_folder):
            return profiles
        
        for filename in os.listdir(self.load_profiles_folder):
            if filename.endswith('.csv'):
                profile_path = os.path.join(self.load_profiles_folder, filename)
                created_date = datetime.fromtimestamp(os.path.getctime(profile_path))
                
                profiles.append({
                    'id': filename.replace('.csv', ''),
                    'name': filename.replace('.csv', '').replace('_', ' ').title(),
                    'created': created_date.strftime('%Y-%m-%d'),
                    'path': profile_path
                })
        
        # Sort by creation date (newest first)
        profiles.sort(key=lambda x: x['created'], reverse=True)
        return profiles
    
    def save_uploaded_file(self, file) -> bool:
        """Save uploaded file and validate it"""
        if not file or not file.filename.endswith('.xlsx'):
            return False
        
        # Save file temporarily to validate
        temp_path = os.path.join(self.inputs_folder, 'temp_' + secure_filename(file.filename))
        file.save(temp_path)
        
        # Validate the file has the required Past_Hourly_Demand sheet
        valid_file = False
        try:
            with pd.ExcelFile(temp_path) as xls:
                if 'Past_Hourly_Demand' in xls.sheet_names:
                    valid_file = True
                else:
                    logger.warning("Required sheet 'Past_Hourly_Demand' not found in uploaded file")
        except Exception as e:
            logger.error(f"Error validating Excel file: {e}")
        
        if valid_file:
            # Save file to inputs folder with standard name
            file_path = self.get_input_file_path()
            shutil.move(temp_path, file_path)
            logger.info(f"Saved valid Excel file to {file_path}")
            return True
        else:
            # Remove temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
    
    def generate_profile_id(self, scenario_name: Optional[str], method: str, base_year: Optional[int] = None) -> str:
        """Generate a unique profile ID"""
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
        """Get the file path for a profile ID"""
        return os.path.join(self.load_profiles_folder, f"{profile_id}.csv")
    
    def load_profile_data(self, profile_id: str) -> Optional[pd.DataFrame]:
        """Load profile data from file"""
        profile_path = self.get_profile_path(profile_id)
        if not os.path.exists(profile_path):
            return None
        
        try:
            return pd.read_csv(profile_path)
        except Exception as e:
            logger.error(f"Error loading profile {profile_id}: {e}")
            return None
    
    def get_profile_metadata(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a profile"""
        df = self.load_profile_data(profile_id)
        if df is None:
            return None
        
        try:
            # Convert timestamp column
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Extract available years
            available_years = sorted(df['timestamp'].dt.year.unique().tolist())
            
            # Calculate profile statistics
            demand_col = 'demand' if 'demand' in df.columns else 'Demand'
            
            peak_demand = df[demand_col].max()
            peak_date = df.loc[df[demand_col].idxmax(), 'timestamp']
            avg_demand = df[demand_col].mean()
            min_demand = df[demand_col].min()
            min_date = df.loc[df[demand_col].idxmin(), 'timestamp']
            std_dev = df[demand_col].std()
            load_factor = (avg_demand / peak_demand) * 100 if peak_demand > 0 else 0
            
            # Create summary
            summary = (f"This load profile spans {len(available_years)} years from "
                      f"{available_years[0] if available_years else 'N/A'} to "
                      f"{available_years[-1] if available_years else 'N/A'}. "
                      f"It has an average demand of {avg_demand:.2f} MW with a peak of "
                      f"{peak_demand:.2f} MW, resulting in a load factor of {load_factor:.2f}%.")
            
            return {
                'profile_id': profile_id,
                'available_years': available_years,
                'profile_stats': {
                    'peak_demand': float(peak_demand),
                    'peak_date': str(peak_date),
                    'avg_demand': float(avg_demand),
                    'min_demand': float(min_demand),
                    'min_date': str(min_date),
                    'std_dev': float(std_dev),
                    'load_factor': float(load_factor),
                    'summary': summary
                }
            }
        except Exception as e:
            logger.error(f"Error calculating metadata for profile {profile_id}: {e}")
            return None
    
    def get_profile_year_data(self, profile_id: str, year: int) -> Optional[List[Dict]]:
        """Get profile data for a specific year"""
        df = self.load_profile_data(profile_id)
        if df is None:
            return None
        
        try:
            # Convert timestamp column
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter for the specified year
            year_df = df[df['timestamp'].dt.year == year]
            
            if year_df.empty:
                return []
            
            # Convert to list of dictionaries
            demand_col = 'demand' if 'demand' in year_df.columns else 'Demand'
            profile_data = []
            
            for _, row in year_df.iterrows():
                profile_data.append({
                    'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'demand': float(row[demand_col])
                })
            
            return profile_data
        except Exception as e:
            logger.error(f"Error getting year data for profile {profile_id}, year {year}: {e}")
            return None

def validate_load_profile_form(form_data: Dict) -> Tuple[bool, Dict[str, str]]:
    """Validate load profile generation form data"""
    errors = {}
    
    # Validate method
    method = form_data.get('method')
    if not method or method not in ['base_year', 'ml_weather']:
        errors['method'] = 'Valid method is required'
    
    # Validate base year if method is base_year
    if method == 'base_year':
        base_year = form_data.get('base_year')
        if not base_year:
            errors['base_year'] = 'Base year is required for base year method'
        else:
            try:
                base_year_int = int(base_year)
                current_year = datetime.now().year
                if base_year_int < 2000 or base_year_int > current_year:
                    errors['base_year'] = f'Base year must be between 2000 and {current_year}'
            except (ValueError, TypeError):
                errors['base_year'] = 'Base year must be a valid integer'
    
    # Validate year range
    try:
        start_year = int(form_data.get('start_year', datetime.now().year))
        end_year = int(form_data.get('end_year', datetime.now().year + 14))
        
        if start_year >= end_year:
            errors['year_range'] = 'End year must be greater than start year'
        
        if end_year - start_year > 50:
            errors['year_range'] = 'Year range cannot exceed 50 years'
    except (ValueError, TypeError):
        errors['year_range'] = 'Invalid year range values'
    
    # Validate output settings
    output_frequency = form_data.get('output_frequency', 'hourly')
    if output_frequency not in ['hourly', 'half_hourly', '15min']:
        errors['output_frequency'] = 'Invalid output frequency'
    
    output_unit = form_data.get('output_unit', 'MW')
    if output_unit not in ['MW', 'kW', 'GW']:
        errors['output_unit'] = 'Invalid output unit'
    
    # Validate load factor improvement if specified
    if form_data.get('use_improved_load_factors') == 'true':
        lf_improvement = form_data.get('load_factor_improvement')
        if lf_improvement:
            try:
                lf_value = float(lf_improvement)
                if lf_value < 0 or lf_value > 10:
                    errors['load_factor_improvement'] = 'Load factor improvement must be between 0 and 10%'
            except (ValueError, TypeError):
                errors['load_factor_improvement'] = 'Load factor improvement must be a valid number'
    
    return len(errors) == 0, errors

def parse_load_factor_form_data(form_data: Dict) -> Dict[str, Any]:
    """Parse and structure load factor related form data"""
    load_factor_config = {
        'use_improved_load_factors': form_data.get('use_improved_load_factors') == 'true',
        'load_factor_improvement': None,
        'custom_load_factors': None,
        'use_excel_load_factors': form_data.get('use_excel_load_factors') == 'true',
        'use_monthly_excel_load_factors': form_data.get('use_monthly_excel_load_factors') == 'true'
    }
    
    # Parse load factor improvement
    lf_improvement_str = form_data.get('load_factor_improvement')
    if lf_improvement_str:
        try:
            load_factor_config['load_factor_improvement'] = float(lf_improvement_str)
        except (ValueError, TypeError):
            logger.warning(f"Invalid load factor improvement value: {lf_improvement_str}")
    
    # Parse custom load factors
    custom_lf_json = form_data.get('custom_load_factors')
    if custom_lf_json:
        try:
            custom_lf_dict = json.loads(custom_lf_json)
            # Convert keys to int and values to float
            load_factor_config['custom_load_factors'] = {
                int(k): float(v) for k, v in custom_lf_dict.items()
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"Invalid custom load factors JSON: {e}")
    
    return load_factor_config

# ==========================================
# CONTEXT PROCESSOR
# ==========================================

@app.context_processor
def utility_processor():
    def is_used(feature_id):
        # In a real implementation, this would check the database or session
        # For demo, return True for specific features
        return feature_id in ['demand-projection', 'load-curve']
    return dict(is_used=is_used)

# ==========================================
# ROUTES - NON-LOAD-PROFILE (UNCHANGED)
# ==========================================

@app.route('/admin/features')
def feature_management():
    if app.config['CURRENT_PROJECT_PATH'] is None:
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('home'))
    
    return render_template('feature_management.html',
                           current_project=app.config['CURRENT_PROJECT'])

@app.route('/api/features', methods=['GET'])
def get_features():
    """Get all features and their status"""
    logger.info("Processing API request for features list")
    
    if not app.config['CURRENT_PROJECT_PATH']:
        logger.warning("No project selected for features request")
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    try:
        project_path = app.config['CURRENT_PROJECT_PATH']
        features = app.feature_manager.get_merged_features(project_path)
        
        return jsonify({
            'status': 'success',
            'features': features.get('features', {}),
            'feature_groups': features.get('feature_groups', {})
        })
    except Exception as e:
        logger.exception(f"Error getting features: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/features/<feature_id>', methods=['PUT'])
def update_feature(feature_id):
    """Enable or disable a feature"""
    logger.info(f"Processing API request to update feature {feature_id}")
    
    if not app.config['CURRENT_PROJECT_PATH']:
        logger.warning("No project selected for feature update")
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    data = request.get_json()
    if not data or 'enabled' not in data:
        logger.warning("Invalid request data for feature update")
        return jsonify({'status': 'error', 'message': 'Missing enabled status'})
    
    try:
        project_path = app.config['CURRENT_PROJECT_PATH']
        success = app.feature_manager.set_feature_enabled(
            feature_id, data['enabled'], project_path
        )
        
        if success:
            logger.info(f"Successfully updated feature {feature_id} to {data['enabled']}")
            return jsonify({
                'status': 'success',
                'feature_id': feature_id,
                'enabled': data['enabled']
            })
        else:
            logger.warning(f"Failed to update feature {feature_id}")
            return jsonify({'status': 'error', 'message': 'Failed to update feature'})
    except Exception as e:
        logger.exception(f"Error updating feature {feature_id}: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/')
def home():
    logger.info("Accessing home route")
    try:
        recent_activities = get_recent_activities()
        logger.debug(f"Retrieved {len(recent_activities)} recent activities")
        
        return render_template('home.html', 
                              recent_activities=recent_activities,
                              current_project=app.config['CURRENT_PROJECT'])
    except Exception as e:
        logger.exception(f"Error rendering home template: {e}")
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('home'))

@app.route('/demand_projection')
def demand_projection():
    logger.info("Accessing demand_projection route")
    if app.config['CURRENT_PROJECT_PATH'] is None:
        logger.warning("No project selected for demand_projection")
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('home'))
    
    demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    logger.debug(f"Looking for input file at {demand_input_file_path}")
    
    if not os.path.exists(demand_input_file_path):
        logger.warning(f"Input demand file not found at {demand_input_file_path}")
        flash('Input demand file not found. Please upload it first.', 'warning')
        return redirect(url_for('home'))
    
    try:
        logger.debug("Loading input demand data")
        sectors, missing_sectors, param_dict, sector_data, aggregated_ele = input_demand_data(demand_input_file_path)
        app.config['START_YEAR']=param_dict.get('Start_Year')
        app.config['End_Year']=param_dict.get('End_Year')
        if not sectors:
            logger.warning("No sectors found in the input file")
            flash('No sectors found in the input file.', 'warning')
            return redirect(url_for('home'))
        
        logger.debug(f"Found {len(sectors)} sectors in input file")
        
        sector_tables = {}
        chart_data = {'sectors': sectors}  # Minimal initial data

        # Process sector data
        for sector, df in sector_data.items():
            sector_tables[sector] = df.to_html(classes='table table-striped table-hover', index=False)

        aggregated_table = aggregated_ele.to_html(classes='table table-striped table-hover', index=False)

        logger.info("Successfully prepared demand projection data")
        return render_template('demand_projection.html',
                               sectors=sectors,
                               missing_sectors=missing_sectors,
                               param_dict=param_dict,
                               sector_tables=sector_tables,
                               aggregated_table=aggregated_table,
                               chart_data=chart_data)
    except Exception as e:
        logger.exception(f"Error processing demand projection: {e}")
        flash(f'Error processing demand projection: {str(e)}', 'danger')
        return redirect(url_for('home'))

@app.route('/demand_visualization')
def demand_visualization():
    logger.info("Accessing demand_visualization route")
    if app.config['CURRENT_PROJECT_PATH'] is None:
        logger.warning("No project selected for demand_visualization")
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('home'))
    try:
        scenarios_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection')
        logger.debug(f"Looking for scenarios at {scenarios_path}")
        
        if not os.path.exists(scenarios_path):
            logger.warning(f"No forecast scenarios found at {scenarios_path}")
            flash('No forecast scenarios found. Please run forecasts first.', 'warning')
            return redirect(url_for('demand_projection'))
        
        scenarios = [d for d in os.listdir(scenarios_path) if os.path.isdir(os.path.join(scenarios_path, d))]
        if not scenarios:
            logger.warning("No forecast scenarios found in directory")
            flash('No forecast scenarios found. Please run forecasts first.', 'warning')
            return redirect(url_for('demand_projection'))
        
        logger.debug(f"Found {len(scenarios)} scenarios: {scenarios}")
        
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
                            logger.warning(f"Could not read sheet {sheet} from {file}: {str(e)}")
                except Exception as e:
                    logger.error(f"Error accessing {file}: {str(e)}")
            
            if all_years:
                start_year = int(min(all_years))
                end_year = int(max(all_years))
        
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        
        if not sectors:
            logger.warning("No valid sector data found for this scenario")
            flash('No valid sector data found for this scenario.', 'warning')
            return redirect(url_for('demand_projection'))
        
        logger.info(f"Successfully prepared visualization data for scenario '{selected_scenario}'")
        return render_template('demand_visualization.html',
                               scenarios=scenarios, selected_scenario=selected_scenario,
                               sectors=sectors, start_year=start_year, end_year=end_year,
                               current_project=app.config['CURRENT_PROJECT'])
    except Exception as e:
        logger.exception(f"Error loading demand visualization: {e}")
        flash(f'Error loading demand visualization: {str(e)}', 'danger')
        return redirect(url_for('home'))

@app.route('/api/save_consolidated_data/<scenario>', methods=['GET'])
def save_consolidated_data(scenario):
    """API endpoint to save consolidated data to CSV for use with load profiles."""
    logger.info(f"Processing API request to save consolidated data for scenario {scenario}")
    
    if not app.config['CURRENT_PROJECT_PATH']:
        logger.warning("No project selected for save_consolidated_data request")
        return jsonify({
            'status': 'error',
            'message': 'No project selected'
        })
    
    try:
        # Get request parameters
        unit = request.args.get('unit', 'kWh')
        from_year = int(request.args.get('from_year', datetime.now().year - 5))
        to_year = int(request.args.get('to_year', datetime.now().year + 10))
        
        # Extract model selections for each sector
        model_params = {}
        for param, value in request.args.items():
            if param.startswith('model_'):
                sector = param.replace('model_', '')
                model_params[sector] = value
        
        # Define the scenario path
        scenario_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection', scenario)
        if not os.path.exists(scenario_path):
            logger.warning(f"Scenario path not found: {scenario_path}")
            return jsonify({
                'status': 'error',
                'message': f'Scenario {scenario} not found'
            })
        
        # Consolidate data from all sectors
        consolidated_data = []
        years = range(from_year, to_year + 1)
        
        # Initialize the DataFrame with years
        df = pd.DataFrame({'Year': years})
        
        # Add data for each sector
        for sector, model in model_params.items():
            sector_df = get_forecast_data_for_sector(scenario_path, sector, from_year, to_year, unit)
            if sector_df is not None and not sector_df.empty and model in sector_df.columns:
                # Rename the model column to sector name
                sector_data = sector_df[['Year', model]].rename(columns={model: sector})
                
                # Merge with main DataFrame
                df = df.merge(sector_data, on='Year', how='left')
        
        # Calculate total
        sector_columns = [col for col in df.columns if col != 'Year']
        if sector_columns:
            df['Total'] = df[sector_columns].sum(axis=1)
        
            # Save to CSV
            file_path = os.path.join(scenario_path, 'consolidated_results.csv')
            df.to_csv(file_path, index=False)
            
            logger.info(f"Successfully saved consolidated data to {file_path}")
            return jsonify({
                'status': 'success',
                'message': 'Consolidated data saved successfully',
                'file_path': file_path
            })
        else:
            logger.warning("No sector data found")
            return jsonify({
                'status': 'error',
                'message': 'No sector data found'
            })
    
    except Exception as e:
        logger.exception(f"Error saving consolidated data: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error saving consolidated data: {str(e)}'
        })

@app.route('/pypsa_modeling')
def pypsa_modeling():
    logger.info("Accessing pypsa_modeling route")
    
    if not app.config['CURRENT_PROJECT']:
        logger.warning("No project selected for pypsa_modeling")
        flash('Please select or create a project first', 'warning')
        return redirect(url_for('home'))
    
    try:
        # Check if pypsa_input_template.xlsx exists
        input_excel_path = Path(app.config['CURRENT_PROJECT_PATH']) / "inputs" / "pypsa_input_template.xlsx"
        input_file_exists = input_excel_path.exists()
        
        logger.debug(f"PyPSA input file exists: {input_file_exists}, path: {input_excel_path}")
        
        if not input_file_exists:
            logger.warning(f"PyPSA input template not found at {input_excel_path}")
            flash('PyPSA input template (pypsa_input_template.xlsx) not found in project inputs folder.', 'warning')
        
        logger.info("Successfully prepared pypsa_modeling data")
        return render_template('pypsa_modeling.html', 
                               current_project=app.config['CURRENT_PROJECT'],
                               input_file_exists=input_file_exists)
    except Exception as e:
        logger.exception(f"Error accessing pypsa_modeling: {e}")
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('home'))

@app.route('/modeling_results')
def modeling_results():
    logger.info("Accessing modeling_results route")
    
    if not app.config['CURRENT_PROJECT']:
        logger.warning("No project selected for modeling_results")
        flash('Please select or create a project first', 'warning')
        return redirect(url_for('home'))
        
    flash('Modeling Results module is coming soon!', 'info')
    return redirect(url_for('home'))

@app.route('/user_guide')
def user_guide():
    logger.info("Accessing user_guide route")
    return render_template('user_guide.html')

@app.route('/tutorials')
def tutorials():
    logger.info("Accessing tutorials route")
    flash('Tutorials page is coming soon!', 'info')
    return redirect(url_for('home'))

# ==========================================
# LOAD PROFILE ROUTES (OPTIMIZED)
# ==========================================

@app.route('/load_profile', methods=['GET', 'POST'])
def load_profile():
    """Route to handle template's url_for('load_profile') references"""
    logger.info("Accessed /load_profile route - redirecting to load_profile_creation")
    return redirect(url_for('load_profile_creation'))

@app.route('/load_profile_creation', methods=['GET', 'POST'])
def load_profile_creation():
    """Main load profile creation route with optimized logic"""
    logger.info("Accessing load_profile_creation route")
    
    # Check if project is selected
    if not app.config['CURRENT_PROJECT_PATH']:
        logger.warning("No project selected when accessing load_profile_creation")
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('home'))
    
    # Initialize load profile manager
    lp_manager = LoadProfileManager(app.config['CURRENT_PROJECT_PATH'])
    
    try:
        # Handle POST request (file upload)
        if request.method == 'POST':
            return _handle_file_upload(lp_manager)
        
        # Handle GET request (display page)
        return _render_load_profile_page(lp_manager)
        
    except Exception as e:
        logger.exception(f"Error in load_profile_creation route: {str(e)}")
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('home'))

def _handle_file_upload(lp_manager: LoadProfileManager):
    """Handle file upload for load profile creation"""
    logger.info("Processing POST request to load_profile_creation")
    
    # Check if file was uploaded
    if 'profile_file' not in request.files:
        logger.warning("No file part in the request")
        flash('No file uploaded', 'warning')
        return redirect(request.url)
    
    file = request.files['profile_file']
    if file.filename == '':
        logger.warning("No file selected in the form")
        flash('No file selected', 'warning')
        return redirect(request.url)
    
    # Validate and save file
    if file and file.filename.endswith('.xlsx'):
        if lp_manager.save_uploaded_file(file):
            logger.info("Successfully uploaded and saved load profile file")
            flash('File uploaded successfully', 'success')
        else:
            logger.warning("File validation failed")
            flash('The Excel file must contain a "Past_Hourly_Demand" sheet', 'danger')
    else:
        logger.warning(f"Invalid file format: {file.filename if file else 'None'}")
        flash('Invalid file format. Please upload an Excel file.', 'danger')
    
    return redirect(url_for('load_profile_creation'))

def _render_load_profile_page(lp_manager: LoadProfileManager):
    """Render the load profile creation page with all necessary data"""
    logger.info("Rendering load profile creation page")
    
    # Check input file status
    input_file_exists, input_file_date = lp_manager.check_input_file_exists()
    logger.debug(f"Input file exists: {input_file_exists}, date: {input_file_date}")
    
    # Get available forecast scenarios
    forecast_scenarios = lp_manager.get_forecast_scenarios()
    logger.debug(f"Found forecast scenarios: {forecast_scenarios}")
    
    # Get available years for base year selection
    available_years = lp_manager.get_available_years() if input_file_exists else []
    logger.debug(f"Available historical years: {available_years}")
    
    # Get generated profiles
    generated_profiles = lp_manager.get_generated_profiles()
    logger.debug(f"Found {len(generated_profiles)} generated profiles")
    
    logger.info("Successfully prepared load profile creation data")
    return render_template(
        'load_profile.html',
        input_file_exists=input_file_exists,
        input_file_date=input_file_date,
        forecast_scenarios=forecast_scenarios,
        available_years=available_years,
        generated_profiles=generated_profiles,
        current_project=app.config['CURRENT_PROJECT']
    )

# ==========================================
# LOAD PROFILE API ROUTES (OPTIMIZED)
# ==========================================

@app.route('/api/projected_future_metrics/<int:base_year>/<int:start_year>/<int:end_year>', methods=['GET'])
def get_projected_future_metrics(base_year: int, start_year: int, end_year: int):
    """API endpoint for projected future metrics with optimized calculations"""
    logger.info(f"API call: projected_future_metrics for base_year={base_year}, range={start_year}-{end_year}")
    
    # Validate project selection
    if not app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    # Validate input parameters
    if start_year >= end_year:
        return jsonify({'status': 'error', 'message': 'End year must be greater than start year'}), 400
    
    if end_year - start_year > 50:
        return jsonify({'status': 'error', 'message': 'Year range cannot exceed 50 years'}), 400
    
    # Initialize load profile manager
    lp_manager = LoadProfileManager(app.config['CURRENT_PROJECT_PATH'])
    excel_file_path = lp_manager.get_input_file_path()
    
    if not os.path.exists(excel_file_path):
        return jsonify({'status': 'error', 'message': 'Load curve input Excel file not found.'}), 404
    
    try:
        # Get forecast scenario from query parameters
        forecast_scenario = request.args.get('forecast_scenario')
        logger.info(f"Forecast scenario from request: {forecast_scenario}")
        
        # Extract base year patterns
        base_year_patterns = extract_monthly_patterns_from_excel(excel_file_path, base_year)
        base_months = base_year_patterns['months']
        base_monthly_shares = {}
        base_monthly_load_factors = {}
        
        # Process pattern data
        raw_shares = base_year_patterns['patternData'].get('Share of Annual (%)', [0]*12)
        raw_load_factors = base_year_patterns['patternData'].get('Load Factor (%)', [0]*12)
        
        for i, month_name in enumerate(base_months):
            base_monthly_shares[month_name] = float(raw_shares[i]) / 100.0 if raw_shares[i] is not None else 0
            base_monthly_load_factors[month_name] = float(raw_load_factors[i]) / 100.0 if raw_load_factors[i] is not None else 0
        
        # Get total annual demand for future years
        project_path = app.config['CURRENT_PROJECT_PATH']
        scenario_name = forecast_scenario if forecast_scenario and forecast_scenario not in ["null", "undefined"] else None
        future_annual_demands_gwh = get_future_annual_demand(project_path, start_year, end_year, scenario_name)
        
        if not future_annual_demands_gwh:
            logger.warning(f"No future annual demand data found for years {start_year}-{end_year} (scenario: {scenario_name})")
        
        # Calculate projections
        projected_data = _calculate_projected_metrics(
            start_year, end_year, base_months, base_monthly_shares, 
            base_monthly_load_factors, future_annual_demands_gwh
        )
        
        return jsonify({
            'status': 'success', 
            'data': projected_data, 
            'baseYearMonths': base_months
        })
    
    except Exception as e:
        logger.exception(f"Error in get_projected_future_metrics: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def _calculate_projected_metrics(start_year: int, end_year: int, base_months: List[str], 
                               base_monthly_shares: Dict[str, float], 
                               base_monthly_load_factors: Dict[str, float],
                               future_annual_demands_gwh: Dict[int, float]) -> List[Dict]:
    """Calculate projected metrics for future years"""
    projected_data = []
    
    # Days in month mapping
    days_in_month_map = {
        'Jan': 31, 'Feb': 28, 'Mar': 31, 'Apr': 30, 'May': 31, 'Jun': 30,
        'Jul': 31, 'Aug': 31, 'Sep': 30, 'Oct': 31, 'Nov': 30, 'Dec': 31
    }
    
    for year_fy in range(start_year, end_year + 1):
        annual_total_gwh = future_annual_demands_gwh.get(year_fy, 0)
        
        if annual_total_gwh == 0:
            logger.warning(f"Annual total demand for FY {year_fy} is 0. Monthly projections will be 0.")
        
        monthly_metrics_for_year = []
        sum_monthly_avg_demand_mw = 0
        max_monthly_max_demand_mw = 0
        
        for month_name in base_months:
            share = base_monthly_shares.get(month_name, 0)
            base_lf = base_monthly_load_factors.get(month_name, 0)
            days = days_in_month_map[month_name]
            
            # Calculate projections
            projected_total_gwh = annual_total_gwh * share
            projected_total_mwh = projected_total_gwh * 1000
            
            if days > 0:
                projected_avg_mw = projected_total_mwh / (days * 24)
            else:
                projected_avg_mw = 0
            
            if base_lf > 0:
                projected_max_mw = projected_avg_mw / base_lf
            else:
                projected_max_mw = 0 if projected_avg_mw == 0 else float('inf')
            
            projected_lf_percent = (projected_avg_mw / projected_max_mw * 100) if projected_max_mw > 0 else 0
            
            monthly_metrics_for_year.append({
                'month': month_name,
                'totalDemand_GWh': round(projected_total_gwh, 2),
                'avgDemand_MW': round(projected_avg_mw, 2),
                'maxDemand_MW': round(projected_max_mw, 2),
                'loadFactor_Percent': round(projected_lf_percent, 1)
            })
            
            sum_monthly_avg_demand_mw += projected_avg_mw
            if projected_max_mw != float('inf'):
                max_monthly_max_demand_mw = max(max_monthly_max_demand_mw, projected_max_mw)
        
        # Calculate yearly load factor
        avg_of_monthly_avg_demands = sum_monthly_avg_demand_mw / 12 if sum_monthly_avg_demand_mw > 0 else 0
        yearly_load_factor_percent = (avg_of_monthly_avg_demands / max_monthly_max_demand_mw * 100) if max_monthly_max_demand_mw > 0 else 0
        
        projected_data.append({
            'year': year_fy,
            'annualTotal_GWh': round(annual_total_gwh, 2),
            'monthlyData': monthly_metrics_for_year,
            'yearlyLoadFactor_Percent': round(yearly_load_factor_percent, 1)
        })
    
    return projected_data

@app.route('/api/monthly_patterns/<int:base_year>', methods=['GET'])
def get_monthly_patterns(base_year: int):
    """API endpoint for monthly patterns with optimized extraction"""
    logger.info(f"Processing request for monthly patterns for year {base_year}")
    
    # Validate project selection
    if not app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    # Validate base year
    current_year = datetime.now().year
    if base_year < 2000 or base_year > current_year:
        return jsonify({'status': 'error', 'message': f'Base year must be between 2000 and {current_year}'}), 400
    
    # Initialize load profile manager
    lp_manager = LoadProfileManager(app.config['CURRENT_PROJECT_PATH'])
    input_file_path = lp_manager.get_input_file_path()
    
    if not os.path.exists(input_file_path):
        return jsonify({'status': 'error', 'message': 'Input file not found'}), 404
    
    try:
        # Extract monthly patterns using optimized function
        patterns = extract_monthly_patterns_from_excel(input_file_path, base_year)
        
        return jsonify({
            'status': 'success',
            'months': patterns['months'],
            'patternData': patterns['patternData'],
            'yearlyLoadFactor': patterns.get('yearlyLoadFactor', 0),
            'calculatedFromExcel': True 
        })
    except Exception as e:
        logger.exception(f"Error generating monthly patterns: {e}")
        return jsonify({'status': 'error', 'message': f'Error generating monthly patterns: {str(e)}'}), 500

@app.route('/api/generate_load_profiles', methods=['POST'])
def generate_load_profiles():
    """API endpoint for generating load profiles with comprehensive validation"""
    logger.info("Processing API request to generate_load_profiles")
    
    # Validate project selection
    if not app.config['CURRENT_PROJECT_PATH']:
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    try:
        # Initialize load profile manager
        lp_manager = LoadProfileManager(app.config['CURRENT_PROJECT_PATH'])
        
        # Validate input file exists
        input_file_path = lp_manager.get_input_file_path()
        if not os.path.exists(input_file_path):
            return jsonify({'status': 'error', 'message': 'Load curve template file not found'}), 404
        
        # Parse and validate form data
        form_data = dict(request.form)
        is_valid, validation_errors = validate_load_profile_form(form_data)
        
        if not is_valid:
            error_messages = '; '.join(validation_errors.values())
            return jsonify({'status': 'error', 'message': f'Validation errors: {error_messages}'}), 400
        
        # Extract form parameters
        generation_params = _extract_generation_parameters(form_data)
        logger.debug(f"Load profile generation params: {generation_params}")
        
        # Load scenario data if specified
        scenario_data = None
        scenario_name = generation_params['forecast_scenario_name']
        if scenario_name and scenario_name not in ["null", "undefined", ""]:
            scenario_data = load_scenario_data(app.config['CURRENT_PROJECT_PATH'], scenario_name)
        
        # Validate data availability
        if not check_total_demand_data(input_file_path) and not (scenario_data and scenario_data.get('Consolidated Electricity Demand')):
            if not scenario_name or scenario_name in ["null", "undefined", ""]:
                return jsonify({
                    'status': 'error', 
                    'message': 'Please select a forecast scenario or provide Total Demand data in the Excel file (Total Demand sheet).'
                }), 400
        
        # Generate profile ID and output path
        profile_id = lp_manager.generate_profile_id(
            scenario_name, 
            generation_params['method'], 
            generation_params.get('base_year')
        )
        output_path = lp_manager.get_profile_path(profile_id)
        
        # Generate load profile
        load_forecast_df = _generate_load_profile(
            input_file_path, scenario_data, generation_params
        )
        
        if load_forecast_df is None or load_forecast_df.empty:
            return jsonify({'status': 'error', 'message': 'Failed to generate load profile. Result was empty.'}), 500
        
        # Apply unit conversion if necessary
        _apply_unit_conversion(load_forecast_df, generation_params['output_unit'])
        
        # Save the generated profile
        load_forecast_df.to_csv(output_path, index=False)
        logger.info(f"Successfully generated load profile: {profile_id} to {output_path}")
        
        # Refresh generated profiles list
        generated_profiles = lp_manager.get_generated_profiles()
        
        return jsonify({
            'status': 'success',
            'message': 'Load profiles generated successfully!',
            'profile_id': profile_id,
            'details': f'Generated {generation_params["output_frequency"]} load profile for years {generation_params["start_year"]}-{generation_params["end_year"]} in {generation_params["output_unit"]}.',
            'profiles': generated_profiles
        })
    
    except Exception as e:
        logger.exception(f"Error in generate_load_profiles API: {e}")
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500

def _extract_generation_parameters(form_data: Dict) -> Dict[str, Any]:
    """Extract and structure generation parameters from form data"""
    # Basic parameters
    params = {
        'method': form_data.get('method'),
        'forecast_scenario_name': form_data.get('forecast_scenario'),
        'base_year': int(form_data['base_year']) if form_data.get('base_year') and form_data['method'] == 'base_year' else None,
        'use_constraints': form_data.get('use_constraints') == 'true',
        'start_year': int(form_data.get('start_year', datetime.now().year)),
        'end_year': int(form_data.get('end_year', datetime.now().year + 14)),
        'output_frequency': form_data.get('output_frequency', 'hourly'),
        'output_unit': form_data.get('output_unit', 'MW')
    }
    
    # Load factor configuration
    lf_config = parse_load_factor_form_data(form_data)
    params.update(lf_config)
    
    return params

def _generate_load_profile(input_file_path: str, scenario_data: Optional[Dict], 
                         params: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """Generate load profile using the specified parameters"""
    # Prepare year range
    year_range_dict = {
        'Start_Year': params['start_year'], 
        'End_Year': params['end_year']
    }
    
    # Generate load profile
    load_forecast_df = create_load_curve(
        excel_file_path=input_file_path,
        base_year=params.get('base_year'),
        scenario_data=scenario_data,
        year_range=year_range_dict,
        method=params['method'],
        apply_constraints=params['use_constraints'],
        improved_load_factor=params.get('load_factor_improvement'),
        future_load_factors=params.get('custom_load_factors'),
        use_excel_load_factors=params.get('use_excel_load_factors', False),
        output_frequency=params['output_frequency']
    )
    
    return load_forecast_df

def _apply_unit_conversion(df: pd.DataFrame, output_unit: str):
    """Apply unit conversion to the demand column"""
    if 'Demand' not in df.columns:
        return
    
    if output_unit == 'kW':
        df['Demand'] = df['Demand'] * 1000
    elif output_unit == 'GW':
        df['Demand'] = df['Demand'] / 1000
    # MW requires no conversion (assumed internal unit)

@app.route('/api/load_profile_metadata/<profile_id>', methods=['GET'])
def get_load_profile_metadata(profile_id):
    """API endpoint for load profile metadata with optimized processing"""
    logger.info(f"Processing API request for load_profile_metadata/{profile_id}")
    
    # Validate inputs
    if not app.config['CURRENT_PROJECT_PATH']:
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    if not profile_id or not profile_id.strip():
        return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
    
    try:
        # Initialize load profile manager and get metadata
        lp_manager = LoadProfileManager(app.config['CURRENT_PROJECT_PATH'])
        metadata = lp_manager.get_profile_metadata(profile_id)
        
        if metadata is None:
            logger.warning(f"Profile not found: {profile_id}")
            return jsonify({'status': 'error', 'message': f'Profile {profile_id} not found'}), 404
        
        logger.info(f"Successfully retrieved profile metadata for {profile_id}")
        return jsonify({
            'status': 'success',
            **metadata
        })
    
    except Exception as e:
        logger.exception(f"Error getting profile metadata for {profile_id}: {e}")
        return jsonify({'status': 'error', 'message': f'Error getting profile metadata: {str(e)}'}), 500

@app.route('/api/load_profile_data/<profile_id>/<year>', methods=['GET'])
def get_load_profile_data(profile_id, year):
    """API endpoint for load profile data with optimized retrieval"""
    logger.info(f"Processing API request for load_profile_data/{profile_id}/{year}")
    
    # Validate inputs
    if not app.config['CURRENT_PROJECT_PATH']:
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    if not profile_id or not profile_id.strip():
        return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
    
    try:
        year_int = int(year)
        if year_int < 2000 or year_int > 2100:
            return jsonify({'status': 'error', 'message': 'Invalid year'}), 400
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Year must be a valid integer'}), 400
    
    try:
        # Initialize load profile manager and get year data
        lp_manager = LoadProfileManager(app.config['CURRENT_PROJECT_PATH'])
        profile_data = lp_manager.get_profile_year_data(profile_id, year_int)
        
        if profile_data is None:
            logger.warning(f"Profile not found: {profile_id}")
            return jsonify({'status': 'error', 'message': f'Profile {profile_id} not found'}), 404
        
        logger.info(f"Successfully retrieved {len(profile_data)} data points for profile {profile_id}, year {year}")
        return jsonify({
            'status': 'success',
            'profile_id': profile_id,
            'year': year,
            'profile_data': profile_data
        })
    
    except Exception as e:
        logger.exception(f"Error getting profile data for {profile_id}/{year}: {e}")
        return jsonify({'status': 'error', 'message': f'Error getting profile data: {str(e)}'}), 500

# ==========================================
# REMAINING API ROUTES (UNCHANGED FROM ORIGINAL)
# ==========================================

@app.route('/api/get_pypsa_settings_from_excel', methods=['GET'])
def api_get_pypsa_settings_from_excel():
    logger.info("Processing API request for get_pypsa_settings_from_excel")
    
    if not app.config['CURRENT_PROJECT_PATH']:
        logger.warning("No project selected for get_pypsa_settings_from_excel")
        return jsonify({'status': 'error', 'message': 'No project selected'})

    input_file_path = Path(app.config['CURRENT_PROJECT_PATH']) / "inputs" / "pypsa_input_template.xlsx"
    logger.debug(f"Looking for PyPSA input file at {input_file_path}")
    
    if not input_file_path.exists():
        logger.warning(f"PyPSA input Excel file not found at {input_file_path}")
        return jsonify({'status': 'error', 'message': 'PyPSA input Excel file not found.'})

    try:
        xls = pd.ExcelFile(input_file_path)

        if 'Settings' not in xls.sheet_names:
            logger.warning("'Settings' sheet not found in the PyPSA Excel file")
            return jsonify({'status': 'error', 'message': "'Settings' sheet not found in the Excel file."})
        
        setting_df_excel = xls.parse('Settings')
        main_settings_table = extract_tables_by_markers(setting_df_excel, '~').get('Main_Settings')
        
        if main_settings_table is None:
            logger.warning("Main_Settings table not found in 'Settings' sheet")
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

        logger.info("Successfully retrieved PyPSA settings from Excel")
        return jsonify({'status': 'success', 'settings': ui_settings})
    except Exception as e:
        logger.exception(f"Error parsing PyPSA settings from Excel: {e}")
        return jsonify({'status': 'error', 'message': f'Error parsing Excel settings: {str(e)}'})

@app.route('/api/run_pypsa_model', methods=['POST'])
def api_run_pypsa_model():
    logger.info("Processing API request to run_pypsa_model")
    
    if not app.config['CURRENT_PROJECT_PATH']:
        logger.warning("No project selected for run_pypsa_model")
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    data = request.get_json()
    scenario_name = data.get('scenarioName')
    ui_settings_overrides = data.get('settings', {}) # Get all settings from UI

    logger.debug(f"PyPSA model run request: scenario={scenario_name}, settings={ui_settings_overrides}")
    
    if not scenario_name:
        logger.warning("Scenario name is required for run_pypsa_model")
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
    
    logger.info(f"Queuing PyPSA job {job_id} for scenario: {scenario_name}")

    try:
        pypsa_thread = threading.Thread(
            target=run_pypsa_model_core, # Call the refactored function
            args=(job_id, app.config['CURRENT_PROJECT_PATH'], scenario_name, ui_settings_overrides) # Pass overrides
        )
        pypsa_thread.daemon = True
        pypsa_thread.start()
        
        logger.info(f"Started PyPSA model thread for job {job_id}")
        
        return jsonify({'status': 'started', 'jobId': job_id, 'message': f'PyPSA model run started for scenario: {scenario_name}'})
    except Exception as e:
        logger.exception(f"Error starting PyPSA model run: {e}")
        pypsa_jobs[job_id]['status'] = 'failed'
        pypsa_jobs[job_id]['error'] = str(e)
        return jsonify({'status': 'error', 'message': f'Error starting PyPSA model: {str(e)}'})

@app.route('/api/pypsa_model_status/<job_id>', methods=['GET'])
def api_get_pypsa_model_status(job_id):
    logger.info(f"Processing API request for pypsa_model_status/{job_id}")
    
    job = pypsa_jobs.get(job_id)
    if not job:
        logger.warning(f"PyPSA job {job_id} not found")
        return jsonify({'status': 'error', 'message': 'Job not found'}), 404
    
    # If completed, scan for result files
    if job['status'] == 'Completed' and job.get('result_files') is None:
        logger.debug(f"Scanning for result files for completed job {job_id}")
        scenario_results_dir = Path(job['project_path']) / "results" / "PyPSA_Modeling" / job['scenario_name']
        if scenario_results_dir.exists():
            job['result_files'] = [f.name for f in scenario_results_dir.iterdir() if f.is_file()]
            logger.debug(f"Found {len(job['result_files'])} result files")
        else:
            job['result_files'] = []
            logger.warning(f"Results directory not found for completed job: {scenario_results_dir}")
    
    logger.debug(f"Job {job_id} status: {job['status']}, progress: {job.get('progress', 0)}")
    return jsonify(job)

@app.route('/api/pypsa_scenarios', methods=['GET'])
def api_get_pypsa_scenarios():
    logger.info("Processing API request for pypsa_scenarios")
    
    if not app.config['CURRENT_PROJECT_PATH']:
        logger.warning("No project selected for pypsa_scenarios")
        return jsonify({'status': 'error', 'message': 'No project selected', 'scenarios': []})

    scenarios_dir = Path(app.config['CURRENT_PROJECT_PATH']) / "results" / "PyPSA_Modeling"
    logger.debug(f"Looking for PyPSA scenarios in {scenarios_dir}")
    
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

                logger.debug(f"Found PyPSA scenario: {scenario_name}, status: {status}")
                scenarios_data.append({
                    'name': scenario_name,
                    'path': str(scenario_path),
                    'status': status,
                    'last_modified': datetime.fromtimestamp(scenario_path.stat().st_mtime).isoformat()
                })
    
    scenarios_data.sort(key=lambda x: x['last_modified'], reverse=True)
    logger.info(f"Retrieved {len(scenarios_data)} PyPSA scenarios")
    return jsonify({'status': 'success', 'scenarios': scenarios_data})

@app.route('/api/download_pypsa_result/<scenario_name>/<path:filename>', methods=['GET'])
def download_pypsa_result_file(scenario_name, filename):
    logger.info(f"Processing API request to download_pypsa_result/{scenario_name}/{filename}")
    
    if not app.config['CURRENT_PROJECT_PATH']:
        logger.warning("No project loaded for download_pypsa_result")
        flash("No project loaded.", "danger")
        return redirect(url_for('pypsa_modeling'))

    scenario_dir = Path(app.config['CURRENT_PROJECT_PATH']) / "results" / "PyPSA_Modeling" / scenario_name
    logger.debug(f"Looking for result file in {scenario_dir}")
    
    # Secure the filename - could be a subfolder like "results_2026/generators.csv"
    # Convert filename from URL path to OS-specific path
    parts = filename.split('/')
    safe_parts = [secure_filename(part) for part in parts]
    file_to_download_path = scenario_dir.joinpath(*safe_parts)
    
    logger.debug(f"Resolved file path: {file_to_download_path}")

    if file_to_download_path.is_file() and file_to_download_path.resolve().is_relative_to(scenario_dir.resolve()):
        logger.info(f"Sending file: {file_to_download_path}")
        return send_file(str(file_to_download_path.resolve()), as_attachment=True)
    else:
        logger.warning(f"File not found or access denied: {file_to_download_path}")
        flash(f"File not found or access denied: {filename}", "danger")
        return redirect(url_for('pypsa_modeling'))

# Keep all other original routes unchanged...
@app.route('/create_project', methods=['POST'])
def create_project():
    logger.info("Processing create_project request")
    
    if request.method != 'POST':
        logger.warning("Invalid request method for create_project")
        return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
    project_name = request.form.get('projectName')
    project_location = request.form.get('projectLocation', '')
    
    logger.debug(f"Requested project creation: name='{project_name}', location='{project_location}'")
    
    if not project_name:
        logger.warning("No project name provided")
        return jsonify({'status': 'error', 'message': 'Please provide a project name'})
    
    if not project_location:
        logger.warning("No project location provided")
        return jsonify({'status': 'error', 'message': 'Please select a project location'})
    
    try:
        safe_project_name = secure_filename(project_name)
        if os.path.isabs(project_location):
            project_path = os.path.join(project_location, safe_project_name)
        else:
            project_path = os.path.join(app.config['UPLOAD_FOLDER'], 'projects', project_location, safe_project_name)
        
        logger.debug(f"Creating project at: {project_path}")
        
        success = create_project_structure(project_path, app.config['TEMPLATE_FOLDER'])
        if success:
            logger.info(f"Project created: {project_path} at {datetime.now()}")
            
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
            logger.error(f"Failed to create project structure at {project_path}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to create project structure. Check server logs for details.'
            })
    except Exception as e:
        logger.exception(f"Error creating project: {e}")
        return jsonify({'status': 'error', 'message': f'Error creating project: {str(e)}'})

@app.route('/validate_project', methods=['POST'])
def validate_project():
    logger.info("Processing validate_project request")
    
    if request.method != 'POST':
        logger.warning("Invalid request method for validate_project")
        return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
    project_path = request.form.get('projectPath')
    
    if not project_path:
        logger.warning("No project path provided")
        return jsonify({'status': 'error', 'message': 'No project path provided'})
    
    try:
        logger.debug(f"Validating project at: {project_path}")
        
        if not os.path.exists(project_path):
            logger.warning(f"Project path does not exist: {project_path}")
            return jsonify({
                'status': 'error', 
                'message': f'The path "{project_path}" does not exist'
            })
        
        validation_result = validate_project_structure(project_path)
        logger.debug(f"Validation result: {validation_result}")
        return jsonify(validation_result)
    except Exception as e:
        logger.exception(f"Error validating project: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error validating project: {str(e)}'
        })

@app.route('/load_project', methods=['POST'])
def load_project():
    logger.info("Processing load_project request")
    
    if request.method != 'POST':
        logger.warning("Invalid request method for load_project")
        return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
    project_path = request.form.get('projectPath')
    
    if not project_path:
        logger.warning("No project path provided")
        return jsonify({'status': 'error', 'message': 'No project path provided'})
    
    try:
        logger.debug(f"Validating and loading project: {project_path}")
        
        validation_result = validate_project_structure(project_path)
        logger.debug(f"Validation result: {validation_result}")
        
        if validation_result['status'] == 'error':
            return jsonify(validation_result)
        
        if validation_result['status'] == 'warning' and validation_result.get('can_fix', False):
            logger.info(f"Fixing missing templates for {project_path}")
            copy_missing_templates(project_path, validation_result.get('missing_templates', []), app.config['TEMPLATE_FOLDER'])
        
        project_name = os.path.basename(os.path.normpath(project_path))
        app.config['CURRENT_PROJECT'] = project_name
        app.config['CURRENT_PROJECT_PATH'] = project_path
        
        user_id = session.get('user_id', 'default_user')
        save_recent_project(user_id, project_name, project_path)
        
        logger.info(f"Successfully loaded project: {project_name} at {project_path}")
        return jsonify({
            'status': 'success',
            'message': 'Project loaded successfully',
            'project_path': project_path,
            'project_name': project_name
        })
    except Exception as e:
        logger.exception(f"Error loading project: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error loading project: {str(e)}'
        })

@app.route('/upload_data', methods=['POST'])
def upload_data():
    logger.info("Processing upload_data request")
    
    if request.method == 'POST':
        if not app.config['CURRENT_PROJECT']:
            logger.warning("No project selected for upload_data")
            flash('Please select or create a project first', 'warning')
            return redirect(url_for('home'))
            
        if 'data_file' not in request.files:
            logger.warning("No file part in upload_data request")
            flash('No file part', 'danger')
            return redirect(url_for('home'))
        
        file = request.files['data_file']
        
        if file.filename == '':
            logger.warning("No file selected in upload_data form")
            flash('No selected file', 'danger')
            return redirect(url_for('home'))
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            project_inputs_folder = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'inputs')
            os.makedirs(project_inputs_folder, exist_ok=True)
            file_path = os.path.join(project_inputs_folder, filename)
            
            logger.info(f"Saving uploaded file to {file_path}")
            file.save(file_path)
            flash('File uploaded successfully!', 'success')
            return redirect(url_for('home'))
        else:
            logger.warning(f"Invalid file type: {file.filename if file else 'None'}")
            flash('Invalid file type. Please upload an Excel (.xlsx) file.', 'danger')
            return redirect(url_for('home'))

@app.route('/download_template/<template_type>')
def download_template(template_type):
    logger.info(f"Processing download_template request for {template_type}")
    
    templates = {
        'data_input': 'data_input_template.xlsx',
        'load_curve': 'load_curve_template.xlsx',
        'pypsa_input': 'pypsa_input_template.xlsx'
    }
    
    if template_type not in templates:
        logger.warning(f"Invalid template type requested: {template_type}")
        flash('Template not found', 'danger')
        return redirect(url_for('home'))
    
    template_path = os.path.join(app.config['TEMPLATE_FOLDER'], templates[template_type])
    
    if not os.path.exists(template_path):
        logger.warning(f"Template file not found: {template_path}")
        create_template_files()
        if not os.path.exists(template_path):
            logger.error(f"Template file {templates[template_type]} not found even after creation attempt")
            flash(f'Template file {templates[template_type]} not found', 'danger')
            return redirect(url_for('home'))
    
    logger.info(f"Sending template file: {template_path}")
    return send_file(template_path, as_attachment=True)

@app.route('/download_user_guide')
def download_user_guide():
    logger.info("Processing download_user_guide request")
    
    guide_path = os.path.join(app.config['TEMPLATE_FOLDER'], 'user_guide.pdf')
    
    if not os.path.exists(guide_path):
        logger.warning(f"User guide PDF not found: {guide_path}")
        flash('User guide PDF not found', 'danger')
        return redirect(url_for('home'))
        
    logger.info(f"Sending user guide file: {guide_path}")
    return send_file(guide_path, as_attachment=True)

@app.route('/download_methodology')
def download_methodology():
    logger.info("Processing download_methodology request")
    
    methodology_path = os.path.join(app.config['TEMPLATE_FOLDER'], 'methodology.pdf')
    
    if not os.path.exists(methodology_path):
        logger.warning(f"Methodology PDF not found: {methodology_path}")
        flash('Methodology PDF not found', 'danger')
        return redirect(url_for('home'))
        
    logger.info(f"Sending methodology file: {methodology_path}")
    return send_file(methodology_path, as_attachment=True)

# ==========================================
# REMAINING API ROUTES
# ==========================================

@app.route('/api/recent_projects', methods=['GET'])
def api_recent_projects():
    logger.info("Processing API request for recent_projects")
    
    user_id = session.get('user_id', 'default_user')
    try:
        filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        logger.debug(f"Looking for recent projects file: {filename}")
        
        if not os.path.exists(filename):
            logger.warning(f"Recent projects file not found for user {user_id}")
            return jsonify({'recent_projects': []})
        
        with open(filename, 'r') as f:
            recent_projects = json.load(f)
        
        logger.info(f"Loaded {len(recent_projects)} recent projects for user {user_id}")
        return jsonify({'recent_projects': recent_projects})
    except Exception as e:
        logger.exception(f"Error reading recent projects: {e}")
        return jsonify({'recent_projects': [], 'error': str(e)})

@app.route('/api/delete_recent_project', methods=['POST'])
def api_delete_recent_project():
    logger.info("Processing API request to delete_recent_project")
    
    user_id = session.get('user_id', 'default_user')
    
    try:
        # Get project path from request
        data = request.get_json()
        if not data or 'projectPath' not in data:
            logger.warning("Project path not provided in request")
            return jsonify({
                'status': 'error',
                'message': 'Project path not provided'
            })
        
        project_path = data['projectPath']
        logger.debug(f"Requested deletion of project: {project_path}")
        
        # Read existing projects
        filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        if not os.path.exists(filename):
            logger.warning(f"Recent projects file not found for user {user_id}")
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
            logger.warning(f"Project {project_path} not found in recent projects")
            return jsonify({
                'status': 'error',
                'message': 'Project not found in recent projects'
            })
        
        # Save the updated list
        with open(filename, 'w') as f:
            json.dump(recent_projects, f, indent=4)
        
        logger.info(f"Removed project {project_path} from recent projects for user {user_id}")
        
        return jsonify({
            'status': 'success',
            'message': 'Project removed from recent projects'
        })
    
    except Exception as e:
        logger.exception(f"Error removing project from recent projects: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        })

@app.route('/api/independent_variables/<sector>', methods=['GET'])
def get_independent_variables(sector):
    logger.info(f"Processing API request for independent_variables/{sector}")
    
    if app.config['CURRENT_PROJECT_PATH'] is None:
        logger.warning("No project selected for independent_variables request")
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        logger.warning(f"Input demand file not found: {demand_input_file_path}")
        return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    
    try:
        logger.debug(f"Loading sector data for {sector} from {demand_input_file_path}")
        # Get sector data
        sectors, _, _, sector_data, _ = input_demand_data(demand_input_file_path)
        
        if sector not in sector_data:
            logger.warning(f"Sector {sector} not found in input data")
            return jsonify({'status': 'error', 'message': f'Sector {sector} not found'})
        
        # Get the variables for this sector
        df = sector_data[sector]
        variables = df.columns.tolist()
        
        # Calculate correlations with Electricity
        correlations = {}
        for var in variables:
            if var != 'Electricity' and var in df.select_dtypes(include=['number']).columns:
                correlations[var] = df[var].corr(df['Electricity'])
        
        logger.info(f"Successfully retrieved {len(variables)} variables for sector {sector}")
        return jsonify({
            'status': 'success',
            'variables': variables,
            'correlations': correlations
        })
    except Exception as e:
        logger.exception(f"Error fetching variables for {sector}: {e}")
        return jsonify({'status': 'error', 'message': f'Error fetching variables: {str(e)}'})

@app.route('/api/correlation_data/<sector>', methods=['GET'])
def get_correlation_data(sector):
    logger.info(f"Processing API request for correlation_data/{sector}")
    
    if app.config['CURRENT_PROJECT_PATH'] is None:
        logger.warning("No project selected for correlation_data request")
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        logger.warning(f"Input demand file not found: {demand_input_file_path}")
        return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    
    try:
        logger.debug(f"Loading data for correlation analysis for sector {sector}")
        # Get sector data
        sectors, _, param_dict, sector_data, aggregated_ele = input_demand_data(demand_input_file_path)
        
        if sector == 'aggregated':
            df = aggregated_ele
            logger.debug("Using aggregated electricity data for correlations")
        elif sector not in sector_data:
            logger.warning(f"Sector {sector} not found in input data")
            return jsonify({'status': 'error', 'message': f'Sector {sector} not found'})
        else:
            df = sector_data[sector]
            logger.debug(f"Using sector {sector} data for correlations")
        
        # Select only numeric columns for correlation analysis
        numeric_df = df.select_dtypes(include=['number'])
        
        # Check if Electricity is in the columns
        if 'Electricity' not in numeric_df.columns:
            logger.warning(f"'Electricity' column not found in {sector} data")
            return jsonify({
                'status': 'success',
                'data': {
                    'variables': [],
                    'correlations': []
                }
            })
        
        # Calculate correlations with Electricity
        try:
            logger.debug("Calculating correlation matrix")
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
            
            logger.info(f"Successfully calculated {len(sorted_variables)} correlations for {sector}")
            return jsonify({
                'status': 'success',
                'data': {
                    'variables': sorted_variables,
                    'correlations': sorted_correlations
                }
            })
        except Exception as e:
            logger.exception(f"Error calculating correlations: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Error calculating correlations: {str(e)}'
            })
    except Exception as e:
        logger.exception(f"Error calculating correlation for {sector}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error calculating correlation: {str(e)}'
        })

@app.route('/api/chart_data/<sector>', methods=['GET'])
def get_chart_data(sector):
    logger.info(f"Processing API request for chart_data/{sector}")
    
    if app.config['CURRENT_PROJECT_PATH'] is None:
        logger.warning("No project selected for chart_data request")
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    demand_input_file_path = f"{app.config['CURRENT_PROJECT_PATH']}/inputs/input_demand_file.xlsx"
    if not os.path.exists(demand_input_file_path):
        logger.warning(f"Input demand file not found: {demand_input_file_path}")
        return jsonify({'status': 'error', 'message': 'Input demand file not found'})
    
    try:
        logger.debug(f"Loading data for chart generation for sector {sector}")
        sectors, _, param_dict, sector_data, aggregated_ele = input_demand_data(demand_input_file_path)
        
        # Get target year from parameters
        target_year = int(param_dict.get('End_Year', 2037))
        start_year = int(param_dict.get('Start_Year', 2006))
        
        # Replace NaN values with None for JSON serialization
        for col in aggregated_ele.columns:
            aggregated_ele[col] = aggregated_ele[col].replace([np.nan, np.inf, -np.inf], None)
        
        chart_data = {}
        if sector == 'aggregated':
            logger.debug("Preparing aggregated sector chart data")
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
                    sector_data_values = [float(v) if v is not None else 0 for v in aggregated_ele[s].tolist()]
                    
                    datasets.append({
                        'label': s,
                        'data': sector_data_values,
                        'backgroundColor': f'rgba({r}, {g}, {b}, 0.7)',
                        'borderColor': f'rgba({r}, {g}, {b}, 1)'
                    })
            
            chart_data = {
                'years': years,
                'datasets': datasets
            }
        else:
            logger.debug(f"Preparing chart data for specific sector: {sector}")
            if sector not in sector_data:
                logger.warning(f"Sector {sector} not found in input data")
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
        
        logger.info(f"Successfully generated chart data for {sector}")
        return jsonify({'status': 'success', 'data': chart_data})
    except Exception as e:
        logger.exception(f"Error fetching chart data for {sector}: {e}")
        return jsonify({'status': 'error', 'message': f'Error fetching chart data: {str(e)}'}), 500

@app.route('/api/forecast_data/<scenario>', methods=['GET'])
def get_forecast_data(scenario):
    logger.info(f"Processing API request for forecast_data/{scenario}")
    
    if app.config['CURRENT_PROJECT_PATH'] is None:
        logger.warning("No project selected for forecast_data request")
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    try:
        scenario_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection', scenario)
        logger.debug(f"Looking for scenario at {scenario_path}")
        
        if not os.path.exists(scenario_path):
            logger.warning(f"Scenario {scenario} not found at {scenario_path}")
            return jsonify({'status': 'error', 'message': f'Scenario {scenario} not found'})
        
        sector_files = [f for f in os.listdir(scenario_path) if f.endswith('.xlsx') and not f.startswith('_')]
        if not sector_files:
            logger.warning(f"No sector data found for scenario {scenario}")
            return jsonify({'status': 'error', 'message': 'No sector data found for this scenario'})
        
        sector_data = {}
        for file in sector_files:
            sector_name = os.path.splitext(file)[0]
            if sector_name.lower() in ['summary', 'consolidated']:
                continue
                
            file_path = os.path.join(scenario_path, file)
            try:
                logger.debug(f"Reading file {file_path}")
                df = pd.read_excel(file_path, sheet_name='Results')
                if 'Year' not in df.columns:
                    logger.warning(f"'Year' column missing in {file}")
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
                logger.error(f"Error processing {file}: {str(e)}")
                continue
        
        if not sector_data:
            logger.warning(f"Could not process any sector data for scenario {scenario}")
            return jsonify({'status': 'error', 'message': 'Could not process any sector data'})
        
        logger.info(f"Successfully retrieved forecast data for {len(sector_data)} sectors in scenario {scenario}")
        return jsonify({
            'status': 'success',
            'data': sector_data
        })
    except Exception as e:
        logger.exception(f"Error fetching forecast data for {scenario}: {e}")
        return jsonify({'status': 'error', 'message': f'Error fetching forecast data: {str(e)}'})

@app.route('/api/run_forecast', methods=['POST'])
def run_forecast():
    logger.info("Processing API request to run_forecast")
    
    if app.config['CURRENT_PROJECT_PATH'] is None:
        logger.warning("No project selected for run_forecast")
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    # Get request data
    data = request.get_json()
    if not data:
        logger.warning("No data provided in run_forecast request")
        return jsonify({'status': 'error', 'message': 'No data provided'})
    
    scenario_name = data.get('scenarioName')
    target_year = data.get('targetYear')
    exclude_covid_years = data.get('excludeCovidYears', True)
    sector_configs = data.get('sectorConfigs', {})
    
    logger.debug(f"Forecast request: scenario={scenario_name}, target_year={target_year}, " +
                 f"exclude_covid={exclude_covid_years}, sectors={list(sector_configs.keys())}")
    
    if not scenario_name or not target_year or not sector_configs:
        logger.warning("Missing required parameters in run_forecast request")
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
    
    logger.info(f"Created forecast job {job_id} for {len(sector_configs)} sectors")
    
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
    logger.info(f"Processing API request for forecast_status/{job_id}")
    
    if job_id not in forecast_jobs:
        logger.warning(f"Job {job_id} not found")
        return jsonify({'status': 'error', 'message': 'Job not found'})
    
    job = forecast_jobs[job_id]
    logger.debug(f"Job {job_id} status: {job['status']}, progress: {job['progress']}, " +
                 f"current sector: {job['currentSector']}")
    
    return jsonify({
        'status': job['status'],
        'progress': job['progress'],
        'currentSector': job['currentSector'],
        'result': job['result'] if job['status'] == 'completed' else None,
        'error': job['error'] if job['status'] == 'failed' else None
    })

@app.route('/api/cancel_forecast/<job_id>', methods=['POST'])
def cancel_forecast(job_id):
    logger.info(f"Processing API request to cancel_forecast/{job_id}")
    
    if job_id not in forecast_jobs:
        logger.warning(f"Job {job_id} not found")
        return jsonify({'status': 'error', 'message': 'Job not found'})
    
    job = forecast_jobs[job_id]
    
    if job['status'] in ['completed', 'failed', 'cancelled']:
        logger.warning(f"Job {job_id} already in terminal state: {job['status']}")
        return jsonify({'status': 'error', 'message': f'Job already {job["status"]}'})
    
    # Mark the job as cancelled
    job['status'] = 'cancelled'
    logger.info(f"Job {job_id} cancelled")
    
    return jsonify({'status': 'cancelled', 'message': 'Forecast job cancelled'})

@app.route('/api/scenario_details/<scenario_name>', methods=['GET'])
def get_scenario_details(scenario_name):
    logger.info(f"Processing API request for scenario_details/{scenario_name}")
    
    try:
        if app.config['CURRENT_PROJECT_PATH'] is None:
            logger.warning("No project selected for scenario_details request")
            return jsonify({
                'status': 'error',
                'message': 'No project selected'
            })
        
        # Get scenario folder path
        scenario_folder = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results', 'demand_projection', scenario_name)
        logger.debug(f"Looking for scenario at {scenario_folder}")
        
        if not os.path.exists(scenario_folder):
            logger.warning(f"Scenario folder not found: {scenario_folder}")
            return jsonify({
                'status': 'error',
                'message': f'Scenario {scenario_name} not found'
            })
        
        # Get list of sectors from files in scenario folder
        sectors = []
        target_year = 2037  # Default
        
        logger.debug(f"Listing files in scenario folder: {scenario_folder}")
        for filename in os.listdir(scenario_folder):
            logger.debug(f"Found file: {filename}")
            if filename.endswith('.xlsx') and filename != 'aggregated.xlsx':
                sectors.append(filename.replace('.xlsx', ''))
        
        logger.debug(f"Identified sectors: {sectors}")
        
        # Try to get target year from metadata file if it exists
        metadata_path = os.path.join(scenario_folder, 'metadata.json')
        logger.debug(f"Checking for metadata file: {metadata_path}")
        
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    target_year = metadata.get('target_year', 2037)
                    logger.debug(f"Loaded target year from metadata: {target_year}")
            except Exception as e:
                logger.error(f"Error reading metadata file: {str(e)}")
                # Continue with the default target year
        else:
            # Also try to check for a summary.json file
            summary_path = os.path.join(scenario_folder, 'summary.json')
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, 'r') as f:
                        summary = json.load(f)
                        target_year = summary.get('target_year', 2037)
                        logger.debug(f"Loaded target year from summary: {target_year}")
                except Exception as e:
                    logger.error(f"Error reading summary file: {str(e)}")
        
        response_data = {
            'status': 'success',
            'scenario_name': scenario_name,
            'sectors': sectors,
            'target_year': target_year
        }
        logger.info(f"Successfully retrieved scenario details for {scenario_name}")
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.exception(f"Error processing scenario details for {scenario_name}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        })

@app.route('/api/download_comparison_data', methods=['POST'])
def download_comparison_data():
    logger.info("Processing API request for download_comparison_data")
    
    if not app.config['CURRENT_PROJECT_PATH']:
        logger.warning("No project loaded for download_comparison_data request")
        return jsonify({"status": "error", "message": "No project loaded."}), 400

    data = request.get_json()
    scenarios = data.get('scenarios', [])
    from_year = int(data.get('fromYear', datetime.now().year - 5))
    to_year = int(data.get('toYear', datetime.now().year + 10))
    unit = data.get('unit', 'TWh')
    sector_model_map = data.get('sectorModelMap', {})

    logger.debug(f"Comparison data request: scenarios={scenarios}, years={from_year}-{to_year}, unit={unit}")
    
    if len(scenarios) < 2:
        logger.warning("Insufficient scenarios for comparison (need at least 2)")
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
            logger.warning(f"No data found for scenario {scenario_name}")
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
        logger.warning("No data found for any of the selected scenarios")
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
    logger.info(f"Successfully created comparison data file: {download_filename}")

    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=download_filename)

# ==========================================
# WORKER FUNCTIONS
# ==========================================

def run_multiple_forecasts_job(job_id, project_path, data):
    """
    Run forecasts for multiple sectors in a single job, intelligently handling existing data
    
    Args:
        job_id (str): The unique identifier for this forecast job
        project_path (str): Path to the project directory
        data (dict): Configuration data for the forecast including scenario name, 
                    target year, and sector-specific configurations
    """
    logger.info(f"Starting forecast job {job_id} for project {project_path}")
    job = forecast_jobs[job_id]
    job['status'] = 'running'
    
    try:
        # Get parameters
        scenario_name = data.get('scenarioName')
        target_year = int(data.get('targetYear'))
        exclude_covid = data.get('excludeCovidYears', True)
        sector_configs = data.get('sectorConfigs', {})
        
        logger.info(f"Job {job_id} configuration: scenario={scenario_name}, target_year={target_year}, " +
                    f"exclude_covid={exclude_covid}, sectors={list(sector_configs.keys())}")
        
        # Update initial progress
        job['progress'] = 5
        
        # Load data
        demand_input_file_path = f"{project_path}/inputs/input_demand_file.xlsx"
        logger.debug(f"Loading input data from {demand_input_file_path}")
        
        try:
            sectors, _, param_dict, sector_data, _ = input_demand_data(demand_input_file_path)
        except Exception as e:
            logger.exception(f"Error loading input data: {e}")
            job['status'] = 'failed'
            job['error'] = f"Failed to load input data: {str(e)}"
            return
        
        # Get start and end years from parameters
        start_year = int(param_dict.get('Start_Year', 2006))
        
        # Validate sectors
        for sector in sector_configs.keys():
            if sector not in sector_data:
                logger.warning(f"Sector {sector} not found in input data, skipping")
                job['error'] = f"Sector {sector} not found in input data"
                job['status'] = 'failed'
                return
        
        # Prepare forecast directory
        forecast_dir = f"{project_path}/results/demand_projection/{scenario_name}"
        os.makedirs(forecast_dir, exist_ok=True)
        
        # Import the forecasting function from models
        try:
            from models.forecasting import Main_forecasting_function
            logger.debug("Successfully imported Main_forecasting_function")
        except ImportError as e:
            logger.exception(f"Error importing forecasting module: {e}")
            job['status'] = 'failed'
            job['error'] = f"Failed to import forecasting module: {str(e)}"
            return
        
        # Process each sector that needs forecasting
        sectors_using_existing_data = []
        sectors_forecasted = []
        sectors_with_errors = []
        
        total_sectors = len(sector_configs)
        logger.info(f"Will process {total_sectors} sectors: {list(sector_configs.keys())}")
        
        for idx, (sector, config) in enumerate(sector_configs.items()):
            # Check for cancellation
            if forecast_jobs[job_id]['status'] == 'cancelled':
                logger.info(f"Job {job_id} was cancelled, stopping processing")
                return
            
            # Update progress
            job['currentSector'] = sector
            job['processedSectors'] = idx
            progress_per_sector = 90 / max(1, total_sectors)
            current_progress = 5 + int(idx * progress_per_sector)
            job['progress'] = current_progress
            
            logger.info(f"Processing sector {sector} ({idx+1}/{total_sectors}), progress: {current_progress}%")
            
            try:
                # Get selected models for this sector
                selected_models = config.get('models', ['MLR', 'SLR', 'WAM', 'TimeSeries'])
                
                logger.debug(f"Models for {sector}: {selected_models}")
                
                # Base parameters for all models
                base_params = {
                    'target_year': target_year,
                    'exclude_covid': exclude_covid
                }
                
                # Set up model-specific parameters
                model_params = {}
                if 'MLR' in selected_models:
                    independent_vars = config.get('independentVars', [])
                    logger.debug(f"MLR independent variables for {sector}: {independent_vars}")
                    model_params['MLR'] = {'independent_vars': independent_vars}
                
                if 'WAM' in selected_models:
                    window_size = int(config.get('windowSize', 10))
                    logger.debug(f"WAM window size for {sector}: {window_size}")
                    model_params['WAM'] = {'window_size': window_size}
                
                # Check if we have valid sector data
                if sector not in sector_data:
                    logger.error(f"Sector {sector} not in input data, skipping")
                    sectors_with_errors.append(sector)
                    continue
                
                # Run forecast for this sector with all selected models
                logger.debug(f"Starting forecast for {sector} with models: {selected_models}")
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
                    logger.debug(f"Sector {sector} used existing data")
                    sectors_using_existing_data.append(sector)
                else:
                    logger.debug(f"Sector {sector} forecast completed")
                    sectors_forecasted.append(sector)
                
            except Exception as e:
                logger.exception(f"Error processing sector {sector}: {str(e)}")
                sectors_with_errors.append(sector)
                
                # Continue processing other sectors despite this error
                continue
            
            # Update progress after each sector
            sector_progress = 5 + int((idx + 1) * progress_per_sector)
            job['progress'] = sector_progress
            job['processedSectors'] = idx + 1
            
            logger.debug(f"Completed sector {sector}, progress: {sector_progress}%")
            
            # Check for cancellation again
            if forecast_jobs[job_id]['status'] == 'cancelled':
                logger.info(f"Job {job_id} was cancelled after processing {sector}")
                return
        
        logger.info(f"All sectors processed. Forecasted: {len(sectors_forecasted)}, " + 
                   f"Used existing: {len(sectors_using_existing_data)}, Errors: {len(sectors_with_errors)}")
        
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
        
        logger.debug(f"Writing summary file to {forecast_dir}/summary.json")
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
        
        logger.info(f"Forecast job {job_id} completed successfully")
        
    except Exception as e:
        # Handle errors
        logger.exception(f"Error in forecast job {job_id}: {str(e)}")
        job['status'] = 'failed'
        job['error'] = str(e)

# ==========================================
# ERROR HANDLERS
# ==========================================

@app.errorhandler(404)
def page_not_found(e):
    logger.warning(f"404 error: {request.path}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"500 error: {str(e)}")
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.exception(f"Unhandled exception: {str(e)}")
    return render_template('500.html'), 500

# ==========================================
# MAIN ENTRY POINT
# ==========================================

if __name__ == '__main__':
    try:
        # Final configuration checks
        validate_app_config()
        
        # Create template files if needed
        create_template_files()
        
        # Start the Flask application
        logger.info("Starting Flask application")
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        print(f"CRITICAL ERROR: {e}")