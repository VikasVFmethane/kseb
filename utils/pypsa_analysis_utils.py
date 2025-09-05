import pypsa
import pandas as pd
import numpy as np
import logging
from typing import Union, Optional, Tuple, Dict, List, Any
from collections import OrderedDict
import os

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Enhanced color palette based on Streamlit dashboard
DEFAULT_COLORS = {
    'Coal': '#000000', 'coal': '#000000',
    'Lignite': '#4B4B4B', 'lignite': '#4B4B4B',
    'Nuclear': '#800080', 'nuclear': '#800080',
    'Hydro': '#0073CF', 'hydro': '#0073CF',
    'Hydro RoR': '#3399FF', 'ror': '#3399FF', 'Hydro Storage': '#3399FF',
    'Solar': '#FFD700', 'solar': '#FFD700', 'pv': '#FFD700', 'Solar PV': '#FFD700',
    'Wind': '#ADD8E6', 'wind': '#ADD8E6', 'onwind': '#ADD8E6', 'offwind': '#ADD8E6',
    'Onshore Wind': '#ADD8E6', 'Offshore Wind': '#6495ED',
    'LFO': '#FF4500', 'lfo': '#FF4500', 'Oil': '#FF4500', 'oil': '#FF4500',
    'Diesel': '#FF4500',
    'Co-Gen': '#228B22', 'co-gen': '#228B22', 'biomass': '#228B22', 'Biomass': '#228B22',
    'PSP': '#3399FF', 'psp': '#3399FF', 'Pumped Hydro': '#3399FF',
    'Battery Storage': '#005B5B', 'battery': '#005B5B', 'Battery': '#005B5B',
    'Planned Battery Storage': '#66B2B2', 'planned battery': '#66B2B2',
    'Planned PSP': '#B0C4DE', 'planned psp': '#B0C4DE',
    'Storage': '#B0C4DE',
    'H2 Storage': '#AFEEEE', 'hydrogen': '#AFEEEE', 'h2': '#AFEEEE', 'H2': '#AFEEEE',
    'Hydrogen Storage': '#AFEEEE',
    'Load': '#000000',
    'Transmission': '#808080', 'Line': '#808080', 'Link': '#A9A9A9',
    'Losses': '#DC143C',
    'Other': '#D3D3D3',
    'Curtailment': '#FF00FF',
    'Excess': '#FF00FF',
    'Storage Charge': '#FFA500',
    'Storage Discharge': '#50C878',
    'Store Charge': '#AFEEEE',
    'Store Discharge': '#87CEEB',
}

# Chart.js compatible color cycle
CHARTJS_COLOR_CYCLE = [
    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40',
    '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384', '#36A2EB', '#FFCE56'
]

# --- Utility Functions ---
def safe_get_snapshots(n: pypsa.Network) -> Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]:
    """Safely get network snapshots."""
    return n.snapshots if hasattr(n, 'snapshots') and n.snapshots is not None else pd.Index([])

def get_time_index(index: Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index, None]) -> Optional[pd.DatetimeIndex]:
    """Extract or convert time component to DatetimeIndex."""
    if index is None or index.empty:
        return None
    if isinstance(index, pd.DatetimeIndex):
        return index
    
    if isinstance(index, pd.MultiIndex):
        time_level = index.get_level_values(-1)
    else:
        time_level = index
        
    if pd.api.types.is_datetime64_any_dtype(time_level):
        return pd.DatetimeIndex(time_level)
    else:
        try:
            converted = pd.to_datetime(time_level, errors='coerce')
            if converted.hasnans and not pd.Series(time_level).hasnans:
                logging.warning(f"Conversion to DatetimeIndex introduced NaNs.")
                return None
            return converted
        except (TypeError, ValueError) as e:
            logging.warning(f"Could not convert to DatetimeIndex: {e}")
            return None

def get_period_index(index: Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index, None]) -> Optional[Union[pd.Index, pd.Series]]:
    """Extract period component from index."""
    if index is None or index.empty:
        return None
    if isinstance(index, pd.MultiIndex):
        return index.get_level_values(0)
    elif isinstance(index, pd.DatetimeIndex):
        return pd.Series(index.year, index=index)
    
    logging.warning(f"Cannot determine period index from type {type(index)}")
    return None

def get_snapshot_weights(n: pypsa.Network, snapshots_idx: Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]) -> pd.Series:
    """Get snapshot weights, defaulting to 1.0."""
    if snapshots_idx is None or snapshots_idx.empty:
        return pd.Series(dtype=float)
        
    if hasattr(n, 'snapshot_weightings') and not n.snapshot_weightings.empty and 'objective' in n.snapshot_weightings.columns:
        weights = n.snapshot_weightings.objective
        common_index = snapshots_idx.intersection(weights.index)
        if not common_index.empty:
            return weights.loc[common_index].reindex(snapshots_idx).fillna(1.0)
        else:
            logging.warning("No common index between snapshots and weights. Using 1.0.")
    else:
        logging.warning("Snapshot weights not found. Using 1.0.")
    return pd.Series(1.0, index=snapshots_idx)

def get_effective_snapshots(n: pypsa.Network, snapshots_slice: Optional[Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]] = None) -> Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]:
    """Get effective snapshots for calculations."""
    if snapshots_slice is not None:
        if not snapshots_slice.empty:
            return snapshots_slice
        else:
            logging.debug("Received empty snapshots_slice")
            return pd.Index([])
    return safe_get_snapshots(n)

def get_carrier_map(comp_df: pd.DataFrame, carriers_df: Optional[pd.DataFrame], default_carrier_name: Optional[str] = None) -> Optional[pd.Series]:
    """Get mapping from components to carrier names."""
    if 'carrier' not in comp_df.columns and default_carrier_name is None:
        return None
    
    carrier_map = comp_df.get('carrier', pd.Series(default_carrier_name, index=comp_df.index))
    carrier_map = carrier_map.copy()

    if not isinstance(carriers_df, pd.DataFrame) or carriers_df.empty:
        unique_carriers = carrier_map.dropna().unique()
        carriers_df_internal = pd.DataFrame(index=unique_carriers)
    else:
        carriers_df_internal = carriers_df.copy()

    if 'nice_name' not in carriers_df_internal.columns:
        carriers_df_internal['nice_name'] = carriers_df_internal.index

    nice_name_map = carriers_df_internal['nice_name'].dropna().to_dict()
    
    original_carriers = carrier_map.copy()
    carrier_map = carrier_map.map(nice_name_map)
    carrier_map.fillna(original_carriers, inplace=True)

    if default_carrier_name:
        carrier_map.fillna(default_carrier_name, inplace=True)
 
    return carrier_map

