# blueprints/loadprofile_bp.py 


from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime
import shutil
from werkzeug.utils import secure_filename

# Import the enhanced load profile system
from utils.load_profile_generator import (
    LoadProfileConfig, LoadProfileGenerator, 
    create_load_curve, UnitConverter, get_financial_year,
    extract_monthly_patterns_from_excel, get_future_annual_demand
)

loadprofile_bp = Blueprint('loadprofile', 
                           __name__, 
                           template_folder='../templates', 
                           static_folder='../static',
                           url_prefix='/load_profile')

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def handle_nan_values(obj):
    """Handle NaN values in JSON serialization"""
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {k: handle_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [handle_nan_values(item) for item in obj]
    return obj

class EnhancedLoadProfileManager:
    """Enhanced Load Profile Manager using the new system"""
    
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.inputs_folder = os.path.join(project_path, 'inputs')
        self.results_folder = os.path.join(project_path, 'results')
        self.load_profiles_folder = os.path.join(self.results_folder, 'load_profiles')
        self.converter = UnitConverter()
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        os.makedirs(self.inputs_folder, exist_ok=True)
        os.makedirs(self.results_folder, exist_ok=True)
        os.makedirs(self.load_profiles_folder, exist_ok=True)
    
    def get_input_file_path(self) -> str:
        """Get path to input Excel file"""
        return os.path.join(self.inputs_folder, 'load_curve_template.xlsx')
    
    def check_input_file_exists(self) -> tuple:
        """Check if input file exists and return modification time"""
        input_file_path = self.get_input_file_path()
        if os.path.exists(input_file_path):
            mod_time = datetime.fromtimestamp(os.path.getmtime(input_file_path))
            return True, mod_time.strftime('%Y-%m-%d %H:%M:%S')
        return False, None
    
    def get_available_years(self) -> list:
        """Get available years from historical data with enhanced error handling"""
        input_file_path = self.get_input_file_path()
        if not os.path.exists(input_file_path):
            current_app.logger.warning(f"Input file not found: {input_file_path}")
            return []
        
        try:
            # Use enhanced data loader
            config = LoadProfileConfig()
            from utils.load_profile_generator import DataLoader
            
            data_loader =DataLoader(input_file_path, self.project_path, config)
            historical_data = data_loader.load_historical_demand()
            
            if historical_data.empty:
                current_app.logger.warning("No historical data found in file")
                return []
            
            years = sorted(historical_data['financial_year'].unique().tolist())
            current_app.logger.info(f"Found {len(years)} available years: {years}")
            return years
            
        except Exception as e:
            current_app.logger.error(f"Error reading historical years: {e}")
            return []
    
    def get_forecast_scenarios(self) -> list:
        """Get available forecast scenarios"""
        demand_projection_folder = os.path.join(self.results_folder, 'demand_projection')
        if not os.path.exists(demand_projection_folder):
            return []
        
        scenarios = []
        try:
            for item in os.listdir(demand_projection_folder):
                item_path = os.path.join(demand_projection_folder, item)
                if os.path.isdir(item_path):
                    # Check if it has consolidated_results.csv
                    csv_path = os.path.join(item_path, 'consolidated_results.csv')
                    if os.path.exists(csv_path):
                        scenarios.append(item)
        except Exception as e:
            current_app.logger.error(f"Error getting forecast scenarios: {e}")
        
        return scenarios
    
    def get_generated_profiles(self) -> list:
        """Get list of generated profiles"""
        profiles = []
        if not os.path.exists(self.load_profiles_folder):
            return profiles
        
        try:
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
        except Exception as e:
            current_app.logger.error(f"Error getting generated profiles: {e}")
        
        profiles.sort(key=lambda x: x['created'], reverse=True)
        return profiles
    
    def save_uploaded_file(self, file) -> bool:
        """Save uploaded Excel file after validation"""
        if not file or not file.filename.endswith('.xlsx'):
            return False
        
        temp_path = os.path.join(self.inputs_folder, 'temp_' + secure_filename(file.filename))
        
        try:
            file.save(temp_path)
            
            # Validate file structure using enhanced data loader
            config = LoadProfileConfig()
            from utils.load_profile_generator import DataLoader
            
            data_loader = DataLoader(temp_path, self.project_path, config)
            historical_data = data_loader.load_historical_demand()
            
            if historical_data.empty:
                raise ValueError("No valid historical demand data found")
            
            # If validation passes, move to final location
            final_path = self.get_input_file_path()
            if os.path.exists(final_path):
                # Backup existing file
                backup_path = final_path + '.backup'
                shutil.move(final_path, backup_path)
            
            shutil.move(temp_path, final_path)
            current_app.logger.info(f"Saved valid Excel file to {final_path}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error validating Excel file: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
    
    def generate_enhanced_profile(self, form_data: dict) -> tuple:
        """Generate profile using the enhanced system"""
        try:
            # Parse form data into configuration
            config = self._parse_generation_config(form_data)
            
            # Get file paths
            excel_file_path = self.get_input_file_path()
            if not os.path.exists(excel_file_path):
                raise FileNotFoundError("Input Excel file not found")
            
            # Extract scenario name
            scenario_name = form_data.get('forecast_scenario')
            if scenario_name in ["null", "undefined", ""]:
                scenario_name = None
            
            # Generate profile using enhanced system
            profile_df = create_load_curve(
                excel_file_path=excel_file_path,
                project_path=self.project_path,
                config=config,
                scenario_name=scenario_name
            )
            
            # Generate profile ID and save
            profile_id = self.generate_profile_id(scenario_name, config.method, config.base_year)
            output_path = self.get_profile_path(profile_id)
            
            # Save to CSV
            profile_df.to_csv(output_path, index=False)
            
            current_app.logger.info(f"Generated enhanced profile {profile_id} successfully")
            
            return True, profile_id, "Enhanced profile generated successfully"
            
        except Exception as e:
            current_app.logger.error(f"Error generating enhanced profile: {e}")
            return False, None, str(e)
    
    def _parse_generation_config(self, form_data: dict) -> LoadProfileConfig:
        """Parse form data into LoadProfileConfig"""
        
        # Parse custom load factors
        custom_load_factors = None
        custom_lf_json = form_data.get('custom_load_factors')
        if custom_lf_json:
            try:
                custom_load_factors = {
                    int(k): float(v) for k, v in json.loads(custom_lf_json).items()
                }
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                current_app.logger.warning(f"Invalid custom load factors JSON: {e}")
        
        # Parse load factor improvement
        lf_improvement = None
        lf_improvement_str = form_data.get('load_factor_improvement')
        if lf_improvement_str:
            try:
                lf_improvement = float(lf_improvement_str)
            except (ValueError, TypeError):
                current_app.logger.warning(f"Invalid load factor improvement: {lf_improvement_str}")
        
        return LoadProfileConfig(
            method=form_data.get('method', 'base_year'),
            base_year=int(form_data['base_year']) if form_data.get('base_year') else None,
            start_year=int(form_data.get('start_year', datetime.now().year)),
            end_year=int(form_data.get('end_year', datetime.now().year + 14)),
            output_frequency=form_data.get('output_frequency', 'hourly'),
            output_unit=form_data.get('output_unit', 'MW'),
            apply_constraints=form_data.get('use_constraints') == 'true',
            use_monthly_peaks=form_data.get('monthly_max') == 'on',
            use_load_factors=form_data.get('use_improved_load_factors') == 'true',
            use_excel_load_factors=form_data.get('use_excel_load_factors') == 'true',
            load_factor_improvement_pct=lf_improvement,
            custom_load_factors=custom_load_factors,
            use_holidays=form_data.get('use_holidays', 'true') == 'true',
            
            # Enhanced settings
            preserve_weekday_weekend_patterns=True,
            preserve_holiday_patterns=True,
            smooth_transitions=True,
            
            # Strict tolerances for better accuracy
            yearly_tolerance_pct=0.01,
            monthly_tolerance_pct=0.1,
            load_factor_tolerance_pct=1.0
        )
    
    def generate_profile_id(self, scenario_name: str, method: str, base_year=None) -> str:
        """Generate unique profile ID"""
        profile_id_parts = []
        
        if scenario_name and scenario_name not in ["null", "undefined", ""]:
            clean_scenario = scenario_name.replace('/', '_').replace('\\', '_')
            profile_id_parts.append(clean_scenario)
        else:
            profile_id_parts.append("excel_annual")
        
        profile_id_parts.append(method)
        
        if method == 'base_year' and base_year:
            profile_id_parts.append(f"by{base_year}")
        
        profile_id_parts.append(datetime.now().strftime('%Y%m%d_%H%M%S'))
        
        return "_".join(profile_id_parts)
    
    def get_profile_path(self, profile_id: str) -> str:
        """Get file path for a profile"""
        return os.path.join(self.load_profiles_folder, f"{profile_id}.csv")
    
    def load_profile_data(self, profile_id: str):
        """Load profile data from CSV file"""
        profile_path = self.get_profile_path(profile_id)
        if not os.path.exists(profile_path):
            return None
        
        try:
            return pd.read_csv(profile_path)
        except Exception as e:
            current_app.logger.error(f"Error loading profile {profile_id}: {e}")
            return None
    
    def get_profile_metadata(self, profile_id: str):
        """Get metadata for a profile"""
        df = self.load_profile_data(profile_id)
        if df is None:
            return None
        
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            available_years = sorted(df['timestamp'].dt.year.unique().tolist())
            
            # Determine demand column
            demand_col = 'demand' if 'demand' in df.columns else 'Demand'
            
            # Calculate statistics
            peak_demand = df[demand_col].max()
            peak_date = df.loc[df[demand_col].idxmax(), 'timestamp']
            avg_demand = df[demand_col].mean()
            min_demand = df[demand_col].min()
            min_date = df.loc[df[demand_col].idxmin(), 'timestamp']
            std_dev = df[demand_col].std()
            load_factor = (avg_demand / peak_demand) * 100 if peak_demand > 0 else 0
            
            # Generate summary
            summary = (
                f"This enhanced load profile spans {len(available_years)} years from "
                f"{available_years[0] if available_years else 'N/A'} to "
                f"{available_years[-1] if available_years else 'N/A'}. "
                f"It has an average demand of {avg_demand:.2f} MW with a peak of "
                f"{peak_demand:.2f} MW, resulting in a load factor of {load_factor:.2f}%. "
                f"Generated with enhanced constraint application ensuring yearly totals, "
                f"monthly patterns, and load factors are preserved."
            )
            
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
            current_app.logger.error(f"Error calculating metadata for profile {profile_id}: {e}")
            return None
    
    def get_profile_year_data(self, profile_id: str, year: int):
        """Get profile data for a specific year"""
        df = self.load_profile_data(profile_id)
        if df is None:
            return None
        
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            year_df = df[df['timestamp'].dt.year == year]
            
            if year_df.empty:
                return []
            
            demand_col = 'demand' if 'demand' in year_df.columns else 'Demand'
            
            profile_data = []
            for _, row in year_df.iterrows():
                profile_data.append({
                    'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'demand': float(row[demand_col])
                })
            
            return profile_data
        except Exception as e:
            current_app.logger.error(f"Error getting year data for profile {profile_id}, year {year}: {e}")
            return None

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_load_profile_form(form_data: dict) -> tuple:
    """Validate load profile generation form data"""
    errors = {}
    
    # Validate method
    method = form_data.get('method')
    if not method or method not in ['base_year', 'ml_weather']:
        errors['method'] = 'Valid method is required'
    
    # Validate base year for base_year method
    if method == 'base_year':
        base_year = form_data.get('base_year')
        if not base_year:
            errors['base_year'] = 'Base year is required for base year method'
        else:
            try:
                base_year_int = int(base_year)
                if base_year_int < 2000 or base_year_int > datetime.now().year:
                    errors['base_year'] = f'Base year must be between 2000 and {datetime.now().year}'
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
    if form_data.get('output_frequency', 'hourly') not in ['hourly', 'half_hourly', '15min']:
        errors['output_frequency'] = 'Invalid output frequency'
    
    if form_data.get('output_unit', 'MW') not in ['MW', 'kW', 'GW']:
        errors['output_unit'] = 'Invalid output unit'
    
    # Validate load factor improvement
    if form_data.get('use_improved_load_factors') == 'true':
        lf_improvement = form_data.get('load_factor_improvement')
        if lf_improvement:
            try:
                lf_val = float(lf_improvement)
                if not (0 <= lf_val <= 10):
                    errors['load_factor_improvement'] = 'Load factor improvement must be between 0 and 10%'
            except (ValueError, TypeError):
                errors['load_factor_improvement'] = 'Load factor improvement must be a valid number'
    
    return len(errors) == 0, errors

# =============================================================================
# ROUTE HANDLERS
# =============================================================================

def _handle_file_upload(lp_manager: EnhancedLoadProfileManager):
    """Handle file upload request"""
    current_app.logger.info("Processing file upload")
    
    if 'profile_file' not in request.files:
        flash('No file uploaded', 'warning')
        return redirect(request.url)
    
    file = request.files['profile_file']
    if file.filename == '':
        flash('No file selected', 'warning')
        return redirect(request.url)
    
    if file and file.filename.endswith('.xlsx'):
        if lp_manager.save_uploaded_file(file):
            flash('File uploaded and validated successfully', 'success')
        else:
            flash('Invalid Excel file. Please ensure it contains required sheets and valid data.', 'danger')
    else:
        flash('Invalid file format. Please upload an Excel file.', 'danger')
    
    return redirect(url_for('loadprofile.load_profile_creation_route'))

def _render_load_profile_page(lp_manager: EnhancedLoadProfileManager):
    """Render the load profile creation page"""
    current_app.logger.info("Rendering load profile creation page")
    
    input_file_exists, input_file_date = lp_manager.check_input_file_exists()
    forecast_scenarios = lp_manager.get_forecast_scenarios()
    available_years = lp_manager.get_available_years() if input_file_exists else []
    generated_profiles = lp_manager.get_generated_profiles()
    
    return render_template(
        'load_profile.html',
        input_file_exists=input_file_exists,
        input_file_date=input_file_date,
        forecast_scenarios=forecast_scenarios,
        available_years=available_years,
        generated_profiles=generated_profiles,
        current_project=current_app.config.get('CURRENT_PROJECT')
    )

# =============================================================================
# ROUTES
# =============================================================================

@loadprofile_bp.route('/', methods=['GET', 'POST'])
def load_profile_base_route():
    """Base route - redirect to creation"""
    return redirect(url_for('loadprofile.load_profile_creation_route'))

@loadprofile_bp.route('/creation', methods=['GET', 'POST'])
def load_profile_creation_route():
    """Main load profile creation route"""
    current_app.logger.info("Accessing load profile creation route")
    
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('core.home'))
    
    lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
    
    try:
        if request.method == 'POST':
            return _handle_file_upload(lp_manager)
        return _render_load_profile_page(lp_manager)
    except Exception as e:
        current_app.logger.exception(f"Error in load profile creation route: {str(e)}")
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('core.home'))

