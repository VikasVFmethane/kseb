# app.py - Updated for Enhanced Load Profile System
"""
Updated Flask application configuration to integrate the enhanced load profile system
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, current_app
import os
import logging
from datetime import datetime

# Import Enhanced Blueprints
from blueprints.core_bp import core_bp
from blueprints.project_bp import project_bp
from blueprints.data_bp import data_bp
from blueprints.demand_bp import demand_bp
from blueprints.loadprofile_bp import loadprofile_bp  # Enhanced version
from blueprints.pypsa_bp import pypsa_bp
from blueprints.admin_bp import admin_bp

# Import Enhanced Load Profile System
from utils.load_profile_generator import LoadProfileConfig, create_load_curve
from utils.features_manager import FeatureManager

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'energy_demand_forecasting_secret_key_enhanced'  # Change in production

# Enhanced Configuration
app.config.update({
    'UPLOAD_FOLDER': 'static/user_uploads',
    'TEMPLATE_FOLDER': 'static/templates',
    'ALLOWED_EXTENSIONS': {'xlsx', 'csv'},
    'MAX_CONTENT_LENGTH': 200 * 1024 * 1024,  # 200MB for large datasets
    'CURRENT_PROJECT': None,
    'CURRENT_PROJECT_PATH': None,
    
    # Enhanced Load Profile Configuration
    'LOAD_PROFILE_CONFIG': {
        'DEFAULT_METHOD': 'base_year',
        'DEFAULT_OUTPUT_UNIT': 'MW',
        'DEFAULT_OUTPUT_FREQUENCY': 'hourly',
        'MAX_YEAR_RANGE': 50,
        'DEFAULT_YEARLY_TOLERANCE_PCT': 0.01,
        'DEFAULT_MONTHLY_TOLERANCE_PCT': 0.1,
        'DEFAULT_LOAD_FACTOR_TOLERANCE_PCT': 1.0,
        'ENABLE_ENHANCED_VALIDATION': True,
        'ENABLE_HIERARCHICAL_CONSTRAINTS': True,
        'AUTO_BACKUP_PROFILES': True
    }
})

# Ensure upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'recent_projects'), exist_ok=True)

# Enhanced logging configuration
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'enhanced_app_{datetime.now().strftime("%Y%m%d")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Create enhanced logger
logger = logging.getLogger(__name__)
logger.info("Enhanced Load Profile Application starting")

# Enhanced configuration validation
def validate_enhanced_app_config():
    """Validate enhanced application configuration"""
    logger.info("Validating enhanced application configuration")
    
    required_config = ['UPLOAD_FOLDER', 'TEMPLATE_FOLDER', 'ALLOWED_EXTENSIONS', 'LOAD_PROFILE_CONFIG']
    missing = [key for key in required_config if not app.config.get(key)]
    
    if missing:
        logger.critical(f"Missing required configuration keys: {missing}")
        raise ValueError(f"Missing required configuration: {missing}")
    
    # Validate load profile specific config
    lp_config = app.config['LOAD_PROFILE_CONFIG']
    required_lp_keys = ['DEFAULT_METHOD', 'DEFAULT_OUTPUT_UNIT', 'ENABLE_ENHANCED_VALIDATION']
    missing_lp = [key for key in required_lp_keys if key not in lp_config]
    
    if missing_lp:
        logger.critical(f"Missing load profile configuration keys: {missing_lp}")
        raise ValueError(f"Missing load profile configuration: {missing_lp}")
    
    # Validate directories
    for key in ['UPLOAD_FOLDER']:
        if app.config.get(key):
            folder = app.config[key]
            if not os.path.exists(folder):
                logger.warning(f"Folder for {key} does not exist: {folder}")
                try:
                    os.makedirs(folder, exist_ok=True)
                    logger.info(f"Created missing folder: {folder}")
                except Exception as e:
                    logger.error(f"Failed to create folder {folder}: {str(e)}")
                    raise
    
    logger.info("Enhanced application configuration validated successfully")

# Validate configuration
validate_enhanced_app_config()

# Register Enhanced Blueprints
app.register_blueprint(core_bp)
app.register_blueprint(project_bp, url_prefix='/project')
app.register_blueprint(data_bp, url_prefix='/data')
app.register_blueprint(demand_bp, url_prefix='/demand')
app.register_blueprint(loadprofile_bp, url_prefix='/load_profile')  # Enhanced version
app.register_blueprint(pypsa_bp, url_prefix='/pypsa')
app.register_blueprint(admin_bp, url_prefix='/admin')

logger.info("All enhanced blueprints registered successfully")

# Initialize enhanced feature manager
if not hasattr(app, 'feature_manager'):
    app.feature_manager = FeatureManager(app)
    logger.info("Enhanced FeatureManager initialized")

# Enhanced context processor
@app.context_processor
def enhanced_feature_processor():
    """Enhanced context processor with load profile features"""
    
    def is_used(feature_id):
        project_path = app.config.get('CURRENT_PROJECT_PATH')
        return app.feature_manager.is_feature_enabled(feature_id, project_path) if hasattr(app, 'feature_manager') and app.feature_manager else False
    
    def get_enabled_features():
        project_path = app.config.get('CURRENT_PROJECT_PATH')
        return app.feature_manager.get_enabled_features(project_path) if hasattr(app, 'feature_manager') and app.feature_manager else []
    
    def get_load_profile_config():
        """Get load profile configuration for templates"""
        return app.config.get('LOAD_PROFILE_CONFIG', {})
    
    def is_enhanced_load_profile_enabled():
        """Check if enhanced load profile features are enabled"""
        return app.config.get('LOAD_PROFILE_CONFIG', {}).get('ENABLE_ENHANCED_VALIDATION', False)
    
    return dict(
        is_used=is_used, 
        get_enabled_features=get_enabled_features,
        get_load_profile_config=get_load_profile_config,
        is_enhanced_load_profile_enabled=is_enhanced_load_profile_enabled
    )

logger.info("Enhanced feature processor registered")

# Enhanced utility functions
def create_default_load_profile_config(**overrides):
    """Create default load profile configuration with optional overrides"""
    config_dict = app.config['LOAD_PROFILE_CONFIG'].copy()
    config_dict.update(overrides)
    
    return LoadProfileConfig(
        method=config_dict.get('DEFAULT_METHOD', 'base_year'),
        output_unit=config_dict.get('DEFAULT_OUTPUT_UNIT', 'MW'),
        output_frequency=config_dict.get('DEFAULT_OUTPUT_FREQUENCY', 'hourly'),
        yearly_tolerance_pct=config_dict.get('DEFAULT_YEARLY_TOLERANCE_PCT', 0.01),
        monthly_tolerance_pct=config_dict.get('DEFAULT_MONTHLY_TOLERANCE_PCT', 0.1),
        load_factor_tolerance_pct=config_dict.get('DEFAULT_LOAD_FACTOR_TOLERANCE_PCT', 1.0),
        apply_constraints=config_dict.get('ENABLE_HIERARCHICAL_CONSTRAINTS', True),
        use_holidays=config_dict.get('USE_HOLIDAYS', True),
        **overrides
    )

def validate_project_for_load_profiles(project_path):
    """Validate that a project is properly set up for enhanced load profiles"""
    if not project_path or not os.path.exists(project_path):
        return False, "Project path does not exist"
    
    inputs_folder = os.path.join(project_path, 'inputs')
    if not os.path.exists(inputs_folder):
        return False, "Project inputs folder not found"
    
    template_file = os.path.join(inputs_folder, 'load_curve_template.xlsx')
    if not os.path.exists(template_file):
        return False, "Load curve template file not found"
    
    return True, "Project is ready for enhanced load profile generation"

# Enhanced API endpoint for system status
@app.route('/api/system/status')
def system_status():
    """Get enhanced system status"""
    try:
        current_project = app.config.get('CURRENT_PROJECT')
        current_project_path = app.config.get('CURRENT_PROJECT_PATH')
        
        # Check project status
        project_valid = False
        project_message = "No project selected"
        if current_project_path:
            project_valid, project_message = validate_project_for_load_profiles(current_project_path)
        
        # Get load profile configuration
        lp_config = app.config.get('LOAD_PROFILE_CONFIG', {})
        
        status = {
            'status': 'operational',
            'timestamp': datetime.now().isoformat(),
            'current_project': current_project,
            'current_project_path': current_project_path,
            'project_valid_for_load_profiles': project_valid,
            'project_message': project_message,
            'enhanced_features': {
                'load_profile_validation': lp_config.get('ENABLE_ENHANCED_VALIDATION', False),
                'hierarchical_constraints': lp_config.get('ENABLE_HIERARCHICAL_CONSTRAINTS', False),
                'auto_backup': lp_config.get('AUTO_BACKUP_PROFILES', False)
            },
            'system_limits': {
                'max_file_size_mb': app.config.get('MAX_CONTENT_LENGTH', 0) / (1024 * 1024),
                'max_year_range': lp_config.get('MAX_YEAR_RANGE', 50),
                'allowed_extensions': list(app.config.get('ALLOWED_EXTENSIONS', []))
            }
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.exception("Error getting system status")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Enhanced API endpoint for load profile system info
@app.route('/api/load_profile/system_info')
def load_profile_system_info():
    """Get load profile system information"""
    try:
        lp_config = app.config.get('LOAD_PROFILE_CONFIG', {})
        
        info = {
            'system_type': 'enhanced_load_profile_generator',
            'version': '2.0.0',
            'features': {
                'pattern_extraction': 'advanced_historical_analysis',
                'constraint_application': 'hierarchical_validation',
                'energy_conservation': 'precise_total_matching',
                'load_factor_optimization': 'energy_preserving_peak_shaving',
                'validation': 'comprehensive_multi_level',
                'data_quality': 'automatic_detection_and_cleaning'
            },
            'configuration': {
                'default_method': lp_config.get('DEFAULT_METHOD'),
                'default_output_unit': lp_config.get('DEFAULT_OUTPUT_UNIT'),
                'default_tolerances': {
                    'yearly_pct': lp_config.get('DEFAULT_YEARLY_TOLERANCE_PCT'),
                    'monthly_pct': lp_config.get('DEFAULT_MONTHLY_TOLERANCE_PCT'),
                    'load_factor_pct': lp_config.get('DEFAULT_LOAD_FACTOR_TOLERANCE_PCT')
                },
                'enhanced_validation_enabled': lp_config.get('ENABLE_ENHANCED_VALIDATION'),
                'hierarchical_constraints_enabled': lp_config.get('ENABLE_HIERARCHICAL_CONSTRAINTS')
            },
            'supported_inputs': {
                'excel_formats': ['.xlsx'],
                'required_sheets': ['Past_Hourly_Demand', 'Total Demand', 'max_demand (optional)', 'load_factors (optional)'],
                'flexible_column_names': True,
                'automatic_validation': True
            },
            'output_options': {
                'units': ['kW', 'MW', 'GW'],
                'frequencies': ['hourly', 'half_hourly', '15min'],
                'formats': ['CSV', 'Excel', 'JSON'],
                'validation_included': True
            }
        }
        
        return jsonify(info)
        
    except Exception as e:
        logger.exception("Error getting load profile system info")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Register utility functions in app context
app.create_default_load_profile_config = create_default_load_profile_config
app.validate_project_for_load_profiles = validate_project_for_load_profiles

# ==========================================
# ENHANCED ERROR HANDLERS
# ==========================================

@app.errorhandler(404)
def enhanced_page_not_found(e):
    logger.warning(f"404 error: Page not found at {request.path}. Error: {e}")
    return render_template('404.html', error=e, enhanced_system=True), 404

@app.errorhandler(500)
def enhanced_internal_server_error(e):
    logger.error(f"500 error: Internal server error. Details: {str(e)}", exc_info=True)
    return render_template('500.html', error=e, enhanced_system=True), 500

@app.errorhandler(413)
def file_too_large(e):
    logger.warning(f"413 error: File too large. Max size: {app.config.get('MAX_CONTENT_LENGTH', 0) / (1024*1024):.1f}MB")
    flash(f'File too large. Maximum size is {app.config.get("MAX_CONTENT_LENGTH", 0) / (1024*1024):.1f}MB', 'danger')
    return redirect(url_for('loadprofile.load_profile_creation_route'))

@app.errorhandler(Exception)
def enhanced_handle_exception(e):
    logger.exception(f"Unhandled exception in enhanced system: {str(e)}")
    return render_template('500.html', error=e, enhanced_system=True), 500

# ==========================================
# ENHANCED INITIALIZATION
# ==========================================

def initialize_enhanced_system():
    """Initialize the enhanced load profile system"""
    logger.info("Initializing enhanced load profile system")
    
    try:
        # Validate configuration
        validate_enhanced_app_config()
        
        # Check if enhanced features are properly configured
        lp_config = app.config.get('LOAD_PROFILE_CONFIG', {})
        if lp_config.get('ENABLE_ENHANCED_VALIDATION'):
            logger.info("Enhanced validation features enabled")
        
        if lp_config.get('ENABLE_HIERARCHICAL_CONSTRAINTS'):
            logger.info("Hierarchical constraint application enabled")
        
        # Test import of enhanced system
        from utils.load_profile_generator import LoadProfileGenerator
        logger.info("Enhanced load profile generator imported successfully")
        
        logger.info("Enhanced load profile system initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize enhanced load profile system: {e}")
        return False

# Initialize enhanced system at startup
enhanced_system_initialized = initialize_enhanced_system()

if not enhanced_system_initialized:
    logger.critical("Enhanced load profile system failed to initialize")
    # You might want to disable load profile features or exit here
else:
    logger.info("✅ Enhanced Load Profile System is ready")

# ==========================================
# ENHANCED HEALTH CHECK
# ==========================================

@app.route('/health')
def health_check():
    """Enhanced health check endpoint"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'components': {
                'flask_app': 'operational',
                'enhanced_load_profile': 'operational' if enhanced_system_initialized else 'degraded',
                'feature_manager': 'operational' if hasattr(app, 'feature_manager') else 'missing',
                'database': 'not_applicable',  # Add if you have a database
                'file_system': 'operational' if os.path.exists(app.config['UPLOAD_FOLDER']) else 'error'
            },
            'configuration': {
                'enhanced_features_enabled': app.config.get('LOAD_PROFILE_CONFIG', {}).get('ENABLE_ENHANCED_VALIDATION', False),
                'max_file_size_mb': app.config.get('MAX_CONTENT_LENGTH', 0) / (1024 * 1024),
                'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER'])
            }
        }
        
        # Determine overall status
        if not enhanced_system_initialized:
            health_status['status'] = 'degraded'
        
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            health_status['status'] = 'unhealthy'
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        return jsonify(health_status), status_code
        
    except Exception as e:
        logger.exception("Error in health check")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ==========================================
# MAIN ENTRY POINT
# ==========================================

if __name__ == '__main__':
    try:
        logger.info("Starting Enhanced Load Profile Flask application")
        
        # Final system check
        if not enhanced_system_initialized:
            logger.warning("Starting with degraded enhanced load profile functionality")
        
        # Start the application
        app.run(
            debug=True, 
            host='0.0.0.0', 
            port=5000,
            use_reloader=False  # Disable reloader to prevent double initialization
        )
        
    except Exception as e:
        logger.critical(f"Failed to start Enhanced Load Profile application: {e}", exc_info=True)
        print(f"CRITICAL ERROR: Could not start enhanced application: {e}")
        exit(1)