def resample_data(data_df, time_index, resolution):
    """Resample data to desired resolution."""
    if not isinstance(time_index, pd.DatetimeIndex):
        logging.warning(f"Cannot resample to {resolution}. Index is not DatetimeIndex.")
        return data_df
    
    df_resampled = data_df.copy()
    df_resampled.index = time_index
    return df_resampled.resample(resolution).mean()

# --- Enhanced Color Palette Generation ---
def get_color_palette(n: pypsa.Network) -> Dict[str, str]:
    """Generate comprehensive color palette for network components."""
    logging.debug("Generating color palette...")
    final_colors = DEFAULT_COLORS.copy()
    color_idx = 0
    
    def add_color_if_new(name, existing_colors, color_idx_ref):
        if name not in existing_colors:
            matched = False
            for default_key, default_color in DEFAULT_COLORS.items():
                if default_key.lower() in str(name).lower():
                    existing_colors[name] = default_color
                    matched = True
                    break
            if not matched:
                existing_colors[name] = CHARTJS_COLOR_CYCLE[color_idx_ref[0] % len(CHARTJS_COLOR_CYCLE)]
                color_idx_ref[0] += 1
        return existing_colors[name]

    # Process carriers from network
    if hasattr(n, "carriers") and isinstance(n.carriers, pd.DataFrame) and not n.carriers.empty:
        carriers_df = n.carriers.copy()
        if 'nice_name' not in carriers_df.columns:
            carriers_df['nice_name'] = carriers_df.index
        
        for carrier_idx, row in carriers_df.iterrows():
            carrier_name = str(carrier_idx)
            nice_name = str(row.get("nice_name", carrier_name))
            
            color_in_df = row.get("color") if "color" in row and pd.notna(row.get("color")) and row.get("color") != "" else None
            
            if color_in_df:
                final_colors[nice_name] = color_in_df
                if nice_name != carrier_name:
                    final_colors[carrier_name] = color_in_df
            else:
                color_for_nice = add_color_if_new(nice_name, final_colors, [color_idx])
                if nice_name != carrier_name and carrier_name not in final_colors:
                    final_colors[carrier_name] = color_for_nice

    # Process component carriers
    all_carrier_names = set()
    for comp_type in ['generators', 'storage_units', 'stores', 'links']:
        if hasattr(n, comp_type):
            comp_df = getattr(n, comp_type)
            if isinstance(comp_df, pd.DataFrame) and not comp_df.empty and 'carrier' in comp_df.columns:
                unique_carriers = comp_df['carrier'].dropna().unique()
                for carrier in unique_carriers:
                    nice_name = carrier
                    if hasattr(n, 'carriers') and isinstance(n.carriers, pd.DataFrame) and \
                       'nice_name' in n.carriers.columns and carrier in n.carriers.index:
                        val = n.carriers.loc[carrier, 'nice_name']
                        if pd.notna(val):
                            nice_name = val
                    
                    all_carrier_names.add(str(nice_name))
                    if str(nice_name) != str(carrier):
                        all_carrier_names.add(str(carrier))

    # Assign colors to all carriers
    for name in sorted(list(all_carrier_names)):
        add_color_if_new(name, final_colors, [color_idx])

    # Add charge/discharge colors for storage components
    for comp_name in final_colors.copy().keys():
        if any(st_kw in comp_name.lower() for st_kw in ['storage', 'store', 'battery', 'psp', 'hydro', 'h2']):
            add_color_if_new(f"{comp_name} Charge", final_colors, [color_idx])
            add_color_if_new(f"{comp_name} Discharge", final_colors, [color_idx])

    # Ensure essential colors exist
    for key, color in DEFAULT_COLORS.items():
        if key not in final_colors:
            final_colors[key] = color

    logging.debug(f"Generated color palette with {len(final_colors)} entries")
    return final_colors

