

import pypsa
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import logging
from typing import Union, Optional, Tuple, Dict, List, Any
from plotly.subplots import make_subplots
from collections import OrderedDict # For to_dict('records', into=OrderedDict)

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Default color palette
DEFAULT_COLORS = {
    'Coal': '#000000', 'coal': '#000000',
    'Lignite': '#4B4B4B', 'lignite': '#4B4B4B',
    'Nuclear': '#800080', 'nuclear': '#800080',
    'Hydro': '#0073CF', 'hydro': '#0073CF', 'hydro ror': '#3399FF',
    'Hydro RoR': '#3399FF', 'ror': '#3399FF', 'Hydro Storage': '#3399FF', # Ensure "Hydro RoR" takes precedence
    'Solar': '#FFD700', 'solar': '#FFD700', 'pv': '#FFD700', 'Solar PV': '#FFD700',
    'Wind': '#ADD8E6', 'wind': '#ADD8E6', 'onwind': '#ADD8E6', 'offwind': '#ADD8E6', 'Onshore Wind': '#ADD8E6', 'Offshore Wind': '#6495ED',
    'LFO': '#FF4500', 'lfo': '#FF4500', 'Oil': '#FF4500', 'oil': '#FF4500', 'Diesel': '#FF4500',
    'Co-Gen': '#228B22', 'co-gen': '#228B22', 'biomass': '#228B22', 'Biomass': '#228B22',
    'PSP': '#3399FF', 'psp': '#3399FF', 'Pumped Hydro': '#3399FF',
    'Battery Storage': '#005B5B', 'battery': '#005B5B', 'Battery': '#005B5B',
    'Planned Battery Storage': '#66B2B2', 'planned battery': '#66B2B2',
    'Planned PSP': '#B0C4DE', 'planned psp': '#B0C4DE',
    'Storage': '#B0C4DE', # Generic storage
    'H2 Storage': '#AFEEEE', 'hydrogen': '#AFEEEE', 'h2': '#AFEEEE', 'H2': '#AFEEEE', 'Hydrogen Storage': '#AFEEEE',
    'Load': '#000000',
    'Transmission': '#808080', 'Line': '#808080', 'Link': '#A9A9A9',
    'Losses': '#DC143C',
    'Other': '#D3D3D3',
    'Curtailment': '#FF00FF',
    'Excess': '#FF00FF', # Often interchangeable with curtailment
    'Storage Charge': '#FFA500', # Generic charge
    'Storage Discharge': '#50C878', # Generic discharge (a green)
    'Store Charge': '#AFEEEE', # Default for 'Store' type if no specific carrier
    'Store Discharge': '#87CEEB', # Default for 'Store' type
}

PLOTLY_COLOR_CYCLE = px.colors.qualitative.Plotly

# --- Utility Functions for Snapshot and Index Handling ---
def safe_get_snapshots(n: pypsa.Network) -> Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]:
    """Safely get network snapshots, returning an empty pd.Index if not available."""
    return n.snapshots if hasattr(n, 'snapshots') and n.snapshots is not None else pd.Index([])

def get_time_index(index: Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index, None]) -> Optional[pd.DatetimeIndex]:
    """
    Extracts or converts the time component of a pandas Index to a DatetimeIndex.
    Returns None if conversion is not possible or index is empty.
    """
    if index is None or index.empty:
        return None
    if isinstance(index, pd.DatetimeIndex):
        return index
    
    target_index_level = index
    if isinstance(index, pd.MultiIndex):
        if index.nlevels > 0:
            target_index_level = index.get_level_values(-1) # Assume time is the last level
        else: # Should not happen for valid MultiIndex
            return None
            
    if pd.api.types.is_datetime64_any_dtype(target_index_level):
        return pd.DatetimeIndex(target_index_level)
    else:
        try:
            # Attempt conversion, handling potential errors for non-convertible types
            converted_index = pd.to_datetime(target_index_level, errors='coerce')
            if converted_index.hasnans and not pd.Series(target_index_level).hasnans: # Check if coercion introduced NaNs
                 logging.warning(f"Conversion to DatetimeIndex introduced NaNs for index type {type(target_index_level)}. Original may not be time-like.")
                 return None
            return converted_index
        except (TypeError, ValueError) as e:
            logging.warning(f"Could not convert index of type {type(target_index_level)} to DatetimeIndex: {e}")
            return None

def get_period_index(index: Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index, None]) -> Optional[Union[pd.Index, pd.Series]]:
    """
    Extracts the period component from a pandas Index.
    For DatetimeIndex, assumes annual periods. For MultiIndex, takes the first level.
    Returns None if not applicable or index is empty.
    """
    if index is None or index.empty:
        return None
    if isinstance(index, pd.MultiIndex):
        if index.nlevels > 0:
            return index.get_level_values(0) # Assume period is the first level
        else:
            return None # Should not happen
    elif isinstance(index, pd.DatetimeIndex):
        return pd.Series(index.year, index=index) # Simple annual period for DatetimeIndex
    
    logging.warning(f"Cannot determine period index from type {type(index)}. Returning None.")
    return None

def get_snapshot_weights(n: pypsa.Network, snapshots_idx: Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]) -> pd.Series:
    """
    Get snapshot weights, aligning with the provided snapshots_idx.
    Defaults to 1.0 if weights are not available or don't align.
    """
    if snapshots_idx is None or snapshots_idx.empty:
        return pd.Series(dtype=float) # Return empty Series if no snapshots
        
    if hasattr(n, 'snapshot_weightings') and not n.snapshot_weightings.empty and 'objective' in n.snapshot_weightings.columns:
        weights = n.snapshot_weightings.objective
        # Align weights with the potentially filtered/sliced snapshots_idx
        common_index = snapshots_idx.intersection(weights.index)
        if not common_index.empty:
            return weights.loc[common_index].reindex(snapshots_idx).fillna(1.0)
        else:
            logging.warning("No common index between provided snapshots and network's snapshot_weightings. Assuming weight 1.0.")
    else:
        logging.warning("Snapshot weights ('objective' column) not found or empty in network.snapshot_weightings. Assuming weight 1.0 for all snapshots.")
    return pd.Series(1.0, index=snapshots_idx)

def get_effective_snapshots(n: pypsa.Network, _snapshots_slice: Optional[Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]] = None) -> Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]:
    """
    Determines the effective set of snapshots to use for calculations.
    If _snapshots_slice is provided and valid, it's used. Otherwise, falls back to network's snapshots.
    Returns an empty pd.Index if no valid snapshots can be determined.
    """
    if _snapshots_slice is not None:
        if not _snapshots_slice.empty:
            return _snapshots_slice
        else:
            # If an empty slice was explicitly passed, it means no data for that selection
            logging.debug("get_effective_snapshots: Received an explicitly empty _snapshots_slice.")
            return pd.Index([]) 
    # Fallback to network's full snapshots if no slice provided
    return safe_get_snapshots(n)

def get_carrier_map(comp_df: pd.DataFrame, carriers_df: Optional[pd.DataFrame], default_carrier_name: Optional[str] = None) -> Optional[pd.Series]:
    """
    Helper function to get a mapping from component names to 'nice' carrier names.
    Uses 'nice_name' from carriers_df if available, otherwise defaults to original carrier or a provided default.
    """
    if 'carrier' not in comp_df.columns and default_carrier_name is None:
        logging.debug(f"Component DataFrame does not have 'carrier' column and no default_carrier_name provided.")
        return None # No basis for carrier mapping
    
    # Start with the 'carrier' column or a default series if 'carrier' is missing but default_carrier_name is given
    carrier_map_series = comp_df.get('carrier', pd.Series(default_carrier_name, index=comp_df.index))
    carrier_map_series = carrier_map_series.copy() # Work on a copy to avoid SettingWithCopyWarning

    # Ensure carriers_df is usable, even if None or empty
    if not isinstance(carriers_df, pd.DataFrame) or carriers_df.empty:
        # Create a minimal carriers_df if none provided, using unique values from carrier_map_series
        unique_carriers_in_comp = carrier_map_series.dropna().unique()
        carriers_df_internal = pd.DataFrame(index=unique_carriers_in_comp)
    else:
        carriers_df_internal = carriers_df.copy()

    carriers_df_internal['nice_name'] = carriers_df_internal.index # Default nice_name to carrier index itself

    nice_name_map_dict = carriers_df_internal['nice_name'].dropna().to_dict()
    
    # Map to nice names, then fill any NaNs (unmapped original carriers) with their original names
    # This handles cases where a carrier in comp_df might not be in carriers_df
    original_carriers = carrier_map_series.copy()
    carrier_map_series = carrier_map_series.map(nice_name_map_dict)
    carrier_map_series.fillna(original_carriers, inplace=True)

    # If a default_carrier_name was provided, ensure any remaining NaNs (e.g. if original carrier was NaN) are filled
    if default_carrier_name:
         carrier_map_series.fillna(default_carrier_name, inplace=True)
 
    return carrier_map_series


