from flask import (Blueprint, render_template, request, redirect, url_for, 
                   flash, jsonify, current_app, send_file, make_response)
import os
import pandas as pd
import numpy as np # For handle_nan_values if included
import json
from datetime import datetime
import threading
import uuid
import tempfile
from pathlib import Path
import inspect # For _api_data_wrapper

import pypsa
import utils.pypsa_analysis_utils as pau
from utils.pypsa_runner import run_pypsa_model_core 
from utils.helpers import extract_tables_by_markers 
from werkzeug.utils import secure_filename 

pypsa_bp = Blueprint('pypsa', 
                     __name__, 
                     template_folder='../templates', 
                     static_folder='../static',
                     url_prefix='/pypsa')

# Blueprint-specific storage for PyPSA jobs
pypsa_jobs = {}

# TEMP_DIR for PyPSA related temporary files
PYPSA_TEMP_DIR = tempfile.mkdtemp(prefix="pypsa_flask_bp_")


# Helper function for NaN handling
def handle_nan_values(obj):
    if isinstance(obj, float) and np.isnan(obj): return None
    if isinstance(obj, dict): return {k: handle_nan_values(v) for k, v in obj.items()}
    if isinstance(obj, list): return [handle_nan_values(item) for item in obj]
    return obj

# ==========================================
# PYPSA HELPER FUNCTIONS
# ==========================================

def get_pypsa_results_folder_bp():
    current_project_base_path = current_app.config.get('CURRENT_PROJECT_PATH')
    if not current_project_base_path:
        current_app.logger.error("get_pypsa_results_folder_bp: CURRENT_PROJECT_PATH not set.")
        return None
    # Consistent path: results/Pypsa_results
    pypsa_results_relative_path = os.path.join('results', 'Pypsa_results')
    return os.path.join(current_project_base_path, pypsa_results_relative_path)

def _get_snapshots_for_period_bp(n: pypsa.Network, 
                                 period_name: str = None, 
                                 start_date_str: str = None, 
                                 end_date_str: str = None):
    snapshots = pau.safe_get_snapshots(n)
    if snapshots.empty: return snapshots
    current_snapshots_slice = snapshots
    if period_name and isinstance(current_snapshots_slice, pd.MultiIndex):
        period_level_values = current_snapshots_slice.get_level_values(0)
        try:
            typed_period_name = period_level_values.dtype.type(period_name)
            period_mask = (period_level_values == typed_period_name)
            if period_mask.any(): current_snapshots_slice = current_snapshots_slice[period_mask]
            else: current_app.logger.warning(f"Period '{period_name}' not found in _get_snapshots_for_period_bp.")
        except ValueError: current_app.logger.warning(f"Could not convert period name '{period_name}' in _get_snapshots_for_period_bp.")
        except Exception as e: current_app.logger.error(f"Error period filtering in _get_snapshots_for_period_bp: {e}", exc_info=True)
    
    if start_date_str and end_date_str:
        try:
            start_dt = pd.Timestamp(start_date_str)
            end_dt = pd.Timestamp(end_date_str).replace(hour=23, minute=59, second=59)
            time_component = pau.get_time_index(current_snapshots_slice)
            if time_component is not None and not time_component.empty:
                date_mask = (time_component >= start_dt) & (time_component <= end_dt)
                if isinstance(current_snapshots_slice, pd.MultiIndex):
                    valid_time_indices = time_component[date_mask]
                    current_snapshots_slice = current_snapshots_slice[current_snapshots_slice.get_level_values(-1).isin(valid_time_indices)]
                else:
                    current_snapshots_slice = current_snapshots_slice[date_mask]
                if current_snapshots_slice.empty: current_app.logger.warning("Date range resulted in empty snapshots in _get_snapshots_for_period_bp.")
        except Exception as e:
            current_app.logger.error(f"Error applying date filter in _get_snapshots_for_period_bp: {e}", exc_info=True)
    return current_snapshots_slice

