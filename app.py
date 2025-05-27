from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, current_app # Keep necessary Flask imports
import os
import logging
from datetime import datetime

# Import Blueprints
from blueprints.core_bp import core_bp
from blueprints.project_bp import project_bp
from blueprints.data_bp import data_bp
from blueprints.demand_bp import demand_bp
from blueprints.loadprofile_bp import loadprofile_bp
from blueprints.pypsa_bp import pypsa_bp
from blueprints.admin_bp import admin_bp

# Import FeatureManager
from utils.features_manager import FeatureManager

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'energy_demand_forecasting_secret_key'  # Change in production

# Configuration
app.config['UPLOAD_FOLDER'] = 'static/user_uploads'
app.config['TEMPLATE_FOLDER'] = 'static/templates' # This is where Flask looks for templates by default
app.config['ALLOWED_EXTENSIONS'] = {'xlsx'}
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
app.config['CURRENT_PROJECT'] = None
app.config['CURRENT_PROJECT_PATH'] = None

# Ensure upload folders exist (minimal version)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'recent_projects'), exist_ok=True)

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
logger = logging.getLogger(__name__) # Main app logger
logger.info("Application starting - Main app.py")


# Configuration validation function
def validate_app_config():
    logger.info("Validating application configuration in app.py")
    required_config = ['UPLOAD_FOLDER', 'TEMPLATE_FOLDER', 'ALLOWED_EXTENSIONS']
    missing = [key for key in required_config if not app.config.get(key)] # Check if key exists and has a value
    if missing:
        logger.critical(f"Missing required configuration keys in app.py: {missing}")
    
    for key in ['UPLOAD_FOLDER']:
        if app.config.get(key):
            folder = app.config[key]
            if not os.path.exists(folder):
                logger.warning(f"Folder for {key} does not exist: {folder} (app.py)")
                try:
                    os.makedirs(folder, exist_ok=True)
                    logger.info(f"Created missing folder: {folder} (app.py)")
                except Exception as e:
                    logger.error(f"Failed to create folder {folder} (app.py): {str(e)}")

validate_app_config() # Call validation at startup

# Register Blueprints
app.register_blueprint(core_bp) 
app.register_blueprint(project_bp, url_prefix='/project')
app.register_blueprint(data_bp, url_prefix='/data')
app.register_blueprint(demand_bp, url_prefix='/demand')
app.register_blueprint(loadprofile_bp, url_prefix='/load_profile')
app.register_blueprint(pypsa_bp, url_prefix='/pypsa')
app.register_blueprint(admin_bp, url_prefix='/admin')

logger.info("All blueprints registered.")

# Initialize feature manager (after blueprints are registered)
if not hasattr(app, 'feature_manager'): 
    app.feature_manager = FeatureManager(app) # app instance is passed to FeatureManager
    logger.info("FeatureManager initialized directly in app.py.")

@app.context_processor
def feature_processor():
    def is_used(feature_id):
        project_path = app.config.get('CURRENT_PROJECT_PATH')
        return app.feature_manager.is_feature_enabled(feature_id, project_path) if hasattr(app, 'feature_manager') and app.feature_manager else False
    
    def get_enabled_features():
        project_path = app.config.get('CURRENT_PROJECT_PATH')
        return app.feature_manager.get_enabled_features(project_path) if hasattr(app, 'feature_manager') and app.feature_manager else []
    
    return dict(is_used=is_used, get_enabled_features=get_enabled_features)

logger.info("Feature processor registered.")

# ==========================================
# ERROR HANDLERS (Keep these in app.py)
# ==========================================
@app.errorhandler(404)
def page_not_found(e):
    logger.warning(f"404 error: Page not found at {request.path} (handled in app.py). Error: {e}")
    return render_template('404.html', error=e), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"500 error: Internal server error. Details: {str(e)} (handled in app.py)", exc_info=True)
    return render_template('500.html', error=e), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.exception(f"Unhandled exception: {str(e)} (handled in app.py)")
    return render_template('500.html', error=e), 500

# ==========================================
# MAIN ENTRY POINT (Keep this in app.py)
# ==========================================
if __name__ == '__main__':
    try:
        logger.info("Attempting to start Flask application via __main__ in app.py.")
        app.run(debug=True, host='0.0.0.0', port=5000) 
    except Exception as e:
        logger.critical(f"Failed to start application from __main__ in app.py: {e}", exc_info=True)
        print(f"CRITICAL ERROR on startup from app.py __main__: {e}")