def get_carrier_capacity(_n: pypsa.Network, attribute: str = "p_nom_opt", period_val_for_assets: Optional[Any] = None) -> pd.DataFrame:
    """
    Calculates aggregated capacity by carrier for specified components and attribute.
    `period_val_for_assets` is used for filtering assets based on build_year/lifetime in multi-period investment models.
    It is NOT for slicing time-series snapshots.
    """
    logging.info(f"get_carrier_capacity: Calculating for attribute '{attribute}'" + 
                 (f" considering assets active in period '{period_val_for_assets}'" if period_val_for_assets is not None else ""))
    
    capacity_data_list = []
    carriers_df = _n.carriers if hasattr(_n, 'carriers') and isinstance(_n.carriers, pd.DataFrame) else pd.DataFrame()

    carriers_df['nice_name'] = carriers_df.index
        
    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}

    for comp_class_name, comp_attr_name_in_n in components_to_check.items():
        if hasattr(_n, comp_attr_name_in_n): # Check if component attribute exists in network object
            df_component_static = getattr(_n, comp_attr_name_in_n, pd.DataFrame())
            if df_component_static.empty: continue

            # Determine the correct capacity attribute to use (p_nom vs e_nom for Stores)
            attr_to_use = attribute
            if comp_class_name == 'Store': # Stores use e_nom, e_nom_opt
                if attribute not in ['e_nom', 'e_nom_opt']:
                    attr_to_use = 'e_nom_opt' if 'e_nom_opt' in df_component_static.columns else 'e_nom'
            elif comp_class_name != 'Store': # Generators, StorageUnits use p_nom, p_nom_opt
                 if attribute not in ['p_nom', 'p_nom_opt']:
                    attr_to_use = 'p_nom_opt' if 'p_nom_opt' in df_component_static.columns else 'p_nom'

            if attr_to_use not in df_component_static.columns:
                logging.debug(f"Attribute '{attr_to_use}' not found in component '{comp_class_name}'. Skipping.")
                continue
            
            df_active_assets = df_component_static
            # Filter assets if period_val_for_assets is provided (for multi-investment period models)
            if period_val_for_assets is not None and 'build_year' in df_component_static.columns and 'lifetime' in df_component_static.columns:
                try:
                    # Ensure period_val_for_assets is compatible type with build_year
                    build_year_series = df_component_static['build_year']
                    if not build_year_series.empty:
                        typed_period = type(build_year_series.iloc[0])(period_val_for_assets)
                        active_mask = (build_year_series <= typed_period) & \
                                    ((build_year_series + df_component_static['lifetime']) > typed_period)
                        df_active_assets = df_component_static[active_mask]
                    else: # No build_year data, cannot filter
                        logging.debug(f"Build_year column empty for {comp_class_name}, cannot filter by period {period_val_for_assets}.")

                except Exception as e_filter:
                    logging.warning(f"Could not filter active assets for {comp_class_name} in period {period_val_for_assets} due to: {e_filter}. Using all assets.")
            
            if not df_active_assets.empty:
                carrier_map = get_carrier_map(df_active_assets, carriers_df, default_carrier_name=comp_class_name)
                if carrier_map is not None:
                    # Sum capacity for the determined attribute, grouped by mapped carrier name
                    summed_capacity_by_carrier = df_active_assets.groupby(carrier_map)[attr_to_use].sum()
                    capacity_data_list.append(summed_capacity_by_carrier)
    
    if capacity_data_list:
        # Combine capacities from different component types (e.g., a carrier might be in Generator and StorageUnit)
        final_combined_capacity = pd.concat(capacity_data_list).groupby(level=0).sum()
        result_df = final_combined_capacity.reset_index()
        result_df.columns = ['Carrier', 'Capacity']
        
        unit_for_attribute = 'MWh' if 'e_nom' in attribute else 'MW' # Determine unit based on attribute name
        result_df['Unit'] = unit_for_attribute
        result_df = result_df[result_df['Capacity'].abs() > 1e-6] # Filter out negligible capacities
        return result_df
    else:
        return pd.DataFrame(columns=['Carrier', 'Capacity', 'Unit']) # Return empty DataFrame with schema

def get_buses_capacity(_n: pypsa.Network, attribute: str = "p_nom_opt", period_val_for_assets: Optional[Any] = None) -> pd.DataFrame:
    """
    Calculates aggregated capacity by bus (region) for specified components and attribute.
    `period_val_for_assets` is used for filtering assets based on build_year/lifetime.
    """
    logging.info(f"get_buses_capacity: Calculating for attribute '{attribute}' by bus" + 
                 (f" considering assets active in period '{period_val_for_assets}'" if period_val_for_assets is not None else ""))
    
    capacity_data_list = []
    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores', 'Load': 'loads'} # Include Loads

    for comp_class_name, comp_attr_name_in_n in components_to_check.items():
        if hasattr(_n, comp_attr_name_in_n):
            df_component_static = getattr(_n, comp_attr_name_in_n, pd.DataFrame())
            if df_component_static.empty or 'bus' not in df_component_static.columns: continue

            attr_to_use = attribute
            if comp_class_name == 'Store':
                if attribute not in ['e_nom', 'e_nom_opt']:
                    attr_to_use = 'e_nom_opt' if 'e_nom_opt' in df_component_static.columns else 'e_nom'
            elif comp_class_name == 'Load': # Loads typically use p_set for demand capacity
                 attr_to_use = 'p_set' if 'p_set' in df_component_static.columns else attribute # Fallback if p_set not there
            elif comp_class_name not in ['Store', 'Load']:
                 if attribute not in ['p_nom', 'p_nom_opt']:
                    attr_to_use = 'p_nom_opt' if 'p_nom_opt' in df_component_static.columns else 'p_nom'

            if attr_to_use not in df_component_static.columns:
                logging.debug(f"Attribute '{attr_to_use}' not found in component '{comp_class_name}' for bus capacity. Skipping.")
                continue
            
            df_active_assets = df_component_static
            if period_val_for_assets is not None and 'build_year' in df_component_static.columns and 'lifetime' in df_component_static.columns:
                try:
                    build_year_series = df_component_static['build_year']
                    if not build_year_series.empty:
                        typed_period = type(build_year_series.iloc[0])(period_val_for_assets)
                        active_mask = (build_year_series <= typed_period) & \
                                    ((build_year_series + df_component_static['lifetime']) > typed_period)
                        df_active_assets = df_component_static[active_mask]
                except Exception as e_filter:
                    logging.warning(f"Could not filter active assets for {comp_class_name} by bus in period {period_val_for_assets}: {e_filter}. Using all.")
            
            if not df_active_assets.empty:
                # Group by 'bus' column to sum capacity per bus
                summed_capacity_by_bus = df_active_assets.groupby('bus')[attr_to_use].sum()
                capacity_data_list.append(summed_capacity_by_bus)
    
    if capacity_data_list:
        final_combined_capacity_by_bus = pd.concat(capacity_data_list).groupby(level=0).sum()
        result_df = final_combined_capacity_by_bus.reset_index()
        result_df.columns = ['Region', 'Capacity'] # 'Region' is used in JS for bus capacity plot
        
        unit_for_attribute = 'MWh' if 'e_nom' in attribute or (comp_class_name == 'Load' and 'e_' in attr_to_use) else 'MW'
        result_df['Unit'] = unit_for_attribute
        result_df = result_df[result_df['Capacity'].abs() > 1e-6]
        return result_df
    else:
        return pd.DataFrame(columns=['Region', 'Capacity', 'Unit'])