# --- Enhanced Data Extraction Functions ---
def get_dispatch_data(n: pypsa.Network, snapshots_slice: Optional[Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]] = None,
                     resolution: str = "1H") -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.DataFrame]:
    """Extract comprehensive dispatch data."""
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        logging.warning("Empty effective snapshots in get_dispatch_data")
        return pd.DataFrame(), pd.Series(dtype=float), pd.DataFrame(), pd.DataFrame()

    logging.info(f"Extracting dispatch data for {len(effective_snapshots)} snapshots, resolution: {resolution}")
    
    gen_dispatch = pd.DataFrame(index=effective_snapshots)
    load_dispatch = pd.Series(0.0, index=effective_snapshots)
    storage_dispatch = pd.DataFrame(index=effective_snapshots)
    store_dispatch = pd.DataFrame(index=effective_snapshots)

    carriers_df = n.carriers if hasattr(n, 'carriers') and isinstance(n.carriers, pd.DataFrame) else pd.DataFrame()
    if 'nice_name' not in carriers_df.columns:
        carriers_df['nice_name'] = carriers_df.index

    # Extract generation data
    if hasattr(n, 'generators') and hasattr(n, 'generators_t') and 'p' in n.generators_t:
        df_static = n.generators
        df_t = n.generators_t['p']
        
        if not df_static.empty and not df_t.empty:
            carrier_map = get_carrier_map(df_static, carriers_df, 'Generator')
            if carrier_map is not None:
                aligned_data = df_t.reindex(index=effective_snapshots, columns=df_static.index).fillna(0)
                cols_to_group = aligned_data.columns.intersection(carrier_map.index)
                if not cols_to_group.empty:
                    gen_dispatch = aligned_data[cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()

    # Extract load data
    if hasattr(n, 'loads') and hasattr(n, 'loads_t'):
        load_attr = 'p_set' if 'p_set' in n.loads_t else 'p' if 'p' in n.loads_t else None
        if load_attr and not n.loads_t[load_attr].empty:
            aligned_load = n.loads_t[load_attr].reindex(index=effective_snapshots, columns=n.loads.index).fillna(0)
            load_dispatch = aligned_load.sum(axis=1)

    # Extract storage units data
    if hasattr(n, 'storage_units') and hasattr(n, 'storage_units_t') and 'p' in n.storage_units_t:
        df_static = n.storage_units
        df_t = n.storage_units_t['p']
        
        if not df_static.empty and not df_t.empty:
            carrier_map = get_carrier_map(df_static, carriers_df, 'StorageUnit')
            if carrier_map is not None:
                aligned_data = df_t.reindex(index=effective_snapshots, columns=df_static.index).fillna(0)
                cols_to_group = aligned_data.columns.intersection(carrier_map.index)
                if not cols_to_group.empty:
                    grouped_p = aligned_data[cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
                    for carrier in grouped_p.columns:
                        storage_dispatch[f"{carrier} Discharge"] = grouped_p[carrier].clip(lower=0)
                        storage_dispatch[f"{carrier} Charge"] = grouped_p[carrier].clip(upper=0)

    # Extract stores data
    if hasattr(n, 'stores') and hasattr(n, 'stores_t') and 'p' in n.stores_t:
        df_static = n.stores
        df_t = n.stores_t['p']
        
        if not df_static.empty and not df_t.empty:
            carrier_map = get_carrier_map(df_static, carriers_df, 'Store')
            if carrier_map is not None:
                aligned_data = df_t.reindex(index=effective_snapshots, columns=df_static.index).fillna(0)
                cols_to_group = aligned_data.columns.intersection(carrier_map.index)
                if not cols_to_group.empty:
                    grouped_p = aligned_data[cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
                    for carrier in grouped_p.columns:
                        store_dispatch[f"{carrier} Discharge"] = grouped_p[carrier].clip(lower=0)
                        store_dispatch[f"{carrier} Charge"] = grouped_p[carrier].clip(upper=0)

    # Clean up zero columns
    gen_dispatch = gen_dispatch.loc[:, (gen_dispatch.abs() > 1e-6).any(axis=0)]
    storage_dispatch = storage_dispatch.loc[:, (storage_dispatch.abs() > 1e-6).any(axis=0)]
    store_dispatch = store_dispatch.loc[:, (store_dispatch.abs() > 1e-6).any(axis=0)]
    
    # Apply time resolution resampling
    if resolution != "1H":
        time_idx = get_time_index(effective_snapshots)
        if time_idx is not None and not time_idx.empty:
            all_data = pd.concat([gen_dispatch, load_dispatch.rename('Load'), 
                                 storage_dispatch, store_dispatch], axis=1)
            all_data.index = time_idx
            resampled_data = all_data.resample(resolution).mean()
            
            gen_dispatch = resampled_data.loc[:, gen_dispatch.columns]
            if 'Load' in resampled_data.columns:
                load_dispatch = resampled_data['Load']
            storage_cols = [col for col in resampled_data.columns if col in storage_dispatch.columns]
            storage_dispatch = resampled_data.loc[:, storage_cols] if storage_cols else pd.DataFrame()
            store_cols = [col for col in resampled_data.columns if col in store_dispatch.columns]
            store_dispatch = resampled_data.loc[:, store_cols] if store_cols else pd.DataFrame()
    
    return gen_dispatch, load_dispatch, storage_dispatch, store_dispatch

def get_carrier_capacity(n: pypsa.Network, attribute: str = "p_nom_opt", period=None) -> pd.DataFrame:
    """Get aggregated capacity by carrier."""
    logging.info(f"Calculating capacity for attribute '{attribute}'" + 
                 (f" for period '{period}'" if period else ""))
    
    capacity_list = []
    is_multi_period = isinstance(safe_get_snapshots(n), pd.MultiIndex)
    carriers_df = n.carriers if hasattr(n, 'carriers') else pd.DataFrame()
    
    if 'nice_name' not in carriers_df.columns:
        carriers_df['nice_name'] = carriers_df.index

    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}

    for comp_cls, comp_attr in components_to_check.items():
        if hasattr(n, comp_attr):
            df_comp = getattr(n, comp_attr)
            if not df_comp.empty and 'carrier' in df_comp.columns:
                # Determine appropriate attribute
                if comp_cls == 'Store':
                    attr_to_use = attribute if attribute in ['e_nom', 'e_nom_opt'] else 'e_nom_opt'
                else:
                    attr_to_use = attribute if attribute in ['p_nom', 'p_nom_opt'] else 'p_nom_opt'

                if attr_to_use not in df_comp.columns:
                    logging.warning(f"Attribute '{attr_to_use}' not found in {comp_cls}")
                    continue

                active_assets_idx = df_comp.index
                # Filter for active assets in multi-period
                if is_multi_period and period is not None:
                    try:
                        if hasattr(n, 'get_active_assets'):
                            active_assets_idx = n.get_active_assets(comp_cls, period)
                        elif 'build_year' in df_comp.columns and 'lifetime' in df_comp.columns:
                            active_assets_idx = df_comp.index[
                                (df_comp['build_year'] <= period) &
                                (df_comp['build_year'] + df_comp['lifetime'] > period)
                            ]
                    except Exception as e:
                        logging.warning(f"Could not filter active assets: {e}")

                df_active = df_comp.loc[active_assets_idx]
                if not df_active.empty:
                    carrier_map = get_carrier_map(df_active, carriers_df)
                    if carrier_map is not None:
                        comp_capacity = df_active.groupby(carrier_map)[attr_to_use].sum()
                        capacity_list.append(comp_capacity)

    if capacity_list:
        combined_capacity = pd.concat(capacity_list).groupby(level=0).sum()
        result_df = combined_capacity.reset_index()
        result_df.columns = ['Carrier', 'Capacity']
        
        # Add unit information
        unit = 'MWh' if 'e_nom' in attribute else 'MW'
        result_df['Unit'] = unit
        result_df = result_df[result_df['Capacity'] > 1e-6]
        return result_df
    else:
        return pd.DataFrame(columns=['Carrier', 'Capacity', 'Unit'])

def get_buses_capacity(n: pypsa.Network, attribute: str = "p_nom_opt", period=None) -> pd.DataFrame:
    """Get aggregated capacity by bus/region."""
    logging.info(f"Calculating capacity by region for attribute '{attribute}'" + 
                 (f" for period '{period}'" if period else ""))
    
    capacity_list = []
    is_multi_period = isinstance(safe_get_snapshots(n), pd.MultiIndex)

    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}

    for comp_cls, comp_attr in components_to_check.items():
        if hasattr(n, comp_attr):
            df_comp = getattr(n, comp_attr)
            if not df_comp.empty and 'bus' in df_comp.columns:
                if comp_cls == 'Store':
                    attr_to_use = attribute if attribute in ['e_nom', 'e_nom_opt'] else 'e_nom_opt'
                else:
                    attr_to_use = attribute if attribute in ['p_nom', 'p_nom_opt'] else 'p_nom_opt'

                if attr_to_use not in df_comp.columns:
                    continue

                active_assets_idx = df_comp.index
                if is_multi_period and period is not None:
                    try:
                        if hasattr(n, 'get_active_assets'):
                            active_assets_idx = n.get_active_assets(comp_cls, period)
                        elif 'build_year' in df_comp.columns and 'lifetime' in df_comp.columns:
                            active_assets_idx = df_comp.index[
                                (df_comp['build_year'] <= period) &
                                (df_comp['build_year'] + df_comp['lifetime'] > period)
                            ]
                    except Exception as e:
                        logging.warning(f"Could not filter active assets: {e}")

                df_active = df_comp.loc[active_assets_idx]
                if not df_active.empty:
                    comp_capacity = df_active.groupby(df_active['bus'])[attr_to_use].sum()
                    capacity_list.append(comp_capacity)

    if capacity_list:
        combined_capacity = pd.concat(capacity_list).groupby(level=0).sum()
        result_df = combined_capacity.reset_index()
        result_df.columns = ['Region', 'Capacity']
        
        unit = 'MWh' if 'e_nom' in attribute else 'MW'
        result_df['Unit'] = unit
        result_df = result_df[result_df['Capacity'] > 1e-6]
        return result_df
    else:
        return pd.DataFrame(columns=['Region', 'Capacity', 'Unit'])

def get_carrier_capacity_new_addition(n: pypsa.Network, method='optimization_diff', period=None) -> pd.DataFrame:
    """Get new capacity additions by carrier."""
    logging.info(f"Calculating new capacity additions using method '{method}'" + 
                 (f" for period '{period}'" if period else ""))
    
    capacity_list = []
    is_multi_period = isinstance(safe_get_snapshots(n), pd.MultiIndex)
    carriers_df = n.carriers if hasattr(n, 'carriers') else pd.DataFrame()
    
    if 'nice_name' not in carriers_df.columns:
        carriers_df['nice_name'] = carriers_df.index
    
    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}
    
    for comp_cls, comp_attr in components_to_check.items():
        if hasattr(n, comp_attr):
            df_comp = getattr(n, comp_attr)
            
            if not df_comp.empty and 'carrier' in df_comp.columns:
                if method == 'optimization_diff':
                    if comp_cls == 'Store':
                        if 'e_nom_opt' not in df_comp.columns or 'e_nom' not in df_comp.columns:
                            continue
                    else:
                        if 'p_nom_opt' not in df_comp.columns or 'p_nom' not in df_comp.columns:
                            continue
                elif method == 'build_year':
                    if 'build_year' not in df_comp.columns:
                        continue
                
                active_assets_idx = df_comp.index
                if is_multi_period and period is not None:
                    try:
                        if hasattr(n, 'get_active_assets'):
                            active_assets_idx = n.get_active_assets(comp_cls, period)
                        elif 'build_year' in df_comp.columns and 'lifetime' in df_comp.columns:
                            active_assets_idx = df_comp.index[
                                (df_comp['build_year'] <= period) &
                                (df_comp['build_year'] + df_comp['lifetime'] > period)
                            ]
                    except Exception as e:
                        logging.warning(f"Could not filter active assets: {e}")
                
                df_active = df_comp.loc[active_assets_idx]
                
                if not df_active.empty:
                    carrier_map = get_carrier_map(df_active, carriers_df)
                    if carrier_map is not None:
                        if method == 'optimization_diff':
                            if comp_cls == 'Store':
                                df_active['new_capacity'] = df_active['e_nom_opt'] - df_active['e_nom']
                            else:
                                df_active['new_capacity'] = df_active['p_nom_opt'] - df_active['p_nom']
                            
                            df_active = df_active[df_active['new_capacity'] > 1e-6]
                            
                            if not df_active.empty:
                                comp_capacity = df_active.groupby(carrier_map)['new_capacity'].sum()
                                capacity_list.append(comp_capacity)
                        
                        elif method == 'build_year':
                            if period is not None:
                                df_built_this_year = df_active[df_active['build_year'] == period]
                                
                                if not df_built_this_year.empty:
                                    if comp_cls == 'Store':
                                        capacity_attr = 'e_nom_opt' if 'e_nom_opt' in df_built_this_year.columns else 'e_nom'
                                    else:
                                        capacity_attr = 'p_nom_opt' if 'p_nom_opt' in df_built_this_year.columns else 'p_nom'
                                    
                                    carrier_map_year = get_carrier_map(df_built_this_year, carriers_df)
                                    if carrier_map_year is not None:
                                        comp_capacity = df_built_this_year.groupby(carrier_map_year)[capacity_attr].sum()
                                        capacity_list.append(comp_capacity)
    
    if capacity_list:
        combined_capacity = pd.concat(capacity_list).groupby(level=0).sum()
        result_df = combined_capacity.reset_index()
        result_df.columns = ['Carrier', 'New_Capacity']
        
        unit = 'MW/MWh'  # Generic unit for mixed components
        result_df['Unit'] = unit
        result_df = result_df[result_df['New_Capacity'] > 1e-6]
        return result_df
    else:
        return pd.DataFrame(columns=['Carrier', 'New_Capacity', 'Unit'])

