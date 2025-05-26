from flask import Blueprint, request, redirect, url_for, flash, jsonify, session, current_app
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import json

# Assuming these will be used by routes moved here.
# If they are not used by the routes defined in this BP, they can be removed.
from utils.helpers import create_project_structure, validate_project_structure, copy_missing_templates

project_bp = Blueprint('project', 
                       __name__, 
                       template_folder='../templates', 
                       static_folder='../static',
                       url_prefix='/project') # Adding a prefix to avoid clashes if any route is named e.g. 'load'

# Helper function moved from app.py
def save_recent_project(user_id, project_name, project_path):
    current_app.logger.info(f"Saving recent project: '{project_name}' at '{project_path}' for user '{user_id}'")
    try:
        recent_projects_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'recent_projects')
        os.makedirs(recent_projects_dir, exist_ok=True) # Ensure dir exists
        
        filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                recent_projects = json.load(f)
                current_app.logger.debug(f"Loaded {len(recent_projects)} existing recent projects")
        else:
            recent_projects = []
            current_app.logger.debug("No existing recent projects file, creating new")
        
        existing_index = None
        for i, project in enumerate(recent_projects):
            if project.get('path') == project_path:
                existing_index = i
                break
        
        if existing_index is not None:
            current_app.logger.debug(f"Project already exists at index {existing_index}, removing")
            recent_projects.pop(existing_index)
        
        recent_projects.insert(0, {
            'name': project_name,
            'path': project_path,
            'last_opened': datetime.now().isoformat(),
            'timestamp': int(datetime.now().timestamp())
        })
        
        recent_projects = recent_projects[:10]
        
        with open(filename, 'w') as f:
            json.dump(recent_projects, f, indent=4)
        
        current_app.logger.info(f"Successfully saved recent project for user {user_id}")
        return True
    except Exception as e:
        current_app.logger.exception(f"Error saving recent project: {e}")
        return False

@project_bp.route('/create', methods=['POST']) # Adjusted route
def create_project_route(): # Renamed to avoid conflict with import
    current_app.logger.info("Processing create_project request via project_bp")
    
    if request.method != 'POST':
        current_app.logger.warning("Invalid request method for create_project")
        return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
    project_name = request.form.get('projectName')
    project_location = request.form.get('projectLocation', '')
    
    current_app.logger.debug(f"Requested project creation: name='{project_name}', location='{project_location}'")
    
    if not project_name:
        current_app.logger.warning("No project name provided")
        return jsonify({'status': 'error', 'message': 'Please provide a project name'})
    
    if not project_location:
        current_app.logger.warning("No project location provided")
        return jsonify({'status': 'error', 'message': 'Please select a project location'})
    
    try:
        safe_project_name = secure_filename(project_name)
        if os.path.isabs(project_location):
            project_path = os.path.join(project_location, safe_project_name)
        else:
            # Ensure 'projects' directory exists within UPLOAD_FOLDER if not absolute
            base_upload_folder = current_app.config['UPLOAD_FOLDER']
            projects_base = os.path.join(base_upload_folder, 'projects')
            os.makedirs(projects_base, exist_ok=True) # Ensure 'projects' dir exists
            
            # Further ensure the specific location directory exists if it's a sub-path
            target_location_path = os.path.join(projects_base, project_location)
            os.makedirs(target_location_path, exist_ok=True)

            project_path = os.path.join(target_location_path, safe_project_name)

        current_app.logger.debug(f"Creating project at: {project_path}")
        
        success = create_project_structure(project_path, current_app.config['TEMPLATE_FOLDER'])
        if success:
            current_app.logger.info(f"Project created: {project_path} at {datetime.now()}")
            
            user_id = session.get('user_id', 'default_user')
            save_recent_project(user_id, project_name, project_path) # Uses the BP's version
            
            current_app.config['CURRENT_PROJECT'] = project_name
            current_app.config['CURRENT_PROJECT_PATH'] = project_path

            return jsonify({
                'status': 'success',
                'message': f'Project "{project_name}" created successfully!',
                'project_path': project_path
            })
        else:
            current_app.logger.error(f"Failed to create project structure at {project_path}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to create project structure. Check server logs for details.'
            })
    except Exception as e:
        current_app.logger.exception(f"Error creating project: {e}")
        return jsonify({'status': 'error', 'message': f'Error creating project: {str(e)}'})

@project_bp.route('/validate', methods=['POST']) # Adjusted route
def validate_project_route(): # Renamed
    current_app.logger.info("Processing validate_project request via project_bp")
    
    if request.method != 'POST':
        current_app.logger.warning("Invalid request method for validate_project")
        return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
    project_path = request.form.get('projectPath')
    
    if not project_path:
        current_app.logger.warning("No project path provided")
        return jsonify({'status': 'error', 'message': 'No project path provided'})
    
    try:
        current_app.logger.debug(f"Validating project at: {project_path}")
        
        if not os.path.exists(project_path):
            current_app.logger.warning(f"Project path does not exist: {project_path}")
            return jsonify({
                'status': 'error', 
                'message': f'The path "{project_path}" does not exist'
            })
        
        validation_result = validate_project_structure(project_path)
        current_app.logger.debug(f"Validation result: {validation_result}")
        return jsonify(validation_result)
    except Exception as e:
        current_app.logger.exception(f"Error validating project: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error validating project: {str(e)}'
        })