def calculate_cuf(n, snapshots_slice=None, **kwargs):
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return pd.DataFrame(columns=['Carrier', 'CUF'])

    logging.info(f"Calculating CUFs for {len(effective_snapshots)} snapshots...")
    if not hasattr(n, 'generators') or n.generators.empty or \
       not hasattr(n, 'generators_t') or 'p' not in n.generators_t or \
       not any(c in n.generators.columns for c in ['p_nom_opt', 'p_nom']) or \
       'carrier' not in n.generators.columns:
        logging.warning("Missing data for CUF calculation.")
        return pd.DataFrame(columns=['Carrier', 'CUF'])

    try:
        # Align generators_t.p with the effective_snapshots
        gen_p_aligned = n.generators_t['p'].reindex(index=effective_snapshots, columns=n.generators.index).fillna(0)
        
        p_nom_attr = 'p_nom_opt' if 'p_nom_opt' in n.generators.columns else 'p_nom'
        gen_p_nom = n.generators[p_nom_attr] # This is a Series indexed by generator name

        weights = get_snapshot_weights(n, effective_snapshots) # Weights Series aligned with effective_snapshots
        
        # Energy produced by each generator over the effective_snapshots period
        energy_produced_per_gen = gen_p_aligned.multiply(weights, axis=0).sum(axis=0) # Sum over time (axis=0)
        
        total_hours_equivalent = weights.sum() # Sum of weights gives total equivalent hours
        if total_hours_equivalent == 0: 
            logging.warning("Total snapshot weight is zero, cannot calculate CUF.")
            return pd.DataFrame(columns=['Carrier', 'CUF'])

        # Potential energy by each generator if it ran at p_nom for total_hours_equivalent
        potential_energy_per_gen = gen_p_nom * total_hours_equivalent
        
        # CUF for each generator
        cuf_per_generator = (energy_produced_per_gen / potential_energy_per_gen.replace(0, np.nan)).fillna(0)
        cuf_per_generator = cuf_per_generator[cuf_per_generator.abs() > 1e-6] # Filter out negligible/zero CUFs

        carrier_map = get_carrier_map(n.generators, n.carriers if hasattr(n, 'carriers') else pd.DataFrame())
        if carrier_map is None or cuf_per_generator.empty: 
            return pd.DataFrame(columns=['Carrier', 'CUF'])
        
        # Average CUF by carrier, considering only generators that had some CUF
        # Ensure we only group by carriers of generators that are in cuf_per_generator
        valid_carrier_map_for_cuf = carrier_map.loc[carrier_map.index.intersection(cuf_per_generator.index)]
        if valid_carrier_map_for_cuf.empty:
             return pd.DataFrame(columns=['Carrier', 'CUF'])
        cuf_by_carrier = cuf_per_generator.groupby(valid_carrier_map_for_cuf).mean()
        
        cuf_df = cuf_by_carrier.reset_index()
        cuf_df.columns = ['Carrier', 'CUF']
        cuf_df.to_csv('debug/cuf.csv')
        return cuf_df[cuf_df['CUF'].notna()] # Ensure no NaN CUFs are returned
    except Exception as e:
        logging.error(f"Error calculating CUFs: {e}", exc_info=True)
        return pd.DataFrame(columns=['Carrier', 'CUF'])

def calculate_curtailment(n, snapshots_slice=None, **kwargs):
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])
        
    logging.info(f"Calculating curtailment for {len(effective_snapshots)} snapshots...")
    req_cols_t = ['p', 'p_max_pu'] # Time-dependent columns needed
    if not hasattr(n, 'generators') or n.generators.empty or \
       not hasattr(n, 'generators_t') or not all(c in n.generators_t for c in req_cols_t) or \
       'carrier' not in n.generators.columns or \
       not any(c in n.generators.columns for c in ['p_nom_opt', 'p_nom']): # Static capacity needed
        logging.warning("Missing essential data for curtailment calculation (generators, p, p_max_pu, p_nom/p_nom_opt, carrier).")
        return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

    try:
        # Identify renewable generators (this might need to be more robust based on your carrier names)
        renewable_keywords = ['solar', 'wind', 'ror'] # Hydro RoR is often considered curtailable
        # Ensure carrier names are strings for matching
        
        temp_generators_df = n.generators.copy() # Work on a copy
        temp_generators_df['carrier_str'] = temp_generators_df['carrier'].astype(str)
        renewable_carriers_names = [c for c in temp_generators_df['carrier_str'].dropna().unique() if any(k in c.lower() for k in renewable_keywords)]
        
        renewable_gens_df = temp_generators_df[temp_generators_df['carrier_str'].isin(renewable_carriers_names)]
        if renewable_gens_df.empty:
            logging.info("No renewable generators found based on keywords. No curtailment to calculate.")
            return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

        p_nom_attr = 'p_nom_opt' if 'p_nom_opt' in renewable_gens_df.columns else 'p_nom'
        p_nom_renewable = renewable_gens_df[p_nom_attr] # Series of nominal capacities for renewable gens

        # Align time-series data with effective_snapshots and relevant generator columns
        p_actual_aligned = n.generators_t['p'].reindex(index=effective_snapshots, columns=renewable_gens_df.index).fillna(0)
        p_max_pu_aligned = n.generators_t['p_max_pu'].reindex(index=effective_snapshots, columns=renewable_gens_df.index).fillna(0)
        
        weights = get_snapshot_weights(n, effective_snapshots) # Weights aligned with effective_snapshots
        
        # Calculate potential power (MW) for each renewable generator at each snapshot
        p_potential_mw = p_max_pu_aligned.multiply(p_nom_renewable.reindex(p_max_pu_aligned.columns), axis=1)
        
        # Calculate curtailment power (MW) = Potential - Actual, cannot be negative
        curtailment_power_mw = (p_potential_mw - p_actual_aligned).clip(lower=0)

        # Calculate energy (MWh) by multiplying power (MW) with snapshot weights (hours)
        curtailment_energy_mwh_per_gen = curtailment_power_mw.multiply(weights, axis=0).sum(axis=0) # Sum over time
        potential_energy_mwh_per_gen = p_potential_mw.multiply(weights, axis=0).sum(axis=0) # Sum over time

        carrier_map = get_carrier_map(renewable_gens_df, n.carriers if hasattr(n, 'carriers') else pd.DataFrame())
        if carrier_map is None: 
            return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

        # Group by mapped carrier name
        curtailment_by_carrier_mwh = curtailment_energy_mwh_per_gen.groupby(carrier_map.loc[curtailment_energy_mwh_per_gen.index]).sum()
        potential_by_carrier_mwh = potential_energy_mwh_per_gen.groupby(carrier_map.loc[potential_energy_mwh_per_gen.index]).sum()
        
        curtailment_results_df = pd.DataFrame({
            'Carrier': curtailment_by_carrier_mwh.index,
            'Curtailment (MWh)': curtailment_by_carrier_mwh.values,
            'Potential (MWh)': potential_by_carrier_mwh.reindex(curtailment_by_carrier_mwh.index).fillna(0).values # Align and fill for carriers with curtailment but maybe no potential if filtered
        })
        # Calculate percentage, avoid division by zero
        curtailment_results_df['Curtailment (%)'] = (curtailment_results_df['Curtailment (MWh)'] / curtailment_results_df['Potential (MWh)'].replace(0, np.nan) * 100).fillna(0)
        curtailment_results_df.to_csv('debug/curtailment_results_df.csv')
        return curtailment_results_df[curtailment_results_df['Potential (MWh)'].abs() > 1e-3] # Filter if potential is negligible
    except Exception as e:
        logging.error(f"Error calculating curtailment: {e}", exc_info=True)
        return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

