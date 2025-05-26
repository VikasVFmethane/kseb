import streamlit as st

# --- 1. Imports ---
import streamlit as st
import pypsa
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import tempfile
import os
import numpy as np
import re
import datetime
import logging
import shutil
import atexit
from pathlib import Path
from typing import Union, Optional, Tuple, Dict, List, Any
from plotly.subplots import make_subplots

# --- 2. Logging and App Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#st.set_page_config(layout="wide", page_title="Advanced PyPSA Dashboard V6.0")

# --- 3. Constants and Defaults ---
DEFAULT_COLORS = {
    'Coal': '#000000', 'coal': '#000000',
    'Lignite': '#4B4B4B', 'lignite': '#4B4B4B',
    'Nuclear': '#800080', 'nuclear': '#800080',
    'Hydro': '#0073CF', 'hydro': '#0073CF',
    'Hydro RoR': '#3399FF', 'ror': '#3399FF', 'Hydro Storage': '#3399FF',
    'Solar': '#FFD700', 'solar': '#FFD700', 'pv': '#FFD700',
    'Wind': '#ADD8E6', 'wind': '#ADD8E6', 'onwind': '#ADD8E6', 'offwind': '#ADD8E6',
    'LFO': '#FF4500', 'lfo': '#FF4500', 'Oil': '#FF4500', 'oil': '#FF4500',
    'Co-Gen': '#228B22', 'co-gen': '#228B22', 'biomass': '#228B22',
    'PSP': '#3399FF', 'psp': '#3399FF',
    'Battery Storage': '#005B5B', 'battery': '#005B5B',
    'Planned Battery Storage': '#66B2B2', 'planned battery': '#66B2B2',
    'Planned PSP': '#B0C4DE', 'planned psp': '#B0C4DE',
    
    # Optional/general fallback categories
    'Storage': '#B0C4DE',
    'H2 Storage': '#AFEEEE', 'hydrogen': '#AFEEEE', 'h2': '#AFEEEE', 'H2': '#AFEEEE',
    'Load': '#000000',
    'Transmission': '#808080', 'Line': '#808080', 'Link': '#A9A9A9',
    'Losses': '#DC143C',
    'Other': '#D3D3D3',
    'Curtailment': '#FF00FF',
    'Excess': '#FF00FF',
    'Storage Charge': '#FFA500',
    'Storage Discharge': '#FFA500',
    'Store Charge': '#AFEEEE',
    'Store Discharge': '#AFEEEE',
}

PLOTLY_COLOR_CYCLE = px.colors.qualitative.Plotly

# --- 4. Utility Functions ---
def safe_get_snapshots(n: pypsa.Network) -> Union[pd.DatetimeIndex, pd.MultiIndex]:

    return n.snapshots

def get_time_index(index: Union[pd.DatetimeIndex, pd.MultiIndex]) -> pd.DatetimeIndex:

    if isinstance(index, pd.MultiIndex):
        # Ensure the second level is datetime-like
        time_level = index.get_level_values(-1) # Use -1 for the last level (timestamp)
        if pd.api.types.is_datetime64_any_dtype(time_level):
            return time_level
        else:
            try:
                return pd.to_datetime(time_level)
            except Exception as e:
                logging.error(f"Could not convert MultiIndex level 1 to DatetimeIndex: {e}")
                raise TypeError("MultiIndex level 1 is not datetime-like.")
    elif isinstance(index, pd.DatetimeIndex):
        return index
    else:
        try:
            return pd.to_datetime(index)
        except Exception as e:
             logging.error(f"Cannot convert index of type {type(index)} to DatetimeIndex: {e}")
             raise TypeError(f"Unsupported snapshot index type: {type(index)}")

def get_period_index(index: Union[pd.DatetimeIndex, pd.MultiIndex]) -> Union[pd.Index, pd.Series]:
   
    if isinstance(index, pd.MultiIndex):
        return index.get_level_values(0)
    elif isinstance(index, pd.DatetimeIndex):
        # Return the year as a simple way to group for "annual" analysis
        return pd.Series(index.year, index=index)
    else:
        logging.warning(f"Cannot determine period index from type {type(index)}. Returning None.")
        return None

def get_snapshot_weights(n: pypsa.Network, snapshots_idx: Union[pd.DatetimeIndex, pd.MultiIndex]) -> pd.Series:
    
    if hasattr(n, 'snapshot_weightings') and not n.snapshot_weightings.empty and 'objective' in n.snapshot_weightings.columns:
        # Ensure weights index matches snapshots index
        weights = n.snapshot_weightings.objective
        # Reindex carefully to handle potential missing indices in snapshots_idx
        common_index = snapshots_idx.intersection(weights.index)
        if common_index.empty:
             logging.warning("No common index between snapshots and snapshot_weightings. Assuming weight 1.0.")
             return pd.Series(1.0, index=snapshots_idx)
        else:
             # Reindex weights to the common index, then reindex to the full snapshots_idx, filling missing with 1.0
             return weights.reindex(common_index).reindex(snapshots_idx).fillna(1.0)
    else:
        logging.warning("Snapshot weights ('objective') not found or empty. Assuming weight 1.0 for all snapshots.")
        return pd.Series(1.0, index=snapshots_idx)

def resample_data(data_df, time_index, resolution):
    #Resample data to desired resolution.#
    if not isinstance(time_index, pd.DatetimeIndex):
        logging.warning(f"Cannot resample data to {resolution}. Index is not a DatetimeIndex.")
        return data_df
    
    # Create a copy of the DataFrame with datetime index
    df_resampled = data_df.copy()
    df_resampled.index = time_index
    
    # Resample
    return df_resampled.resample(resolution).mean()

def cleanup_temp_files():
    #Clean up temporary files when the app is closed.#
    if 'temp_dir' in st.session_state:
        try:
            shutil.rmtree(st.session_state['temp_dir'])
            logging.info(f"Cleaned up temporary directory: {st.session_state['temp_dir']}")
        except Exception as e:
            logging.error(f"Error cleaning up temp directory: {e}", exc_info=True)

# --- 5. Color Palette Functions ---
def get_color_palette(_n: pypsa.Network) -> Dict[str, str]:
    #Generates a color mapping dictionary for carriers and components.#
    logging.info("Generating color palette...")
    final_colors = DEFAULT_COLORS.copy()
    color_idx = 0
    all_keys = set(final_colors.keys()) # Keep track of keys already assigned

    # 1. Get colors from n.carriers
    if hasattr(_n, "carriers") and not _n.carriers.empty:
        carriers_df = _n.carriers
        carriers_df['nice_name']=carriers_df.index
        has_color = "color" in carriers_df.columns
        has_nice_name = "nice_name" in carriers_df.columns

        # Check if colors are defined in the carriers DataFrame
        if has_color and carriers_df["color"].notna().any():
            # Process carrier colors
            for idx, row in carriers_df.iterrows():
                carrier_name = idx
                nice_name = row.get("nice_name") if has_nice_name and pd.notna(row.get("nice_name")) else carrier_name
                color = row.get("color") if has_color and pd.notna(row.get("color")) and row.get("color") != "" else None
                key_to_use = nice_name # Prioritize nice_name

                if color:
                    final_colors[key_to_use] = color
                    all_keys.add(key_to_use)
                    if nice_name != carrier_name and carrier_name not in all_keys:
                        final_colors[carrier_name] = color
                        all_keys.add(carrier_name)
                else:
                    # Match to defaults if no color specified
                    matched = False
                    for default_key, default_color in DEFAULT_COLORS.items():
                        # Check both lowercase versions for better matching
                        if default_key.lower() in key_to_use.lower() or default_key.lower() in carrier_name.lower():
                            if key_to_use not in all_keys:
                                final_colors[key_to_use] = default_color
                                all_keys.add(key_to_use)
                            if nice_name != carrier_name and carrier_name not in all_keys:
                                final_colors[carrier_name] = default_color
                                all_keys.add(carrier_name)
                            matched = True
                            break
        else:
            # No colors in carriers - log this situation
            logging.info("No colors defined in carriers DataFrame. Using default colors.")
            
            # Make sure all carriers at least have a default color mapping
            for carrier in carriers_df.index:
                nice_name = carrier
                if has_nice_name and pd.notna(carriers_df.loc[carrier, "nice_name"]):
                    nice_name = carriers_df.loc[carrier, "nice_name"]
                
                # Try to match with default colors
                matched = False
                for default_key, default_color in DEFAULT_COLORS.items():
                    if default_key.lower() in str(carrier).lower() or (nice_name and default_key.lower() in str(nice_name).lower()):
                        if carrier not in all_keys:
                            final_colors[carrier] = default_color
                            all_keys.add(carrier)
                        if nice_name != carrier and nice_name not in all_keys:
                            final_colors[nice_name] = default_color
                            all_keys.add(nice_name)
                        matched = True
                        break
                
                # If no match found, use Plotly colors
                if not matched:
                    color = PLOTLY_COLOR_CYCLE[color_idx % len(PLOTLY_COLOR_CYCLE)]
                    if carrier not in all_keys:
                        final_colors[carrier] = color
                        all_keys.add(carrier)
                    if nice_name != carrier and nice_name not in all_keys:
                        final_colors[nice_name] = color
                        all_keys.add(nice_name)
                    color_idx += 1

    # 2. Ensure all used carriers/components have a color
    all_used_names = set()
    # Add carriers from components
    for comp_name in ['generators', 'storage_units', 'stores', 'links']:
        if hasattr(_n, comp_name):
            df_comp = getattr(_n, comp_name)
            if not df_comp.empty and 'carrier' in df_comp.columns:
                # Map to nice_name if available
                carrier_map = df_comp['carrier']
                if hasattr(_n, 'carriers') and 'nice_name' in _n.carriers.columns:
                     nice_name_map = _n.carriers['nice_name'].dropna()
                     carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
                all_used_names.update(carrier_map.dropna().unique())

    # Add component types themselves (for cost breakdown etc.)
    all_used_names.update(_n.components.keys())

    # Assign fallback colors and specific storage charge/discharge colors
    for name in sorted(list(all_used_names)):
        if name not in all_keys:
            # Try matching to default keys first
            matched = False
            for default_key, default_color in DEFAULT_COLORS.items():
                 if default_key.lower() in str(name).lower():
                     final_colors[name] = default_color
                     all_keys.add(name)
                     matched = True
                     break
            # If still no match, use Plotly cycle
            if not matched:
                 final_colors[name] = PLOTLY_COLOR_CYCLE[color_idx % len(PLOTLY_COLOR_CYCLE)]
                 all_keys.add(name)
                 color_idx += 1

        # Assign specific charge/discharge colors based on the main carrier color
        is_storage = any(sub in str(name).lower() for sub in ['battery', 'phs', 'hydro', 'h2', 'storage', 'store'])
        if is_storage:
            base_color = final_colors[name]
            if f"{name} Charge" not in all_keys: final_colors[f"{name} Charge"] = base_color
            if f"{name} Discharge" not in all_keys: final_colors[f"{name} Discharge"] = base_color
            all_keys.update([f"{name} Charge", f"{name} Discharge"])

    # Ensure essential default keys have colors
    for key, color in DEFAULT_COLORS.items():
        if key not in all_keys:
            final_colors[key] = color

    logging.info(f"Generated color palette with {len(final_colors)} entries.")
    return final_colors