def calculate_cuf(n, snapshots_slice=None, **kwargs):
    """Calculate Capacity Utilization Factors."""
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return pd.DataFrame(columns=['Carrier', 'CUF'])

    logging.info(f"Calculating CUFs for {len(effective_snapshots)} snapshots")
    
    if not hasattr(n, 'generators') or n.generators.empty or \
       not hasattr(n, 'generators_t') or 'p' not in n.generators_t or \
       not any(c in n.generators.columns for c in ['p_nom_opt', 'p_nom']) or \
       'carrier' not in n.generators.columns:
        logging.warning("Missing data for CUF calculation")
        return pd.DataFrame(columns=['Carrier', 'CUF'])

    try:
        gen_p_aligned = n.generators_t['p'].reindex(index=effective_snapshots, columns=n.generators.index).fillna(0)
        
        p_nom_attr = 'p_nom_opt' if 'p_nom_opt' in n.generators.columns else 'p_nom'
        gen_p_nom = n.generators[p_nom_attr]

        weights = get_snapshot_weights(n, effective_snapshots)
        
        energy_produced_per_gen = gen_p_aligned.multiply(weights, axis=0).sum(axis=0)
        total_hours_equivalent = weights.sum()
        
        if total_hours_equivalent == 0:
            logging.warning("Total snapshot weight is zero")
            return pd.DataFrame(columns=['Carrier', 'CUF'])

        potential_energy_per_gen = gen_p_nom * total_hours_equivalent
        cuf_per_generator = (energy_produced_per_gen / potential_energy_per_gen.replace(0, np.nan)).fillna(0)
        cuf_per_generator = cuf_per_generator[cuf_per_generator.abs() > 1e-6]

        carrier_map = get_carrier_map(n.generators, n.carriers if hasattr(n, 'carriers') else pd.DataFrame())
        if carrier_map is None or cuf_per_generator.empty:
            return pd.DataFrame(columns=['Carrier', 'CUF'])
        
        valid_carrier_map = carrier_map.loc[carrier_map.index.intersection(cuf_per_generator.index)]
        if valid_carrier_map.empty:
            return pd.DataFrame(columns=['Carrier', 'CUF'])
        
        cuf_by_carrier = cuf_per_generator.groupby(valid_carrier_map).mean()
        cuf_df = cuf_by_carrier.reset_index()
        cuf_df.columns = ['Carrier', 'CUF']
        return cuf_df[cuf_df['CUF'].notna()]
        
    except Exception as e:
        logging.error(f"Error calculating CUFs: {e}", exc_info=True)
        return pd.DataFrame(columns=['Carrier', 'CUF'])