def get_storage_soc(n: pypsa.Network, snapshots_slice=None) -> pd.DataFrame:
    """
    Extracts State of Charge (SoC) for storage_units and e (energy) for stores,
    aligned to effective_snapshots.
    """
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return pd.DataFrame()

    logging.info(f"get_storage_soc: Extracting SoC/energy for {len(effective_snapshots)} snapshots...")
    soc_data_frames_list = [] # Store DataFrames for each component type before concat
    carriers_df = n.carriers if hasattr(n, 'carriers') and isinstance(n.carriers, pd.DataFrame) else pd.DataFrame()

    # Configuration for storage-like components
    storage_components_config = {
        'storage_units': {'soc_attr': 'state_of_charge', 'default_carrier_suffix': 'StorageUnit'},
        'stores': {'soc_attr': 'e', 'default_carrier_suffix': 'Store'},
    }

    for comp_name_plural, config in storage_components_config.items():
        if hasattr(n, comp_name_plural) and hasattr(n, f"{comp_name_plural}_t"): # Check component and its time-series exist
            df_static = getattr(n, comp_name_plural, pd.DataFrame())
            if df_static.empty: continue

            soc_attr_name = config['soc_attr']
            comp_t_data_all = getattr(n, f"{comp_name_plural}_t", {}) # Get the dict of time-series dataframes
            comp_t_soc_data = comp_t_data_all.get(soc_attr_name)

            if comp_t_soc_data is not None and not comp_t_soc_data.empty:
                # Align SoC data with effective_snapshots (index and columns)
                aligned_soc_data = comp_t_soc_data.reindex(index=effective_snapshots, columns=df_static.index).fillna(0)
                
                # Get carrier mapping, using a suffix to distinguish if a carrier is used for different storage types
                carrier_map = get_carrier_map(df_static, carriers_df, default_carrier_name=f"Default {config['default_carrier_suffix']}")
                if carrier_map is not None:
                    # Suffix the mapped carrier names to make them unique per component type
                    # e.g., "Battery (StorageUnit)" vs "Hydrogen (Store)"
                    suffixed_carrier_map = carrier_map.apply(lambda x: f"{x} ({config['default_carrier_suffix']})")
                    
                    valid_cols_for_grouping = aligned_soc_data.columns.intersection(suffixed_carrier_map.index)
                    if not valid_cols_for_grouping.empty:
                        grouped_soc_data = aligned_soc_data[valid_cols_for_grouping].groupby(
                            suffixed_carrier_map.loc[valid_cols_for_grouping], axis=1
                        ).sum()
                        soc_data_frames_list.append(grouped_soc_data)
    
    if not soc_data_frames_list: 
        return pd.DataFrame(index=effective_snapshots) # Return empty DF with correct index
        
    # Concatenate all SoC/energy dataframes, then reindex again to ensure full effective_snapshots index
    combined_soc_df = pd.concat(soc_data_frames_list, axis=1).reindex(effective_snapshots).fillna(0)
    return combined_soc_df.loc[:, (combined_soc_df.abs() > 1e-6).any(axis=0)] # Filter out all-zero columns

def calculate_co2_emissions(n, snapshots_slice=None, **kwargs):
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    empty_total_df = pd.DataFrame(columns=['Period', 'Total CO2 Emissions (Tonnes)'])
    empty_carrier_df = pd.DataFrame(columns=['Period', 'Carrier', 'Emissions (Tonnes)'])
    if effective_snapshots.empty:
        return empty_total_df, empty_carrier_df

    logging.info(f"Calculating CO2 emissions for {len(effective_snapshots)} snapshots...")
    
    if not hasattr(n, 'generators') or n.generators.empty or \
       not hasattr(n, 'generators_t') or 'p' not in n.generators_t or \
       not hasattr(n, 'carriers') or 'co2_emissions' not in n.carriers.columns:
        logging.warning("Missing data for CO2 emissions (generators, p, carriers.co2_emissions).")
        return empty_total_df, empty_carrier_df

    try:
        co2_factors_per_carrier = n.carriers['co2_emissions'].dropna() # Series: carrier -> co2_factor
        if co2_factors_per_carrier.empty: 
            logging.info("No CO2 emission factors defined in n.carriers.co2_emissions.")
            return empty_total_df, empty_carrier_df

        # Filter generators that have carriers with defined CO2 factors
        emitting_gens_df = n.generators[n.generators['carrier'].isin(co2_factors_per_carrier.index)]
        if emitting_gens_df.empty: 
            logging.info("No generators found with carriers that have CO2 emission factors.")
            return empty_total_df, empty_carrier_df

        # Align generation data (p) with effective_snapshots and relevant generators
        gen_p_aligned = n.generators_t.p.reindex(index=effective_snapshots, columns=emitting_gens_df.index).fillna(0)
        weights = get_snapshot_weights(n, effective_snapshots) # Weights aligned with effective_snapshots

        # Map CO2 factors to each generator based on its carrier
        co2_factors_for_gens = emitting_gens_df['carrier'].map(co2_factors_per_carrier) # Series: generator_name -> co2_factor
        
        # Calculate emissions (Tonnes) for each generator at each snapshot: Power (MW) * Factor (tCO2/MWh) * Weight (h)
        emissions_timeseries_per_gen = gen_p_aligned.multiply(co2_factors_for_gens, axis=1).multiply(weights, axis=0)

        # Determine snapshot periods (e.g., years if MultiIndex)
        snapshot_periods = get_period_index(effective_snapshots) # Returns Series or Index
        
        total_emissions_records = []
        carrier_emissions_records = []

        if snapshot_periods is not None and isinstance(effective_snapshots, pd.MultiIndex): # Multi-period case
            # Total emissions per period
            total_emissions_sum_per_period = emissions_timeseries_per_gen.sum(axis=1).groupby(snapshot_periods).sum()
            for period_val, total_em_val in total_emissions_sum_per_period.items():
                total_emissions_records.append({'Period': str(period_val), 'Total CO2 Emissions (Tonnes)': total_em_val})

            # Emissions by carrier per period
            carrier_map_for_emitting_gens = get_carrier_map(emitting_gens_df, n.carriers)
            if carrier_map_for_emitting_gens is not None:
                emissions_grouped_by_carrier_t = emissions_timeseries_per_gen.groupby(
                    carrier_map_for_emitting_gens.loc[emissions_timeseries_per_gen.columns.intersection(carrier_map_for_emitting_gens.index)], axis=1
                ).sum()
                emissions_by_carrier_per_period = emissions_grouped_by_carrier_t.groupby(snapshot_periods).sum()
                for period_val, series_val in emissions_by_carrier_per_period.iterrows():
                    for carrier_name, em_val in series_val.items():
                        if abs(em_val) > 1e-3:
                             carrier_emissions_records.append({'Period': str(period_val), 'Carrier': carrier_name, 'Emissions (Tonnes)': em_val})
        else: # Single period case (or DatetimeIndex treated as one overall period)
            total_overall_emissions = emissions_timeseries_per_gen.sum().sum() # Sum over gens, then over time
            total_emissions_records.append({'Period': 'Overall', 'Total CO2 Emissions (Tonnes)': total_overall_emissions})
            
            carrier_map_for_emitting_gens = get_carrier_map(emitting_gens_df, n.carriers)
            if carrier_map_for_emitting_gens is not None:
                emissions_sum_by_carrier_overall = emissions_timeseries_per_gen.groupby(
                     carrier_map_for_emitting_gens.loc[emissions_timeseries_per_gen.columns.intersection(carrier_map_for_emitting_gens.index)], axis=1
                ).sum().sum(axis=0) # Sum over time, then by carrier
                for carrier_name, em_val in emissions_sum_by_carrier_overall.items():
                    if abs(em_val) > 1e-3:
                        carrier_emissions_records.append({'Period': 'Overall', 'Carrier': carrier_name, 'Emissions (Tonnes)': em_val})
        
        return pd.DataFrame(total_emissions_records), pd.DataFrame(carrier_emissions_records)
    except Exception as e:
        logging.error(f"Error calculating CO2 emissions: {e}", exc_info=True)
        return empty_total_df, empty_carrier_df

def calculate_marginal_prices(n: pypsa.Network, snapshots_slice=None, resolution: str = "1H") -> pd.DataFrame:
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty: return pd.DataFrame()

    logging.info(f"Extracting marginal prices for {len(effective_snapshots)} snapshots, resolution: {resolution}...")
    if not hasattr(n, "buses_t") or 'marginal_price' not in n.buses_t:
        logging.warning("No marginal price data found in n.buses_t.")
        return pd.DataFrame(index=effective_snapshots) # Return empty DF with correct index
    
    # Align prices data with effective_snapshots
    price_data_aligned = n.buses_t['marginal_price'].reindex(index=effective_snapshots).fillna(0) # Fill NaNs if slice extends beyond original
    
    if resolution != "1H":
        time_index_for_resampling = get_time_index(effective_snapshots) # Get DatetimeIndex part
        if time_index_for_resampling is not None and not time_index_for_resampling.empty:
            price_data_df_for_resample = price_data_aligned.copy()
            # Important: Ensure the index for resampling is the DatetimeIndex part
            price_data_df_for_resample.index = time_index_for_resampling 
            return price_data_df_for_resample.resample(resolution).mean()
        else:
            logging.warning(f"Cannot resample marginal prices to {resolution}. Valid DatetimeIndex not available from effective_snapshots.")
    return price_data_aligned