@project_bp.route('/load', methods=['POST']) # Adjusted route
def load_project_route(): # Renamed
    current_app.logger.info("Processing load_project request via project_bp")
    
    if request.method != 'POST':
        current_app.logger.warning("Invalid request method for load_project")
        return jsonify({'status': 'error', 'message': 'Invalid request method'})
    
    project_path = request.form.get('projectPath')
    
    if not project_path:
        current_app.logger.warning("No project path provided")
        return jsonify({'status': 'error', 'message': 'No project path provided'})
    
    try:
        current_app.logger.debug(f"Validating and loading project: {project_path}")
        
        validation_result = validate_project_structure(project_path)
        current_app.logger.debug(f"Validation result: {validation_result}")
        
        if validation_result['status'] == 'error':
            return jsonify(validation_result)
        
        if validation_result['status'] == 'warning' and validation_result.get('can_fix', False):
            current_app.logger.info(f"Fixing missing templates for {project_path}")
            copy_missing_templates(project_path, validation_result.get('missing_templates', []), current_app.config['TEMPLATE_FOLDER'])
        
        project_name = os.path.basename(os.path.normpath(project_path))
        current_app.config['CURRENT_PROJECT'] = project_name
        current_app.config['CURRENT_PROJECT_PATH'] = project_path
        
        user_id = session.get('user_id', 'default_user')
        save_recent_project(user_id, project_name, project_path) # Uses the BP's version
        
        current_app.logger.info(f"Successfully loaded project: {project_name} at {project_path}")
        return jsonify({
            'status': 'success',
            'message': 'Project loaded successfully',
            'project_path': project_path,
            'project_name': project_name
        })
    except Exception as e:
        current_app.logger.exception(f"Error loading project: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error loading project: {str(e)}'
        })

@project_bp.route('/api/recent_projects', methods=['GET'])
def api_recent_projects():
    current_app.logger.info("Processing API request for recent_projects via project_bp")
    user_id = session.get('user_id', 'default_user')
    try:
        recent_projects_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'recent_projects')
        filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        current_app.logger.debug(f"Looking for recent projects file: {filename}")
        
        if not os.path.exists(filename):
            current_app.logger.warning(f"Recent projects file not found for user {user_id}")
            return jsonify({'recent_projects': []})
        
        with open(filename, 'r') as f:
            recent_projects_data = json.load(f) # Renamed to avoid conflict
        
        current_app.logger.info(f"Loaded {len(recent_projects_data)} recent projects for user {user_id}")
        return jsonify({'recent_projects': recent_projects_data})
    except Exception as e:
        current_app.logger.exception(f"Error reading recent projects: {e}")
        return jsonify({'recent_projects': [], 'error': str(e)})

@project_bp.route('/api/delete_recent_project', methods=['POST'])
def api_delete_recent_project():
    current_app.logger.info("Processing API request to delete_recent_project via project_bp")
    user_id = session.get('user_id', 'default_user')
    
    try:
        data = request.get_json()
        if not data or 'projectPath' not in data:
            current_app.logger.warning("Project path not provided in request")
            return jsonify({'status': 'error', 'message': 'Project path not provided'})
        
        project_path_to_delete = data['projectPath'] # Renamed
        current_app.logger.debug(f"Requested deletion of project: {project_path_to_delete}")
        
        recent_projects_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'recent_projects')
        filename = os.path.join(recent_projects_dir, f"{user_id}.json")
        if not os.path.exists(filename):
            current_app.logger.warning(f"Recent projects file not found for user {user_id}")
            return jsonify({'status': 'error', 'message': 'Recent projects file not found'})
        
        with open(filename, 'r') as f:
            recent_projects_list = json.load(f) # Renamed
        
        found = False
        for i, project_item in enumerate(recent_projects_list): # Renamed
            if project_item.get('path') == project_path_to_delete:
                recent_projects_list.pop(i)
                found = True
                break
        
        if not found:
            current_app.logger.warning(f"Project {project_path_to_delete} not found in recent projects")
            return jsonify({'status': 'error', 'message': 'Project not found in recent projects'})
        
        with open(filename, 'w') as f:
            json.dump(recent_projects_list, f, indent=4)
        
        current_app.logger.info(f"Removed project {project_path_to_delete} from recent projects for user {user_id}")
        
        return jsonify({'status': 'success', 'message': 'Project removed from recent projects'})
    
    except Exception as e:
        current_app.logger.exception(f"Error removing project from recent projects: {e}")
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'})