def calculate_curtailment(n, snapshots_slice=None, **kwargs):
    """Calculate renewable curtailment."""
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])
        
    logging.info(f"Calculating curtailment for {len(effective_snapshots)} snapshots")
    
    req_cols = ['p', 'p_max_pu']
    if not hasattr(n, 'generators') or n.generators.empty or \
       not hasattr(n, 'generators_t') or not all(c in n.generators_t for c in req_cols) or \
       'carrier' not in n.generators.columns or \
       not any(c in n.generators.columns for c in ['p_nom_opt', 'p_nom']):
        logging.warning("Missing data for curtailment calculation")
        return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

    try:
        renewable_keywords = ['solar', 'wind', 'ror']
        
        temp_generators_df = n.generators.copy()
        temp_generators_df['carrier_str'] = temp_generators_df['carrier'].astype(str)
        renewable_carriers = [c for c in temp_generators_df['carrier_str'].dropna().unique() 
                            if any(k in c.lower() for k in renewable_keywords)]
        
        renewable_gens_df = temp_generators_df[temp_generators_df['carrier_str'].isin(renewable_carriers)]
        if renewable_gens_df.empty:
            logging.info("No renewable generators found")
            return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

        p_nom_attr = 'p_nom_opt' if 'p_nom_opt' in renewable_gens_df.columns else 'p_nom'
        p_nom_renewable = renewable_gens_df[p_nom_attr]

        p_actual_aligned = n.generators_t['p'].reindex(index=effective_snapshots, columns=renewable_gens_df.index).fillna(0)
        p_max_pu_aligned = n.generators_t['p_max_pu'].reindex(index=effective_snapshots, columns=renewable_gens_df.index).fillna(0)
        
        weights = get_snapshot_weights(n, effective_snapshots)
        
        p_potential_mw = p_max_pu_aligned.multiply(p_nom_renewable.reindex(p_max_pu_aligned.columns), axis=1)
        curtailment_power_mw = (p_potential_mw - p_actual_aligned).clip(lower=0)

        curtailment_energy_mwh = curtailment_power_mw.multiply(weights, axis=0).sum(axis=0)
        potential_energy_mwh = p_potential_mw.multiply(weights, axis=0).sum(axis=0)

        carrier_map = get_carrier_map(renewable_gens_df, n.carriers if hasattr(n, 'carriers') else pd.DataFrame())
        if carrier_map is None:
            return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

        curtailment_by_carrier = curtailment_energy_mwh.groupby(carrier_map.loc[curtailment_energy_mwh.index]).sum()
        potential_by_carrier = potential_energy_mwh.groupby(carrier_map.loc[potential_energy_mwh.index]).sum()
        
        curtailment_df = pd.DataFrame({
            'Carrier': curtailment_by_carrier.index,
            'Curtailment (MWh)': curtailment_by_carrier.values,
            'Potential (MWh)': potential_by_carrier.reindex(curtailment_by_carrier.index).fillna(0).values
        })
        curtailment_df['Curtailment (%)'] = (curtailment_df['Curtailment (MWh)'] / curtailment_df['Potential (MWh)'].replace(0, np.nan) * 100).fillna(0)
        return curtailment_df[curtailment_df['Potential (MWh)'].abs() > 1e-3]
        
    except Exception as e:
        logging.error(f"Error calculating curtailment: {e}", exc_info=True)
        return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

def get_storage_soc(n: pypsa.Network, snapshots_slice=None) -> pd.DataFrame:
    """Extract Storage State of Charge data."""
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return pd.DataFrame()

    logging.info(f"Extracting SoC for {len(effective_snapshots)} snapshots")
    
    soc_data_list = []
    carriers_df = n.carriers if hasattr(n, 'carriers') and isinstance(n.carriers, pd.DataFrame) else pd.DataFrame()
    
    if 'nice_name' not in carriers_df.columns:
        carriers_df['nice_name'] = carriers_df.index

    storage_components = {
        'storage_units': {'soc_attr': 'state_of_charge', 'suffix': 'StorageUnit'},
        'stores': {'soc_attr': 'e', 'suffix': 'Store'},
    }

    for comp_name, config in storage_components.items():
        if hasattr(n, comp_name) and hasattr(n, f"{comp_name}_t"):
            df_static = getattr(n, comp_name, pd.DataFrame())
            if df_static.empty:
                continue

            soc_attr = config['soc_attr']
            comp_t_data = getattr(n, f"{comp_name}_t", {})
            soc_data = comp_t_data.get(soc_attr)

            if soc_data is not None and not soc_data.empty:
                aligned_soc = soc_data.reindex(index=effective_snapshots, columns=df_static.index).fillna(0)
                
                carrier_map = get_carrier_map(df_static, carriers_df, f"Default {config['suffix']}")
                if carrier_map is not None:
                    suffixed_carrier_map = carrier_map.apply(lambda x: f"{x} ({config['suffix']})")
                    
                    valid_cols = aligned_soc.columns.intersection(suffixed_carrier_map.index)
                    if not valid_cols.empty:
                        grouped_soc = aligned_soc[valid_cols].groupby(
                            suffixed_carrier_map.loc[valid_cols], axis=1
                        ).sum()
                        soc_data_list.append(grouped_soc)
    
    if not soc_data_list:
        return pd.DataFrame(index=effective_snapshots)
        
    combined_soc = pd.concat(soc_data_list, axis=1).reindex(effective_snapshots).fillna(0)
    return combined_soc.loc[:, (combined_soc.abs() > 1e-6).any(axis=0)]