# --- 6. Data Extraction Functions ---
def get_dispatch_data(_n: pypsa.Network, _snapshots_slice: Optional[Union[pd.DatetimeIndex, pd.MultiIndex]] = None, 
                     resolution: str = "1H") -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.DataFrame]:
    """#
    Extracts dispatch data for generators, load, storage units, and stores.
    Uses _snapshots_slice argument with leading underscore to avoid hashing issues.
    Supports time resolution aggregation.
    #"""
    snapshots = safe_get_snapshots(_n)
    if _snapshots_slice is not None:
        # Ensure the slice is valid within the network's snapshots
        snapshots = snapshots[snapshots.isin(_snapshots_slice)]

    if snapshots.empty:
        logging.warning("get_dispatch_data called with empty or invalid snapshots slice.")
        return pd.DataFrame(), pd.Series(dtype=float), pd.DataFrame(), pd.DataFrame()

    logging.info(f"Extracting dispatch data for {len(snapshots)} snapshots.")

    # Convert snapshots to datetime index for resampling
    time_index = get_time_index(snapshots)
    
    # Helper to get carrier map (nice_name preferred)
    def get_carrier_map(comp_df, carriers_df):
        if 'carrier' not in comp_df.columns: return None
        carrier_map = comp_df['carrier']
        # Handle empty carriers_df
        if carriers_df is None or carriers_df.empty:
            carriers_df = pd.DataFrame(index=carrier_map.unique())
        
        # Add nice_name column if missing
        if 'nice_name' not in carriers_df.columns:
            carriers_df['nice_name'] = carriers_df.index
      
        # Check if carriers_df is a DataFrame and has 'nice_name'
        if isinstance(carriers_df, pd.DataFrame) and 'nice_name' in carriers_df.columns:
            nice_name_map = carriers_df['nice_name'].dropna()
            carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
        return carrier_map

    carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
    if not hasattr(carriers_df, 'nice_name'):
        carriers_df['nice_name'] = carriers_df.index
    
    gen_dispatch = pd.DataFrame(index=snapshots)
    load_dispatch = pd.Series(index=snapshots, dtype=float)
    storage_dispatch = pd.DataFrame(index=snapshots)
    store_dispatch = pd.DataFrame(index=snapshots)

    # Get generation
    if 'generators' in _n.components.keys() and hasattr(_n, 'generators_t') and 'p' in _n.generators_t:
        df_static = _n.generators
        df_t = _n.generators_t["p"]

        if not df_t.empty and not df_static.empty:
            carrier_map = get_carrier_map(df_static, carriers_df)
            if carrier_map is not None:
                valid_gens = df_static.index[carrier_map.notna()]
                cols_to_group = df_t.columns.intersection(valid_gens)
                if not cols_to_group.empty:
                    valid_snapshots_idx = snapshots[snapshots.isin(df_t.index)]
                    if not valid_snapshots_idx.empty:
                        # Group by the carrier map, ensuring index alignment
                        gen_dispatch = df_t.loc[valid_snapshots_idx, cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()

    # Get load
    if 'loads' in _n.components.keys() and hasattr(_n, 'loads_t'):
        load_col = 'p_set' if 'p_set' in _n.loads_t else 'p' if 'p' in _n.loads_t else None
        if load_col and not _n.loads_t[load_col].empty:
            valid_snapshots_idx = snapshots[snapshots.isin(_n.loads_t[load_col].index)]
            if not valid_snapshots_idx.empty:
                 load_dispatch = _n.loads_t[load_col].loc[valid_snapshots_idx].sum(axis=1)

    # Get storage units
    if 'storage_units' in _n.components.keys() and hasattr(_n, 'storage_units_t') and 'p' in _n.storage_units_t:
        df_static = _n.storage_units
        df_t = _n.storage_units_t["p"]
        if not df_t.empty and not df_static.empty:
            carrier_map = get_carrier_map(df_static, carriers_df) if 'carrier' in df_static.columns else pd.Series('Storage Unit', index=df_static.index)
            valid_comps = df_static.index[carrier_map.notna()]
            cols_to_group = df_t.columns.intersection(valid_comps)
            if not cols_to_group.empty:
                valid_snapshots_idx = snapshots[snapshots.isin(df_t.index)]
                if not valid_snapshots_idx.empty:
                    # Group by the carrier map, ensuring index alignment
                    grouped_p = df_t.loc[valid_snapshots_idx, cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
                    for carrier in grouped_p.columns:
                        storage_dispatch[f"{carrier} Discharge"] = grouped_p[carrier].clip(lower=0)
                        storage_dispatch[f"{carrier} Charge"] = grouped_p[carrier].clip(upper=0)

    # Get stores
    if 'stores' in _n.components.keys() and hasattr(_n, 'stores_t') and 'p' in _n.stores_t:
        df_static = _n.stores
        df_t = _n.stores_t['p']
        if not df_t.empty and not df_static.empty:
            carrier_map = get_carrier_map(df_static, carriers_df) if 'carrier' in df_static.columns else pd.Series('Store', index=df_static.index)
            valid_comps = df_static.index[carrier_map.notna()]
            cols_to_group = df_t.columns.intersection(valid_comps)
            if not cols_to_group.empty:
                valid_snapshots_idx = snapshots[snapshots.isin(df_t.index)]
                if not valid_snapshots_idx.empty:
                    # Group by the carrier map, ensuring index alignment
                    grouped_p = df_t.loc[valid_snapshots_idx, cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
                    for carrier in grouped_p.columns:
                        store_dispatch[f"{carrier} Discharge"] = grouped_p[carrier].clip(lower=0)
                        store_dispatch[f"{carrier} Charge"] = grouped_p[carrier].clip(upper=0)

    # Reindex and fill NaNs introduced by slicing/filtering
    gen_dispatch = gen_dispatch.reindex(snapshots).fillna(0)
    load_dispatch = load_dispatch.reindex(snapshots).fillna(0)
    storage_dispatch = storage_dispatch.reindex(snapshots).fillna(0)
    store_dispatch = store_dispatch.reindex(snapshots).fillna(0)

    # Clean up columns with all zeros
    gen_dispatch = gen_dispatch.loc[:, (gen_dispatch != 0).any(axis=0)]
    storage_dispatch = storage_dispatch.loc[:, (storage_dispatch != 0).any(axis=0)]
    store_dispatch = store_dispatch.loc[:, (store_dispatch != 0).any(axis=0)]
    
    # Apply time resolution aggregation if needed
    if resolution != "1H":
        # Convert index to DatetimeIndex if not already
        if not isinstance(time_index, pd.DatetimeIndex):
            logging.warning(f"Cannot resample data to {resolution}. Index is not a DatetimeIndex.")
        else:
            # Create a DataFrame with all data for resampling
            all_data = pd.concat([gen_dispatch, load_dispatch.rename('Load'), 
                                  storage_dispatch, store_dispatch], axis=1)
            
            # Set the DatetimeIndex
            all_data.index = time_index
            
            # Resample data
            resampled_data = all_data.resample(resolution).mean()
            
            # Extract back the components
            gen_dispatch = resampled_data.loc[:, gen_dispatch.columns]
            if 'Load' in resampled_data.columns:
                load_dispatch = resampled_data['Load']
            storage_cols = [col for col in resampled_data.columns if col in storage_dispatch.columns]
            storage_dispatch = resampled_data.loc[:, storage_cols] if storage_cols else pd.DataFrame()
            store_cols = [col for col in resampled_data.columns if col in store_dispatch.columns]
            store_dispatch = resampled_data.loc[:, store_cols] if store_cols else pd.DataFrame()
    
    return gen_dispatch, load_dispatch, storage_dispatch, store_dispatch

def get_carrier_capacity(_n: pypsa.Network, attribute: str = "p_nom_opt", period=None) -> pd.DataFrame:
    #Gets aggregated capacity by carrier, filtering for active assets in a period if specified.#
    logging.info(f"Calculating capacity for attribute '{attribute}'" + (f" for period '{period}'" if period else ""))
    capacity_list = []
    is_multi_period = isinstance(safe_get_snapshots(_n), pd.MultiIndex)
    carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
    
    if not hasattr(carriers_df, 'nice_name'):
        carriers_df['nice_name'] = carriers_df.index

    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}

    for comp_cls, comp_attr in components_to_check.items():
        if comp_attr in _n.components.keys():
            df_comp = getattr(_n, comp_attr)
            if not df_comp.empty and 'carrier' in df_comp.columns:
                # Determine the appropriate attribute based on component type
                if comp_cls == 'Store':
                    attr_to_use = attribute if attribute in ['e_nom', 'e_nom_opt'] else 'e_nom_opt'
                else:
                    attr_to_use = attribute if attribute in ['p_nom', 'p_nom_opt'] else 'p_nom_opt'

                if attr_to_use not in df_comp.columns:
                    logging.warning(f"Attribute '{attr_to_use}' not found in component '{comp_cls}'. Skipping.")
                    continue

                active_assets_idx = df_comp.index
                # Filter for active assets only if multi-period and period is specified
                if is_multi_period and period is not None:
                    try:
                        if hasattr(_n, 'get_active_assets'):
                            active_assets_idx = _n.get_active_assets(comp_cls, period)
                        elif 'build_year' in df_comp.columns and 'lifetime' in df_comp.columns:
                            active_assets_idx = df_comp.index[
                                (df_comp['build_year'] <= period) &
                                (df_comp['build_year'] + df_comp['lifetime'] > period)
                            ]
                    except Exception as e:
                        logging.warning(f"Could not filter active assets for {comp_cls} in period {period}: {e}. Using all.")

                df_active = df_comp.loc[active_assets_idx]

                if not df_active.empty:
                    # Map carriers to nice_names
                    carrier_map = df_active['carrier']
                    if carriers_df is None or carriers_df.empty:
                        carriers_df = pd.DataFrame(index=carrier_map.unique())
                    
                    if 'nice_name' not in carriers_df.columns:
                        carriers_df['nice_name'] = carriers_df.index
                        
                    if 'nice_name' in carriers_df.columns:
                        nice_name_map = carriers_df['nice_name'].dropna()
                        carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)

                    comp_capacity = df_active.groupby(carrier_map)[attr_to_use].sum()
                    capacity_list.append(comp_capacity)

    if capacity_list:
        combined_capacity = pd.concat(capacity_list).groupby(level=0).sum()  # Sum across component types
        result_df = combined_capacity.reset_index()
        result_df.columns = ['Carrier', 'Capacity']
        result_df = result_df[result_df['Capacity'] > 1e-6]
        return result_df.set_index('Carrier')
    else:
        return pd.DataFrame(columns=['Capacity'])


def get_carrier_capacity_new_addition(_n: pypsa.Network, method='optimization_diff', period=None) -> pd.DataFrame:
    """
    Gets new capacity additions by carrier, using either:
    1. Difference between optimized and nominal capacity (method='optimization_diff')
    2. Filtering by build_year (method='build_year')
    
    Parameters:
    -----------
    _n : pypsa.Network
        PyPSA network object
    method : str
        Method to calculate new additions:
        - 'optimization_diff': p_nom_opt - p_nom (or e_nom_opt - e_nom for stores)
        - 'build_year': Group by build_year
    period : int, optional
        Period to analyze for multi-period networks
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with new capacity additions by carrier
    """
    logging.info(f"Calculating new capacity additions using method '{method}'" + 
                 (f" for period '{period}'" if period else ""))
    
    capacity_list = []
    is_multi_period = isinstance(safe_get_snapshots(_n), pd.MultiIndex)
    carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
    
    if not hasattr(carriers_df, 'nice_name'):
        carriers_df['nice_name'] = carriers_df.index
    
    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}
    
    for comp_cls, comp_attr in components_to_check.items():
        if comp_attr in _n.components.keys():
            df_comp = getattr(_n, comp_attr)
            
            if not df_comp.empty and 'carrier' in df_comp.columns:
                # Skip if required columns are missing
                if method == 'optimization_diff':
                    if comp_cls == 'Store':
                        if 'e_nom_opt' not in df_comp.columns or 'e_nom' not in df_comp.columns:
                            logging.warning(f"'e_nom_opt' or 'e_nom' not found in {comp_cls}. Skipping.")
                            continue
                    else:  # Generator or StorageUnit
                        if 'p_nom_opt' not in df_comp.columns or 'p_nom' not in df_comp.columns:
                            logging.warning(f"'p_nom_opt' or 'p_nom' not found in {comp_cls}. Skipping.")
                            continue
                elif method == 'build_year':
                    if 'build_year' not in df_comp.columns:
                        logging.warning(f"'build_year' not found in {comp_cls}. Skipping.")
                        continue
                
                active_assets_idx = df_comp.index
                # Filter for active assets if multi-period and period specified
                if is_multi_period and period is not None:
                    try:
                        if hasattr(_n, 'get_active_assets'):
                            active_assets_idx = _n.get_active_assets(comp_cls, period)
                        elif 'build_year' in df_comp.columns and 'lifetime' in df_comp.columns:
                            active_assets_idx = df_comp.index[
                                (df_comp['build_year'] <= period) &
                                (df_comp['build_year'] + df_comp['lifetime'] > period)
                            ]
                    except Exception as e:
                        logging.warning(f"Could not filter active assets for {comp_cls} in period {period}: {e}. Using all.")
                
                df_active = df_comp.loc[active_assets_idx]
                
                if not df_active.empty:
                    # Map carriers to nice_names
                    carrier_map = df_active['carrier']
                    if 'nice_name' in carriers_df.columns:
                        nice_name_map = carriers_df['nice_name'].dropna()
                        carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
                    
                    # Calculate new additions based on selected method
                    if method == 'optimization_diff':
                        # Calculate difference between optimized and nominal capacity
                        if comp_cls == 'Store':
                            df_active['new_capacity'] = df_active['e_nom_opt'] - df_active['e_nom']
                        else:  # Generator or StorageUnit
                            df_active['new_capacity'] = df_active['p_nom_opt'] - df_active['p_nom']
                        
                        # Filter for positive additions only
                        df_active = df_active[df_active['new_capacity'] > 1e-6]
                        
                        if not df_active.empty:
                            comp_capacity = df_active.groupby(carrier_map)['new_capacity'].sum()
                            capacity_list.append(comp_capacity)
                    
                    elif method == 'build_year':
                        # For build_year method, only include assets built in the specified period
                        if period is not None:
                            df_built_this_year = df_active[df_active['build_year'] == period]
                            
                            if not df_built_this_year.empty:
                                # Use the appropriate capacity attribute based on component type
                                if comp_cls == 'Store':
                                    capacity_attr = 'e_nom_opt' if 'e_nom_opt' in df_built_this_year.columns else 'e_nom'
                                else:  # Generator or StorageUnit
                                    capacity_attr = 'p_nom_opt' if 'p_nom_opt' in df_built_this_year.columns else 'p_nom'
                                
                                carrier_map_year = df_built_this_year['carrier']
                                if 'nice_name' in carriers_df.columns:
                                    nice_name_map = carriers_df['nice_name'].dropna()
                                    carrier_map_year = carrier_map_year.map(nice_name_map).fillna(carrier_map_year)
                                
                                comp_capacity = df_built_this_year.groupby(carrier_map_year)[capacity_attr].sum()
                                capacity_list.append(comp_capacity)
    
    if capacity_list:
        combined_capacity = pd.concat(capacity_list).groupby(level=0).sum()
        result_df = combined_capacity.reset_index()
        result_df.columns = ['Carrier', 'New_Capacity']
        result_df = result_df[result_df['New_Capacity'] > 1e-6]
        return result_df.set_index('Carrier')
    else:
        return pd.DataFrame(columns=['New_Capacity'])