# =============================================================================
# ENHANCED API ROUTES
# =============================================================================

@loadprofile_bp.route('/api/generate_load_profiles', methods=['POST'])
def generate_load_profiles_api():
    """Generate load profiles using enhanced system"""
    current_app.logger.info("Processing API request to generate enhanced load profiles")
    
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    try:
        lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        
        # Validate input file exists
        input_file_path = lp_manager.get_input_file_path()
        if not os.path.exists(input_file_path):
            return jsonify({
                'status': 'error', 
                'message': 'Load curve template file not found. Please upload a valid Excel file first.'
            }), 404
        
        # Get form data
        form_data = dict(request.form)
        
        # Validate form data
        is_valid, validation_errors = validate_load_profile_form(form_data)
        if not is_valid:
            error_message = '; '.join(validation_errors.values())
            return jsonify({
                'status': 'error', 
                'message': f'Validation errors: {error_message}'
            }), 400
        
        # Generate profile using enhanced system
        success, profile_id, message = lp_manager.generate_enhanced_profile(form_data)
        
        if success:
            # Get updated list of profiles
            generated_profiles = lp_manager.get_generated_profiles()
            
            return jsonify({
                'status': 'success',
                'message': 'Enhanced load profiles generated successfully!',
                'profile_id': profile_id,
                'details': message,
                'profiles': handle_nan_values(generated_profiles),
                'enhanced': True
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Enhanced generation failed: {message}'
            }), 500
            
    except Exception as e:
        current_app.logger.exception(f"Error in generate_load_profiles_api: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }), 500

@loadprofile_bp.route('/api/monthly_patterns/<int:base_year>', methods=['GET'])
def get_monthly_patterns_api(base_year: int):
    """Get monthly patterns for base year using enhanced system"""
    current_app.logger.info(f"Getting enhanced monthly patterns for year {base_year}")
    
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    if not (2000 <= base_year <= datetime.now().year):
        return jsonify({
            'status': 'error', 
            'message': f'Base year must be between 2000 and {datetime.now().year}'
        }), 400
    
    try:
        lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        input_file_path = lp_manager.get_input_file_path()
        
        if not os.path.exists(input_file_path):
            return jsonify({'status': 'error', 'message': 'Input file not found'}), 404
        
        # Use enhanced system to extract patterns
        patterns = extract_monthly_patterns_from_excel(input_file_path, base_year)
        
        return jsonify({
            'status': 'success',
            **patterns,
            'enhanced': True,
            'calculatedFromExcel': True
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error generating enhanced monthly patterns: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error generating enhanced monthly patterns: {str(e)}'
        }), 500

@loadprofile_bp.route('/api/projected_future_metrics/<int:base_year>/<int:start_year>/<int:end_year>', methods=['GET'])
def get_projected_future_metrics_api(base_year: int, start_year: int, end_year: int):
    """Get projected future metrics using enhanced system"""
    current_app.logger.info(f"Getting enhanced projected metrics for base_year={base_year}, range={start_year}-{end_year}")
    
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    if start_year >= end_year:
        return jsonify({
            'status': 'error', 
            'message': 'End year must be greater than start year'
        }), 400
    
    if end_year - start_year > 50:
        return jsonify({
            'status': 'error', 
            'message': 'Year range cannot exceed 50 years'
        }), 400
    
    try:
        lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        excel_file_path = lp_manager.get_input_file_path()
        
        if not os.path.exists(excel_file_path):
            return jsonify({
                'status': 'error', 
                'message': 'Load curve input Excel file not found.'
            }), 404
        
        # Get scenario name from query params
        forecast_scenario = request.args.get('forecast_scenario')
        scenario_name = forecast_scenario if forecast_scenario and forecast_scenario not in ["null", "undefined"] else None
        
        # Load annual demand using enhanced system
        annual_targets = get_future_annual_demand(
            current_app.config['CURRENT_PROJECT_PATH'], 
            start_year, end_year, scenario_name
        )
        
        if not annual_targets:
            return jsonify({
                'status': 'error',
                'message': 'No annual demand data found for the specified range'
            }), 404
        
        # Extract patterns using enhanced system
        patterns = extract_monthly_patterns_from_excel(excel_file_path, base_year)
        monthly_shares = {i+1: share/100 for i, share in enumerate(patterns['patternData']['Share of Annual (%)'])}
        
        # Calculate projections
        projected_data = []
        months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
        
        for year in range(start_year, end_year + 1):
            if year not in annual_targets:
                current_app.logger.warning(f"No annual target for FY {year}")
                continue
            
            annual_total_gwh = annual_targets[year]
            
            monthly_data = []
            for i, month_name in enumerate(months):
                month_num = [4,5,6,7,8,9,10,11,12,1,2,3][i]
                share = monthly_shares.get(month_num, 1/12)
                monthly_total_gwh = annual_total_gwh * share
                
                # Calculate monthly metrics
                days_in_month = 30  # Approximate
                monthly_avg_mw = monthly_total_gwh * 1000 / (days_in_month * 24)
                
                # Use pattern load factors
                monthly_lf = patterns['patternData']['Load Factor (%)'][i] / 100
                monthly_max_mw = monthly_avg_mw / monthly_lf if monthly_lf > 0 else monthly_avg_mw / 0.65
                
                monthly_data.append({
                    'month': month_name,
                    'totalDemand_GWh': round(monthly_total_gwh, 2),
                    'avgDemand_MW': round(monthly_avg_mw, 2),
                    'maxDemand_MW': round(monthly_max_mw, 2),
                    'loadFactor_Percent': round(monthly_lf * 100, 1)
                })
            
            # Calculate yearly load factor
            total_avg = sum(m['avgDemand_MW'] for m in monthly_data) / 12
            max_peak = max(m['maxDemand_MW'] for m in monthly_data)
            yearly_lf = (total_avg / max_peak * 100) if max_peak > 0 else 0
            
            projected_data.append({
                'year': year,
                'annualTotal_GWh': round(annual_total_gwh, 2),
                'monthlyData': monthly_data,
                'yearlyLoadFactor_Percent': round(yearly_lf, 1)
            })
        
        return jsonify({
            'status': 'success',
            'data': handle_nan_values(projected_data),
            'baseYearMonths': months,
            'enhanced': True
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error in get_projected_future_metrics_api: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@loadprofile_bp.route('/api/metadata/<profile_id>', methods=['GET'])
def get_load_profile_metadata_api(profile_id):
    """Get load profile metadata"""
    current_app.logger.info(f"Getting metadata for enhanced profile {profile_id}")
    
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    if not profile_id or not profile_id.strip():
        return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
    
    try:
        lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        metadata = lp_manager.get_profile_metadata(profile_id)
        
        if metadata is None:
            return jsonify({
                'status': 'error', 
                'message': f'Enhanced profile {profile_id} not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'enhanced': True,
            **handle_nan_values(metadata)
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error getting profile metadata for {profile_id}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting profile metadata: {str(e)}'
        }), 500

@loadprofile_bp.route('/api/data/<profile_id>/<year>', methods=['GET'])
def get_load_profile_data_api(profile_id, year):
    """Get load profile data for specific year"""
    current_app.logger.info(f"Getting enhanced profile data for {profile_id}/{year}")
    
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    if not profile_id or not profile_id.strip():
        return jsonify({'status': 'error', 'message': 'Profile ID is required'}), 400
    
    try:
        year_int = int(year)
        if not (2000 <= year_int <= 2100):
            return jsonify({'status': 'error', 'message': 'Invalid year'}), 400
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Year must be a valid integer'}), 400
    
    try:
        lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        profile_data = lp_manager.get_profile_year_data(profile_id, year_int)
        
        if profile_data is None:
            return jsonify({
                'status': 'error', 
                'message': f'Enhanced profile {profile_id} not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'profile_id': profile_id,
            'year': year,
            'enhanced': True,
            'profile_data': handle_nan_values(profile_data)
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error getting profile data for {profile_id}/{year}: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting profile data: {str(e)}'
        }), 500

# Validation endpoint for troubleshooting
@loadprofile_bp.route('/api/validate_input_file', methods=['GET'])
def validate_input_file_api():
    """Validate input file structure and data"""
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    try:
        lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        input_file_path = lp_manager.get_input_file_path()
        
        if not os.path.exists(input_file_path):
            return jsonify({
                'status': 'error',
                'message': 'Input file not found',
                'file_path': input_file_path
            })
        
        # Test data loading
        config = LoadProfileConfig()
        from utils.load_profile_generator import DataLoader
        
        data_loader = DataLoader(input_file_path, current_app.config['CURRENT_PROJECT_PATH'], config)
        
        validation_results = {}
        
        # Test historical data loading
        try:
            historical_data = data_loader.load_historical_demand()
            validation_results['historical_data'] = {
                'status': 'success',
                'rows': len(historical_data),
                'years': sorted(historical_data['financial_year'].unique().tolist()) if not historical_data.empty else [],
                'date_range': {
                    'start': str(historical_data['datetime'].min()) if not historical_data.empty else None,
                    'end': str(historical_data['datetime'].max()) if not historical_data.empty else None
                }
            }
        except Exception as e:
            validation_results['historical_data'] = {
                'status': 'error',
                'message': str(e)
            }
        
        # Test annual targets loading
        try:
            annual_targets = data_loader.load_annual_targets()
            validation_results['annual_targets'] = {
                'status': 'success',
                'years': list(annual_targets.keys()),
                'values': {str(k): v for k, v in annual_targets.items()}
            }
        except Exception as e:
            validation_results['annual_targets'] = {
                'status': 'error',
                'message': str(e)
            }
        
        # Test monthly peaks loading
        try:
            monthly_peaks = data_loader.load_monthly_peaks()
            validation_results['monthly_peaks'] = {
                'status': 'success',
                'years_with_peaks': list(monthly_peaks.keys()),
                'peak_count': sum(len(peaks) for peaks in monthly_peaks.values())
            }
        except Exception as e:
            validation_results['monthly_peaks'] = {
                'status': 'error',
                'message': str(e)
            }
        
        return jsonify({
            'status': 'success',
            'file_path': input_file_path,
            'validation_results': validation_results
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error validating input file: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Validation error: {str(e)}'
        })
    



@loadprofile_bp.route('/api/future_patterns/<int:base_year>/<int:start_year>/<int:end_year>', methods=['GET'])
def get_future_patterns_detailed_api(base_year: int, start_year: int, end_year: int):
    """Get detailed future patterns with enhanced analysis"""
    current_app.logger.info(f"Getting detailed future patterns for base_year={base_year}, range={start_year}-{end_year}")
    
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    if start_year >= end_year:
        return jsonify({
            'status': 'error', 
            'message': 'End year must be greater than start year'
        }), 400
    
    if end_year - start_year > 25:
        return jsonify({
            'status': 'error', 
            'message': 'Year range cannot exceed 25 years for detailed patterns'
        }), 400
    
    try:
        lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        excel_file_path = lp_manager.get_input_file_path()
        
        if not os.path.exists(excel_file_path):
            return jsonify({
                'status': 'error', 
                'message': 'Load curve input Excel file not found.'
            }), 404
        
        # Get scenario name from query params
        forecast_scenario = request.args.get('forecast_scenario')
        scenario_name = forecast_scenario if forecast_scenario and forecast_scenario not in ["null", "undefined"] else None
        
        # Load annual demand using enhanced system
        annual_targets = get_future_annual_demand(
            current_app.config['CURRENT_PROJECT_PATH'], 
            start_year, end_year, scenario_name
        )
        
        if not annual_targets:
            return jsonify({
                'status': 'error',
                'message': 'No annual demand data found for the specified range'
            }), 404
        
        # Extract base year patterns
        base_patterns = extract_monthly_patterns_from_excel(excel_file_path, base_year)
        monthly_shares = {i+1: share/100 for i, share in enumerate(base_patterns['patternData']['Share of Annual (%)'])}
        
        # Generate enhanced projections with more detail
        projected_data = []
        months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
        month_numbers = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
        
        # Calculate seasonal indices for more accurate projections
        base_load_factors = [lf/100 for lf in base_patterns['patternData']['Load Factor (%)']]
        
        for year in range(start_year, end_year + 1):
            if year not in annual_targets:
                current_app.logger.warning(f"No annual target for FY {year}")
                continue
            
            annual_total_gwh = annual_targets[year]
            
            monthly_data = []
            monthly_totals = []
            monthly_peaks = []
            
            for i, (month_name, month_num) in enumerate(zip(months, month_numbers)):
                share = monthly_shares.get(month_num, 1/12)
                monthly_total_gwh = annual_total_gwh * share
                monthly_totals.append(monthly_total_gwh)
                
                # Calculate more accurate monthly metrics
                if month_num in [12, 1, 2]:  # Winter months
                    days_in_month = 31 if month_num in [12, 1] else 28
                elif month_num in [4, 6, 9, 11]:  # 30-day months
                    days_in_month = 30
                else:
                    days_in_month = 31
                
                monthly_avg_mw = monthly_total_gwh * 1000 / (days_in_month * 24)
                
                # Use base year load factors with slight adjustments
                base_lf = base_load_factors[i]
                
                # Apply load factor improvement if specified
                load_factor_improvement = request.args.get('load_factor_improvement', type=float, default=0.0)
                if load_factor_improvement > 0:
                    years_from_base = year - base_year
                    improved_lf = base_lf * ((1 + load_factor_improvement/100) ** years_from_base)
                    adjusted_lf = min(improved_lf, 0.95)  # Cap at 95%
                else:
                    adjusted_lf = base_lf
                
                monthly_max_mw = monthly_avg_mw / adjusted_lf if adjusted_lf > 0 else monthly_avg_mw / 0.65
                monthly_peaks.append(monthly_max_mw)
                
                # Calculate additional metrics
                monthly_min_mw = monthly_avg_mw * 0.6  # Estimate minimum as 60% of average
                peak_to_avg_ratio = monthly_max_mw / monthly_avg_mw if monthly_avg_mw > 0 else 1.0
                
                monthly_data.append({
                    'month': month_name,
                    'month_number': month_num,
                    'totalDemand_GWh': round(monthly_total_gwh, 3),
                    'avgDemand_MW': round(monthly_avg_mw, 2),
                    'maxDemand_MW': round(monthly_max_mw, 2),
                    'minDemand_MW': round(monthly_min_mw, 2),
                    'loadFactor_Percent': round(adjusted_lf * 100, 2),
                    'peakToAvgRatio': round(peak_to_avg_ratio, 2),
                    'daysInMonth': days_in_month,
                    'shareOfAnnual_Percent': round(share * 100, 2)
                })
            
            # Calculate yearly metrics
            total_avg = sum(m['avgDemand_MW'] for m in monthly_data) / 12
            max_peak = max(m['maxDemand_MW'] for m in monthly_data)
            yearly_lf = (total_avg / max_peak * 100) if max_peak > 0 else 0
            
            # Seasonal analysis
            summer_months = [m for m in monthly_data if m['month_number'] in [4, 5, 6]]  # Apr-Jun
            monsoon_months = [m for m in monthly_data if m['month_number'] in [7, 8, 9, 10]]  # Jul-Oct
            winter_months = [m for m in monthly_data if m['month_number'] in [11, 12, 1, 2, 3]]  # Nov-Mar
            
            seasonal_analysis = {
                'summer_avg_demand': sum(m['avgDemand_MW'] for m in summer_months) / len(summer_months),
                'summer_peak_demand': max(m['maxDemand_MW'] for m in summer_months),
                'monsoon_avg_demand': sum(m['avgDemand_MW'] for m in monsoon_months) / len(monsoon_months),
                'monsoon_peak_demand': max(m['maxDemand_MW'] for m in monsoon_months),
                'winter_avg_demand': sum(m['avgDemand_MW'] for m in winter_months) / len(winter_months),
                'winter_peak_demand': max(m['maxDemand_MW'] for m in winter_months),
            }
            
            # Growth analysis (if not first year)
            growth_metrics = {}
            if projected_data:  # If there's previous year data
                prev_year_data = projected_data[-1]
                growth_metrics = {
                    'annual_growth_rate': ((annual_total_gwh - prev_year_data['annualTotal_GWh']) / prev_year_data['annualTotal_GWh'] * 100) if prev_year_data['annualTotal_GWh'] > 0 else 0,
                    'peak_growth_rate': ((max_peak - prev_year_data['peakDemand_MW']) / prev_year_data['peakDemand_MW'] * 100) if prev_year_data['peakDemand_MW'] > 0 else 0,
                    'load_factor_change': yearly_lf - prev_year_data['yearlyLoadFactor_Percent']
                }
            
            projected_data.append({
                'year': year,
                'annualTotal_GWh': round(annual_total_gwh, 3),
                'peakDemand_MW': round(max_peak, 2),
                'avgDemand_MW': round(total_avg, 2),
                'monthlyData': monthly_data,
                'yearlyLoadFactor_Percent': round(yearly_lf, 2),
                'seasonalAnalysis': seasonal_analysis,
                'growthMetrics': growth_metrics,
                'dataQuality': {
                    'confidence_level': 'high' if base_year >= 2020 else 'medium',
                    'projection_method': 'enhanced_base_year_scaling',
                    'load_factor_adjustment': load_factor_improvement > 0
                }
            })
        
        # Calculate overall statistics
        overall_stats = {
            'total_years': len(projected_data),
            'total_growth_rate': ((projected_data[-1]['annualTotal_GWh'] - projected_data[0]['annualTotal_GWh']) / projected_data[0]['annualTotal_GWh'] * 100) if len(projected_data) >= 2 else 0,
            'average_annual_growth': sum(y.get('growthMetrics', {}).get('annual_growth_rate', 0) for y in projected_data[1:]) / max(len(projected_data) - 1, 1),
            'peak_month_frequency': {},
            'min_year_demand': min(y['annualTotal_GWh'] for y in projected_data),
            'max_year_demand': max(y['annualTotal_GWh'] for y in projected_data),
            'average_load_factor': sum(y['yearlyLoadFactor_Percent'] for y in projected_data) / len(projected_data),
            'load_factor_trend': 'increasing' if projected_data[-1]['yearlyLoadFactor_Percent'] > projected_data[0]['yearlyLoadFactor_Percent'] else 'decreasing'
        }
        
        # Count peak month occurrences
        for year_data in projected_data:
            peak_month = max(year_data['monthlyData'], key=lambda m: m['maxDemand_MW'])['month']
            overall_stats['peak_month_frequency'][peak_month] = overall_stats['peak_month_frequency'].get(peak_month, 0) + 1
        
        # Enhanced response
        return jsonify({
            'status': 'success',
            'data': handle_nan_values(projected_data),
            'baseYear': base_year,
            'projectionPeriod': {'start': start_year, 'end': end_year},
            'scenario': scenario_name,
            'baseYearMonths': months,
            'baseYearPatterns': base_patterns,
            'overallStatistics': overall_stats,
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'data_source': 'enhanced_load_profile_system',
                'version': '2.0.0',
                'base_year_source': 'excel_historical_data',
                'projection_method': 'pattern_scaling_with_constraints'
            },
            'enhanced': True
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error in get_future_patterns_detailed_api: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@loadprofile_bp.route('/api/seasonal_analysis/<int:base_year>/<int:start_year>/<int:end_year>', methods=['GET'])
def get_seasonal_analysis_api(base_year: int, start_year: int, end_year: int):
    """Get detailed seasonal analysis for future patterns"""
    current_app.logger.info(f"Getting seasonal analysis for base_year={base_year}, range={start_year}-{end_year}")
    
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    try:
        # Get the detailed future patterns first
        lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        excel_file_path = lp_manager.get_input_file_path()
        
        if not os.path.exists(excel_file_path):
            return jsonify({'status': 'error', 'message': 'Input file not found'}), 404
        
        # Get scenario and load factor improvement from query params
        forecast_scenario = request.args.get('forecast_scenario')
        load_factor_improvement = request.args.get('load_factor_improvement', type=float, default=0.0)
        
        # Load annual targets
        annual_targets = get_future_annual_demand(
            current_app.config['CURRENT_PROJECT_PATH'], 
            start_year, end_year, forecast_scenario
        )
        
        if not annual_targets:
            return jsonify({'status': 'error', 'message': 'No annual demand data found'}), 404
        
        # Extract patterns and perform seasonal analysis
        base_patterns = extract_monthly_patterns_from_excel(excel_file_path, base_year)
        
        # Define seasons (adjust based on your region)
        season_definitions = {
            'Summer': {'months': [4, 5, 6], 'description': 'April - June'},
            'Monsoon': {'months': [7, 8, 9, 10], 'description': 'July - October'},
            'Winter': {'months': [11, 12, 1, 2, 3], 'description': 'November - March'}
        }
        
        # Calculate seasonal patterns for each year
        seasonal_analysis = {}
        months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
        month_to_num = {month: [4,5,6,7,8,9,10,11,12,1,2,3][i] for i, month in enumerate(months)}
        
        base_monthly_shares = {i+1: share/100 for i, share in enumerate(base_patterns['patternData']['Share of Annual (%)'])}
        base_load_factors = [lf/100 for lf in base_patterns['patternData']['Load Factor (%)']]
        
        for season_name, season_info in season_definitions.items():
            seasonal_analysis[season_name] = {
                'description': season_info['description'],
                'months': [months[i] for i in range(12) if [4,5,6,7,8,9,10,11,12,1,2,3][i] in season_info['months']],
                'yearly_data': []
            }
            
            for year in range(start_year, end_year + 1):
                if year not in annual_targets:
                    continue
                
                annual_total_gwh = annual_targets[year]
                season_total = 0
                season_peak = 0
                season_avg = 0
                month_count = 0
                
                for month_num in season_info['months']:
                    share = base_monthly_shares.get(month_num, 1/12)
                    monthly_total_gwh = annual_total_gwh * share
                    season_total += monthly_total_gwh
                    
                    # Calculate monthly metrics
                    days_map = {1:31, 2:28, 3:31, 4:30, 5:31, 6:30, 7:31, 8:31, 9:30, 10:31, 11:30, 12:31}
                    days_in_month = days_map.get(month_num, 30)
                    monthly_avg_mw = monthly_total_gwh * 1000 / (days_in_month * 24)
                    
                    # Get base load factor for this month
                    month_index = [4,5,6,7,8,9,10,11,12,1,2,3].index(month_num)
                    base_lf = base_load_factors[month_index]
                    
                    # Apply load factor improvement
                    if load_factor_improvement > 0:
                        years_from_base = year - base_year
                        improved_lf = base_lf * ((1 + load_factor_improvement/100) ** years_from_base)
                        adjusted_lf = min(improved_lf, 0.95)
                    else:
                        adjusted_lf = base_lf
                    
                    monthly_max_mw = monthly_avg_mw / adjusted_lf if adjusted_lf > 0 else monthly_avg_mw / 0.65
                    season_peak = max(season_peak, monthly_max_mw)
                    season_avg += monthly_avg_mw
                    month_count += 1
                
                season_avg = season_avg / month_count if month_count > 0 else 0
                season_lf = (season_avg / season_peak * 100) if season_peak > 0 else 0
                
                seasonal_analysis[season_name]['yearly_data'].append({
                    'year': year,
                    'total_demand_gwh': round(season_total, 2),
                    'peak_demand_mw': round(season_peak, 1),
                    'avg_demand_mw': round(season_avg, 1),
                    'load_factor_percent': round(season_lf, 1),
                    'share_of_annual_percent': round((season_total / annual_total_gwh) * 100, 1)
                })
        
        # Calculate seasonal trends
        seasonal_trends = {}
        for season_name, season_data in seasonal_analysis.items():
            yearly_data = season_data['yearly_data']
            if len(yearly_data) >= 2:
                first_year = yearly_data[0]
                last_year = yearly_data[-1]
                
                trends = {
                    'demand_growth_rate': ((last_year['total_demand_gwh'] - first_year['total_demand_gwh']) / first_year['total_demand_gwh'] * 100) if first_year['total_demand_gwh'] > 0 else 0,
                    'peak_growth_rate': ((last_year['peak_demand_mw'] - first_year['peak_demand_mw']) / first_year['peak_demand_mw'] * 100) if first_year['peak_demand_mw'] > 0 else 0,
                    'load_factor_change': last_year['load_factor_percent'] - first_year['load_factor_percent'],
                    'avg_annual_growth': 0
                }
                
                # Calculate average annual growth
                if len(yearly_data) > 1:
                    growth_rates = []
                    for i in range(1, len(yearly_data)):
                        if yearly_data[i-1]['total_demand_gwh'] > 0:
                            rate = (yearly_data[i]['total_demand_gwh'] - yearly_data[i-1]['total_demand_gwh']) / yearly_data[i-1]['total_demand_gwh'] * 100
                            growth_rates.append(rate)
                    trends['avg_annual_growth'] = sum(growth_rates) / len(growth_rates) if growth_rates else 0
                
                seasonal_trends[season_name] = trends
        
        return jsonify({
            'status': 'success',
            'baseYear': base_year,
            'projectionPeriod': {'start': start_year, 'end': end_year},
            'seasonDefinitions': season_definitions,
            'seasonalAnalysis': seasonal_analysis,
            'seasonalTrends': seasonal_trends,
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'load_factor_improvement_applied': load_factor_improvement,
                'scenario': forecast_scenario
            }
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error in seasonal analysis: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@loadprofile_bp.route('/api/pattern_comparison/<int:base_year1>/<int:base_year2>', methods=['GET'])
def compare_base_year_patterns_api(base_year1: int, base_year2: int):
    """Compare patterns between two base years"""
    current_app.logger.info(f"Comparing patterns between FY {base_year1} and FY {base_year2}")
    
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'}), 400
    
    try:
        lp_manager = EnhancedLoadProfileManager(current_app.config['CURRENT_PROJECT_PATH'])
        excel_file_path = lp_manager.get_input_file_path()
        
        if not os.path.exists(excel_file_path):
            return jsonify({'status': 'error', 'message': 'Input file not found'}), 404
        
        # Extract patterns for both years
        patterns1 = extract_monthly_patterns_from_excel(excel_file_path, base_year1)
        patterns2 = extract_monthly_patterns_from_excel(excel_file_path, base_year2)
        
        # Calculate differences
        months = patterns1['months']
        comparison_data = {
            'months': months,
            'base_year_1': {
                'year': base_year1,
                'yearly_load_factor': patterns1['yearlyLoadFactor'],
                'pattern_data': patterns1['patternData']
            },
            'base_year_2': {
                'year': base_year2,
                'yearly_load_factor': patterns2['yearlyLoadFactor'],
                'pattern_data': patterns2['patternData']
            },
            'differences': {}
        }
        
        # Calculate metric differences
        for metric in patterns1['patternData'].keys():
            values1 = patterns1['patternData'][metric]
            values2 = patterns2['patternData'][metric]
            
            differences = []
            for i, (v1, v2) in enumerate(zip(values1, values2)):
                try:
                    diff = float(v2) - float(v1)
                    diff_percent = (diff / float(v1) * 100) if float(v1) != 0 else 0
                    differences.append({
                        'absolute': round(diff, 3),
                        'percent': round(diff_percent, 2)
                    })
                except (ValueError, TypeError):
                    differences.append({'absolute': 0, 'percent': 0})
            
            comparison_data['differences'][metric] = differences
        
        # Calculate overall comparison metrics
        load_factor_diff = patterns2['yearlyLoadFactor'] - patterns1['yearlyLoadFactor']
        
        # Find months with biggest changes
        share_differences = comparison_data['differences'].get('Share of Annual (%)', [])
        if share_differences:
            max_increase_idx = max(range(len(share_differences)), key=lambda i: share_differences[i]['absolute'])
            max_decrease_idx = min(range(len(share_differences)), key=lambda i: share_differences[i]['absolute'])
            
            comparison_summary = {
                'load_factor_change': {
                    'absolute': round(load_factor_diff, 2),
                    'direction': 'increase' if load_factor_diff > 0 else 'decrease'
                },
                'biggest_monthly_increase': {
                    'month': months[max_increase_idx],
                    'change_percent': share_differences[max_increase_idx]['percent']
                },
                'biggest_monthly_decrease': {
                    'month': months[max_decrease_idx],
                    'change_percent': share_differences[max_decrease_idx]['percent']
                },
                'pattern_similarity': calculate_pattern_similarity(patterns1['patternData'], patterns2['patternData'])
            }
        else:
            comparison_summary = {'error': 'Could not calculate comparison metrics'}
        
        return jsonify({
            'status': 'success',
            'comparison_data': comparison_data,
            'comparison_summary': comparison_summary,
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'comparison_type': 'base_year_patterns'
            }
        })
        
    except Exception as e:
        current_app.logger.exception(f"Error in pattern comparison: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def calculate_pattern_similarity(patterns1, patterns2):
    """Calculate similarity between two pattern sets"""
    try:
        # Focus on share of annual patterns for similarity calculation
        shares1 = patterns1.get('Share of Annual (%)', [])
        shares2 = patterns2.get('Share of Annual (%)', [])
        
        if len(shares1) != len(shares2) or len(shares1) == 0:
            return 0
        
        # Calculate correlation coefficient
        import numpy as np
        correlation = np.corrcoef(shares1, shares2)[0, 1]
        
        # Convert to percentage similarity
        similarity_percent = max(0, correlation * 100)
        
        return round(similarity_percent, 1)
        
    except Exception:
        return 0