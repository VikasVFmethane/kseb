import os
import json
import logging
from datetime import datetime
import numpy as np
import pandas as pd
from werkzeug.utils import secure_filename
from typing import Dict, Any, List, Optional, Tuple, Union # Added for type hints

logger = logging.getLogger(__name__)

def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if a file has an allowed extension."""
    logger.debug(f"Checking file '{filename}' against allowed extensions: {allowed_extensions}")
    if not filename:
        logger.warning("Empty filename passed to allowed_file.")
        return False
    
    parts = filename.rsplit('.', 1)
    if len(parts) < 2: # No extension
        logger.debug(f"Filename '{filename}' has no extension.")
        return False
        
    ext = parts[1].lower()
    is_allowed = ext in allowed_extensions
    
    if is_allowed:
        logger.debug(f"File extension '{ext}' for filename '{filename}' is allowed.")
    else:
        logger.debug(f"File extension '{ext}' for filename '{filename}' is not in {allowed_extensions}.")
    return is_allowed

def save_recent_project(user_id: str, project_name: str, project_path: str, recent_projects_dir_path: str) -> bool:
    """Save project to recent projects list."""
    logger.info(f"Saving recent project: '{project_name}' at '{project_path}' for user '{user_id}' to dir '{recent_projects_dir_path}'")
    try:
        # Ensure the directory exists
        os.makedirs(recent_projects_dir_path, exist_ok=True)
        filename = os.path.join(recent_projects_dir_path, f"{secure_filename(user_id)}.json")
        
        recent_projects: List[Dict[str, Any]] = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    recent_projects = json.load(f)
                logger.debug(f"Loaded {len(recent_projects)} existing recent projects from {filename}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from {filename}: {e}. Initializing with empty list.")
                recent_projects = []
            except IOError as e:
                logger.error(f"IOError reading {filename}: {e}. Initializing with empty list.")
                recent_projects = []
        else:
            logger.debug(f"No existing recent projects file at {filename}, creating new list.")
        
        existing_index: Optional[int] = None
        for i, project in enumerate(recent_projects):
            if project.get('path') == project_path:
                existing_index = i
                break
        
        if existing_index is not None:
            logger.debug(f"Project '{project_name}' already exists at index {existing_index}, removing old entry.")
            recent_projects.pop(existing_index)
        
        recent_projects.insert(0, {
            'name': project_name,
            'path': project_path,
            'last_opened': datetime.now().isoformat(),
            'timestamp': int(datetime.now().timestamp())
        })
        
        recent_projects = recent_projects[:10] # Keep only most recent 10
        
        try:
            with open(filename, 'w') as f:
                json.dump(recent_projects, f, indent=4)
            logger.info(f"Successfully saved recent project list for user {user_id} to {filename}")
        except IOError as e:
            logger.error(f"Error writing recent projects file {filename}: {e}")
            return False
        
        return True
    except Exception as e:
        logger.exception(f"An unexpected error occurred in save_recent_project for user {user_id}, project {project_name}: {e}")
        return False

def get_forecast_data_for_sector(scenario_path: str, sector: str, from_year: int, to_year: int, unit: str) -> Optional[pd.DataFrame]:
    """Helper function to get forecast data for a specific sector."""
    logger.debug(f"Getting forecast data for sector '{sector}' in path '{scenario_path}' for years {from_year}-{to_year}, unit '{unit}'")
    file_path = os.path.join(scenario_path, f"{secure_filename(sector)}.xlsx")
    
    try:
        if not os.path.exists(file_path):
            logger.warning(f"Sector file not found: {file_path}")
            return None
        
        df = pd.read_excel(file_path, sheet_name='Results')
        
        if 'Year' not in df.columns:
            logger.warning(f"'Year' column missing in {file_path}")
            return None
        
        df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
        df = df.dropna(subset=['Year']) # Remove rows where Year could not be coerced
        df['Year'] = df['Year'].astype(int)
        
        df = df[(df['Year'] >= from_year) & (df['Year'] <= to_year)]
        
        # Placeholder for unit conversion logic if ever needed
        # For now, assume data is in the correct unit or 'unit_conversion' column logic is handled elsewhere/previously
        if unit != 'TWh' and 'unit_conversion_factor_to_twh' in df.columns: # Example column name
            logger.info(f"Unit conversion might be needed for sector {sector}. Current unit: TWh (assumed), requested: {unit}.")
            # df['Value'] = df['Value'] * df['unit_conversion_factor_to_twh'] # Example conversion
            pass
        
        logger.debug(f"Successfully retrieved and filtered data for sector {sector} from {file_path}")
        return df
        
    except FileNotFoundError:
        logger.warning(f"Forecast file not found for sector {sector} at path: {file_path}")
        return None
    except pd.errors.EmptyDataError:
        logger.warning(f"No data found in 'Results' sheet of {file_path} for sector {sector}.")
        return None
    except KeyError as e: # Handles missing 'Results' sheet or other key errors from pandas
        logger.warning(f"Sheet 'Results' or expected column not found in {file_path} for sector {sector}: {e}")
        return None
    except Exception as e:
        logger.exception(f"An unexpected error occurred getting forecast data for sector {sector} from {file_path}: {e}")
        return None

def handle_nan_values(obj: Any) -> Any:
    """Convert NaN values to null for JSON serialization."""
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: handle_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [handle_nan_values(item) for item in obj]
    return obj

def validate_load_profile_form(form_data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    """Validate load profile generation form data."""
    errors: Dict[str, str] = {}
    logger.debug(f"Validating load profile form data: {form_data}")
    
    method = form_data.get('method')
    if not method or method not in ['base_year', 'ml_weather']:
        errors['method'] = 'Valid method (base_year or ml_weather) is required.'
        logger.warning(f"Validation error: method '{method}' is invalid.")
    
    if method == 'base_year':
        base_year_str = form_data.get('base_year')
        if not base_year_str:
            errors['base_year'] = 'Base year is required for base year method.'
            logger.warning("Validation error: base_year not provided for base_year method.")
        else:
            try:
                base_year_int = int(base_year_str)
                current_year = datetime.now().year
                if not (2000 <= base_year_int <= current_year):
                    errors['base_year'] = f'Base year must be between 2000 and {current_year}. Got {base_year_int}.'
                    logger.warning(f"Validation error: base_year '{base_year_int}' out of range.")
            except (ValueError, TypeError):
                errors['base_year'] = 'Base year must be a valid integer.'
                logger.warning(f"Validation error: base_year '{base_year_str}' is not an integer.")
    
    try:
        start_year = int(form_data.get('start_year', str(datetime.now().year)))
        end_year = int(form_data.get('end_year', str(datetime.now().year + 14)))
        
        if start_year >= end_year:
            errors['year_range'] = 'End year must be greater than start year.'
            logger.warning(f"Validation error: start_year {start_year} >= end_year {end_year}.")
        
        if end_year - start_year > 50:
            errors['year_range'] = 'Year range cannot exceed 50 years.'
            logger.warning(f"Validation error: year range {end_year - start_year} exceeds 50 years.")
            
    except (ValueError, TypeError) as e:
        errors['year_range'] = f'Invalid year range values: {e}'
        logger.warning(f"Validation error: invalid year range values - {e}")
    
    output_frequency = form_data.get('output_frequency', 'hourly')
    if output_frequency not in ['hourly', 'half_hourly', '15min']:
        errors['output_frequency'] = "Invalid output frequency. Choose from 'hourly', 'half_hourly', '15min'."
        logger.warning(f"Validation error: invalid output_frequency '{output_frequency}'.")
    
    output_unit = form_data.get('output_unit', 'MW')
    if output_unit not in ['MW', 'kW', 'GW']:
        errors['output_unit'] = "Invalid output unit. Choose from 'MW', 'kW', 'GW'."
        logger.warning(f"Validation error: invalid output_unit '{output_unit}'.")
    
    if form_data.get('use_improved_load_factors') == 'true':
        lf_improvement_str = form_data.get('load_factor_improvement')
        if lf_improvement_str:
            try:
                lf_value = float(lf_improvement_str)
                if not (0 <= lf_value <= 10): # Assuming percentage 0-10%
                    errors['load_factor_improvement'] = 'Load factor improvement must be between 0% and 10%.'
                    logger.warning(f"Validation error: lf_improvement '{lf_value}' out of range 0-10%.")
            except (ValueError, TypeError):
                errors['load_factor_improvement'] = 'Load factor improvement must be a valid number.'
                logger.warning(f"Validation error: lf_improvement '{lf_improvement_str}' is not a number.")
    
    is_valid = not errors
    if not is_valid:
        logger.info(f"Load profile form validation failed with errors: {errors}")
    else:
        logger.info("Load profile form validation successful.")
    return is_valid, errors

def parse_load_factor_form_data(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and structure load factor related form data."""
    logger.debug(f"Parsing load factor form data: {form_data}")
    
    load_factor_config = {
        'use_improved_load_factors': form_data.get('use_improved_load_factors') == 'true',
        'load_factor_improvement': None,
        'custom_load_factors': None,
        'use_excel_load_factors': form_data.get('use_excel_load_factors') == 'true',
        'use_monthly_excel_load_factors': form_data.get('use_monthly_excel_load_factors') == 'true'
    }
    
    lf_improvement_str = form_data.get('load_factor_improvement')
    if load_factor_config['use_improved_load_factors'] and lf_improvement_str:
        try:
            load_factor_config['load_factor_improvement'] = float(lf_improvement_str) / 100.0 # Convert % to decimal
            logger.debug(f"Parsed load_factor_improvement: {load_factor_config['load_factor_improvement']}")
        except (ValueError, TypeError):
            logger.warning(f"Invalid load factor improvement value '{lf_improvement_str}', defaulting to None.")
    
    custom_lf_json_str = form_data.get('custom_load_factors')
    if custom_lf_json_str:
        try:
            custom_lf_dict_str_keys = json.loads(custom_lf_json_str)
            load_factor_config['custom_load_factors'] = {
                int(k): float(v) / 100.0 for k, v in custom_lf_dict_str_keys.items() # Convert % to decimal
            }
            logger.debug(f"Parsed custom_load_factors: {load_factor_config['custom_load_factors']}")
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"Invalid custom load factors JSON string '{custom_lf_json_str}': {e}. Defaulting to None.")
            
    logger.info(f"Successfully parsed load factor config: {load_factor_config}")
    return load_factor_config