def plot_new_capacity_additions(networks_dict,combined_colors, method='optimization_diff', label_name='Scenario'):
    """
    Plots new capacity additions for multiple networks or periods.
    
    Parameters:
    -----------
    networks_dict : dict
        Dictionary of PyPSA networks to compare
    method : str
        Method to calculate new additions ('optimization_diff' or 'build_year')
    label_name : str
        Label for the x-axis in the plot
    """
    with st.spinner(f"Calculating new capacity additions..."):
        # Get capacity addition data for each network/period
        additions_data = {}
        for key, network in networks_dict.items():
            try:
                add_df = get_carrier_capacity_new_addition(network, method=method, period=key if method == 'build_year' else None)
                
                # Filter out Market if present
                if add_df is not None and not add_df.empty and 'Market' in add_df.index:
                    add_df = add_df[add_df.index != 'Market']
                    
                if not add_df.empty:
                    additions_data[key] = add_df
            except Exception as e:
                logging.error(f"Error getting new capacity additions for {label_name} {key}: {e}", exc_info=True)
        
        if not additions_data:
            st.info(f"No new capacity addition data available.")
        else:
            # Create DataFrame for plotting
            plot_data = []
            for key, df in additions_data.items():
                for carrier, row in df.iterrows():
                    plot_data.append({
                        label_name: key,
                        'Carrier': carrier,
                        'New_Capacity': row['New_Capacity']
                    })
                    
            plot_df = pd.DataFrame(plot_data)
            
            # Determine unit based on method and components
            unit = 'MW/MWh' 
          
            # Create capacity additions comparison plot
            fig_add = px.bar(
                plot_df,
                x=label_name,
                y='New_Capacity',
                color='Carrier',
                title=f"New Capacity Additions ({unit}) by {label_name}",
                labels={'New_Capacity': f'New Capacity ({unit})'},
                color_discrete_map=combined_colors
            )
            st.plotly_chart(fig_add, use_container_width=True)
            
            # Show the raw data
            with st.expander("View Raw New Capacity Addition Data"):
                for key, df in additions_data.items():
                    st.subheader(f"{label_name}: {key}")
                    st.dataframe(df)



def get_buses_capacity(_n: pypsa.Network, attribute: str = "p_nom_opt", period=None) -> pd.DataFrame:
    #Gets aggregated capacity by bus/region, filtering for active assets in a period if specified.#
    logging.info(f"Calculating capacity by region for attribute '{attribute}'" + (f" for period '{period}'" if period else ""))
    capacity_list = []
    is_multi_period = isinstance(safe_get_snapshots(_n), pd.MultiIndex)

    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}

    for comp_cls, comp_attr in components_to_check.items():
        if comp_attr in _n.components.keys():
            df_comp = getattr(_n, comp_attr)
            if not df_comp.empty and 'bus' in df_comp.columns:
                # Determine the appropriate attribute based on component type
                if comp_cls == 'Store':
                    attr_to_use = attribute if attribute in ['e_nom', 'e_nom_opt'] else 'e_nom_opt'
                else:
                    attr_to_use = attribute if attribute in ['p_nom', 'p_nom_opt'] else 'p_nom_opt'

                if attr_to_use not in df_comp.columns:
                    logging.warning(f"Attribute '{attr_to_use}' not found in component '{comp_cls}'. Skipping.")
                    continue

                active_assets_idx = df_comp.index
                # Filter for active assets only if multi-period and period is specified
                if is_multi_period and period is not None:
                    try:
                        if hasattr(_n, 'get_active_assets'):
                            active_assets_idx = _n.get_active_assets(comp_cls, period)
                        elif 'build_year' in df_comp.columns and 'lifetime' in df_comp.columns:
                            active_assets_idx = df_comp.index[
                                (df_comp['build_year'] <= period) &
                                (df_comp['build_year'] + df_comp['lifetime'] > period)
                            ]
                    except Exception as e:
                        logging.warning(f"Could not filter active assets for {comp_cls} in period {period}: {e}. Using all.")

                df_active = df_comp.loc[active_assets_idx]
                if not df_active.empty:
                    # Group by bus
                    comp_capacity = df_active.groupby(df_active['bus'])[attr_to_use].sum()
                    capacity_list.append(comp_capacity)

    if capacity_list:
        combined_capacity = pd.concat(capacity_list).groupby(level=0).sum()  # Sum across component types
        result_df = combined_capacity.reset_index()
        result_df.columns = ['Region', 'Capacity']
        result_df = result_df[result_df['Capacity'] > 1e-6]
        return result_df.set_index('Region')
    else:
        return pd.DataFrame(columns=['Capacity'])