def _api_data_wrapper_bp(network_rel_path, data_extraction_func_name_in_pau: str, **route_specific_kwargs):
    pypsa_folder = get_pypsa_results_folder_bp()
    if not pypsa_folder:
        return make_response(jsonify({'status': 'error', 'message': 'Project context not available for PyPSA results.'}), 500)
    
    full_path = os.path.normpath(os.path.join(pypsa_folder, network_rel_path))
    if not full_path.startswith(os.path.normpath(pypsa_folder)):
        return make_response(jsonify({'status': 'error', 'message': 'Invalid file path for PyPSA network.'}), 400)
    if not os.path.exists(full_path):
        return make_response(jsonify({'status': 'error', 'message': f'Network file not found: {network_rel_path}'}), 404)

    period_name_req = request.args.get('period')
    start_date_req = request.args.get('start_date')
    end_date_req = request.args.get('end_date')
    resolution_req = request.args.get('resolution', '1H')

    try:
        n = pypsa.Network(full_path)
        actual_data_func = getattr(pau, data_extraction_func_name_in_pau, None)
        if not callable(actual_data_func):
            current_app.logger.critical(f"PyPSA data extraction function '{data_extraction_func_name_in_pau}' not found.")
            return make_response(jsonify({'status': 'error', 'message': 'Server misconfiguration: PyPSA data function not found.'}), 500)

        filtered_snapshots = _get_snapshots_for_period_bp(n, period_name_req, start_date_req, end_date_req)
        
        if filtered_snapshots.empty:
            empty_payload_content = {}
            if data_extraction_func_name_in_pau == "dispatch_data_payload_former": 
                empty_payload_content = {'generation': [], 'load': [], 'storage': [], 'store': [], 'timestamps': []}
            elif data_extraction_func_name_in_pau == "get_carrier_capacity": 
                empty_payload_content = {'by_carrier': [], 'by_region': []}
            elif data_extraction_func_name_in_pau == "combined_metrics_extractor_wrapper": 
                empty_payload_content = {'cuf': [], 'curtailment': []}
            elif data_extraction_func_name_in_pau == "extract_api_storage_data_payload_former":
                empty_payload_content = {'charge_discharge': [], 'state_of_charge': []}
            elif data_extraction_func_name_in_pau == "emissions_payload_former":
                empty_payload_content = {'total_emissions': [], 'emissions_by_carrier': []}
            elif data_extraction_func_name_in_pau == "extract_api_prices_data_payload_former":
                 empty_payload_content = {'bus_prices': [], 'line_loading': [], 'generator_marginal_cost':[]} # Match pau
            elif data_extraction_func_name_in_pau == "extract_api_network_flow_payload_former":
                 empty_payload_content = {'line_flows': [], 'bus_balance': []}


            response_key_base = data_extraction_func_name_in_pau.replace("get_", "").replace("_payload", "").replace("_former","").replace("_extractor_wrapper","").replace("_extractor","")
            return jsonify({
                'status': 'success',
                response_key_base + "_data": empty_payload_content,
                'colors': pau.get_color_palette(n) if hasattr(pau, 'get_color_palette') else {},
                'message': "No data available for the selected PyPSA filters."})

        func_args = {'n': n, '_snapshots_slice': filtered_snapshots, 'snapshots_slice': filtered_snapshots,
                     'resolution': resolution_req, 'period': period_name_req, 'period_name': period_name_req}
        func_args.update(route_specific_kwargs)
        
        sig = inspect.signature(actual_data_func)
        valid_func_args = {k: v for k, v in func_args.items() if k in sig.parameters}
        if '_n' in sig.parameters and 'n' not in valid_func_args : valid_func_args['_n'] = n

        raw_result_payload = actual_data_func(**valid_func_args)
        color_palette = pau.get_color_palette(n) if hasattr(pau, 'get_color_palette') else {}

        def serialize_item_for_json(item):
            if isinstance(item, pd.DataFrame):
                df_reset = item.copy()
                original_index_names = [name if name is not None else f"level_{i}" for i, name in enumerate(df_reset.index.names)]
                is_multi = isinstance(df_reset.index, pd.MultiIndex)
                df_reset = df_reset.reset_index()
                
                if is_multi:
                    for i, name in enumerate(original_index_names):
                        if name in df_reset.columns: # If original index level name was already a column name
                             df_reset.rename(columns={name: f"index_{name}"}, inplace=True)
                        df_reset.rename(columns={f"level_{i}": name}, inplace=True)
                else: # Single index
                    if original_index_names[0] in df_reset.columns and original_index_names[0] != 'index':
                         df_reset.rename(columns={original_index_names[0]: f"index_{original_index_names[0]}"}, inplace=True)
                    df_reset.rename(columns={'index': original_index_names[0]}, inplace=True)

                for col in df_reset.columns:
                    if pd.api.types.is_datetime64_any_dtype(df_reset[col]): df_reset[col] = df_reset[col].astype(str)
                    elif isinstance(df_reset[col].dtype, pd.PeriodDtype): df_reset[col] = df_reset[col].astype(str)
                return handle_nan_values(df_reset.to_dict(orient='records'))
            elif isinstance(item, pd.Series):
                idx_name = item.index.name if item.index.name else 'index'
                val_col_name = item.name if item.name else 'value'
                series_reset = item.copy().reset_index(name=val_col_name)
                if idx_name in series_reset.columns and idx_name != 'index': # if original index name was already a column name
                    series_reset.rename(columns={idx_name: f"index_{idx_name}"}, inplace=True)
                series_reset.rename(columns={'index': idx_name}, inplace=True)

                if pd.api.types.is_datetime64_any_dtype(series_reset[idx_name]): series_reset[idx_name] = series_reset[idx_name].astype(str)
                return handle_nan_values(series_reset.to_dict(orient='records'))
            return handle_nan_values(item)

        serialized_payload_content = {k: serialize_item_for_json(v) for k, v in raw_result_payload.items()}
        response_key_base = data_extraction_func_name_in_pau.replace("get_", "").replace("_payload", "").replace("_former","").replace("_extractor_wrapper","").replace("_extractor","")
        
        response_dict = {'status': 'success', response_key_base + "_data": serialized_payload_content}
        if color_palette: response_dict['colors'] = color_palette
        return jsonify(response_dict)

    except FileNotFoundError:
        return make_response(jsonify({'status': 'error', 'message': f'Network file disappeared: {network_rel_path}'}), 404)
    except Exception as e:
        current_app.logger.error(f"CRITICAL ERROR in _api_data_wrapper_bp for '{data_extraction_func_name_in_pau}', network '{network_rel_path}'. Error: {type(e).__name__} - {str(e)}", exc_info=True)
        return make_response(jsonify({'status': 'error', 'message': f"Server error processing PyPSA data for '{data_extraction_func_name_in_pau}'.", 'details': f"{type(e).__name__}: {str(e)}"}), 500)