def calculate_network_losses(n: pypsa.Network, snapshots_slice=None, **kwargs) -> pd.DataFrame:
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty:
        return pd.DataFrame(columns=['Period', 'Losses (MWh)'])

    logging.info(f"Calculating network losses for {len(effective_snapshots)} snapshots...")
    all_losses_timeseries_list = [] # Store time series of losses for each component type (lines, links)
    
    # Line losses: p0 (flow at bus0) + p1 (flow at bus1) gives total power injected/withdrawn by the line.
    # If p0 + p1 is non-zero, it represents losses (or gain, if defined that way). Conventionally, sum is losses.
    if hasattr(n, 'lines') and hasattr(n, 'lines_t') and 'p0' in n.lines_t and 'p1' in n.lines_t:
        p0_lines_aligned = n.lines_t.p0.reindex(index=effective_snapshots).fillna(0)
        p1_lines_aligned = n.lines_t.p1.reindex(index=effective_snapshots).fillna(0)
        # Sum of flows into the line from both ends; positive sum means net loss from system perspective.
        line_losses_t_series = (p0_lines_aligned + p1_lines_aligned).sum(axis=1) # Sum losses across all lines for each snapshot
        all_losses_timeseries_list.append(line_losses_t_series)

    # Link losses: Similar logic, but efficiency might be involved for some link types.
    # For simplicity, using p0+p1 for basic links. Transformers might have specific loss parameters.
    # PyPSA often models losses in links by having p0 != -p1 * efficiency.
    if hasattr(n, 'links') and hasattr(n, 'links_t') and 'p0' in n.links_t and 'p1' in n.links_t:
        # A more accurate approach would be to filter links that are explicitly lossy (e.g. efficiency < 1)
        # Or if PyPSA stores losses_t for links. For now, p0+p1 is a common proxy if losses are modeled as flow difference.
        p0_links_aligned = n.links_t.p0.reindex(index=effective_snapshots).fillna(0)
        p1_links_aligned = n.links_t.p1.reindex(index=effective_snapshots).fillna(0)
        # Sum of flows. For a passive link, p0 = -p1 if lossless. If p0 + p1 != 0, it's loss/gain.
        link_losses_t_series = (p0_links_aligned + p1_links_aligned).sum(axis=1)
        all_losses_timeseries_list.append(link_losses_t_series)

    if not all_losses_timeseries_list: 
        return pd.DataFrame(columns=['Period', 'Losses (MWh)'])

    # Sum losses from all component types (lines, links) for each snapshot
    total_system_losses_t_series = pd.concat(all_losses_timeseries_list, axis=1).sum(axis=1)
    
    weights = get_snapshot_weights(n, effective_snapshots) # Weights aligned with effective_snapshots
    # Calculate energy losses (MWh) by multiplying power losses (MW) with snapshot weights (hours)
    weighted_energy_losses = total_system_losses_t_series * weights 
    
    snapshot_periods = get_period_index(effective_snapshots) # Returns Series or Index
    losses_records_for_df = []

    if snapshot_periods is not None and isinstance(effective_snapshots, pd.MultiIndex): # Multi-period case
        # Sum energy losses for each period
        total_losses_per_period = weighted_energy_losses.groupby(snapshot_periods).sum()
        for period_val, loss_mwh_val in total_losses_per_period.items():
            losses_records_for_df.append({'Period': str(period_val), 'Losses (MWh)': loss_mwh_val})
    else: # Single period case (or DatetimeIndex treated as one overall period)
        total_overall_losses_mwh = weighted_energy_losses.sum() # Sum over all snapshots
        losses_records_for_df.append({'Period': 'Overall', 'Losses (MWh)': total_overall_losses_mwh})
        
    return pd.DataFrame(losses_records_for_df)

def calculate_line_loading(n: pypsa.Network, snapshots_slice=None, **kwargs) -> List[Dict[str, Any]]:
    effective_snapshots = get_effective_snapshots(n, snapshots_slice)
    if effective_snapshots.empty: return []

    line_loading_records = []
    if hasattr(n, 'lines') and hasattr(n, 'lines_t') and 'p0' in n.lines_t and not n.lines_t.p0.empty and \
       's_nom' in n.lines.columns and not n.lines.s_nom.empty: # Check s_nom exists and is not empty
        
        # Align p0 time-series with effective_snapshots and line names
        p0_flows_aligned = n.lines_t.p0.reindex(index=effective_snapshots, columns=n.lines.index).fillna(0)
        
        # Align s_nom (static capacity) with the columns (lines) of p0_flows_aligned
        # Replace 0 with NaN in s_nom to avoid division by zero, then fillna if needed or let it propagate
        s_nom_capacities = n.lines.s_nom.reindex(p0_flows_aligned.columns).replace(0, np.nan) 

        if not p0_flows_aligned.empty and not s_nom_capacities.isna().all(): # Ensure s_nom is not all NaN
            # Calculate loading: abs(flow) / capacity. Transpose for easier division.
            # Loading is calculated per snapshot, then averaged over time.
            # Broadcasting s_nom_capacities across the time index of p0_flows_aligned.
            loading_ratio_timeseries = p0_flows_aligned.abs().div(s_nom_capacities, axis=1) # Result is MW/MVA or p.u. if s_nom is base
            
            # Average loading over the effective_snapshots period for each line
            average_loading_percentage = loading_ratio_timeseries.mean(axis=0) * 100 # Mean over time (axis=0)
            
            # Filter out lines with negligible loading and sort
            significant_loading_lines = average_loading_percentage[average_loading_percentage.abs() > 0.1].sort_values(ascending=False)
            
            for line_name, load_percentage_val in significant_loading_lines.items():
                line_loading_records.append({"line": line_name, "loading": round(load_percentage_val, 2)})
    return line_loading_records

# --- Payload Formatting Functions (for API responses) ---

def dispatch_data_payload_former(n, snapshots_slice=None, resolution="1H", **kwargs) -> Dict[str, Any]: # Added type hint
    """Format dispatch data for API response."""
    # Corrected call to get_dispatch_data
    gen_dispatch, load_dispatch, storage_units_disp, stores_disp = get_dispatch_data(
        n, 
        _snapshots_slice=snapshots_slice, 
        resolution=resolution
    )
    
    final_data_index = pd.DataFrame().index 
    if not gen_dispatch.empty: final_data_index = gen_dispatch.index
    elif not load_dispatch.empty: final_data_index = load_dispatch.index
    elif not storage_units_disp.empty: final_data_index = storage_units_disp.index
    elif not stores_disp.empty: final_data_index = stores_disp.index
    
    timestamps_for_payload = [str(ts) for ts in get_time_index(final_data_index)] if not final_data_index.empty else []
    
    load_data_records = []
    if not load_dispatch.empty and not load_dispatch.isna().all():
        # Assuming load_dispatch is a Series with a DatetimeIndex (or similar)
        for idx_val, series_val in load_dispatch.items(): 
            load_data_records.append(OrderedDict([('timestamp', str(idx_val)), ('load', series_val if pd.notna(series_val) else 0.0)]))
    
    return {
        'generation': gen_dispatch.reset_index().to_dict('records', into=OrderedDict) if not gen_dispatch.empty else [],
        'load': load_data_records,
        'storage': storage_units_disp.reset_index().to_dict('records', into=OrderedDict) if not storage_units_disp.empty else [],
        'store': stores_disp.reset_index().to_dict('records', into=OrderedDict) if not stores_disp.empty else [],
        'timestamps': timestamps_for_payload,
    }