def get_total_generation_by_period(_n: pypsa.Network) -> pd.DataFrame:
    #Calculates total energy generation per carrier per period.#
    logging.info("Calculating total generation by period...")
    if 'generators' not in _n.components.keys() or not hasattr(_n, 'generators_t') or 'p' not in _n.generators_t:
        return pd.DataFrame()

    gen_p = _n.generators_t['p']
    df_static = _n.generators
    carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
    
    if not hasattr(carriers_df, 'nice_name'):
        carriers_df['nice_name'] = carriers_df.index
        
    if gen_p.empty or df_static.empty or 'carrier' not in df_static.columns:
        return pd.DataFrame()

    # Map carriers (nice_name preferred)
    carrier_map = df_static['carrier']
    nice_name_map = carriers_df['nice_name'].dropna()
    carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
    
    valid_gens = df_static.index[carrier_map.notna()]
    cols_to_group = gen_p.columns.intersection(valid_gens)

    if not cols_to_group.empty:
        # Helper for period aggregation
        def get_period_aggregates(data_t: pd.DataFrame) -> pd.DataFrame:
            #Aggregates time-series data by period using snapshot weightings.#
            snapshots = safe_get_snapshots(_n)
            periods = get_period_index(snapshots)
            if periods is None: return pd.DataFrame()  # Cannot aggregate without periods

            weights = get_snapshot_weights(_n, snapshots)

            # Ensure data_t index matches weights index before multiplying
            data_aligned, weights_aligned = data_t.align(weights, axis=0, join='inner')
            if data_aligned.empty: return pd.DataFrame()  # No common index

            weighted_data = data_aligned.multiply(weights_aligned, axis=0)

            # Group by period level and sum
            period_agg = weighted_data.groupby(get_period_index(weighted_data.index)).sum()
            return period_agg
            
        gen_p_by_carrier = gen_p[cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
        period_generation = get_period_aggregates(gen_p_by_carrier)
        return period_generation  # Index=Period, Columns=Carrier, Values=Energy (e.g., MWh)
    else:
        return pd.DataFrame()

def calculate_cuf(_n: pypsa.Network) -> pd.DataFrame:
    #Calculate Capacity Utilization Factors (CUFs) by carrier.#
    logging.info("Calculating CUFs...")
    if 'generators' not in _n.components.keys() or _n.generators.empty or \
       not hasattr(_n, 'generators_t') or 'p' not in _n.generators_t or \
       not any(c in _n.generators.columns for c in ['p_nom_opt', 'p_nom']) or \
       'carrier' not in _n.generators.columns:
        logging.warning("Missing data for CUF calculation.")
        return pd.DataFrame(columns=['Carrier', 'CUF'])

    try:
        snapshots = safe_get_snapshots(_n)
        if snapshots.empty: return pd.DataFrame(columns=['Carrier', 'CUF'])

        gen_p = _n.generators_t['p'].loc[snapshots]
        p_nom_attr = 'p_nom_opt' if 'p_nom_opt' in _n.generators.columns else 'p_nom'
        gen_p_nom = _n.generators[p_nom_attr]

        weights = get_snapshot_weights(_n, snapshots)
        energy_produced = gen_p.multiply(weights, axis=0).sum()
        total_weight = weights.sum()
       
        potential_energy = gen_p_nom * total_weight
        
        cuf_per_generator = (energy_produced / potential_energy).replace([np.inf, -np.inf], np.nan).fillna(0)
        cuf_per_generator = cuf_per_generator[cuf_per_generator > 0]
 
        carrier_map = _n.generators['carrier']
        carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
        
        if not hasattr(carriers_df, 'nice_name'):
            carriers_df['nice_name'] = carriers_df.index
            
        if carriers_df is not None and not carriers_df.empty and 'nice_name' in carriers_df.columns:
            nice_name_map = carriers_df['nice_name'].dropna()
            carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
          
        cuf_by_carrier = cuf_per_generator.groupby(carrier_map).mean()

        cuf_df = cuf_by_carrier.reset_index()
        cuf_df.columns = ['Carrier', 'CUF']
        return cuf_df[cuf_df['CUF'].notna() & (cuf_df['CUF'] > 1e-6)]  # Filter negligible CUFs

    except Exception as e:
        logging.error(f"Error calculating CUFs: {e}", exc_info=True)
        return pd.DataFrame(columns=['Carrier', 'CUF'])

def calculate_curtailment(_n: pypsa.Network) -> pd.DataFrame:
    #Calculate renewable curtailment by carrier.#
    logging.info("Calculating curtailment...")
    req_cols = ['p', 'p_max_pu']
    if 'generators' not in _n.components.keys() or _n.generators.empty or \
       not hasattr(_n, 'generators_t') or not all(c in _n.generators_t for c in req_cols) or \
       'carrier' not in _n.generators.columns or \
       not any(c in _n.generators.columns for c in ['p_nom_opt', 'p_nom']):
        logging.warning("Missing data for curtailment calculation.")
        return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

    try:
        snapshots = safe_get_snapshots(_n)
        if snapshots.empty: return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

        renewable_keywords = ['solar', 'wind']  #, 'ror', 'geothermal'
        renewable_carriers = [c for c in _n.generators['carrier'].dropna().unique() if any(k in c.lower() for k in renewable_keywords)]

        renewable_gens = _n.generators[_n.generators['carrier'].isin(renewable_carriers)]
      
        if renewable_gens.empty: return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

        p_nom_attr = 'p_nom_opt' if 'p_nom_opt' in renewable_gens.columns else 'p_nom'
        p_nom = renewable_gens[p_nom_attr]

        # Align indices before calculations
        valid_snapshots = snapshots[snapshots.isin(_n.generators_t['p'].index) & snapshots.isin(_n.generators_t['p_max_pu'].index)]
        if valid_snapshots.empty: return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

        p_actual = _n.generators_t['p'].loc[valid_snapshots, renewable_gens.index]
        p_max_pu = _n.generators_t['p_max_pu'].loc[valid_snapshots, renewable_gens.index]
        weights = get_snapshot_weights(_n, valid_snapshots)
        weights=weights.mean()
  
        p_potential = p_max_pu.multiply(p_nom.reindex(p_max_pu.columns), axis=1)  # Ensure p_nom aligns
        curtailment_power = (p_potential - p_actual).clip(lower=0)
        
        curtailment_energy = (curtailment_power * weights).sum()
        potential_energy = (p_potential * weights).sum()

        carrier_map = renewable_gens['carrier']
        carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
        carriers_df['nice_name'] = carriers_df.index
        if not hasattr(carriers_df, 'nice_name'):
            carriers_df['nice_name'] = carriers_df.index
            
        if carriers_df is not None and not carriers_df.empty and 'nice_name' in carriers_df.columns:
            nice_name_map = carriers_df['nice_name'].dropna()
            carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
   
        curtailment_by_carrier = curtailment_energy.groupby(carrier_map).sum()
        potential_by_carrier = potential_energy.groupby(carrier_map).sum()
       
        curtailment_df = pd.DataFrame({
            'Carrier': curtailment_by_carrier.index,
            'Curtailment (MWh)': curtailment_by_carrier.values,
            'Potential (MWh)': potential_by_carrier.reindex(curtailment_by_carrier.index).fillna(0).values
        })
        curtailment_df['Curtailment (%)'] = (curtailment_df['Curtailment (MWh)'] / curtailment_df['Potential (MWh)'] * 100).fillna(0)
        return curtailment_df[curtailment_df['Potential (MWh)'] > 1e-3]

    except Exception as e:
        logging.error(f"Error calculating curtailment: {e}", exc_info=True)
        return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

def get_storage_soc(_n: pypsa.Network) -> pd.DataFrame:
    #Extracts State of Charge (SoC) data for StorageUnit and Store.#
    logging.info("Extracting Storage SoC...")
    soc_data_list = []
    snapshots = safe_get_snapshots(_n)
    if snapshots.empty: return pd.DataFrame()
    carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
    
    if not hasattr(carriers_df, 'nice_name'):
        carriers_df['nice_name'] = carriers_df.index

    def process_soc(comp_cls, comp_attr, soc_attr):
        if comp_cls in _n.components.keys() and hasattr(_n, f"{comp_attr}_t") and soc_attr in getattr(_n, f"{comp_attr}_t"):
            df_soc_raw = getattr(_n, f"{comp_attr}_t")[soc_attr]
            df_static = getattr(_n, comp_attr)
            df_static = df_static.copy()
            # Align snapshots
            valid_snapshots = snapshots[snapshots.isin(df_soc_raw.index)]
            if valid_snapshots.empty: return
            df_soc = df_soc_raw.loc[valid_snapshots]
            
            if 'carrier' in df_static.columns:
                df_static['carrier'] = df_static['carrier'].fillna(df_static['bus'])
            else:
                df_static['carrier'] = df_static['bus']
            
            if not df_soc.empty and not df_static.empty:
                carrier_map = df_static['carrier'] if 'carrier' in df_static.columns else pd.Series(comp_cls, index=df_static.index)
                if carriers_df is not None and not carriers_df.empty:
                    if 'nice_name' not in carriers_df.columns:
                        carriers_df['nice_name'] = carriers_df.index
                    nice_name_map = carriers_df['nice_name'].dropna()
                    carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
                carrier_map = carrier_map.apply(lambda x: f"{x} ({comp_cls})" if isinstance(x, str) else comp_cls)
                
                valid_comps = df_static.index[carrier_map.notna()]
                cols_to_group = df_soc.columns.intersection(valid_comps)
                
                if not cols_to_group.empty:
                     grouped_soc = df_soc[cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
                     soc_data_list.append(grouped_soc)
    
    process_soc('storage_units', 'storage_units', 'state_of_charge')
    process_soc('stores', 'stores', 'e')

    if not soc_data_list: return pd.DataFrame()
    # Use outer join and reindex to ensure all snapshots are present
    combined_soc = pd.concat(soc_data_list, axis=1, join='outer').reindex(snapshots).fillna(0)
    return combined_soc.loc[:, (combined_soc != 0).any(axis=0)]

def calculate_co2_emissions(_n: pypsa.Network) -> Tuple[pd.DataFrame, pd.DataFrame]:
    #Calculate total CO2 emissions and emissions by carrier per period.#
    logging.info("Calculating CO2 emissions...")
    total_emissions_df = pd.DataFrame(columns=['Period', 'Total CO2 Emissions (Tonnes)'])
    emissions_by_carrier_df = pd.DataFrame(columns=['Period', 'Carrier', 'Emissions (Tonnes)'])

    if 'generators' not in _n.components.keys() or _n.generators.empty or \
       not hasattr(_n, 'generators_t') or 'p' not in _n.generators_t or \
       not hasattr(_n, 'carriers') or 'co2_emissions' not in _n.carriers.columns:
        logging.warning("Missing data for CO2 emissions calculation.")
        return total_emissions_df, emissions_by_carrier_df

    try:
        snapshots = safe_get_snapshots(_n)
        if snapshots.empty: return total_emissions_df, emissions_by_carrier_df

        co2_factors = _n.carriers['co2_emissions'].dropna()
        if co2_factors.empty: return total_emissions_df, emissions_by_carrier_df

        emitting_gens = _n.generators[_n.generators['carrier'].isin(co2_factors.index)]
        if emitting_gens.empty: return total_emissions_df, emissions_by_carrier_df

        # Align indices
        valid_snapshots = snapshots[snapshots.isin(_n.generators_t.p.index)]
        if valid_snapshots.empty: return total_emissions_df, emissions_by_carrier_df

        gen_p = _n.generators_t.p.loc[valid_snapshots, emitting_gens.index]
        weights = get_snapshot_weights(_n, valid_snapshots)

        carrier_map = emitting_gens['carrier']
        co2_map = carrier_map.map(co2_factors)
        emissions_t = gen_p.multiply(co2_map, axis=1).multiply(weights, axis=0)  # Tonnes

        periods = get_period_index(valid_snapshots)
        period_total_emissions = emissions_t.sum(axis=1).groupby(periods).sum()

        carrier_display_map = carrier_map
        carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
        
        if not hasattr(carriers_df, 'nice_name'):
            carriers_df['nice_name'] = carriers_df.index
            
        if carriers_df is not None and not carriers_df.empty and 'nice_name' in carriers_df.columns:
            nice_name_map = carriers_df['nice_name'].dropna()
            carrier_display_map = carrier_display_map.map(nice_name_map).fillna(carrier_display_map)
            
        emissions_by_carrier_t = emissions_t.groupby(carrier_display_map, axis=1).sum()  # Group by display name
        period_emissions_by_carrier = emissions_by_carrier_t.groupby(periods).sum()

        if not period_total_emissions.empty:
            total_emissions_df = period_total_emissions.reset_index()
            total_emissions_df.columns = ['Period', 'Total CO2 Emissions (Tonnes)']

        if not period_emissions_by_carrier.empty:
            period_emissions_by_carrier.index.name = 'Period'
            emissions_by_carrier_df = period_emissions_by_carrier.reset_index().melt(
                id_vars='Period', var_name='Carrier', value_name='Emissions (Tonnes)'
            )
            emissions_by_carrier_df = emissions_by_carrier_df[emissions_by_carrier_df['Emissions (Tonnes)'] > 1e-3]

        return total_emissions_df, emissions_by_carrier_df

    except Exception as e:
        logging.error(f"Error calculating CO2 emissions: {e}", exc_info=True)
        return total_emissions_df, emissions_by_carrier_df

def calculate_marginal_prices(_n: pypsa.Network, resolution: str = "1H") -> pd.DataFrame:
    #Extract and process marginal prices from the network.#
    logging.info("Extracting marginal prices...")
    
    if not hasattr(_n, "buses_t") or 'marginal_price' not in _n.buses_t:
        logging.warning("No marginal price data found.")
        return pd.DataFrame()
    
    price_data = _n.buses_t['marginal_price']
    if price_data.empty:
        return pd.DataFrame()
    
    # Get time index for resampling if needed
    time_index = get_time_index(price_data.index)
    
    # Resample if needed
    if resolution != "1H" and isinstance(time_index, pd.DatetimeIndex):
        price_data = resample_data(price_data, time_index, resolution)
    
    return price_data

def calculate_network_losses(_n: pypsa.Network) -> pd.DataFrame:
    #Calculates total network losses per period.#
    logging.info("Calculating network losses...")
    losses_list = []
    snapshots = safe_get_snapshots(_n)
    periods = get_period_index(snapshots)
    if periods is None: return pd.DataFrame()
    weights = get_snapshot_weights(_n, snapshots)

    # Line losses
    if 'lines' in _n.components.keys() and hasattr(_n, 'lines_t') and 'p0' in _n.lines_t and 'p1' in _n.lines_t:
        valid_snapshots = snapshots[snapshots.isin(_n.lines_t.p0.index)]
        if not valid_snapshots.empty:
             p0 = _n.lines_t.p0.loc[valid_snapshots]
             p1 = _n.lines_t.p1.loc[valid_snapshots]
             line_losses_t = (p0 + p1).sum(axis=1) # Sum losses across all lines per snapshot
             losses_list.append(line_losses_t)

    # Link losses (simplified: p0+p1)
    if 'links' in _n.components.keys() and hasattr(_n, 'links_t') and 'p0' in _n.links_t and 'p1' in _n.links_t:
         valid_snapshots = snapshots[snapshots.isin(_n.links_t.p0.index)]
         if not valid_snapshots.empty:
             p0_link = _n.links_t.p0.loc[valid_snapshots]
             p1_link = _n.links_t.p1.loc[valid_snapshots]
             link_losses_t = (p0_link + p1_link).sum(axis=1)
             losses_list.append(link_losses_t)

    if not losses_list: return pd.DataFrame()

    total_losses_t = pd.concat(losses_list, axis=1).sum(axis=1)
    weighted_losses = total_losses_t * weights.reindex(total_losses_t.index) # Align weights
    period_losses = weighted_losses.groupby(get_period_index(weighted_losses.index)).sum()
    period_losses_df = period_losses.reset_index()
    period_losses_df.columns = ['Period', 'Losses (MWh)']
    return period_losses_df

# --- 7. Plotting Functions ---
def plot_dispatch_stack(gen_dispatch, load_dispatch, storage_dispatch, store_dispatch, carrier_colors, 
                        title="Power Dispatch and Load", plot_index=None, resolution="1H"):
    #Generates the interactive dispatch stack plot.#
    fig = go.Figure()
    all_storage = pd.concat([storage_dispatch, store_dispatch], axis=1).fillna(0)
    if plot_index is None:  # Infer from data if not provided
        if not gen_dispatch.empty: plot_index = gen_dispatch.index
        elif not load_dispatch.empty: plot_index = load_dispatch.index
        elif not all_storage.empty: plot_index = all_storage.index
        else: return fig  # Cannot plot if no index

    plot_time_index = get_time_index(plot_index)  # Ensure we use datetime for x-axis

    # 1. Generation - Ensure we have a color for each carrier
    for carrier in sorted(gen_dispatch.columns):
        # Default to carrier-specific color or a generic one if not found
        color = carrier_colors.get(carrier, None)
        if color is None:
            # Try case-insensitive matching
            carrier_lower = carrier.lower()
            matched = False
            for default_key, default_color in DEFAULT_COLORS.items():
                if default_key.lower() in carrier_lower:
                    color = default_color
                    matched = True
                    break
            if not matched:
                color = DEFAULT_COLORS.get('Other', '#D3D3D3')  # Fallback to Other or gray
        
        fig.add_trace(go.Scatter(
            x=plot_time_index, 
            y=gen_dispatch[carrier], 
            mode='lines', 
            name=carrier, 
            stackgroup='positive', 
            line=dict(width=0), 
            fill='tonexty', 
            fillcolor=color, 
            hovertemplate='%{x|%Y-%m-%d %H:%M}<br>' + f'{carrier}: %{{y:.1f}} MW<extra></extra>'
        ))
    
    # 2. Storage Discharge
    discharge_cols = sorted([c for c in all_storage.columns if 'Discharge' in c and all_storage[c].sum() > 1e-3])
    for col in discharge_cols:
        color = carrier_colors.get(col, DEFAULT_COLORS.get('Storage Discharge', '#FFA500'))
        fig.add_trace(go.Scatter(
            x=plot_time_index, 
            y=all_storage[col], 
            mode='lines', 
            name=col, 
            stackgroup='positive', 
            line=dict(width=0), 
            fill='tonexty', 
            fillcolor=color, 
            hovertemplate='%{x|%Y-%m-%d %H:%M}<br>' + f'{col}: %{{y:.1f}} MW<extra></extra>'
        ))
    
    # 3. Storage Charge
    charge_cols = sorted([c for c in all_storage.columns if 'Charge' in c and all_storage[c].sum() < -1e-3])
    for col in charge_cols:
        color = carrier_colors.get(col, DEFAULT_COLORS.get('Storage Charge', '#FFA500'))
        fig.add_trace(go.Scatter(
            x=plot_time_index, 
            y=all_storage[col], 
            mode='lines', 
            name=col, 
            stackgroup='negative', 
            line=dict(width=0), 
            fill='tonexty', 
            fillcolor=color, 
            hovertemplate='%{x|%Y-%m-%d %H:%M}<br>' + f'{col}: %{{y:.1f}} MW<extra></extra>'
        ))
    
    # 4. Load Line
    if not load_dispatch.isna().all() and load_dispatch.sum() > 0:
        fig.add_trace(go.Scatter(
            x=plot_time_index, 
            y=load_dispatch, 
            mode='lines', 
            name='Load', 
            line=dict(color=carrier_colors.get('Load', 'black'), width=2), 
            hovertemplate='%{x|%Y-%m-%d %H:%M}<br>Load: %{y:.1f} MW<extra></extra>'
        ))

    # Add resolution information to title
    resolution_info = f" ({resolution} resolution)" if resolution != "1H" else ""
    title_with_resolution = f"{title}{resolution_info}"

    fig.update_layout(
        title=title_with_resolution,
        xaxis_title="Time", 
        yaxis_title="Power (MW)", 
        hovermode='x unified', 
        legend_title="Component/Carrier", 
        height=600, 
        yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1)
    )
    return fig

def plot_area_stack(df, colors, title, y_axis_label):
    #Generates a stacked area plot from a DataFrame (index=time, columns=categories).#
    df_plot = df.loc[:, (df.abs() > 1e-3).any(axis=0)]  # Plot only non-negligible columns
    fig = px.area(df_plot, title=title, labels={'value': y_axis_label, 'variable': 'Carrier'}, color_discrete_map=colors)
    fig.update_layout(xaxis_title="Period", yaxis_title=y_axis_label, legend_title="Carrier")
    return fig

def plot_bar_stack(df, colors, title, y_axis_label, barmode='stack'):
    #Generates a stacked bar plot from a DataFrame (index=time, columns=categories).#
    df_plot = df.loc[:, (df.abs() > 1e-3).any(axis=0)]  # Plot only non-negligible columns
    fig = px.bar(df_plot, title=title, labels={'value': y_axis_label, 'variable': 'Carrier'}, color_discrete_map=colors, barmode=barmode)
    fig.update_layout(xaxis_title="Period", yaxis_title=y_axis_label, legend_title="Carrier")
    return fig

def create_daily_profile_plot(gen_dispatch, load_dispatch, storage_dispatch, store_dispatch, carrier_colors):
    #Creates a daily profile plot by averaging by hour of day.#
    all_data = pd.concat([gen_dispatch, storage_dispatch, store_dispatch], axis=1)
    all_data['Load'] = load_dispatch
    
    # Extract time index
    time_idx = get_time_index(all_data.index)
    if not isinstance(time_idx, pd.DatetimeIndex):
        return go.Figure()
    
    # Group by hour of day and calculate mean
    all_data.index = time_idx
    hourly_avg = all_data.groupby(time_idx.hour).mean()
    hourly_avg.index.name = 'Hour of Day'
    
    # Create plot
    df_melted = hourly_avg.reset_index().melt(
        id_vars='Hour of Day',
        var_name='Component/Carrier',
        value_name='Average Power (MW)'
    )
    
    df_melted = df_melted[df_melted['Average Power (MW)'].abs() > 1e-3]
    
    if not df_melted.empty:
        fig = px.line(df_melted, x='Hour of Day', y='Average Power (MW)', 
                     color='Component/Carrier', title='Average Daily Profile', 
                     color_discrete_map=carrier_colors)
        fig.update_layout(xaxis=dict(tickmode='linear', dtick=1), legend_title="Component/Carrier")
        return fig
    
    return go.Figure()
def create_daily_profile_plot_new(gen_dispatch, load_dispatch, storage_dispatch, store_dispatch, carrier_colors):
    """
    Creates a daily profile plot by averaging by hour of day,
    using an area stack for generation/storage and a line for load.
    Negative values in components will be shown as a separate stacked area below the x-axis.
    """
    # Concatenate all data except load initially for stacking
    components_to_stack = pd.concat([gen_dispatch, storage_dispatch, store_dispatch], axis=1)

    # Extract time index
    time_idx = get_time_index(components_to_stack.index)
    if not isinstance(time_idx, pd.DatetimeIndex):
        print("Error: Could not extract valid datetime index.")
        return go.Figure() # Return empty figure if time index is invalid

    # Group by hour of day and calculate mean for components to stack
    components_to_stack.index = time_idx
    hourly_avg_stack = components_to_stack.groupby(time_idx.hour).mean()
    hourly_avg_stack.index.name = 'Hour of Day'

    # Group by hour of day and calculate mean for load
    load_dispatch.index = time_idx
    hourly_avg_load = load_dispatch.groupby(time_idx.hour).mean()
    hourly_avg_load.index.name = 'Hour of Day'

    # Melt the stacked data for plotting
    df_melted = hourly_avg_stack.reset_index().melt(
        id_vars='Hour of Day',
        var_name='Component/Carrier',
        value_name='Average Power (MW)'
    )

    # Separate positive and negative values
    df_positive = df_melted[df_melted['Average Power (MW)'] >= -1e-3].copy() # Include near-zero with positive
    df_negative = df_melted[df_melted['Average Power (MW)'] < -1e-3].copy()

    # Create the area stack plot for positive components
    fig = go.Figure()

    if not df_positive.empty:
        # Use Plotly Graph Objects for more control over stacking and traces
        # Create area traces for positive values
        for carrier in df_positive['Component/Carrier'].unique():
            df_carrier = df_positive[df_positive['Component/Carrier'] == carrier]
            fig.add_trace(
                go.Scatter(
                    x=df_carrier['Hour of Day'],
                    y=df_carrier['Average Power (MW)'],
                    mode='lines',
                    line=dict(width=0), # Hide line
                    fill='tonexty', # Stack
                    name=carrier,
                    stackgroup='positive_components', # Group positive areas for stacking
                    legendgroup=carrier,
                    showlegend=True,
                    hoverinfo='x+y+name',
                    fillcolor=carrier_colors.get(carrier, '#cccccc') # Use color map
                )
            )

    # Add the area stack plot for negative components
    if not df_negative.empty:
         # Create area traces for negative values
        for carrier in df_negative['Component/Carrier'].unique():
            df_carrier = df_negative[df_negative['Component/Carrier'] == carrier]
            fig.add_trace(
                go.Scatter(
                    x=df_carrier['Hour of Day'],
                    y=df_carrier['Average Power (MW)'],
                    mode='lines',
                    line=dict(width=0), # Hide line
                    fill='tonexty', # Stack
                    name=f'{carrier} (Negative)', # Differentiate negative traces in legend
                    stackgroup='negative_components', # Group negative areas for stacking
                    legendgroup=carrier, # Keep same legend group if desired, or change
                    showlegend=True,
                    hoverinfo='x+y+name',
                    fillcolor=carrier_colors.get(carrier, '#cccccc') # Use color map
                )
            )


    # Add the load data as a line trace
    if not hourly_avg_load.empty:
        fig.add_trace(
            go.Scatter(
                x=hourly_avg_load.index,
                y=hourly_avg_load.values,
                mode='lines',
                name='Load', # Name for the legend
                line=dict(color='black', width=2), # Customize line appearance
                legendgroup='Load', # Group for legend
                showlegend=True, # Ensure it appears in the legend
                hoverinfo='x+y+name'
            )
        )

    # Update layout for better readability
    fig.update_layout(
        xaxis=dict(tickmode='linear', dtick=1), # Ensure hourly ticks
        yaxis_title='Average Power (MW)',
        title='Average Daily Profile (Generation/Storage Stacked, Load as Line)',
        legend_title="Component/Carrier",
        hovermode='x unified' # Improve hover experience
    )

    return fig





def create_duration_curve(data, title="Duration Curve", y_label="Power (MW)"):
    #Creates a duration curve for the provided data.#
    if data.isna().all() or data.empty:
        return go.Figure()
    
    sorted_data = data.sort_values(ascending=False)
    x_values = np.linspace(0, 100, len(sorted_data))
    
    fig = px.area(x=x_values, y=sorted_data.values, 
                 labels={'x': 'Duration (%)', 'y': y_label}, 
                 title=title)
    
    return fig

def plot_comparison(data_dict, x_label, y_label, title, plot_type='bar', color_map=None):
    #Creates a comparison plot between different periods/years.#
    if not data_dict or all(d.empty for d in data_dict.values()):
        return go.Figure()
    
    # Create a combined DataFrame with MultiIndex
    df_list = []
    for key, df in data_dict.items():
        df_temp = df.copy()
        df_temp[x_label] = key
        df_list.append(df_temp.reset_index())
    
    combined_df = pd.concat(df_list)
    
    if plot_type == 'bar':
        fig = px.bar(combined_df, x='Carrier', y='Capacity', color=x_label,
                    barmode='group', title=title, color_discrete_map=color_map)
        fig.update_layout(xaxis_title='Carrier', yaxis_title=y_label)
    
    elif plot_type == 'line':
        fig = px.line(combined_df, x='Carrier', y='CUF', color=x_label,
                     markers=True, title=title, color_discrete_map=color_map)
        fig.update_layout(xaxis_title='Carrier', yaxis_title=y_label)
    
    return fig

def plot_hourly_generation_heatmap(hourly_gen_data, carrier_colors, selected_carrier=None):
    """ #
        Create a heatmap visualization of hourly generation across periods.
        
        Parameters:
        -----------
        hourly_gen_data : pd.DataFrame
            DataFrame with MultiIndex (period, snapshot) and columns for each carrier
        carrier_colors : dict
            Dictionary mapping carriers to colors
        selected_carrier : str, optional
            If provided, only plot data for this carrier
        
        Returns:
        --------
        plotly.graph_objects.Figure
            Heatmap visualization
        #"""
    if hourly_gen_data.empty:
        return go.Figure()
    
    # If a carrier is selected, filter for just that carrier
    if selected_carrier is not None and selected_carrier in hourly_gen_data.columns:
        plot_data = hourly_gen_data[[selected_carrier]]
        title = f"Hourly {selected_carrier} Generation Across Periods"
        colorscale = [[0, 'white'], [1, carrier_colors.get(selected_carrier, 'blue')]]
    else:
        # If no carrier selected, use total generation
        plot_data = hourly_gen_data.sum(axis=1).to_frame('Total')
        title = "Total Hourly Generation Across Periods"
        colorscale = 'Viridis'
    
    # Handle both MultiIndex and single index cases
    if isinstance(hourly_gen_data.index, pd.MultiIndex):
        # For multi-period data, pivot to get periods as columns
        periods = hourly_gen_data.index.get_level_values(0).unique()
        
        # Convert to more manageable daily or weekly averages if too many snapshots
        snapshots = hourly_gen_data.index.get_level_values(1)
        
        if len(snapshots) > 1000:  # If too many snapshots, aggregate to daily averages
            # Extract date from timestamps
            if hasattr(snapshots, 'date'):
                dates = pd.Series([ts.date() for ts in snapshots], index=snapshots)
                
                # Create a new index with period and date
                new_index = pd.MultiIndex.from_tuples(
                    [(hourly_gen_data.index.get_level_values(0)[i], dates[i]) 
                     for i in range(len(hourly_gen_data))],
                    names=['period', 'date']
                )
                
                # Group by the new index and compute daily averages
                temp_df = plot_data.copy()
                temp_df.index = new_index
                plot_data = temp_df.groupby(level=[0, 1]).mean()
                
                # Update title to reflect daily averaging
                title = title.replace("Hourly", "Daily Average")
        
        # Prepare data for heatmap
        if isinstance(plot_data.index, pd.MultiIndex) and plot_data.index.nlevels == 2:
            # Pivot the data to get periods as columns, timestamps as rows
            pivot_table = pd.pivot_table(
                plot_data.reset_index(), 
                values=plot_data.columns[0], 
                index='snapshot' if 'snapshot' in plot_data.index.names else 'date',
                columns='period'
            )
        else:
            # If not a MultiIndex, just use the data as is
            pivot_table = plot_data
        
        # Create heatmap
        fig = px.imshow(
            pivot_table, 
            color_continuous_scale=colorscale,
            labels={'color': 'Generation (MW)'},
            title=title
        )
        
        # Adjust layout for better readability
        fig.update_layout(
            xaxis_title="Period",
            yaxis_title="Time",
            height=800,
            coloraxis_colorbar=dict(
                title="MW",
            )
        )
    else:
        # For single period data, create a simple line plot
        fig = px.line(
            plot_data, 
            title=title,
            labels={'value': 'Generation (MW)', 'index': 'Time'}
        )
        
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Generation (MW)",
            height=600
        )
    
    return fig

