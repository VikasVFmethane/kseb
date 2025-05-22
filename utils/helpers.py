# Create or update utils/helpers.py

import os
import shutil
import pandas as pd
def slugify(text):
    """
    Convert text to a safe slug for use in IDs and URLs.
    """
    # Basic implementation that handles most cases
    import re
    from unicodedata import normalize
    
    # Convert to lowercase and normalize unicode
    text = str(text).lower().strip()
    text = normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    
    # Replace spaces and special characters with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    
    return text
def create_project_structure(project_path, template_folder=None):
    """
    Create the standard project folder structure
    
    Args:
        project_path (str): The path where the project structure will be created
        template_folder (str, optional): Path to template folder. 
                                        If None, no template files are copied.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create main project folder if it doesn't exist
        os.makedirs(project_path, exist_ok=True)
        
        # Create input and results folders
        inputs_folder = os.path.join(project_path, 'inputs')
        results_folder = os.path.join(project_path, 'results')
        
        os.makedirs(inputs_folder, exist_ok=True)
        os.makedirs(results_folder, exist_ok=True)
        
        # Create subfolders in results
        demand_projection_folder = os.path.join(results_folder, 'demand_projection')
        load_profiles_folder = os.path.join(results_folder, 'load_profiles')
        pypsa_results_folder = os.path.join(results_folder, 'Pypsa_results')
        
        os.makedirs(demand_projection_folder, exist_ok=True)
        os.makedirs(load_profiles_folder, exist_ok=True)
        os.makedirs(pypsa_results_folder, exist_ok=True)
        
        # Copy template files to inputs folder if a template folder is provided
        if template_folder:
            templates = {
                'data_input_template.xlsx': 'data_input_template.xlsx',
                'load_curve_template.xlsx': 'load_curve_template.xlsx',
                'pypsa_input_template.xlsx': 'pypsa_input_template.xlsx'
            }
            
            for source_name, dest_name in templates.items():
                source_path = os.path.join(template_folder, source_name)
                
                if os.path.exists(source_path):
                    dest_path = os.path.join(inputs_folder, dest_name)
                    shutil.copy2(source_path, dest_path)
                else:
                    print(f"Warning: Template file {source_name} not found")
        
        return True
    
    except Exception as e:
        print(f"Error creating project structure: {e}")
        return False

def validate_project_structure(project_path):
    """Helper function to validate project structure"""
    # Check if the path exists
    if not os.path.exists(project_path):
        return {
            'status': 'error', 
            'message': f'The path "{project_path}" does not exist'
        }
    
    # Check if it's a directory
    if not os.path.isdir(project_path):
        return {
            'status': 'error', 
            'message': f'The path "{project_path}" is not a directory'
        }
    
    # Check for required folders
    inputs_folder = os.path.join(project_path, 'inputs')
    results_folder = os.path.join(project_path, 'results')
    
    if not os.path.exists(inputs_folder) or not os.path.isdir(inputs_folder):
        return {
            'status': 'error', 
            'message': 'Invalid project structure: "inputs" folder is missing'
        }
    
    if not os.path.exists(results_folder) or not os.path.isdir(results_folder):
        return {
            'status': 'error', 
            'message': 'Invalid project structure: "results" folder is missing'
        }
    
    # Check for subfolders in results
    required_subfolders = ['demand_projection', 'load_profiles', 'Pypsa_results']
    missing_subfolders = []
    
    for subfolder in required_subfolders:
        subfolder_path = os.path.join(results_folder, subfolder)
        if not os.path.exists(subfolder_path) or not os.path.isdir(subfolder_path):
            missing_subfolders.append(subfolder)
    
    if missing_subfolders:
        return {
            'status': 'warning',
            'message': f'Project structure is incomplete: Missing subfolders in "results": {", ".join(missing_subfolders)}',
            'missing_folders': missing_subfolders
        }
    
    # Check for template files in inputs folder
    template_files = ['data_input_template.xlsx', 'load_curve_template.xlsx', 'pypsa_input_template.xlsx']
    missing_templates = []
    
    for template in template_files:
        template_path = os.path.join(inputs_folder, template)
        if not os.path.exists(template_path):
            missing_templates.append(template)
    
    if missing_templates:
        # This is just a warning, not an error - we can copy the templates
        return {
            'status': 'warning',
            'message': f'Template files missing: {", ".join(missing_templates)}',
            'missing_templates': missing_templates,
            'can_fix': True
        }
    
    # All validation passed
    return {
        'status': 'success',
        'message': 'Valid project structure detected'
    }

def copy_missing_templates(project_path, missing_templates, template_folder):
    """Helper function to copy missing template files to the project"""
    if not missing_templates:
        return True
    
    inputs_folder = os.path.join(project_path, 'inputs')
    success = True
    
    for template in missing_templates:
        source_path = os.path.join(template_folder, template)
        dest_path = os.path.join(inputs_folder, template)
        
        try:
            if os.path.exists(source_path):
                shutil.copy2(source_path, dest_path)
                print(f"Copied template: {template}")
            else:
                print(f"Warning: Template file {template} not found in template folder")
                success = False
        except Exception as e:
            print(f"Error copying template {template}: {e}")
            success = False
    
    return success


def find_special_symbols(df, marker):
    markers = []
    for i, row in df.iterrows():
        for j, value in enumerate(row):
            if isinstance(value, str) and value.startswith(marker):
                markers.append((i, j, value[len(marker):].strip()))
    return markers
def extract_table(df, start_row, start_col):
    end_row = start_row + 1
    while end_row < len(df) and pd.notnull(df.iloc[end_row, start_col]):
        end_row += 1

    end_col = start_col + 1
    while end_col < len(df.columns) and pd.notnull(df.iloc[start_row, end_col]):
        end_col += 1

    table = df.iloc[start_row:end_row, start_col:end_col].copy()
    table.columns = table.iloc[0]
    table = table[1:].reset_index(drop=True)

    return table
def extract_tables_by_markers(df, marker):
    markers = find_special_symbols(df, marker)
    tables = {}
    for marker_info in markers:
        start_row, start_col, table_name = marker_info
        tables[table_name] = extract_table(df, start_row + 1, start_col)
    return tables