# ==========================================
# PYPSA MAIN AND API ROUTES
# ==========================================
@pypsa_bp.route('/modeling')
def pypsa_modeling_route():
    current_app.logger.info("Accessing pypsa_modeling route via pypsa_bp")
    if not current_app.config.get('CURRENT_PROJECT'):
        flash('Please select or create a project first', 'warning')
        return redirect(url_for('core.home'))
    try:
        input_excel_path = Path(current_app.config['CURRENT_PROJECT_PATH']) / "inputs" / "pypsa_input_template.xlsx"
        input_file_exists = input_excel_path.exists()
        if not input_file_exists:
            flash('PyPSA input template (pypsa_input_template.xlsx) not found in project inputs folder.', 'warning')
        return render_template('pypsa_modeling.html', 
                               current_project=current_app.config['CURRENT_PROJECT'],
                               input_file_exists=input_file_exists)
    except Exception as e:
        current_app.logger.exception(f"Error accessing pypsa_modeling_route: {e}")
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('core.home'))

@pypsa_bp.route('/results')
def pypsa_results_route():
    current_app.logger.info("Accessing PyPSA results page via pypsa_bp")
    if current_app.config.get('CURRENT_PROJECT_PATH') is None: 
        flash('Please select or create a project first.', 'warning')
        return redirect(url_for('core.home'))
    
    pypsa_folder = get_pypsa_results_folder_bp()
    scenarios = []
    nc_files_info = []
    if pypsa_folder and os.path.exists(pypsa_folder):
        for item in os.listdir(pypsa_folder):
            item_path = os.path.join(pypsa_folder, item)
            if os.path.isdir(item_path):
                scenarios.append(item)
                for root, _, files_in_dir in os.walk(item_path):
                    for file_item in files_in_dir:
                        if file_item.endswith('.nc'):
                            full_file_path = os.path.join(root, file_item)
                            rel_path_to_file = os.path.relpath(full_file_path, pypsa_folder)
                            nc_files_info.append({'scenario': item, 'filename': file_item, 'path': rel_path_to_file.replace(os.sep, '/')})
    else:
        if pypsa_folder: os.makedirs(pypsa_folder, exist_ok=True)
        flash('PyPSA results folder empty or not found. Please upload .nc files or run simulations.', 'info')

    return render_template('pypsa_results.html',
                           scenarios=sorted(list(set(scenarios))),
                           nc_files=nc_files_info,
                           current_project=current_app.config.get('CURRENT_PROJECT', 'N/A'))