def get_dispatch_data(_n: pypsa.Network, _snapshots_slice: Optional[Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]] = None,
                     resolution: str = "1H") -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.DataFrame]:
    effective_snapshots = get_effective_snapshots(_n, _snapshots_slice)
    if effective_snapshots.empty:
        logging.warning("get_dispatch_data: Effective snapshots are empty. Returning empty data structures.")
        return pd.DataFrame(), pd.Series(dtype=float), pd.DataFrame(), pd.DataFrame()

    logging.info(f"get_dispatch_data: Extracting dispatch data for {len(effective_snapshots)} effective_snapshots, resolution: {resolution}.")
    
    gen_dispatch_agg = pd.DataFrame(index=effective_snapshots)
    load_dispatch_sum = pd.Series(0.0, index=effective_snapshots) 
    storage_units_dispatch_agg = pd.DataFrame(index=effective_snapshots)
    stores_dispatch_agg = pd.DataFrame(index=effective_snapshots)

    carriers_df = _n.carriers if hasattr(_n, 'carriers') and isinstance(_n.carriers, pd.DataFrame) else pd.DataFrame()
 
    
    
    carriers_df['nice_name'] = carriers_df.index
    carriers_df.to_csv('debug/carrier.csv')  
    # Generators
    if hasattr(_n, 'generators') and hasattr(_n, 'generators_t') and 'p' in _n.generators_t:
        df_static_gens = getattr(_n, 'generators', pd.DataFrame())

        comp_t_data_gens = _n.generators_t.p
        if not df_static_gens.empty and not comp_t_data_gens.empty:
            carrier_map_gens = get_carrier_map(df_static_gens, carriers_df, 'Generator') # Default name if carrier is missing
            if carrier_map_gens is not None:
                aligned_data_gens = comp_t_data_gens.reindex(index=effective_snapshots, columns=df_static_gens.index).fillna(0)
                cols_for_grouping_gens = aligned_data_gens.columns.intersection(carrier_map_gens.index)
                if not cols_for_grouping_gens.empty:
                    carrier_map_slice_gens = carrier_map_gens.loc[cols_for_grouping_gens]
                    if not carrier_map_slice_gens.empty:
                        gen_dispatch_agg_temp = aligned_data_gens[cols_for_grouping_gens].groupby(
                            carrier_map_slice_gens, axis=1
                        ).sum()
                        for col in gen_dispatch_agg_temp.columns:
                            gen_dispatch_agg[col] = gen_dispatch_agg_temp[col]
    gen_dispatch_agg.to_csv('debug/generators_gen.csv')
    # Loads
    if hasattr(_n, 'loads') and hasattr(_n, 'loads_t'):
        df_static_loads = getattr(_n, 'loads', pd.DataFrame())
        load_p_attr = 'p_set' if 'p_set' in _n.loads_t else 'p' if 'p' in _n.loads_t else None
        if load_p_attr:
            comp_t_data_loads = _n.loads_t.get(load_p_attr)
            if not df_static_loads.empty and comp_t_data_loads is not None and not comp_t_data_loads.empty:
                aligned_data_loads = comp_t_data_loads.reindex(index=effective_snapshots, columns=df_static_loads.index).fillna(0)
                load_dispatch_sum.update(aligned_data_loads.sum(axis=1)) 

    # Storage Units and Stores
    for comp_name, df_out, default_suffix in [
        ('storage_units', storage_units_dispatch_agg, 'StorageUnit'),
        ('stores', stores_dispatch_agg, 'Store')
    ]:
        if hasattr(_n, comp_name) and hasattr(_n, f"{comp_name}_t") and 'p' in getattr(_n, f"{comp_name}_t", {}):
            df_static_storage = getattr(_n, comp_name, pd.DataFrame())
            comp_t_data_storage = getattr(_n, f"{comp_name}_t").p 
            if not df_static_storage.empty and not comp_t_data_storage.empty:
                carrier_map_storage = get_carrier_map(df_static_storage, carriers_df, default_suffix)
                if carrier_map_storage is not None:
                    aligned_data_storage = comp_t_data_storage.reindex(index=effective_snapshots, columns=df_static_storage.index).fillna(0)
                    cols_for_grouping_storage = aligned_data_storage.columns.intersection(carrier_map_storage.index)
                    if not cols_for_grouping_storage.empty:
                        carrier_map_slice_storage = carrier_map_storage.loc[cols_for_grouping_storage]
                        if not carrier_map_slice_storage.empty:
                            grouped_p_storage = aligned_data_storage[cols_for_grouping_storage].groupby(
                                carrier_map_slice_storage, axis=1
                            ).sum()
                            for carrier in grouped_p_storage.columns:
                                df_out[f"{carrier} Discharge"] = grouped_p_storage[carrier].clip(lower=0)
                                df_out[f"{carrier} Charge"] = grouped_p_storage[carrier].clip(upper=0) # Negative is charge

    # Final cleanup of all-zero columns and resampling
    gen_dispatch_agg = gen_dispatch_agg.loc[:, (gen_dispatch_agg.abs() > 1e-6).any(axis=0)]
    storage_units_dispatch_agg = storage_units_dispatch_agg.loc[:, (storage_units_dispatch_agg.abs() > 1e-6).any(axis=0)]
    stores_dispatch_agg = stores_dispatch_agg.loc[:, (stores_dispatch_agg.abs() > 1e-6).any(axis=0)]
    
    if resolution != "1H":
        time_idx_resample = get_time_index(effective_snapshots)
        if time_idx_resample is not None and not time_idx_resample.empty:
            def _resample_safe(df_series, base_idx_for_time):
                if df_series.empty: return df_series
                temp = df_series.copy()
                current_time_idx = get_time_index(temp.index)
                if current_time_idx is None or current_time_idx.empty:
                    base_time_idx = get_time_index(base_idx_for_time)
                    if base_time_idx is None or base_time_idx.empty:
                        logging.warning(f"Cannot resample for resolution {resolution}: no valid DatetimeIndex available.")
                        return df_series 
                    temp.index = base_time_idx
                else:
                    temp.index = current_time_idx
                
                if not isinstance(temp.index, pd.DatetimeIndex) or temp.index.empty:
                     logging.warning(f"Resampling skipped for resolution {resolution}: Index is not a valid DatetimeIndex or is empty.")
                     return df_series
                return temp.resample(resolution).mean()

            gen_dispatch_agg = _resample_safe(gen_dispatch_agg, effective_snapshots)
            load_dispatch_sum = _resample_safe(load_dispatch_sum, effective_snapshots)
            storage_units_dispatch_agg = _resample_safe(storage_units_dispatch_agg, effective_snapshots)
            stores_dispatch_agg = _resample_safe(stores_dispatch_agg, effective_snapshots)
        else:
            logging.warning(f"Cannot resample to {resolution}, DatetimeIndex not available from effective_snapshots.")
            
    return gen_dispatch_agg, load_dispatch_sum, storage_units_dispatch_agg, stores_dispatch_agg

def carrier_capacity_payload_former(n, snapshots_slice=None, attribute="p_nom_opt", **kwargs) -> Dict[str, Any]:
    """Formats carrier and bus capacity data. `period` from kwargs is for asset filtering."""
    period_for_assets = kwargs.get('period') # This 'period' is for build_year/lifetime filtering
    
    df_capacity_by_carrier = get_carrier_capacity(n, attribute=attribute, period_val_for_assets=period_for_assets)
    df_capacity_by_region = get_buses_capacity(n, attribute=attribute, period_val_for_assets=period_for_assets)
    
    return {
        'by_carrier': df_capacity_by_carrier.to_dict('records', into=OrderedDict) if not df_capacity_by_carrier.empty else [],
        'by_region': df_capacity_by_region.to_dict('records', into=OrderedDict) if not df_capacity_by_region.empty else [],
    }

def combined_metrics_extractor_wrapper(n, snapshots_slice=None, **kwargs) -> Dict[str, Any]:
    """Combines CUF and curtailment metrics for API response."""
    cuf_data_df = calculate_cuf(n, snapshots_slice=snapshots_slice)
    curtailment_data_df = calculate_curtailment(n, snapshots_slice=snapshots_slice)
    return {
        'cuf': cuf_data_df.to_dict('records', into=OrderedDict) if not cuf_data_df.empty else [],
        'curtailment': curtailment_data_df.to_dict('records', into=OrderedDict) if not curtailment_data_df.empty else []
    }