def plot_generation_profile_by_period(hourly_gen_data, carrier_colors):
            
        # Create a visualization showing typical daily generation profiles for each period.
        
        # Parameters:
        # -----------
        # hourly_gen_data : pd.DataFrame
        #     DataFrame with MultiIndex (period, snapshot) and columns for each carrier
        # carrier_colors : dict
        #     Dictionary mapping carriers to colors
        
        # Returns:
        # --------
        # plotly.graph_objects.Figure
        #     Line plot of daily generation profiles by period
    if hourly_gen_data.empty:
        return go.Figure()
    
    # Handle both MultiIndex and single index cases
    if isinstance(hourly_gen_data.index, pd.MultiIndex):
        # Extract periods
        periods = hourly_gen_data.index.get_level_values(0).unique()
        
        # Create a figure with subplots - one for each period
        fig = make_subplots(
            rows=len(periods), 
            cols=1,
            shared_xaxes=True,
            subplot_titles=[f"Period {p}" for p in periods],
            vertical_spacing=0.05
        )
        
        # For each period, calculate and plot the average daily profile
        for i, period in enumerate(periods):
            period_data = hourly_gen_data.loc[period]
            
            # Get the timestamps and convert to hours of day
            timestamps = period_data.index
            if hasattr(timestamps, 'hour'):
                hours = timestamps.hour
                
                # Group by hour of day and calculate mean for each carrier
                daily_profile = period_data.groupby(hours).mean()
                
                # Plot each carrier
                for carrier in daily_profile.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=daily_profile.index, 
                            y=daily_profile[carrier],
                            name=carrier,
                            line=dict(color=carrier_colors.get(carrier, None)),
                            showlegend=(i == 0)  # Only show legend for the first period
                        ),
                        row=i+1, 
                        col=1
                    )
        
        # Update layout
        fig.update_layout(
            height=300 * len(periods),
            title="Average Daily Generation Profiles by Period",
            legend_title="Carrier",
            xaxis_title="Hour of Day",
        )
        
        # Update all y-axes
        for i in range(len(periods)):
            fig.update_yaxes(title_text="Generation (MW)", row=i+1, col=1)
    else:
        # For single period data, create a simple hourly profile
        timestamps = hourly_gen_data.index
        if hasattr(timestamps, 'hour'):
            hours = timestamps.hour
            daily_profile = hourly_gen_data.groupby(hours).mean()
            
            fig = px.line(
                daily_profile,
                labels={'value': 'Generation (MW)', 'index': 'Hour of Day'},
                title="Average Daily Generation Profile",
                color_discrete_map=carrier_colors
            )
            
            fig.update_layout(
                xaxis_title="Hour of Day",
                yaxis_title="Generation (MW)",
                height=600,
                legend_title="Carrier"
            )
        else:
            # If timestamps don't have hours, create a simple line plot
            fig = px.line(
                hourly_gen_data,
                title="Generation Time Series",
                labels={'value': 'Generation (MW)', 'index': 'Time'},
                color_discrete_map=carrier_colors
            )
    
    return fig