@pypsa_bp.route('/api/scan_files', methods=['GET'])
def api_scan_pypsa_files_api():
    pypsa_folder = get_pypsa_results_folder_bp()
    if not pypsa_folder: return jsonify({'status': 'error', 'message': 'No project selected.'})
    scenarios, nc_files_info = [], []
    if os.path.exists(pypsa_folder):
        for item in os.listdir(pypsa_folder):
            item_path = os.path.join(pypsa_folder, item)
            if os.path.isdir(item_path):
                scenarios.append(item)
                for root, _, files_in_dir in os.walk(item_path):
                    for file_item in files_in_dir:
                        if file_item.endswith('.nc'):
                            rel_path = os.path.relpath(os.path.join(root, file_item), pypsa_folder)
                            nc_files_info.append({'scenario': item, 'filename': file_item, 'path': rel_path.replace(os.sep, '/')})
    else: os.makedirs(pypsa_folder, exist_ok=True)
    return jsonify({'status': 'success', 'scenarios': sorted(list(set(scenarios))), 'files': nc_files_info})

@pypsa_bp.route('/api/upload_network', methods=['POST'])
def api_upload_pypsa_network_api():
    pypsa_folder = get_pypsa_results_folder_bp()
    if not pypsa_folder: return jsonify({'status': 'error', 'message': 'No project selected.'})
    if 'network_file' not in request.files: return jsonify({'status': 'error', 'message': 'No file part'})
    file_obj = request.files['network_file']
    scenario_name = request.form.get('scenario', 'default_uploads')
    if file_obj.filename == '': return jsonify({'status': 'error', 'message': 'No selected file'})
    if not file_obj.filename.endswith('.nc'): return jsonify({'status': 'error', 'message': 'Only .nc valid'})
    try:
        scenario_path = os.path.join(pypsa_folder, scenario_name)
        os.makedirs(scenario_path, exist_ok=True)
        filename = secure_filename(file_obj.filename)
        save_path = os.path.join(scenario_path, filename)
        file_obj.save(save_path)
        rel_path = os.path.relpath(save_path, pypsa_folder)
        return jsonify({'status': 'success', 'message': 'Uploaded.', 'file_info': {'scenario': scenario_name, 'filename': filename, 'path': rel_path.replace(os.sep, '/')}})
    except Exception as e: 
        current_app.logger.error(f"PyPSA Upload error: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)})

@pypsa_bp.route('/api/network_info/<path:network_rel_path>', methods=['GET'])
def api_get_pypsa_network_info_api(network_rel_path):
    pypsa_folder = get_pypsa_results_folder_bp()
    if not pypsa_folder: return jsonify({'status': 'error', 'message': 'Project context not available.'})
    full_path = os.path.normpath(os.path.join(pypsa_folder, network_rel_path))
    if not full_path.startswith(os.path.normpath(pypsa_folder)):
        return jsonify({'status': 'error', 'message': 'Invalid file path.'}), 400
    if not os.path.exists(full_path):
        return jsonify({'status': 'error', 'message': f'Network file not found: {network_rel_path}'}), 404
    try:
        n = pypsa.Network(full_path)
        snaps = pau.safe_get_snapshots(n)
        is_multi = isinstance(snaps, pd.MultiIndex) and snaps.nlevels > 1
        
        periods = []
        if is_multi and hasattr(snaps, 'levels') and len(snaps.levels) > 0:
            periods = sorted(snaps.levels[0].astype(str).unique().tolist())
        
        components_info = {}
        if hasattr(n, 'components'):
            for component_name in n.components.keys():
                try:
                    component_list_name = n.components[component_name]["list_name"]
                    if hasattr(n, component_list_name):
                        component_df = getattr(n, component_list_name)
                        components_info[component_name] = len(component_df)
                    else:
                        components_info[component_name] = 0
                except (KeyError, TypeError):
                    try:
                        if hasattr(n, component_name): # Fallback for older PyPSA or different structure
                            component_df = getattr(n, component_name)
                            components_info[component_name] = len(component_df) if hasattr(component_df, '__len__') else 0
                        else:
                            components_info[component_name] = 0
                    except Exception:
                        components_info[component_name] = 0
        
        carriers_list = []
        if hasattr(n, 'carriers') and not n.carriers.empty:
            carriers_list = n.carriers.index.tolist()
        
        start_s, end_s = "N/A", "N/A"
        if not snaps.empty:
            s0_raw, s_end_raw = snaps[0], snaps[-1]
            start_s = str(pau.get_time_index(pd.Index([s0_raw]))[0]) if pau.get_time_index(pd.Index([s0_raw])) is not None else str(s0_raw)
            end_s = str(pau.get_time_index(pd.Index([s_end_raw]))[0]) if pau.get_time_index(pd.Index([s_end_raw])) is not None else str(s_end_raw)


        info = {
            'name': os.path.basename(network_rel_path),
            'components': components_info,
            'carriers': carriers_list,
            'snapshots': {
                'count': len(snaps),
                'start': start_s,
                'end': end_s,
                'is_multi_period': is_multi
            },
            'periods': periods,
            'optimization_status': getattr(n, 'objective_status', 'N/A') # PyPSA sometimes uses objective_status
        }
        return jsonify({'status': 'success', 'network_info': info})
    except Exception as e:
       
        error_payload = {'status': 'error', 'message': f"Error processing network info: {str(e)}"}
        response = make_response(jsonify(error_payload), 500)
        response.mimetype = "application/json"
        return response

@pypsa_bp.route('/api/extract_period/<path:network_rel_path>/<period_name_req>', methods=['GET'])
def api_extract_period_network_api(network_rel_path, period_name_req):
    pypsa_folder = get_pypsa_results_folder_bp()
    if not pypsa_folder: return jsonify({'status': 'error', 'message': 'No project selected.'})

    original_full_path = os.path.normpath(os.path.join(pypsa_folder, network_rel_path))
    if not original_full_path.startswith(os.path.normpath(pypsa_folder)):
        return jsonify({'status': 'error', 'message': 'Invalid original file path.'}), 400
    if not os.path.exists(original_full_path):
        return jsonify({'status': 'error', 'message': f'Original network file not found: {network_rel_path}'}), 404

    try:
        n_orig = pypsa.Network(original_full_path)
        if not isinstance(n_orig.snapshots, pd.MultiIndex) or n_orig.snapshots.nlevels < 1:
            return jsonify({'status': 'error', 'message': 'Network does not have multi-period snapshots.'}), 400

        period_level_values = n_orig.snapshots.get_level_values(0)
        try:
            typed_period_name = period_level_values.dtype.type(period_name_req)
        except ValueError:
             return jsonify({'status': 'error', 'message': f"Could not convert period name '{period_name_req}' to the type of the snapshot period level."}), 400

        if typed_period_name not in period_level_values:
            return jsonify({'status': 'error', 'message': f"Period '{period_name_req}' not found in network snapshots."}), 404

        period_snapshots = n_orig.snapshots[period_level_values == typed_period_name]
        
        # Create a new network for the specific period
        n_period = pypsa.Network()
        
        # Copy components that are not time-dependent
        for component_name in n_orig.components:
            if component_name not in n_orig.component_attrs or not n_orig.component_attrs[component_name].get("type", "").endswith("_t"):
                n_period.madd(component_name, n_orig.df(component_name).index, **n_orig.df(component_name))
        
        # Copy time-dependent components, filtering by the period's snapshots
        for component_name in n_orig.components:
            if n_orig.component_attrs[component_name].get("type", "").endswith("_t"):
                df_t_orig = n_orig.pnl(component_name)
                if not df_t_orig.empty:
                    # Filter by the snapshots of the selected period
                    df_t_period = df_t_orig.loc[period_snapshots]
                    if not df_t_period.empty:
                        # Ensure the component itself exists in n_period before adding time series data
                        for item_name in df_t_period.columns.get_level_values(0).unique():
                             if item_name not in n_period.df(component_name).index and item_name in n_orig.df(component_name).index:
                                n_period.add(component_name, item_name, **n_orig.df(component_name).loc[item_name])
                        n_period.import_series_from_dataframe(df_t_period, component_name)

        n_period.set_snapshots(period_snapshots.get_level_values(1)) # Use the time part of the multi-index

        # Save the new network to a temporary file
        temp_dir_path = Path(PYPSA_TEMP_DIR)
        temp_dir_path.mkdir(parents=True, exist_ok=True)
        
        base_name = Path(network_rel_path).stem
        new_filename = f"{base_name}_period_{period_name_req}.nc"
        temp_file_path = temp_dir_path / new_filename
        
        n_period.export_to_netcdf(str(temp_file_path))
        
        # Determine scenario name from original path for saving
        scenario_name_from_path = Path(network_rel_path).parts[0] if len(Path(network_rel_path).parts) > 1 else "extracted_periods"
        
        # Save to the project's PyPSA results folder
        target_scenario_folder = Path(pypsa_folder) / scenario_name_from_path
        target_scenario_folder.mkdir(parents=True, exist_ok=True)
        final_save_path = target_scenario_folder / new_filename
        
        os.replace(str(temp_file_path), str(final_save_path)) # Move from temp to final location
        
        new_rel_path = os.path.relpath(str(final_save_path), pypsa_folder).replace(os.sep, '/')

        return jsonify({
            'status': 'success', 
            'message': f'Network for period {period_name_req} extracted and saved.',
            'new_network_path': new_rel_path,
            'new_filename': new_filename,
            'scenario': scenario_name_from_path
        })

    except Exception as e:
        current_app.logger.error(f"Error extracting period network for {network_rel_path}, period {period_name_req}: {e}", exc_info=True)
        return make_response(jsonify({'status': 'error', 'message': f"Error extracting period network: {str(e)}"}), 500)


@pypsa_bp.route('/api/dispatch_data/<path:network_rel_path>', methods=['GET'])
def api_get_dispatch_data_api(network_rel_path):
    return _api_data_wrapper_bp(network_rel_path, "dispatch_data_payload_former")

@pypsa_bp.route('/api/capacity_data/<path:network_rel_path>', methods=['GET'])
def api_get_capacity_data_api(network_rel_path):
    attribute = request.args.get('attribute', 'p_nom_opt')
    return _api_data_wrapper_bp(network_rel_path, "get_carrier_capacity", attribute=attribute)


@pypsa_bp.route('/api/metrics_data/<path:network_rel_path>', methods=['GET'])
def api_get_metrics_data_api(network_rel_path):
    return _api_data_wrapper_bp(network_rel_path, "combined_metrics_extractor_wrapper")

@pypsa_bp.route('/api/storage_data/<path:network_rel_path>', methods=['GET'])
def api_get_storage_data_api(network_rel_path):
    return _api_data_wrapper_bp(network_rel_path, "extract_api_storage_data_payload_former")

@pypsa_bp.route('/api/emissions_data/<path:network_rel_path>', methods=['GET'])
def api_get_emissions_data_api(network_rel_path):
    return _api_data_wrapper_bp(network_rel_path, "emissions_payload_former")

@pypsa_bp.route('/api/prices_data/<path:network_rel_path>', methods=['GET'])
def api_get_prices_data_api(network_rel_path):
    return _api_data_wrapper_bp(network_rel_path, "extract_api_prices_data_payload_former")

@pypsa_bp.route('/api/network_flow/<path:network_rel_path>', methods=['GET'])
def api_get_network_flow_data_api(network_rel_path):
    return _api_data_wrapper_bp(network_rel_path, "extract_api_network_flow_payload_former")

@pypsa_bp.route('/api/compare_networks', methods=['POST'])
def api_compare_networks_api():
    pypsa_folder = get_pypsa_results_folder_bp()
    if not pypsa_folder: return jsonify({'status': 'error', 'message': 'No project selected.'})
    try:
        req_data = request.get_json()
        file_paths_rel = req_data.get('file_paths', [])
        if len(file_paths_rel) < 2:
            return jsonify({'status': 'error', 'message': 'At least two network files are required for comparison.'}), 400

        networks_to_compare = {}
        for rel_path in file_paths_rel:
            full_path = os.path.normpath(os.path.join(pypsa_folder, rel_path))
            if not full_path.startswith(os.path.normpath(pypsa_folder)) or not os.path.exists(full_path):
                return jsonify({'status': 'error', 'message': f'Invalid or non-existent file path: {rel_path}'}), 400
            try:
                # Use filename as key, or a more unique identifier if needed
                network_key = os.path.basename(rel_path) 
                networks_to_compare[network_key] = pypsa.Network(full_path)
            except Exception as e:
                 return jsonify({'status': 'error', 'message': f"Error loading network {rel_path}: {str(e)}"}), 500
        
        comparison_results = pau.compare_networks_results(networks_to_compare)
        
        # Serialize comparison_results (assuming it's a dict of DataFrames/Series)
        serialized_results = {}
        for key, value in comparison_results.items():
            if isinstance(value, pd.DataFrame):
                serialized_results[key] = handle_nan_values(value.reset_index().to_dict(orient='records'))
            elif isinstance(value, pd.Series):
                 serialized_results[key] = handle_nan_values(value.reset_index().to_dict(orient='records'))
            else: # Handle other types like dicts of numbers/strings
                serialized_results[key] = handle_nan_values(value)

        return jsonify({'status': 'success', 'comparison_data': serialized_results})

    except Exception as e:
        current_app.logger.error(f"PyPSA Compare error: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Error during network comparison: {str(e)}'}), 500


@pypsa_bp.route('/api/get_settings_from_excel', methods=['GET'])
def api_get_pypsa_settings_from_excel_api():
    current_app.logger.info("Processing API request for get_pypsa_settings_from_excel via pypsa_bp")
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'})
    input_file_path = Path(current_app.config['CURRENT_PROJECT_PATH']) / "inputs" / "pypsa_input_template.xlsx"
    if not input_file_path.exists():
        return jsonify({'status': 'error', 'message': 'PyPSA input Excel file not found.'})
    try:
        xls = pd.ExcelFile(input_file_path)
        if 'Settings' not in xls.sheet_names:
            return jsonify({'status': 'error', 'message': "'Settings' sheet not found in the Excel file."})
        setting_df_excel = xls.parse('Settings')
        main_settings_table = extract_tables_by_markers(setting_df_excel, '~').get('Main_Settings')
        if main_settings_table is None:
            return jsonify({'status': 'error', 'message': "Main_Settings table not found in 'Settings' sheet."})
        settings_dict = {}
        for _, row in main_settings_table.iterrows():
            if pd.notna(row.get('Setting')) and pd.notna(row.get('Option')):
                val = row['Option']
                try: settings_dict[row['Setting']] = int(val) if isinstance(val, (int, float)) and float(val).is_integer() else float(val)
                except ValueError: settings_dict[row['Setting']] = str(val)
        ui_settings = {
            'Run Pypsa Model on': settings_dict.get('Run Pypsa Model on', 'All Snapshots'),
            'Weightings': int(settings_dict.get('Weightings', 1)),
            'Base_Year': int(settings_dict.get('Base_Year', 2025)),
            'Multi Year Investment': settings_dict.get('Multi Year Investment', 'No'),
            'Generator Cluster': settings_dict.get('Generator Cluster', 'No') == 'Yes',
        }
        return jsonify({'status': 'success', 'settings': ui_settings})
    except Exception as e:
        current_app.logger.exception(f"Error parsing PyPSA settings from Excel (pypsa_bp): {e}")
        return jsonify({'status': 'error', 'message': f'Error parsing Excel settings: {str(e)}'})

@pypsa_bp.route('/api/run_model', methods=['POST'])
def api_run_pypsa_model_api():
    current_app.logger.info("Processing API request to run_pypsa_model via pypsa_bp")
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected'})
    data = request.get_json()
    scenario_name = data.get('scenarioName')
    ui_settings_overrides = data.get('settings', {})
    if not scenario_name:
        return jsonify({'status': 'error', 'message': 'Scenario name is required'})

    job_id = str(uuid.uuid4())
    pypsa_jobs[job_id] = {
        'status': 'queued', 'progress': 0, 
        'log': [f"Job {job_id} for scenario '{scenario_name}' queued.\n"],
        'scenario_name': scenario_name, 'project_path': current_app.config['CURRENT_PROJECT_PATH'],
        'start_time': datetime.now().isoformat(), 'current_step': 'Initializing...',
        'result_files': None, 'error': None}
    try:
        pypsa_thread = threading.Thread(target=run_pypsa_model_core, 
                                        args=(job_id, current_app.config['CURRENT_PROJECT_PATH'], scenario_name, ui_settings_overrides, pypsa_jobs))
        pypsa_thread.daemon = True
        pypsa_thread.start()
        return jsonify({'status': 'started', 'jobId': job_id, 'message': f'PyPSA model run started for scenario: {scenario_name}'})
    except Exception as e:
        current_app.logger.exception(f"Error starting PyPSA model run (pypsa_bp): {e}")
        pypsa_jobs[job_id]['status'] = 'failed'
        pypsa_jobs[job_id]['error'] = str(e)
        return jsonify({'status': 'error', 'message': f'Error starting PyPSA model: {str(e)}'})

@pypsa_bp.route('/api/model_status/<job_id>', methods=['GET'])
def api_get_pypsa_model_status_api(job_id):
    current_app.logger.info(f"Processing API request for pypsa_model_status/{job_id} via pypsa_bp")
    job = pypsa_jobs.get(job_id)
    if not job: return jsonify({'status': 'error', 'message': 'Job not found'}), 404
    
    if job['status'] == 'Completed' and job.get('result_files') is None:
        scenario_results_dir = Path(job['project_path']) / "results" / "Pypsa_results" / job['scenario_name']
        if scenario_results_dir.exists(): job['result_files'] = [f.name for f in scenario_results_dir.iterdir() if f.is_file()]
        else: job['result_files'] = []
    return jsonify(job)

@pypsa_bp.route('/api/scenarios', methods=['GET'])
def api_get_pypsa_scenarios_api():
    current_app.logger.info("Processing API request for pypsa_scenarios via pypsa_bp")
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        return jsonify({'status': 'error', 'message': 'No project selected', 'scenarios': []})
    scenarios_dir = Path(current_app.config['CURRENT_PROJECT_PATH']) / "results" / "Pypsa_results"
    scenarios_data = []
    if scenarios_dir.exists():
        for scenario_path_item in scenarios_dir.iterdir():
            if scenario_path_item.is_dir():
                s_name = scenario_path_item.name
                status = "Unknown"
                job_found = False
                for j_id, j_info in pypsa_jobs.items():
                    if j_info['scenario_name'] == s_name and j_info['project_path'] == current_app.config['CURRENT_PROJECT_PATH']:
                        status = j_info['status']
                        job_found = True
                        break
                if not job_found and (list(scenario_path_item.glob('*.nc')) or list(scenario_path_item.glob('results_*/generators.csv'))):
                    status = "Completed"
                scenarios_data.append({'name': s_name, 'path': str(scenario_path_item), 'status': status, 
                                       'last_modified': datetime.fromtimestamp(scenario_path_item.stat().st_mtime).isoformat()})
    scenarios_data.sort(key=lambda x: x['last_modified'], reverse=True)
    return jsonify({'status': 'success', 'scenarios': scenarios_data})

@pypsa_bp.route('/api/download_result/<scenario_name>/<path:filename>', methods=['GET'])
def download_pypsa_result_file_api(scenario_name, filename):
    current_app.logger.info(f"Processing API request to download_pypsa_result/{scenario_name}/{filename} via pypsa_bp")
    if not current_app.config.get('CURRENT_PROJECT_PATH'):
        flash("No project loaded.", "danger")
        return redirect(url_for('pypsa.pypsa_modeling_route'))
    scenario_dir = Path(current_app.config['CURRENT_PROJECT_PATH']) / "results" / "Pypsa_results" / scenario_name
    parts = filename.split('/')
    safe_parts = [secure_filename(part) for part in parts]
    file_to_download_path = scenario_dir.joinpath(*safe_parts)
    if file_to_download_path.is_file() and str(file_to_download_path.resolve()).startswith(str(scenario_dir.resolve())):
        return send_file(str(file_to_download_path.resolve()), as_attachment=True)
    else:
        flash(f"File not found or access denied: {filename}", "danger")
        return redirect(url_for('pypsa.pypsa_results_route')) 