def extract_api_storage_data_payload_former(n, snapshots_slice=None, resolution="1H", **kwargs) -> Dict[str, Any]:
    """Formats storage SoC and charge/discharge statistics for API."""
    soc_df_processed = get_storage_soc(n, snapshots_slice=snapshots_slice)
    
    time_idx_for_soc_resample = get_time_index(soc_df_processed.index)
    soc_df_final_for_plot = soc_df_processed 
    if resolution != "1H" and time_idx_for_soc_resample is not None and not time_idx_for_soc_resample.empty:
        soc_df_temp_for_resample = soc_df_processed.copy()
        soc_df_temp_for_resample.index = time_idx_for_soc_resample 
        soc_df_final_for_plot = soc_df_temp_for_resample.resample(resolution).mean()
    
    timestamps_for_soc_payload = [str(ts) for ts in get_time_index(soc_df_final_for_plot.index)] if not soc_df_final_for_plot.empty else []
    storage_types_in_soc_payload = soc_df_final_for_plot.columns.tolist()

    _, _, storage_units_dispatch, stores_dispatch = get_dispatch_data(n, _snapshots_slice=snapshots_slice, resolution=resolution)
    all_storage_dispatch_data = pd.concat([storage_units_dispatch, stores_dispatch], axis=1).fillna(0)
    
    storage_stats_records = []
    if not all_storage_dispatch_data.empty:
        weights_for_dispatch_stats = get_snapshot_weights(n, all_storage_dispatch_data.index)
        
        charge_columns_in_dispatch = [c for c in all_storage_dispatch_data.columns if 'Charge' in c and all_storage_dispatch_data[c].abs().sum() > 1e-3]
        discharge_columns_in_dispatch = [c for c in all_storage_dispatch_data.columns if 'Discharge' in c and all_storage_dispatch_data[c].abs().sum() > 1e-3]
        processed_storage_bases = set()
        
        for discharge_col_name in discharge_columns_in_dispatch:
            base_name_match = discharge_col_name.replace(" Discharge", "") 
            if base_name_match in processed_storage_bases: continue

            charge_col_match_name = next((c_col for c_col in charge_columns_in_dispatch if c_col.replace(" Charge", "") == base_name_match), None)

            if charge_col_match_name:
                discharge_series = all_storage_dispatch_data[discharge_col_name]
                charge_series = all_storage_dispatch_data[charge_col_match_name] 

                total_discharged_energy = (discharge_series * weights_for_dispatch_stats).sum()
                total_charged_energy = abs((charge_series * weights_for_dispatch_stats).sum()) 
                
                efficiency_percent = (total_discharged_energy / total_charged_energy * 100) if total_charged_energy > 1e-6 else np.nan
                
                storage_stats_records.append(OrderedDict([
                    ('Storage_Type', base_name_match), 
                    ('Charge_MWh', total_charged_energy),
                    ('Discharge_MWh', total_discharged_energy),
                    ('Efficiency_Percent', efficiency_percent if pd.notna(efficiency_percent) else None)
                ]))
                processed_storage_bases.add(base_name_match)
    
    return {
        'soc': soc_df_final_for_plot.reset_index().to_dict('records', into=OrderedDict) if not soc_df_final_for_plot.empty else [],
        'stats': storage_stats_records,
        'timestamps': timestamps_for_soc_payload, 
        'storage_types': storage_types_in_soc_payload 
    }

def emissions_payload_former(n, snapshots_slice=None, period_name=None, **kwargs) -> Dict[str, Any]:
    """Formats CO2 emissions data. `period_name` from URL for multi-period asset filtering."""
    total_emissions_df, emissions_by_carrier_df = calculate_co2_emissions(n, snapshots_slice=snapshots_slice)
    
    if period_name:
        if not total_emissions_df.empty and 'Period' in total_emissions_df.columns:
            total_emissions_df = total_emissions_df[total_emissions_df['Period'] == str(period_name)]
        if not emissions_by_carrier_df.empty and 'Period' in emissions_by_carrier_df.columns:
            emissions_by_carrier_df = emissions_by_carrier_df[emissions_by_carrier_df['Period'] == str(period_name)]
            
    return {
        'total': total_emissions_df.to_dict('records', into=OrderedDict) if not total_emissions_df.empty else [],
        'by_carrier': emissions_by_carrier_df.to_dict('records', into=OrderedDict) if not emissions_by_carrier_df.empty else []
    }

def extract_api_prices_data_payload_former(n, snapshots_slice=None, resolution="1H", **kwargs) -> Dict[str, Any]:
    """Formats marginal price data for API response."""
    price_data_processed = calculate_marginal_prices(n, snapshots_slice=snapshots_slice, resolution=resolution)
    
    if price_data_processed.empty:
        return {'available': False, 'message': 'No marginal prices available for the selected criteria.'}

    unit_str = "currency/MWh" 
    if hasattr(n, 'buses') and 'unit' in n.buses.columns and not n.buses.unit.empty:
        bus_unit = n.buses.unit.dropna().iloc[0] if not n.buses.unit.dropna().empty else "currency"
        unit_str = f"{bus_unit}/MWh"
    
    avg_prices_by_bus = price_data_processed.mean(axis=0).sort_values(ascending=False) 
    min_prices_by_bus = price_data_processed.min(axis=0)
    max_prices_by_bus = price_data_processed.max(axis=0)
    
    avg_price_records = []
    for bus_id, avg_price_val in avg_prices_by_bus.items():
        avg_price_records.append(OrderedDict([
            ('bus', bus_id),
            ('price', avg_price_val if pd.notna(avg_price_val) else None),
            ('min_price', min_prices_by_bus.get(bus_id) if pd.notna(min_prices_by_bus.get(bus_id)) else None),
            ('max_price', max_prices_by_bus.get(bus_id) if pd.notna(max_prices_by_bus.get(bus_id)) else None),
        ]))
    
    if price_data_processed.shape[1] > 1: 
        system_avg_price_per_snapshot = price_data_processed.mean(axis=1).dropna()
    else: 
        system_avg_price_per_snapshot = price_data_processed.iloc[:, 0].dropna()
        
    duration_curve_values = sorted(system_avg_price_per_snapshot.values, reverse=True) if not system_avg_price_per_snapshot.empty else []
    
    timestamps_for_payload = [str(ts) for ts in get_time_index(price_data_processed.index)] if not price_data_processed.empty else []

    return {
        'available': True,
        'unit': unit_str,
        'avg_by_bus': avg_price_records,
        'duration_curve': [float(p) for p in duration_curve_values], 
        'timestamps': timestamps_for_payload, 
        'buses': price_data_processed.columns.tolist() 
    }

def extract_api_network_flow_payload_former(n, snapshots_slice=None, period_name=None, **kwargs) -> Dict[str, Any]:
    """Formats network flow (losses, line loading) data. `period_name` for multi-period output filtering."""
    losses_df = calculate_network_losses(n, snapshots_slice=snapshots_slice)
    line_loading_records = calculate_line_loading(n, snapshots_slice=snapshots_slice)

    if period_name:
        if not losses_df.empty and 'Period' in losses_df.columns:
            losses_df = losses_df[losses_df['Period'] == str(period_name)]
    
    return {
        'losses': losses_df.to_dict('records', into=OrderedDict) if not losses_df.empty else [],
        'line_loading': line_loading_records 
    }