def calculate_co2_emissions(n, snapshots_slice=None, **kwargs):
    """Calculate CO2 emissions."""
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    empty_total = pd.DataFrame(columns=['Period', 'Total CO2 Emissions (Tonnes)'])
    empty_carrier = pd.DataFrame(columns=['Period', 'Carrier', 'Emissions (Tonnes)'])
    
    if effective_snapshots.empty:
        return empty_total, empty_carrier

    logging.info(f"Calculating CO2 emissions for {len(effective_snapshots)} snapshots")
    
    if not hasattr(n, 'generators') or n.generators.empty or \
       not hasattr(n, 'generators_t') or 'p' not in n.generators_t or \
       not hasattr(n, 'carriers') or 'co2_emissions' not in n.carriers.columns:
        logging.warning("Missing data for CO2 emissions")
        return empty_total, empty_carrier

    try:
        co2_factors = n.carriers['co2_emissions'].dropna()
        if co2_factors.empty:
            return empty_total, empty_carrier

        emitting_gens = n.generators[n.generators['carrier'].isin(co2_factors.index)]
        if emitting_gens.empty:
            return empty_total, empty_carrier

        gen_p_aligned = n.generators_t.p.reindex(index=effective_snapshots, columns=emitting_gens.index).fillna(0)
        weights = get_snapshot_weights(n, effective_snapshots)

        co2_factors_for_gens = emitting_gens['carrier'].map(co2_factors)
        emissions_t = gen_p_aligned.multiply(co2_factors_for_gens, axis=1).multiply(weights, axis=0)

        periods = get_period_index(effective_snapshots)
        
        total_records = []
        carrier_records = []

        if periods is not None and isinstance(effective_snapshots, pd.MultiIndex):
            total_per_period = emissions_t.sum(axis=1).groupby(periods).sum()
            for period, total_em in total_per_period.items():
                total_records.append({'Period': str(period), 'Total CO2 Emissions (Tonnes)': total_em})

            carrier_map = get_carrier_map(emitting_gens, n.carriers)
            if carrier_map is not None:
                emissions_by_carrier_t = emissions_t.groupby(
                    carrier_map.loc[emissions_t.columns.intersection(carrier_map.index)], axis=1
                ).sum()
                emissions_by_carrier_per_period = emissions_by_carrier_t.groupby(periods).sum()
                for period, series in emissions_by_carrier_per_period.iterrows():
                    for carrier, em_val in series.items():
                        if abs(em_val) > 1e-3:
                            carrier_records.append({'Period': str(period), 'Carrier': carrier, 'Emissions (Tonnes)': em_val})
        else:
            total_overall = emissions_t.sum().sum()
            total_records.append({'Period': 'Overall', 'Total CO2 Emissions (Tonnes)': total_overall})
            
            carrier_map = get_carrier_map(emitting_gens, n.carriers)
            if carrier_map is not None:
                emissions_by_carrier = emissions_t.groupby(
                    carrier_map.loc[emissions_t.columns.intersection(carrier_map.index)], axis=1
                ).sum().sum(axis=0)
                for carrier, em_val in emissions_by_carrier.items():
                    if abs(em_val) > 1e-3:
                        carrier_records.append({'Period': 'Overall', 'Carrier': carrier, 'Emissions (Tonnes)': em_val})
        
        return pd.DataFrame(total_records), pd.DataFrame(carrier_records)
        
    except Exception as e:
        logging.error(f"Error calculating CO2 emissions: {e}", exc_info=True)
        return empty_total, empty_carrier

def calculate_marginal_prices(n: pypsa.Network, snapshots_slice=None, resolution: str = "1H") -> pd.DataFrame:
    """Extract marginal prices."""
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return pd.DataFrame()

    logging.info(f"Extracting marginal prices for {len(effective_snapshots)} snapshots")
    
    if not hasattr(n, "buses_t") or 'marginal_price' not in n.buses_t:
        logging.warning("No marginal price data found")
        return pd.DataFrame(index=effective_snapshots)
    
    price_data = n.buses_t['marginal_price'].reindex(index=effective_snapshots).fillna(0)
    
    if resolution != "1H":
        time_index = get_time_index(effective_snapshots)
        if time_index is not None and not time_index.empty:
            price_data_resample = price_data.copy()
            price_data_resample.index = time_index
            return price_data_resample.resample(resolution).mean()
        else:
            logging.warning(f"Cannot resample prices to {resolution}")
    
    return price_data

def calculate_network_losses(n: pypsa.Network, snapshots_slice=None, **kwargs) -> pd.DataFrame:
    """Calculate network losses."""
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return pd.DataFrame(columns=['Period', 'Losses (MWh)'])

    logging.info(f"Calculating network losses for {len(effective_snapshots)} snapshots")
    
    losses_list = []
    
    # Line losses
    if hasattr(n, 'lines') and hasattr(n, 'lines_t') and 'p0' in n.lines_t and 'p1' in n.lines_t:
        p0_aligned = n.lines_t.p0.reindex(index=effective_snapshots).fillna(0)
        p1_aligned = n.lines_t.p1.reindex(index=effective_snapshots).fillna(0)
        line_losses = (p0_aligned + p1_aligned).sum(axis=1)
        losses_list.append(line_losses)

    # Link losses
    if hasattr(n, 'links') and hasattr(n, 'links_t') and 'p0' in n.links_t and 'p1' in n.links_t:
        p0_links = n.links_t.p0.reindex(index=effective_snapshots).fillna(0)
        p1_links = n.links_t.p1.reindex(index=effective_snapshots).fillna(0)
        link_losses = (p0_links + p1_links).sum(axis=1)
        losses_list.append(link_losses)

    if not losses_list:
        return pd.DataFrame(columns=['Period', 'Losses (MWh)'])

    total_losses = pd.concat(losses_list, axis=1).sum(axis=1)
    weights = get_snapshot_weights(n, effective_snapshots)
    weighted_losses = total_losses * weights
    
    periods = get_period_index(effective_snapshots)
    losses_records = []

    if periods is not None and isinstance(effective_snapshots, pd.MultiIndex):
        losses_per_period = weighted_losses.groupby(periods).sum()
        for period, loss_val in losses_per_period.items():
            losses_records.append({'Period': str(period), 'Losses (MWh)': loss_val})
    else:
        total_losses_overall = weighted_losses.sum()
        losses_records.append({'Period': 'Overall', 'Losses (MWh)': total_losses_overall})
        
    return pd.DataFrame(losses_records)

def calculate_line_loading(n: pypsa.Network, snapshots_slice=None, **kwargs) -> List[Dict[str, Any]]:
    """Calculate line loading."""
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return []

    line_loading_records = []
    if hasattr(n, 'lines') and hasattr(n, 'lines_t') and 'p0' in n.lines_t and \
       's_nom' in n.lines.columns and not n.lines.s_nom.empty:
        
        p0_flows = n.lines_t.p0.reindex(index=effective_snapshots, columns=n.lines.index).fillna(0)
        s_nom_capacities = n.lines.s_nom.reindex(p0_flows.columns).replace(0, np.nan)

        if not p0_flows.empty and not s_nom_capacities.isna().all():
            loading_ratio = p0_flows.abs().div(s_nom_capacities, axis=1)
            avg_loading_pct = loading_ratio.mean(axis=0) * 100
            
            significant_loading = avg_loading_pct[avg_loading_pct.abs() > 0.1].sort_values(ascending=False)
            
            for line_name, loading_val in significant_loading.items():
                line_loading_records.append({"line": line_name, "loading": round(loading_val, 2)})
    
    return line_loading_records

