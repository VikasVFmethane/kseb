from flask import Blueprint, request, redirect, url_for, flash, send_file, current_app
import os
from werkzeug.utils import secure_filename

data_bp = Blueprint('data', 
                    __name__, 
                    template_folder='../templates', 
                    static_folder='../static',
                    url_prefix='/data')

# Helper functions moved from app.py
def allowed_file(filename):
    # Check if a file has an allowed extension
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def create_template_files():
    # Create template files if they don't exist
    current_app.logger.info("Creating template files if needed (data_bp)")
    try:
        # In a real scenario, this function would actually create/copy template files.
        # For now, it's a placeholder as in the original app.py.
        # Example:
        # template_dir = current_app.config['TEMPLATE_FOLDER']
        # required_templates = ['data_input_template.xlsx', 'load_curve_template.xlsx']
        # for tpl_name in required_templates:
        #     tpl_path = os.path.join(template_dir, tpl_name)
        #     if not os.path.exists(tpl_path):
        #         # Logic to create or copy the template file
        #         current_app.logger.info(f"Creating {tpl_name}...")
        #         # with open(tpl_path, 'w') as f: f.write("Placeholder content") # Example
        pass
    except Exception as e:
        current_app.logger.error(f"Error creating template files (data_bp): {e}")

@data_bp.route('/upload', methods=['POST']) # Adjusted route from /upload_data
def upload_data_route(): # Renamed
    current_app.logger.info("Processing upload_data request via data_bp")
    
    if request.method == 'POST':
        if not current_app.config.get('CURRENT_PROJECT'):
            current_app.logger.warning("No project selected for upload_data via data_bp")
            flash('Please select or create a project first', 'warning')
            return redirect(url_for('core.home')) # Assuming home is in core_bp
            
        if 'data_file' not in request.files:
            current_app.logger.warning("No file part in upload_data request via data_bp")
            flash('No file part', 'danger')
            return redirect(url_for('core.home')) # Redirect to a relevant page
        
        file = request.files['data_file']
        
        if file.filename == '':
            current_app.logger.warning("No file selected in upload_data form via data_bp")
            flash('No selected file', 'danger')
            return redirect(url_for('core.home')) 
        
        if file and allowed_file(file.filename): # Uses BP's allowed_file
            filename = secure_filename(file.filename)
            # Ensure 'inputs' directory exists in the current project
            project_inputs_folder = os.path.join(current_app.config['CURRENT_PROJECT_PATH'], 'inputs')
            os.makedirs(project_inputs_folder, exist_ok=True)
            
            file_path = os.path.join(project_inputs_folder, filename)
            
            current_app.logger.info(f"Saving uploaded file to {file_path} via data_bp")
            file.save(file_path)
            flash('File uploaded successfully!', 'success')
            return redirect(url_for('core.home')) # Or a more relevant page
        else:
            current_app.logger.warning(f"Invalid file type: {file.filename if file else 'None'} via data_bp")
            flash('Invalid file type. Please upload an Excel (.xlsx) file.', 'danger')
            return redirect(url_for('core.home'))

@data_bp.route('/download/template/<template_type>') # Adjusted from /download_template/<template_type>
def download_template_route(template_type): # Renamed
    current_app.logger.info(f"Processing download_template request for {template_type} via data_bp")
    
    templates = {
        'data_input': 'data_input_template.xlsx', # This was not in original app.py but good to have
        'load_curve': 'load_curve_template.xlsx',
        'pypsa_input': 'pypsa_input_template.xlsx',
        # Adding other templates from static/templates for completeness
        'input_demand_file': 'input_demand_file.xlsx', # from static/templates
        'load_profile_excel': 'load_profile.xlsx' # from static/templates, distinct from load_curve
    }
    
    if template_type not in templates:
        current_app.logger.warning(f"Invalid template type requested: {template_type} via data_bp")
        flash('Template not found', 'danger')
        return redirect(url_for('core.home'))
    
    # Templates are in app.config['TEMPLATE_FOLDER'] which is 'static/templates'
    template_path = os.path.join(current_app.config['TEMPLATE_FOLDER'], templates[template_type])
    
    if not os.path.exists(template_path):
        current_app.logger.warning(f"Template file not found: {template_path} via data_bp")
        create_template_files() # Attempt to create if missing
        if not os.path.exists(template_path):
            current_app.logger.error(f"Template file {templates[template_type]} not found even after creation attempt (data_bp)")
            flash(f'Template file {templates[template_type]} not found', 'danger')
            return redirect(url_for('core.home'))
    
    current_app.logger.info(f"Sending template file: {template_path} via data_bp")
    return send_file(template_path, as_attachment=True)

@data_bp.route('/download/user_guide') # Adjusted from /download_user_guide
def download_user_guide_route(): # Renamed
    current_app.logger.info("Processing download_user_guide request via data_bp")
    
    # Assuming user_guide.pdf is in app.config['TEMPLATE_FOLDER'] or a similar configured static location
    # The original app.py implies 'static/templates/user_guide.pdf'
    guide_path = os.path.join(current_app.config['TEMPLATE_FOLDER'], 'user_guide.pdf') 
    
    if not os.path.exists(guide_path):
        current_app.logger.warning(f"User guide PDF not found: {guide_path} via data_bp")
        flash('User guide PDF not found', 'danger')
        return redirect(url_for('core.home'))
        
    current_app.logger.info(f"Sending user guide file: {guide_path} via data_bp")
    return send_file(guide_path, as_attachment=True)

@data_bp.route('/download/methodology') # Adjusted from /download_methodology
def download_methodology_route(): # Renamed
    current_app.logger.info("Processing download_methodology request via data_bp")
    
    # Assuming methodology.pdf is in app.config['TEMPLATE_FOLDER']
    methodology_path = os.path.join(current_app.config['TEMPLATE_FOLDER'], 'methodology.pdf')
    
    if not os.path.exists(methodology_path):
        current_app.logger.warning(f"Methodology PDF not found: {methodology_path} via data_bp")
        flash('Methodology PDF not found', 'danger')
        return redirect(url_for('core.home'))
        
    current_app.logger.info(f"Sending methodology file: {methodology_path} via data_bp")
    return send_file(methodology_path, as_attachment=True)