# --- 8. Multi-Period Network Handler ---
def extract_period_networks(network_path, output_dir):
    # #
    # Extract individual period networks from a multi-period network file.
    
    # Parameters:
    # -----------
    # network_path : str
    #     Path to the multi-period network file (.nc)
    # output_dir : str
    #     Directory to save the extracted period networks
    
    # Returns:
    # --------
    # dict
    #     Dictionary mapping period names to their file paths
    # #
    logging.info(f"Extracting period networks from {network_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the original network
    n_original = pypsa.Network()
    n_original.import_from_netcdf(network_path)
    
    # Check if it's a multi-period network
    snapshots = n_original.snapshots
    if not isinstance(snapshots, pd.MultiIndex):
        logging.info("Not a multi-period network, no extraction needed")
        return {"single_period": network_path}
    
    # Get periods
    periods = list(snapshots.levels[0])
    logging.info(f"Found {len(periods)} periods: {periods}")
    
    period_networks = {}
    
    # Extract each period with better error handling
    for period in periods:
        try:
            with st.spinner(f"Extracting period {period}..."):
                # Filter snapshots for this period
                period_snapshots = snapshots[snapshots.get_level_values(0) == period]
                
                if period_snapshots.empty:
                    logging.warning(f"No snapshots found for period {period}. Skipping.")
                    continue
                
                # Create a new network with only this period's data
                n_period = pypsa.Network()
                
                # Copy static data
                for component in n_original.components.keys():
                    list_name = n_original.components[component]["list_name"]
                    component_df = getattr(n_original, list_name)
                    if not component_df.empty:
                        # Filter for active assets in this period if build_year exists
                        if "build_year" in component_df.columns and "lifetime" in component_df.columns:
                            active_assets = component_df[
                                (component_df["build_year"] <= period) & 
                                ((component_df["build_year"] + component_df["lifetime"]) > period)
                            ]
                            setattr(n_period, list_name, active_assets)
                        else:
                            setattr(n_period, list_name, component_df.copy())
                
                # Copy carriers table
                if hasattr(n_original, 'carriers') and not n_original.carriers.empty:
                    n_period.carriers = n_original.carriers.copy()
                
                # Convert multi-index to regular datetime index for the period
                time_index = period_snapshots.get_level_values(1)  # Get the time level
                n_period.set_snapshots(time_index)
                
                # Copy time-dependent data for this period
                for component in n_original.components.keys():
                    list_name = n_original.components[component]["list_name"]
                    pnl_name = f"{list_name}_t"
                    
                    if hasattr(n_original, pnl_name):
                        pnl_dict = getattr(n_original, pnl_name)
                        period_pnl_dict = {}
                        
                        for key, df in pnl_dict.items():
                            if isinstance(df.index, pd.MultiIndex) and df.index.equals(snapshots):
                                # Data has full multi-index
                                period_data = df.loc[period_snapshots]
                                # Reset index to just the time part
                                period_data.index = time_index
                                period_pnl_dict[key] = period_data
                            elif df.index.isin(period_snapshots).any():
                                # Data has some overlap with period snapshots
                                common_idx = df.index.intersection(period_snapshots)
                                if not common_idx.empty:
                                    period_data = df.loc[common_idx]
                                    # Map multi-index to single time index
                                    if isinstance(period_data.index, pd.MultiIndex):
                                        time_idx_map = {multi_idx: multi_idx[1] for multi_idx in common_idx}
                                        period_data.index = [time_idx_map[idx] for idx in period_data.index]
                                    period_pnl_dict[key] = period_data
                        
                        if period_pnl_dict:
                            setattr(n_period, pnl_name, period_pnl_dict)
                
                # Copy snapshot weightings if they exist
                if hasattr(n_original, 'snapshot_weightings') and not n_original.snapshot_weightings.empty:
                    if isinstance(n_original.snapshot_weightings.index, pd.MultiIndex):
                        period_weights = n_original.snapshot_weightings.loc[period_snapshots]
                        period_weights.index = time_index
                        n_period.snapshot_weightings = period_weights
                
                # Save to file with absolute path and check for success
                period_file = os.path.join(os.path.abspath(output_dir), f"period_{period}.nc")
                n_period.export_to_netcdf(period_file)
                
                # Verify the file exists
                if os.path.exists(period_file):
                    period_networks[str(period)] = period_file
                    logging.info(f"Created period network for {period} at {period_file}")
                else:
                    logging.error(f"Failed to create file for period {period} at {period_file}")
        except Exception as e:
            logging.error(f"Error extracting period {period}: {e}", exc_info=True)
            st.warning(f"Error extracting period {period}: {e}")
    
    if not period_networks:
        st.error("Failed to extract any period networks. Using original network instead.")
        return {"single_period": network_path}
    
    return period_networks

def process_multi_period_network(uploaded_file):
    # #
    # Process an uploaded file to extract period networks if it's a multi-period network.
    
    # Parameters:
    # -----------
    # uploaded_file : UploadedFile
    #     The uploaded PyPSA network file
    
    # Returns:
    # --------
    # dict
    #     Dictionary mapping period names to their respective networks
    # #
    try:
        # Create temp directory for processing
        temp_dir = tempfile.mkdtemp(prefix="pypsa_dashboard_")
        
        # Store temp_dir in session state for cleanup
        if 'temp_dir' not in st.session_state:
            st.session_state['temp_dir'] = temp_dir
        
        # Save uploaded file to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".nc") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        
        # Extract period networks if it's a multi-period network
        period_networks_paths = extract_period_networks(
            tmp_path, 
            os.path.join(temp_dir, 'periods')
        )
        
        # Load each period network
        period_networks = {}
        for period, path in period_networks_paths.items():
            n = pypsa.Network()
            n.import_from_netcdf(path)
            period_networks[period] = n
            
        # Clean up temp file
        os.remove(tmp_path)
        
        return period_networks
        
    except Exception as e:
        st.error(f"Error processing network: {e}")
        logging.error(f"Error processing network: {e}", exc_info=True)
        return {}

# --- 9. Analysis Functions ---
def analyze_network(network, title_prefix=""):
    #Performs comprehensive analysis on a PyPSA network.#
    try:
        carrier_colors = get_color_palette(network)
    except Exception as e:
        st.error(f"Error generating colors: {e}")
        carrier_colors = DEFAULT_COLORS
    
    # Create tabs for different analysis views
    analysis_tabs = st.tabs([
        "Dispatch & Load", 
        "Capacity", 
        "Metrics", 
        "Storage",
        "Emissions",
        "Prices",
        "Network Flow"
    ])
    
    # Get snapshots
    snapshots = safe_get_snapshots(network)
    if snapshots.empty:
        st.warning("No snapshots available for analysis.")
        return
    
    # ----------------- Dispatch & Load Tab -----------------
    with analysis_tabs[0]:
        st.header("Generation Dispatch Analysis")
        
        # Time period selection and resolution
        col1, col2 = st.columns(2)
        with col1:
            resolution = st.selectbox(
                "Select time resolution:",
                ["1H", "3H", "6H", "12H", "1D", "1W"],
                index=0
            )
        
        with col2:
            # Add date range filter if we have datetime index
            if isinstance(snapshots, pd.DatetimeIndex) or (
                isinstance(snapshots, pd.MultiIndex) and 
                pd.api.types.is_datetime64_any_dtype(snapshots.get_level_values(-1))
            ):
                # Get datetime index
                if isinstance(snapshots, pd.MultiIndex):
                    time_index = snapshots.get_level_values(-1)
                else:
                    time_index = snapshots
                
                min_date = time_index.min().date()
                max_date = time_index.max().date()
                
                date_range = st.date_input(
                    "Select date range:",
                    [min_date,  max_date],
                    min_value=min_date,
                    max_value=max_date
                )
                
                if len(date_range) == 2:
                    start_date, end_date = date_range
                    
                    # Filter snapshots
                    if isinstance(snapshots, pd.MultiIndex):
                        mask = (
                            (snapshots.get_level_values(-1).date >= start_date) & 
                            (snapshots.get_level_values(-1).date <= end_date)
                        )
                        filtered_snapshots = snapshots[mask]
                    else:
                        mask = (
                            (snapshots.date >= start_date) & 
                            (snapshots.date <= end_date)
                        )
                        filtered_snapshots = snapshots[mask]
                else:
                    filtered_snapshots = snapshots
            else:
                filtered_snapshots = snapshots
                st.info("Date filtering not available for this network's snapshot structure.")
        
        # Extract dispatch data
        with st.spinner("Extracting dispatch data..."):
            gen_dispatch, load, storage_charge, storage_discharge = get_dispatch_data(
                network, 
                _snapshots_slice=filtered_snapshots,
                resolution=resolution
            )
        
        # Create dispatch plot
        if gen_dispatch.empty and load.isna().all() and storage_charge.empty and storage_discharge.empty:
            st.info("No dispatch/load data available for the selected period.")
        else:
            dispatch_plot = plot_dispatch_stack(
                gen_dispatch, 
                load, 
                storage_charge, 
                storage_discharge, 
                carrier_colors,
                title=f"{title_prefix} Generation Dispatch",
                plot_index=filtered_snapshots,
                resolution=resolution
            )
            st.plotly_chart(dispatch_plot, use_container_width=True)
        
        # Add additional analysis
        with st.expander("Daily Profiles & Load Duration Curve"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Daily profile plot
                daily_profile = create_daily_profile_plot(
                    gen_dispatch, load, storage_charge, storage_discharge, carrier_colors
                )
                st.plotly_chart(daily_profile, use_container_width=True)
                st.plotly_chart(create_daily_profile_plot_new(gen_dispatch, load, storage_charge, storage_discharge, carrier_colors), use_container_width=True)
            with col2:
                # Load duration curve
                if not load.isna().all() and load.sum() > 0:
                    load_duration = create_duration_curve(
                        load, 
                        title="Load Duration Curve", 
                        y_label="Load (MW)"
                    )
                    st.plotly_chart(load_duration, use_container_width=True)
                else:
                    st.info("No load data available for duration curve.")
        
        # Display summary statistics
        with st.expander("Dispatch Summary Statistics"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Generation by Technology")
                gen_summary = gen_dispatch.sum()
                st.dataframe(gen_summary.reset_index().rename(columns={"index": "Technology", 0: "Energy (MWh)"}))
            
            with col2:
                st.subheader("Load Statistics")
                if not load.isna().all() and load.sum() > 0:
                    st.metric("Total Load (MWh)", f"{load.sum():.2f}")
                    st.metric("Peak Load (MW)", f"{load.max():.2f}")
                    st.metric("Min Load (MW)", f"{load.min():.2f}")
                else:
                    st.info("No load data available.")
    
    # ----------------- Capacity Tab -----------------
    with analysis_tabs[1]:
        st.header("Installed Capacity Analysis")
        
        cap_attr = st.selectbox(
            "Capacity Attribute:", 
            ['p_nom_opt', 'e_nom_opt', 'p_nom', 'e_nom'], 
            key=f"cap_attr_{title_prefix}"
        )
        
        with st.spinner(f"Calculating capacity ({cap_attr})..."):
            capacity_df = get_carrier_capacity(network, attribute=cap_attr)
            
            # Filter out Market if present
            if capacity_df is not None and not capacity_df.empty and 'Market' in capacity_df.index:
                capacity_df = capacity_df[capacity_df.index != 'Market']
            
            # Set appropriate units
            unit_series = pd.Series("MW", index=capacity_df.index)
            if 'AC' in capacity_df.index:
                capacity_df = capacity_df.rename(index={'AC': 'Storage'})
                unit_series.loc['Storage'] = "MWh"
            
            if capacity_df.empty:
                st.info(f"No capacity data found for '{cap_attr}'.")
            else:
                # Display capacity table
                st.dataframe(capacity_df)
                
                # Create capacity bar chart
                fig_cap = px.bar(
                    capacity_df,
                    x=capacity_df.index,
                    y='Capacity',
                    color=capacity_df.index,
                    labels={'index': 'Carrier', 'Capacity': 'Capacity'},
                    title=f'Installed Capacity ({cap_attr}) by Carrier',
                    color_discrete_map=carrier_colors
                )
                
                # Add dynamic y-axis label with mixed units
                fig_cap.update_yaxes(title_text="Capacity (MW/MWh)")
                fig_cap.update_layout(showlegend=False)
                st.plotly_chart(fig_cap, use_container_width=True)
        
        # Capacity by region
        with st.expander("Capacity by Region"):
            with st.spinner("Calculating regional capacity..."):
                buses_capacity_df = get_buses_capacity(network, attribute=cap_attr)
                
                if buses_capacity_df.empty:
                    st.info("No capacity data found for regions.")
                else:
                    # Assign unit per region/carrier
                    unit_series = pd.Series("MW", index=buses_capacity_df.index)
                    if 'Store' in buses_capacity_df.index:
                        unit_series.loc['Store'] = "MWh"
                    
                    # Add unit as a column for hover template
                    buses_capacity_df = buses_capacity_df.copy()
                    buses_capacity_df['Unit'] = unit_series
                    
                    # Display region capacity table
                    st.dataframe(buses_capacity_df)
                    
                    # Create region capacity bar chart
                    fig_region = px.bar(
                        buses_capacity_df,
                        x=buses_capacity_df.index,
                        y='Capacity',
                        color=buses_capacity_df.index,
                        custom_data=['Unit'],
                        labels={'index': 'Region', 'Capacity': 'Capacity'},
                        title='Installed Capacity by Region',
                    )
                    
                    # Customize hover to show units
                    fig_region.update_traces(
                        hovertemplate="<b>%{x}</b><br>Capacity: %{y:.2f} %{customdata[0]}<extra></extra>"
                    )
                    
                    fig_region.update_yaxes(title_text="Capacity (MW/MWh)")
                    fig_region.update_layout(showlegend=False)
                    st.plotly_chart(fig_region, use_container_width=True)
    
    # ----------------- Metrics Tab -----------------
    with analysis_tabs[2]:
        st.header("System Metrics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Capacity Factors (CUF)")
            with st.spinner("Calculating capacity factors..."):
                cuf_df = calculate_cuf(network)
                
                if cuf_df.empty:
                    st.info("No CUF data available.")
                else:
                    # Display CUF table
                    st.dataframe(cuf_df)
                    
                    # Create CUF bar chart
                    fig_cuf = px.bar(
                        cuf_df.sort_values('CUF', ascending=False), 
                        x='Carrier', 
                        y='CUF', 
                        color='Carrier', 
                        title='Capacity Utilization Factor (CUF)', 
                        color_discrete_map=carrier_colors
                    )
                    fig_cuf.update_layout(yaxis_tickformat='.1%', showlegend=False)
                    st.plotly_chart(fig_cuf, use_container_width=True)
        
        with col2:
            st.subheader("Renewable Curtailment")
            with st.spinner("Calculating curtailment..."):
                curt_df = calculate_curtailment(network)
                
                if curt_df.empty:
                    st.info("No curtailment data available.")
                else:
                    # Display curtailment table
                    st.dataframe(curt_df)
                    
                    # Create curtailment bar chart
                    fig_curt = px.bar(
                        curt_df.sort_values('Curtailment (%)', ascending=False), 
                        x='Carrier', 
                        y='Curtailment (%)', 
                        color='Carrier', 
                        title='Curtailment (% of Potential)', 
                        color_discrete_map=carrier_colors
                    )
                    fig_curt.update_layout(yaxis_tickformat='.1f', yaxis_title='Curtailment (%)', showlegend=False)
                    st.plotly_chart(fig_curt, use_container_width=True)
    
    # ----------------- Storage Tab -----------------
    with analysis_tabs[3]:
        st.header("Storage Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("State of Charge (SoC)")
            with st.spinner("Fetching SoC data..."):
                soc_df = get_storage_soc(network)
                
                if soc_df.empty:
                    st.info("No State of Charge data available.")
                else:
                    # Convert index to datetime for plotting
                    soc_plot_idx = get_time_index(soc_df.index)
                    
                    # Melt dataframe for plotting
                    df_melted = soc_df.reset_index(drop=True).melt(
                        var_name='Storage Type', 
                        value_name='SoC (MWh)'
                    )
                    df_melted['Time'] = np.tile(soc_plot_idx, len(soc_df.columns))
                    

                fig_soc = px.line(
                    df_melted, 
                    x='Time', 
                    y='SoC (MWh)', 
                    color='Storage Type', 
                    title='Storage State of Charge (SoC)', 
                    color_discrete_map=carrier_colors
                )
                st.plotly_chart(fig_soc, use_container_width=True)

        with col2:
            st.subheader("Storage Utilization")
            
            # Calculate storage charge/discharge statistics
            if not storage_charge.empty or not storage_discharge.empty:
                all_storage = pd.concat([storage_charge, storage_discharge], axis=1).fillna(0)
                
                # Get charge/discharge columns
                charge_cols = [c for c in all_storage.columns if 'Charge' in c and all_storage[c].sum() < -1e-3]
                discharge_cols = [c for c in all_storage.columns if 'Discharge' in c and all_storage[c].sum() > 1e-3]
                
                # Calculate statistics
                storage_stats = []
                
                for discharge_col in discharge_cols:
                    base_name = discharge_col.replace(' Discharge', '')
                    charge_col = f"{base_name} Charge"
                    
                    if charge_col in charge_cols:
                        discharge_energy = all_storage[discharge_col].sum()
                        charge_energy = abs(all_storage[charge_col].sum())
                        
                        if charge_energy > 0:
                            efficiency = discharge_energy / charge_energy
                        else:
                            efficiency = np.nan
                        
                        storage_stats.append({
                            'Storage Type': base_name,
                            'Charge (MWh)': charge_energy,
                            'Discharge (MWh)': discharge_energy,
                            'Efficiency (%)': efficiency * 100 if not np.isnan(efficiency) else np.nan
                        })
                
                if storage_stats:
                    stats_df = pd.DataFrame(storage_stats)
                    st.dataframe(stats_df)
                    
                    # Create storage utilization chart
                    fig_util = px.bar(
                        stats_df,
                        x='Storage Type',
                        y=['Charge (MWh)', 'Discharge (MWh)'],
                        barmode='group',
                        title='Storage Energy Throughput',
                        color_discrete_map={'Charge (MWh)': '#FFA500', 'Discharge (MWh)': '#32CD32'}
                    )
                    st.plotly_chart(fig_util, use_container_width=True)
                else:
                    st.info("No storage utilization data available.")
            else:
                st.info("No storage charge/discharge data available.")

    # 2. EMISSIONS TAB
    with analysis_tabs[4]:
        st.header("CO₂ Emissions Analysis")
        
        with st.spinner("Calculating CO₂ emissions..."):
            total_emissions, emissions_by_carrier = calculate_co2_emissions(network)
            
            if total_emissions.empty and emissions_by_carrier.empty:
                st.info("No CO₂ emissions data available. Make sure carriers have 'co2_emissions' values.")
            else:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Total CO₂ Emissions")
                    
                    if not total_emissions.empty:
                        # For non-multi-period, just use the first row
                        total_val = total_emissions['Total CO2 Emissions (Tonnes)'].iloc[0]
                        st.metric("Total CO₂ Emissions (Tonnes)", f"{total_val:,.0f}")
                        
                        # Convert to appropriate units for display
                        if total_val > 1e6:
                            st.metric("Total CO₂ Emissions (Million Tonnes)", f"{total_val/1e6:.2f}")
                    else:
                        st.info("No total emissions data available.")
                
                with col2:
                    st.subheader("CO₂ Emissions by Carrier")
                    
                    if not emissions_by_carrier.empty:
                        # Filter to current period if multi-period
                        if 'Period' in emissions_by_carrier.columns:
                            period = emissions_by_carrier['Period'].iloc[0]
                            emissions_this_period = emissions_by_carrier[emissions_by_carrier['Period'] == period]
                        else:
                            emissions_this_period = emissions_by_carrier
                        
                        # Create emissions by carrier chart
                        fig_em_bar = px.bar(
                            emissions_this_period.sort_values('Emissions (Tonnes)', ascending=False), 
                            x='Carrier', 
                            y='Emissions (Tonnes)', 
                            color='Carrier', 
                            title='CO₂ Emissions by Carrier', 
                            color_discrete_map=carrier_colors
                        )
                        fig_em_bar.update_layout(showlegend=False)
                        st.plotly_chart(fig_em_bar, use_container_width=True)
                    else:
                        st.info("No emissions by carrier data available.")

    # 3. PRICES TAB
    with analysis_tabs[5]:
        st.header("Marginal Prices Analysis")
        
        # Get price data with the selected resolution
        with st.spinner("Extracting price data..."):
            price_data = calculate_marginal_prices(network, resolution)
            
            if price_data.empty:
                st.info("No marginal price data found in this network.")
            else:
                price_unit = f" ({network.buses.unit.iloc[0]}/MWh)" if 'unit' in network.buses and not network.buses.unit.empty else " ($/MWh)"
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Average Price by Bus")
                    avg_prices = price_data.mean().sort_values(ascending=False)
                    
                    if not avg_prices.isna().all():
                        # Display average price table
                        avg_price_df = avg_prices.reset_index()
                        avg_price_df.columns = ['Bus', f'Average Price{price_unit}']
                        st.dataframe(avg_price_df)
                        
                        # Create average price bar chart
                        fig_avg_p = px.bar(
                            avg_prices,
                            x=avg_prices.index,
                            y=avg_prices.values,
                            labels={'index': 'Bus', 'y': f'Average Price{price_unit}'},
                            title='Average Marginal Price by Bus'
                        )
                        fig_avg_p.update_layout(xaxis_title='Bus', yaxis_title=f'Average Price{price_unit}')
                        st.plotly_chart(fig_avg_p, use_container_width=True)
                
                with col2:
                    st.subheader("Price Duration Curve")
                    # Calculate system-wide average price
                    mean_prices = price_data.mean(axis=1)
                    
                    if not mean_prices.isna().all():
                        # Create price duration curve
                        fig_pdc = create_duration_curve(
                            mean_prices,
                            title="Price Duration Curve",
                            y_label=f"Price{price_unit}"
                        )
                        st.plotly_chart(fig_pdc, use_container_width=True)
                
                # Price heatmap (potentially slow, so put in expander)
                with st.expander("Price Heatmap (potentially slow to render)"):
                    if st.button("Generate Price Heatmap", key=f"price_heatmap_{title_prefix}"):
                        with st.spinner("Generating price heatmap..."):
                            # Transpose for better visualization
                            price_t = price_data.T
                            time_labels = get_time_index(price_t.columns)
                            
                            # Create heatmap
                            fig_hm = px.imshow(
                                price_t,
                                x=time_labels,
                                y=price_t.index,
                                aspect="auto",
                                labels={'x': 'Time', 'y': 'Bus', 'color': f'Price{price_unit}'},
                                title='Bus Marginal Price Heatmap'
                            )
                            st.plotly_chart(fig_hm, use_container_width=True)

    # 4. NETWORK FLOW TAB
    with analysis_tabs[6]:
        st.header("Network Flow & Losses Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Network Losses")
            
            with st.spinner("Calculating network losses..."):
                losses_df = calculate_network_losses(network)
                
                if losses_df.empty:
                    st.info("No network loss data available.")
                else:
                    # If multi-period, get loss for current period
                    if 'Period' in losses_df.columns:
                        # Use the first period in the dataframe
                        period = losses_df['Period'].iloc[0]
                        losses_this_period = losses_df[losses_df['Period'] == period]
                        
                        if not losses_this_period.empty:
                            loss_val = losses_this_period['Losses (MWh)'].iloc[0]
                            st.metric("Total Losses (MWh)", f"{loss_val:,.0f}")
                            
                            # Convert to GWh if large value
                            if loss_val > 1000:
                                st.metric("Total Losses (GWh)", f"{loss_val/1000:.2f}")
                    else:
                        # Single period - just use the value directly
                        if 'Losses (MWh)' in losses_df.columns:
                            loss_val = losses_df['Losses (MWh)'].iloc[0]
                            st.metric("Total Losses (MWh)", f"{loss_val:,.0f}")
        
        with col2:
            st.subheader("Line Loading")
            
            if 'lines' in network.components.keys() and hasattr(network, 'lines_t') and 'p0' in network.lines_t and 's_nom' in network.lines.columns:
                with st.spinner("Calculating line loading..."):
                    # Get line flow data
                    if not network.lines_t.p0.empty and not network.lines.empty:
                        p0 = network.lines_t.p0.loc[snapshots]
                        s_nom = network.lines.s_nom.reindex(p0.columns).fillna(1e-6)  # Avoid division by zero
                        
                        # Calculate loading percentage
                        loading = (p0.abs() / s_nom).mean() * 100  # Average loading over the period as percentage
                        loading = loading[loading > 0.1]  # Filter insignificant loading
                        
                        if loading.empty:
                            st.info("No significant line loading detected.")
                        else:
                            # Display loading table
                            loading_df = loading.sort_values(ascending=False).reset_index()
                            loading_df.columns = ['Line', 'Average Loading (%)']
                            st.dataframe(loading_df)
                            
                            # Create loading bar chart
                            fig_load = px.bar(
                                loading.sort_values(ascending=False),
                                labels={'index': 'Line', 'value': 'Loading (%)'},
                                title="Average Line Loading (%)"
                            )
                            fig_load.update_layout(showlegend=False)
                            st.plotly_chart(fig_load, use_container_width=True)
                    else:
                        st.info("No line flow data available.")
            else:
                st.info("Line data (lines_t.p0, lines.s_nom) not available in this network.")
def compare_periods(networks_dict, label_name="Period"):


    """Compares multiple periods or years."""
    if not networks_dict:
        st.info(f"No {label_name.lower()}s available for comparison.")
        return
    
    # Get a combined color palette across all networks
    combined_colors = {}
    for network in networks_dict.values():
        try:
            colors = get_color_palette(network)
            combined_colors.update(colors)
        except Exception as e:
            logging.error(f"Error generating colors: {e}", exc_info=True)
    
    if not combined_colors:
        combined_colors = DEFAULT_COLORS
    
    # Create tabs for different comparison views
    comparison_tabs = st.tabs([
        "Capacity Comparison", 
        "Generation Comparison",
        "Metrics Comparison",
        "Emissions Comparison"
    ])
    
    # ----------------- Capacity Comparison Tab -----------------
    with comparison_tabs[0]:
        st.header(f"Capacity Comparison by {label_name}")
        
        cap_attr = st.selectbox(
            "Capacity Attribute:",
            ['p_nom_opt', 'e_nom_opt', 'p_nom', 'e_nom'],
            key=f"compare_cap_attr"
        )
        
        with st.spinner(f"Calculating capacity for comparison..."):
            # Get capacity data for each period/year
            capacity_data = {}
            for key, network in networks_dict.items():
                try:
                    cap_df = get_carrier_capacity(network, attribute=cap_attr)
                    # Filter out Market if present
                    if cap_df is not None and not cap_df.empty and 'Market' in cap_df.index:
                        cap_df = cap_df[cap_df.index != 'Market']
                    
                    if not cap_df.empty:
                        capacity_data[key] = cap_df
                except Exception as e:
                    logging.error(f"Error getting capacity for {label_name} {key}: {e}", exc_info=True)
            
            if not capacity_data:
                st.info(f"No capacity data available for comparison.")
            else:
                # Create DataFrame for plotting
                plot_data = []
                for key, df in capacity_data.items():
                    for carrier, row in df.iterrows():
                        plot_data.append({
                            label_name: key,
                            'Carrier': carrier,
                            'Capacity': row['Capacity']
                        })
                
                plot_df = pd.DataFrame(plot_data)
                
                # Determine unit based on attribute
                unit = 'MW' if 'p_nom' in cap_attr else 'MWh'
               
                # Create capacity comparison plot
                fig_cap = px.bar(
                    plot_df,
                    x=label_name,
                    y='Capacity',
                    color='Carrier',
                 
                    title=f"Installed Capacity ({unit}) by {label_name}",
                    labels={'Capacity': f'Capacity ({unit})'}, 
                    color_discrete_map=combined_colors
                )
                st.plotly_chart(fig_cap, use_container_width=True)
                
                # Show the raw data
                with st.expander("View Raw Capacity Data"):
                    for key, df in capacity_data.items():
                        st.subheader(f"{label_name}: {key}")
                        st.dataframe(df)
        cap_attr_new_addition = st.selectbox(
            "Capacity Attribute:",
            ['build_year', 'optimization_diff'],
            key=f"new_addition_method"
        )        
        plot_new_capacity_additions(networks_dict,combined_colors, method=cap_attr_new_addition, label_name='Year')
    # ----------------- Generation Comparison Tab -----------------
    with comparison_tabs[1]:
        st.header(f"Generation Comparison by {label_name}")
        
        with st.spinner("Calculating generation for comparison..."):
            # Get generation data for each period/year
            gen_data = {}
            for key, network in networks_dict.items():
                try:
                    # Get all snapshots for this network
                    snapshots = safe_get_snapshots(network)
                    
                    # Extract generation data
                    gen_dispatch, _, _, _ = get_dispatch_data(network)
                    
                    if not gen_dispatch.empty:
                        # Calculate total generation by carrier
                        total_gen = gen_dispatch.sum()
                        gen_df = pd.DataFrame({'Generation (MWh)': total_gen})
                        gen_data[key] = gen_df
                except Exception as e:
                    logging.error(f"Error getting generation for {label_name} {key}: {e}", exc_info=True)
            
            if not gen_data:
                st.info(f"No generation data available for comparison.")
            else:
                # Create DataFrame for plotting
                plot_data = []
                for key, df in gen_data.items():
                    for carrier, row in df.iterrows():
                        plot_data.append({
                            label_name: key,
                            'Carrier': carrier,
                            'Generation (MWh)': row['Generation (MWh)']
                        })
                
                plot_df = pd.DataFrame(plot_data)
               
                # Create plot
                fig_gen = px.bar(
                    plot_df,
                    x=label_name,
                    y='Generation (MWh)',
                    color='Carrier',
                  
                    title=f"Total Generation by {label_name}", 
                    color_discrete_map=combined_colors
                )
                st.plotly_chart(fig_gen, use_container_width=True)
                
                # Generate generation share chart
                shares_data = []
                for key, df in gen_data.items():
                    total = df['Generation (MWh)'].sum()
                    if total > 0:
                        for carrier, row in df.iterrows():
                            shares_data.append({
                                label_name: key,
                                'Carrier': carrier,
                                'Share (%)': row['Generation (MWh)'] / total * 100
                            })
                
                if shares_data:
                    shares_df = pd.DataFrame(shares_data)
                    fig_shares = px.bar(
                        shares_df,
                        x=label_name,
                        y='Share (%)',
                        color='Carrier',
                        title=f"Generation Mix by {label_name}",
                        color_discrete_map=combined_colors
                    )
                    st.plotly_chart(fig_shares, use_container_width=True)
                
                # Show the raw data
                with st.expander("View Raw Generation Data"):
                    for key, df in gen_data.items():
                        st.subheader(f"{label_name}: {key}")
                        st.dataframe(df)
    
    # ----------------- Metrics Comparison Tab -----------------
    with comparison_tabs[2]:
        st.header(f"Metrics Comparison by {label_name}")
        
        with st.spinner("Calculating metrics for comparison..."):
            # Get CUF data for each period/year
            cuf_data = {}
            curtailment_data = {}
            
            for key, network in networks_dict.items():
                try:
                    # Calculate CUF
                    cuf_df = calculate_cuf(network)
                    if not cuf_df.empty:
                        cuf_data[key] = cuf_df.set_index('Carrier')
                        
                    # Calculate curtailment
                    curt_df = calculate_curtailment(network)
                    if not curt_df.empty:
                        curt_df_processed = curt_df[['Carrier', 'Curtailment (%)']].set_index('Carrier')
                        curtailment_data[key] = curt_df_processed
                        
                except Exception as e:
                    logging.error(f"Error calculating metrics for {label_name} {key}: {e}", exc_info=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(f"Capacity Factors by {label_name}")
                
                if not cuf_data:
                    st.info(f"No capacity factor data available for comparison.")
                else:
                    # Create DataFrame for plotting
                    cuf_plot_data = []
                    for key, df in cuf_data.items():
                        for carrier, row in df.iterrows():
                            cuf_plot_data.append({
                                label_name: key,
                                'Carrier': carrier,
                                'CUF': row['CUF']
                            })
                    
                    cuf_plot_df = pd.DataFrame(cuf_plot_data)
                   
                    # Create plot
                    fig_cuf = px.bar(
                        cuf_plot_df,
                        x=label_name,
                        y='CUF',
                        color='Carrier',
                        barmode='group',
                        title=f"Capacity Factors by {label_name}", 
                            color_discrete_map=combined_colors
                    )
                    fig_cuf.update_layout(yaxis_tickformat='.1%')
                    st.plotly_chart(fig_cuf, use_container_width=True)
            
            with col2:
                st.subheader(f"Curtailment by {label_name}")
                
                if not curtailment_data:
                    st.info(f"No curtailment data available for comparison.")
                else:
                    # Create DataFrame for plotting
                    curt_plot_data = []
                    for key, df in curtailment_data.items():
                        for carrier, row in df.iterrows():
                            curt_plot_data.append({
                                label_name: key,
                                'Carrier': carrier,
                                'Curtailment (%)': row['Curtailment (%)']
                            })
                    
                    curt_plot_df = pd.DataFrame(curt_plot_data)
                    curt_plot_df.to_clipboard()
                    # Create plot
                    fig_curt = px.bar(
                        curt_plot_df,
                        x=label_name,
                        y='Curtailment (%)',
                        color='Carrier',
                        barmode='group',
                        title=f"Curtailment by {label_name}",
                        color_discrete_map=combined_colors
                    )
                    st.plotly_chart(fig_curt, use_container_width=True)
    
    # ----------------- Emissions Comparison Tab -----------------
    with comparison_tabs[3]:
        st.header(f"Emissions Comparison by {label_name}")
        
        with st.spinner("Calculating emissions for comparison..."):
            # Get emissions data for each period/year
            total_emissions_data = {}
            emissions_by_carrier_data = {}
            
            for key, network in networks_dict.items():
                try:
                    total_emissions, emissions_by_carrier = calculate_co2_emissions(network)
                    
                    if not total_emissions.empty:
                        # For simple comparison, just use the total value
                        total_val = total_emissions['Total CO2 Emissions (Tonnes)'].iloc[0]
                        total_emissions_data[key] = total_val
                    
                    if not emissions_by_carrier.empty:
                        # If Period column exists, use the first period's data
                        if 'Period' in emissions_by_carrier.columns:
                            period = emissions_by_carrier['Period'].iloc[0]
                            emissions_this_period = emissions_by_carrier[emissions_by_carrier['Period'] == period]
                        else:
                            emissions_this_period = emissions_by_carrier
                        
                        emissions_df = emissions_this_period.set_index('Carrier')['Emissions (Tonnes)']
                        emissions_by_carrier_data[key] = emissions_df
                except Exception as e:
                    logging.error(f"Error calculating emissions for {label_name} {key}: {e}", exc_info=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(f"Total CO₂ Emissions by {label_name}")
                
                if not total_emissions_data:
                    st.info(f"No emissions data available for comparison.")
                else:
                    # Create DataFrame for plotting
                    totals_df = pd.DataFrame({
                        label_name: list(total_emissions_data.keys()),
                        'Total CO₂ Emissions (Tonnes)': list(total_emissions_data.values())
                    })
                    
                    # Create plot
                    fig_total = px.bar(
                        totals_df,
                        x=label_name,
                        y='Total CO₂ Emissions (Tonnes)',
                        title=f"Total CO₂ Emissions by {label_name}", 
                            color_discrete_map=combined_colors
                    )
                    st.plotly_chart(fig_total, use_container_width=True)
            
            with col2:
                st.subheader(f"CO₂ Emissions by Carrier and {label_name}")
                
                if not emissions_by_carrier_data:
                    st.info(f"No emissions by carrier data available for comparison.")
                else:
                    # Create DataFrame for plotting
                    emissions_plot_data = []
                    for key, series in emissions_by_carrier_data.items():
                        for carrier, value in series.items():
                            emissions_plot_data.append({
                                label_name: key,
                                'Carrier': carrier,
                                'Emissions (Tonnes)': value
                            })
                    
                    emissions_plot_df = pd.DataFrame(emissions_plot_data)
                    
                    # Create plot
                    fig_emissions = px.bar(
                        emissions_plot_df,
                        x=label_name,
                        y='Emissions (Tonnes)',
                        color='Carrier',
                        #barmode='group',
                        title=f"CO₂ Emissions by Carrier and {label_name}", 
                            color_discrete_map=combined_colors
                    )
                    st.plotly_chart(fig_emissions, use_container_width=True)

# 5. MAIN FUNCTION
def main():
    """Main function for the Streamlit dashboard."""
    st.title("Advanced PyPSA Network Analysis Dashboard V6.0")
    


    # Initialize session state for temp directory if needed
    if 'temp_dir' not in st.session_state:
        st.session_state['temp_dir'] = tempfile.mkdtemp(prefix="pypsa_dashboard_")
    
    # File upload mode selection
    upload_mode = st.sidebar.radio("Select upload mode:", ["Single file", "Multiple files (year_XXXX.nc format)"])
    
    if upload_mode == "Single file":
        uploaded_file = st.sidebar.file_uploader("Upload your PyPSA .nc file", type=["nc"])
        
        if uploaded_file is not None:
            # Process the network file
            with st.spinner(f"Loading network '{uploaded_file.name}'..."):
                period_networks = process_multi_period_network(uploaded_file)
                
                # Check if we have multiple periods
                if len(period_networks) > 1:
                    # Multi-period network handling
                    st.sidebar.success(f"Multi-period network detected with {len(period_networks)} periods")
                    periods = sorted(period_networks.keys())
                    
                    # Create a selector for periods
                    selected_period = st.sidebar.selectbox(
                        "Select period for analysis:",
                        periods,
                        format_func=lambda p: f"Period {p}"
                    )
                    
                    # Analyze the selected period network
                    selected_network = period_networks[selected_period]
                    analyze_network(selected_network, f"Period: {selected_period}")
                    
                    # Add cross-period analysis option
                    if st.sidebar.checkbox("Enable cross-period analysis"):
                        st.sidebar.header("Cross-Period Analysis")
                        
                        # Select multiple periods for comparison
                        comparison_periods = st.sidebar.multiselect(
                            "Select periods to compare:",
                            periods,
                            default=periods[:min(2, len(periods))]
                        )
                        comparison_periods = sorted(comparison_periods)
                        if comparison_periods:
                            st.header("Cross-Period Comparison")
                            compare_periods(
                                {p: period_networks[p] for p in comparison_periods},
                                "Period"
                            )
                else:
                    # Single-period network
                    st.sidebar.success("Single-period network loaded successfully")
                    network = list(period_networks.values())[0]
                    analyze_network(network)
        else:
            st.info("Please upload a PyPSA network file (.nc) using the sidebar.")
    else:
        # Multiple files upload for year-by-year comparison
        uploaded_files = st.sidebar.file_uploader(
            "Upload PyPSA .nc files (year_XXXX.nc format)",
            type=["nc"],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            # Extract year from filenames and load networks
            networks_by_year = {}
            
            for file in uploaded_files:
                # Try both formats: year_XXXX and XXXX_
                year_match = re.search(r'year_(\d{4})', file.name.lower()) or re.search(r'(\d{4})_', file.name)
                if year_match:
                    year = int(year_match.group(1))
                    with st.spinner(f"Loading network for year {year}..."):
                        try:
                            # Process network file to extract the single year network
                            period_networks = process_multi_period_network(file)
                            # Use the first period (or single period) as the year network
                            network = list(period_networks.values())[0]
                            networks_by_year[year] = network
                            st.sidebar.success(f"Loaded network for year {year}")
                        except Exception as e:
                            st.sidebar.error(f"Error loading file for year {year}: {e}")
                else:
                    st.sidebar.warning(f"Could not extract year from filename {file.name}. Expected format: year_XXXX.nc or XXXX_something.nc")
            
            if networks_by_year:
                # Sort years chronologically
                years = sorted(networks_by_year.keys())
                
                # Create tabs for different analyses
                tabs = st.tabs([
                    "Single Year Analysis", 
                    "Year-to-Year Comparison"
                ])
                
                with tabs[0]:
                    st.header("Single Year Analysis")
                    
                    # Let user select a year
                    selected_year = st.selectbox(
                        "Select year for detailed analysis:", 
                        years,
                        format_func=lambda y: f"Year {y}"
                    )
                    
                    if selected_year:
                        network = networks_by_year[selected_year]
                        analyze_network(network, f"Year {selected_year}")
                
                with tabs[1]:
                    st.header("Year-to-Year Comparison")
                    
                    # Let user select years to compare
                    comparison_years = st.multiselect(
                        "Select years to compare:",
                        years,
                        default=years[:min(3, len(years))]
                    )
                    comparison_years = sorted(comparison_years)
                
                    if comparison_years:
                        compare_periods(
                            {y: networks_by_year[y] for y in comparison_years},
                            "Year"
                        )
            else:
                st.warning("No valid networks loaded. Please upload files in the format year_XXXX.nc or XXXX_network.nc")
        else:
            st.info("Please upload multiple PyPSA network files (.nc) for year-by-year comparison using the sidebar.")
    st.markdown("""
    Upload your PyPSA network results (`.nc` files) to visualize energy dispatch, capacity, storage operation, and more.
    
    This dashboard supports:
    - Single-period networks
    - Multi-period networks (automatic period detection)
    - Year-by-year comparisons (upload files named year_XXXX.nc)
    
    Created by: Energy Modeling Team (Vasudha Foundation)
    """)
    st.markdown("""
    This page provides the complete code for the Advanced PyPSA Network Visualization Dashboard (Version 0.1).

    ## Features

    - Single-period and multi-period network support
    - Year-by-year comparison capabilities
    - Interactive visualizations for:
    - Generation dispatch
    - Installed capacity
    - Capacity factors
    - Storage operation
    - CO₂ emissions
    - Marginal prices
    - Network flow & losses


    """)
# Register cleanup function to run when the app closes
atexit.register(cleanup_temp_files)

# --- Run the main app ---
if __name__ == "__main__":
    main()