# --- Payload Formatting Functions ---
def dispatch_data_payload_former(n, snapshots_slice=None, resolution="1H", **kwargs) -> Dict[str, Any]:
    """Format dispatch data for API response."""
    gen_dispatch, load_dispatch, storage_dispatch, store_dispatch = get_dispatch_data(
        n, snapshots_slice=snapshots_slice, resolution=resolution
    )
    
    # Determine index for timestamps
    final_index = pd.DataFrame().index
    if not gen_dispatch.empty:
        final_index = gen_dispatch.index
    elif not load_dispatch.empty:
        final_index = load_dispatch.index
    elif not storage_dispatch.empty:
        final_index = storage_dispatch.index
    elif not store_dispatch.empty:
        final_index = store_dispatch.index
    
    timestamps = [str(ts) for ts in get_time_index(final_index)] if not final_index.empty else []
    
    # Format load data
    load_records = []
    if not load_dispatch.empty and not load_dispatch.isna().all():
        for idx, val in load_dispatch.items():
            load_records.append(OrderedDict([
                ('timestamp', str(idx)), 
                ('load', val if pd.notna(val) else 0.0)
            ]))
    
    return {
        'generation': gen_dispatch.reset_index().to_dict('records', into=OrderedDict) if not gen_dispatch.empty else [],
        'load': load_records,
        'storage': storage_dispatch.reset_index().to_dict('records', into=OrderedDict) if not storage_dispatch.empty else [],
        'store': store_dispatch.reset_index().to_dict('records', into=OrderedDict) if not store_dispatch.empty else [],
        'timestamps': timestamps,
    }

def carrier_capacity_payload_former(n, snapshots_slice=None, attribute="p_nom_opt", **kwargs) -> Dict[str, Any]:
    """Format capacity data for API response."""
    period = kwargs.get('period')
    
    capacity_by_carrier = get_carrier_capacity(n, attribute=attribute, period=period)
    capacity_by_region = get_buses_capacity(n, attribute=attribute, period=period)
    
    return {
        'by_carrier': capacity_by_carrier.to_dict('records', into=OrderedDict) if not capacity_by_carrier.empty else [],
        'by_region': capacity_by_region.to_dict('records', into=OrderedDict) if not capacity_by_region.empty else [],
    }

def new_capacity_additions_payload_former(n, snapshots_slice=None, **kwargs) -> Dict[str, Any]:
    """Format new capacity additions data for API response."""
    method = kwargs.get('method', 'optimization_diff')
    period = kwargs.get('period')

    new_additions = get_carrier_capacity_new_addition(n, method=method, period=period)
    
    return {
        'new_additions': new_additions.to_dict('records', into=OrderedDict) if not new_additions.empty else [],
    }

def combined_metrics_extractor_wrapper(n, snapshots_slice=None, **kwargs) -> Dict[str, Any]:
    """Combine CUF and curtailment metrics."""
    cuf_data = calculate_cuf(n, snapshots_slice=snapshots_slice)
    curtailment_data = calculate_curtailment(n, snapshots_slice=snapshots_slice)
    
    return {
        'cuf': cuf_data.to_dict('records', into=OrderedDict) if not cuf_data.empty else [],
        'curtailment': curtailment_data.to_dict('records', into=OrderedDict) if not curtailment_data.empty else []
    }

def extract_api_storage_data_payload_former(n, snapshots_slice=None, resolution="1H", **kwargs) -> Dict[str, Any]:
    """Format storage data for API response."""
    soc_df = get_storage_soc(n, snapshots_slice=snapshots_slice)
    
    # Apply resampling if needed
    if resolution != "1H" and not soc_df.empty:
        time_idx = get_time_index(soc_df.index)
        if time_idx is not None and not time_idx.empty:
            soc_df_temp = soc_df.copy()
            soc_df_temp.index = time_idx
            soc_df = soc_df_temp.resample(resolution).mean()
    
    timestamps = [str(ts) for ts in get_time_index(soc_df.index)] if not soc_df.empty else []
    storage_types = soc_df.columns.tolist()

    # Calculate storage statistics
    _, _, storage_dispatch, store_dispatch = get_dispatch_data(n, snapshots_slice=snapshots_slice, resolution=resolution)
    all_storage = pd.concat([storage_dispatch, store_dispatch], axis=1).fillna(0)
    
    storage_stats = []
    if not all_storage.empty:
        weights = get_snapshot_weights(n, all_storage.index)
        
        charge_cols = [c for c in all_storage.columns if 'Charge' in c and all_storage[c].abs().sum() > 1e-3]
        discharge_cols = [c for c in all_storage.columns if 'Discharge' in c and all_storage[c].abs().sum() > 1e-3]
        processed_bases = set()
        
        for discharge_col in discharge_cols:
            base_name = discharge_col.replace(" Discharge", "")
            if base_name in processed_bases:
                continue

            charge_col = next((c for c in charge_cols if c.replace(" Charge", "") == base_name), None)

            if charge_col:
                discharge_energy = (all_storage[discharge_col] * weights).sum()
                charge_energy = abs((all_storage[charge_col] * weights).sum())
                
                efficiency = (discharge_energy / charge_energy * 100) if charge_energy > 1e-6 else np.nan
                
                storage_stats.append(OrderedDict([
                    ('Storage_Type', base_name),
                    ('Charge_MWh', charge_energy),
                    ('Discharge_MWh', discharge_energy),
                    ('Efficiency_Percent', efficiency if pd.notna(efficiency) else None)
                ]))
                processed_bases.add(base_name)
    
    return {
        'soc': soc_df.reset_index().to_dict('records', into=OrderedDict) if not soc_df.empty else [],
        'stats': storage_stats,
        'timestamps': timestamps,
        'storage_types': storage_types
    }

def emissions_payload_former(n, snapshots_slice=None, period_name=None, **kwargs) -> Dict[str, Any]:
    """Format emissions data for API response."""
    total_emissions, emissions_by_carrier = calculate_co2_emissions(n, snapshots_slice=snapshots_slice)
    
    if period_name:
        if not total_emissions.empty and 'Period' in total_emissions.columns:
            total_emissions = total_emissions[total_emissions['Period'] == str(period_name)]
        if not emissions_by_carrier.empty and 'Period' in emissions_by_carrier.columns:
            emissions_by_carrier = emissions_by_carrier[emissions_by_carrier['Period'] == str(period_name)]
            
    return {
        'total': total_emissions.to_dict('records', into=OrderedDict) if not total_emissions.empty else [],
        'by_carrier': emissions_by_carrier.to_dict('records', into=OrderedDict) if not emissions_by_carrier.empty else []
    }

