from flask import Blueprint, render_template, request, jsonify, current_app, flash, redirect, url_for
from utils.features_manager import FeatureManager # Import the class

admin_bp = Blueprint('admin', 
                     __name__, 
                     template_folder='../templates', 
                     static_folder='../static',
                     url_prefix='/admin')

# Feature Manager Initialization and Context Processor
# This function will be called during app setup when registering the blueprint
def init_admin_feature_manager(app_instance):
    if not hasattr(app_instance, 'feature_manager'):
        app_instance.feature_manager = FeatureManager(app_instance)
        current_app.logger.info("FeatureManager initialized via admin_bp.")

    # The context processor should ideally be registered on the app itself,
    # or this blueprint needs to be aware of how to provide these globally.
    # For simplicity, we'll define it here and it can be registered in app.py
    # when this blueprint is registered.
    # Alternatively, if FeatureManager is specific to admin routes, this is fine.
    # Given its usage in app.py's context_processor, it seems global.
    # Let's assume for now we might need to register this part in app.py,
    # but the manager instance can be created here.

@admin_bp.record_once
def on_load(state):
    # This function is called when the blueprint is registered.
    # Initialize FeatureManager here if it's tied to this blueprint's lifecycle
    # However, FeatureManager in original app.py is app-global.
    # We will initialize it in app.py after blueprint registration.
    # For now, this blueprint will assume current_app.feature_manager exists.
    pass

# Routes
@admin_bp.route('/features')
def feature_management_route(): # Renamed
    current_app.logger.info("Accessing feature_management route via admin_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None:
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('core.home')) # To core blueprint
    
    # Assuming feature_manager is initialized and available on current_app
    if not hasattr(current_app, 'feature_manager'):
        flash('Feature Manager not available. Please check application setup.', 'danger')
        return redirect(url_for('core.home'))

    return render_template('feature_management.html',
                           current_project=current_app.config.get('CURRENT_PROJECT'))

@admin_bp.route('/api/features', methods=['GET'])
def get_features_api(): # Renamed
    current_app.logger.info("Processing API request for features list via admin_bp")
    if not hasattr(current_app, 'feature_manager'):
        return jsonify({'status': 'error', 'message': 'Feature Manager not available.'}), 500
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    try:
        project_path = current_app.config['CURRENT_PROJECT_PATH']
        features = current_app.feature_manager.get_merged_features(project_path)
        
        return jsonify({
            'status': 'success',
            'features': features.get('features', {}),
            'feature_groups': features.get('feature_groups', {})
        })
    except Exception as e:
        current_app.logger.exception(f"Error getting features via admin_bp: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@admin_bp.route('/api/features/<feature_id>', methods=['PUT'])
def update_feature_api(feature_id): # Renamed
    current_app.logger.info(f"Processing API request to update feature {feature_id} via admin_bp")
    if not hasattr(current_app, 'feature_manager'):
        return jsonify({'status': 'error', 'message': 'Feature Manager not available.'}), 500
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'})
    
    data = request.get_json()
    if not data or 'enabled' not in data:
        return jsonify({'status': 'error', 'message': 'Missing enabled status'})
    
    try:
        project_path = current_app.config['CURRENT_PROJECT_PATH']
        success = current_app.feature_manager.set_feature_enabled(
            feature_id, data['enabled'], project_path
        )
        
        if success:
            return jsonify({'status': 'success', 'feature_id': feature_id, 'enabled': data['enabled']})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to update feature'})
    except Exception as e:
        current_app.logger.exception(f"Error updating feature {feature_id} via admin_bp: {e}")
        return jsonify({'status': 'error', 'message': str(e)})