# --- Color Palette Generation ---
def get_color_palette(_n: pypsa.Network) -> Dict[str, str]:
    logging.debug("get_color_palette: Generating color palette...")
    final_colors = DEFAULT_COLORS.copy()
    color_idx_cycle = 0 
    
    def add_color_if_new(name, existing_colors_dict, cycle_idx_ref):
        if name not in existing_colors_dict:
            matched_default = False
            for default_key, default_color_val in DEFAULT_COLORS.items():
                if default_key.lower() in str(name).lower():
                    existing_colors_dict[name] = default_color_val
                    matched_default = True
                    break
            if not matched_default:
                existing_colors_dict[name] = PLOTLY_COLOR_CYCLE[cycle_idx_ref[0] % len(PLOTLY_COLOR_CYCLE)]
                cycle_idx_ref[0] += 1
        return existing_colors_dict[name] 

    if hasattr(_n, "carriers") and isinstance(_n.carriers, pd.DataFrame) and not _n.carriers.empty:
        carriers_df_copy = _n.carriers.copy()
      
        carriers_df_copy['nice_name'] = carriers_df_copy.index
        
        for carrier_idx, row_data in carriers_df_copy.iterrows():
            original_carrier_name = str(carrier_idx)
            nice_carrier_name = str(row_data.get("nice_name", original_carrier_name))
            
            color_in_df = row_data.get("color") if "color" in row_data and pd.notna(row_data["color"]) and row_data["color"] != "" else None
            
            if color_in_df:
                final_colors[nice_carrier_name] = color_in_df
                if nice_carrier_name != original_carrier_name:
                    final_colors[original_carrier_name] = color_in_df 
            else:
                color_for_nice_name = add_color_if_new(nice_carrier_name, final_colors, [color_idx_cycle])
                if nice_carrier_name != original_carrier_name and original_carrier_name not in final_colors:
                    final_colors[original_carrier_name] = color_for_nice_name
    
    all_component_carrier_names = set()
    for comp_type_plural in ['generators', 'storage_units', 'stores', 'links']: 
        if hasattr(_n, comp_type_plural):
            comp_df = getattr(_n, comp_type_plural)
            if isinstance(comp_df, pd.DataFrame) and not comp_df.empty and 'carrier' in comp_df.columns:
                unique_carriers_in_comp = comp_df['carrier'].dropna().unique()
                for orig_carrier_name_in_comp in unique_carriers_in_comp:
                    nice_name_from_carriers_df = orig_carrier_name_in_comp 
                    if hasattr(_n, 'carriers') and isinstance(_n.carriers, pd.DataFrame) and \
                       'nice_name' in _n.carriers.columns and orig_carrier_name_in_comp in _n.carriers.index:
                        val = _n.carriers.loc[orig_carrier_name_in_comp, 'nice_name']
                        if pd.notna(val): nice_name_from_carriers_df = val
                    
                    all_component_carrier_names.add(str(nice_name_from_carriers_df))
                    if str(nice_name_from_carriers_df) != str(orig_carrier_name_in_comp):
                         all_component_carrier_names.add(str(orig_carrier_name_in_comp))

    for name_to_color in sorted(list(all_component_carrier_names)):
        add_color_if_new(name_to_color, final_colors, [color_idx_cycle])

    for charge_discharge_key in ['Storage Charge', 'Storage Discharge', 'Store Charge', 'Store Discharge']:
        if charge_discharge_key not in final_colors and charge_discharge_key in DEFAULT_COLORS:
            final_colors[charge_discharge_key] = DEFAULT_COLORS[charge_discharge_key]
            
    for comp_name_key in final_colors.copy().keys(): 
        if any(st_kw in comp_name_key.lower() for st_kw in ['storage', 'store', 'battery', 'psp', 'hydro', 'h2']):
             add_color_if_new(f"{comp_name_key} Charge", final_colors, [color_idx_cycle])
             add_color_if_new(f"{comp_name_key} Discharge", final_colors, [color_idx_cycle])

    logging.debug(f"get_color_palette: Final palette has {len(final_colors)} entries.")
    return final_colors
def get_carrier_capacity_new_addition(_n: pypsa.Network, method: str = 'optimization_diff', period_val_for_assets: Optional[Any] = None) -> pd.DataFrame:
    """
    Gets new capacity additions by carrier.
    - 'optimization_diff': p_nom_opt - p_nom (or e_nom_opt - e_nom for stores).
    - 'build_year': Capacity of assets with build_year == period_val_for_assets.
    `period_val_for_assets` is used for filtering assets in multi-period or for 'build_year' method.
    """
    logging.info(f"get_carrier_capacity_new_addition: Method='{method}'" +
                 (f", Period='{period_val_for_assets}'" if period_val_for_assets is not None else ""))

    capacity_additions_list = []
    carriers_df = _n.carriers if hasattr(_n, 'carriers') and isinstance(_n.carriers, pd.DataFrame) else pd.DataFrame()
    if not hasattr(carriers_df, 'nice_name'):
        carriers_df['nice_name'] = carriers_df.index

    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}

    for comp_class_name, comp_attr_name_in_n in components_to_check.items():
        if hasattr(_n, comp_attr_name_in_n):
            df_component_static = getattr(_n, comp_attr_name_in_n, pd.DataFrame())
            if df_component_static.empty: continue

            # Determine active assets based on period_val_for_assets
            df_active_assets = df_component_static
            if period_val_for_assets is not None and 'build_year' in df_component_static.columns and 'lifetime' in df_component_static.columns:
                try:
                    build_year_series = df_component_static['build_year']
                    if not build_year_series.empty:
                        typed_period = type(build_year_series.iloc[0])(period_val_for_assets)
                        active_mask = (build_year_series <= typed_period) & \
                                      ((build_year_series + df_component_static['lifetime']) > typed_period)
                        df_active_assets = df_component_static[active_mask]
                except Exception as e_filter:
                    logging.warning(f"Could not filter active assets for {comp_class_name} in period {period_val_for_assets}: {e_filter}.")

            if df_active_assets.empty: continue

            carrier_map = get_carrier_map(df_active_assets, carriers_df, default_carrier_name=comp_class_name)
            if carrier_map is None: continue

            new_capacity_series = pd.Series(dtype=float)

            if method == 'optimization_diff':
                nom_attr = 'p_nom'
                nom_opt_attr = 'p_nom_opt'
                if comp_class_name == 'Store':
                    nom_attr = 'e_nom'
                    nom_opt_attr = 'e_nom_opt'

                if nom_attr in df_active_assets.columns and nom_opt_attr in df_active_assets.columns:
                    new_capacity_series = (df_active_assets[nom_opt_attr] - df_active_assets[nom_attr]).clip(lower=0)
                else:
                    logging.debug(f"Required attributes for 'optimization_diff' not in {comp_class_name}. Opt: {nom_opt_attr}, Nom: {nom_attr}")

            elif method == 'build_year':
                if 'build_year' in df_active_assets.columns and period_val_for_assets is not None:
                    # Ensure period_val_for_assets is compatible type for comparison
                    build_year_series_active = df_active_assets['build_year']
                    if not build_year_series_active.empty:
                        typed_period_for_build_year = type(build_year_series_active.iloc[0])(period_val_for_assets)
                        built_in_period_mask = (build_year_series_active == typed_period_for_build_year)
                        
                        df_built_in_period = df_active_assets[built_in_period_mask]
                        
                        if not df_built_in_period.empty:
                            cap_attr_for_build_year = 'p_nom_opt' if 'p_nom_opt' in df_built_in_period.columns else 'p_nom'
                            if comp_class_name == 'Store':
                                cap_attr_for_build_year = 'e_nom_opt' if 'e_nom_opt' in df_built_in_period.columns else 'e_nom'
                            
                            if cap_attr_for_build_year in df_built_in_period.columns:
                                new_capacity_series = df_built_in_period[cap_attr_for_build_year]
                            else:
                                logging.debug(f"Capacity attribute for 'build_year' method not found in {comp_class_name}: {cap_attr_for_build_year}")
                    else:
                        logging.debug(f"Build_year column empty for {comp_class_name}, cannot use 'build_year' method.")

            if not new_capacity_series.empty:
                summed_new_capacity = new_capacity_series.groupby(carrier_map).sum()
                capacity_additions_list.append(summed_new_capacity)

    if capacity_additions_list:
        final_combined_additions = pd.concat(capacity_additions_list).groupby(level=0).sum()
        result_df = final_combined_additions.reset_index()
        result_df.columns = ['Carrier', 'New_Capacity'] # Consistent column name
        
        # Determine unit based on the attributes likely used
        # This is a simplification; if mixing p_nom and e_nom additions, unit could be ambiguous
        # For 'build_year', it depends on what attribute was summed.
        # For 'optimization_diff', it's usually power (MW) or energy (MWh) based on component.
        # A more robust solution might need to track units per component type if mixing.
        unit_for_additions = 'MW/MWh' # Generic if mixed
        if method == 'build_year' or method == 'optimization_diff':
             # Check if any 'e_nom' related attributes were likely involved (for Stores)
            if any('e_nom' in col for col in df_component_static.columns if comp_class_name == 'Store'):
                unit_for_additions = 'MWh'
            else:
                unit_for_additions = 'MW'
                
        result_df['Unit'] = unit_for_additions
        result_df = result_df[result_df['New_Capacity'].abs() > 1e-6]
        return result_df
    else:
        return pd.DataFrame(columns=['Carrier', 'New_Capacity', 'Unit'])


# --- NEW PAYLOAD FORMER for New Capacity Additions ---
def new_capacity_additions_payload_former(n, snapshots_slice=None, **kwargs) -> Dict[str, Any]:
    """Formats new capacity additions data for API response."""
    method = kwargs.get('method', 'optimization_diff') # Get method from request or default
    period_for_assets = kwargs.get('period') # Period for asset filtering or build_year matching

    df_new_additions = get_carrier_capacity_new_addition(n, method=method, period_val_for_assets=period_for_assets)
    
    return {
        'new_additions': df_new_additions.to_dict('records', into=OrderedDict) if not df_new_additions.empty else [],
    }