def extract_api_prices_data_payload_former(n, snapshots_slice=None, resolution="1H", **kwargs) -> Dict[str, Any]:
    """Format price data for API response."""
    price_data = calculate_marginal_prices(n, snapshots_slice=snapshots_slice, resolution=resolution)
    
    if price_data.empty:
        return {'available': False, 'message': 'No marginal prices available'}

    unit = "currency/MWh"
    if hasattr(n, 'buses') and 'unit' in n.buses.columns and not n.buses.unit.empty:
        bus_unit = n.buses.unit.dropna().iloc[0] if not n.buses.unit.dropna().empty else "currency"
        unit = f"{bus_unit}/MWh"
    
    avg_prices = price_data.mean(axis=0).sort_values(ascending=False)
    min_prices = price_data.min(axis=0)
    max_prices = price_data.max(axis=0)
    
    avg_price_records = []
    for bus_id, avg_price in avg_prices.items():
        avg_price_records.append(OrderedDict([
            ('bus', bus_id),
            ('price', avg_price if pd.notna(avg_price) else None),
            ('min_price', min_prices.get(bus_id) if pd.notna(min_prices.get(bus_id)) else None),
            ('max_price', max_prices.get(bus_id) if pd.notna(max_prices.get(bus_id)) else None),
        ]))
    
    # Duration curve
    if price_data.shape[1] > 1:
        system_avg_price = price_data.mean(axis=1).dropna()
    else:
        system_avg_price = price_data.iloc[:, 0].dropna()
        
    duration_curve = sorted(system_avg_price.values, reverse=True) if not system_avg_price.empty else []
    timestamps = [str(ts) for ts in get_time_index(price_data.index)] if not price_data.empty else []

    return {
        'available': True,
        'unit': unit,
        'avg_by_bus': avg_price_records,
        'duration_curve': [float(p) for p in duration_curve],
        'timestamps': timestamps,
        'buses': price_data.columns.tolist()
    }

def extract_api_network_flow_payload_former(n, snapshots_slice=None, period_name=None, **kwargs) -> Dict[str, Any]:
    """Format network flow data for API response."""
    losses_df = calculate_network_losses(n, snapshots_slice=snapshots_slice)
    line_loading_records = calculate_line_loading(n, snapshots_slice=snapshots_slice)

    if period_name:
        if not losses_df.empty and 'Period' in losses_df.columns:
            losses_df = losses_df[losses_df['Period'] == str(period_name)]
    
    return {
        'losses': losses_df.to_dict('records', into=OrderedDict) if not losses_df.empty else [],
        'line_loading': line_loading_records
    }

# --- Network Comparison Functions ---
def compare_networks_results(networks_dict: Dict[str, pypsa.Network], comparison_type: str = 'capacity', **kwargs) -> Dict[str, Any]:
    """Compare multiple networks."""
    results = {}
    
    if comparison_type == 'capacity':
        attribute = kwargs.get('attribute', 'p_nom_opt')
        capacity_data = {}
        
        for label, network in networks_dict.items():
            try:
                capacity_df = get_carrier_capacity(network, attribute=attribute)
                if 'Market' in capacity_df.index:
                    capacity_df = capacity_df[capacity_df.index != 'Market']
                capacity_data[label] = capacity_df.to_dict('records') if not capacity_df.empty else []
            except Exception as e:
                capacity_data[label] = {'error': str(e)}
        
        results = {
            'type': 'capacity',
            'data': capacity_data,
            'unit': 'MWh' if 'e_nom' in attribute else 'MW',
            'label_name': 'Network'
        }
    
    elif comparison_type == 'new_capacity_additions':
        method = kwargs.get('new_capacity_method', 'optimization_diff')
        additions_data = {}
        
        for label, network in networks_dict.items():
            try:
                additions_df = get_carrier_capacity_new_addition(network, method=method)
                if 'Market' in additions_df.index:
                    additions_df = additions_df[additions_df.index != 'Market']
                additions_data[label] = additions_df.to_dict('records') if not additions_df.empty else []
            except Exception as e:
                additions_data[label] = {'error': str(e)}
        
        results = {
            'type': 'new_capacity_additions',
            'data': additions_data,
            'method': method,
            'unit': 'MW/MWh',
            'label_name': 'Network'
        }
    
    elif comparison_type == 'generation':
        generation_data = {}
        
        for label, network in networks_dict.items():
            try:
                gen_dispatch, _, _, _ = get_dispatch_data(network)
                if not gen_dispatch.empty:
                    total_gen = gen_dispatch.sum()
                    gen_df = pd.DataFrame({'Generation': total_gen})
                    generation_data[label] = gen_df.reset_index().to_dict('records')
                else:
                    generation_data[label] = []
            except Exception as e:
                generation_data[label] = {'error': str(e)}
        
        results = {
            'type': 'generation',
            'data': generation_data,
            'unit': 'MWh',
            'label_name': 'Network'
        }
    
    elif comparison_type == 'metrics':
        cuf_data = {}
        curtailment_data = {}
        
        for label, network in networks_dict.items():
            try:
                cuf_df = calculate_cuf(network)
                cuf_data[label] = cuf_df.to_dict('records') if not cuf_df.empty else []
                
                curt_df = calculate_curtailment(network)
                curtailment_data[label] = curt_df.to_dict('records') if not curt_df.empty else []
            except Exception as e:
                cuf_data[label] = {'error': str(e)}
                curtailment_data[label] = {'error': str(e)}
        
        results = {
            'type': 'metrics',
            'data': {
                'cuf': cuf_data,
                'curtailment': curtailment_data
            },
            'label_name': 'Network'
        }
    
    elif comparison_type == 'emissions':
        total_emissions_data = {}
        by_carrier_emissions_data = {}
        
        for label, network in networks_dict.items():
            try:
                total_em, by_carrier_em = calculate_co2_emissions(network)
                total_emissions_data[label] = total_em.to_dict('records') if not total_em.empty else []
                by_carrier_emissions_data[label] = by_carrier_em.to_dict('records') if not by_carrier_em.empty else []
            except Exception as e:
                total_emissions_data[label] = {'error': str(e)}
                by_carrier_emissions_data[label] = {'error': str(e)}
        
        results = {
            'type': 'emissions',
            'data': {
                'total': total_emissions_data,
                'by_carrier': by_carrier_emissions_data
            },
            'unit': 'Tonnes',
            'label_name': 'Network'
        }
    
    # Add colors from the first available network
    colors = {}
    for network in networks_dict.values():
        try:
            colors = get_color_palette(network)
            break
        except:
            continue
    
    if colors:
        results['colors'] = colors
    
    return results