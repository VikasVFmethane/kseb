
# import pypsa
# import pandas as pd
# import numpy as np
# import plotly.express as px
# import plotly.graph_objects as go
# import logging
# from typing import Union, Optional, Tuple, Dict, List, Any
# from plotly.subplots import make_subplots

# # Logging configuration
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# # Default color palette
# DEFAULT_COLORS = {
#     'Coal': '#000000', 'coal': '#000000',
#     'Lignite': '#4B4B4B', 'lignite': '#4B4B4B',
#     'Nuclear': '#800080', 'nuclear': '#800080',
#     'Hydro': '#0073CF', 'hydro': '#0073CF',
#     'Hydro RoR': '#3399FF', 'ror': '#3399FF', 'Hydro Storage': '#3399FF',
#     'Solar': '#FFD700', 'solar': '#FFD700', 'pv': '#FFD700',
#     'Wind': '#ADD8E6', 'wind': '#ADD8E6', 'onwind': '#ADD8E6', 'offwind': '#ADD8E6',
#     'LFO': '#FF4500', 'lfo': '#FF4500', 'Oil': '#FF4500', 'oil': '#FF4500',
#     'Co-Gen': '#228B22', 'co-gen': '#228B22', 'biomass': '#228B22',
#     'PSP': '#3399FF', 'psp': '#3399FF',
#     'Battery Storage': '#005B5B', 'battery': '#005B5B',
#     'Planned Battery Storage': '#66B2B2', 'planned battery': '#66B2B2',
#     'Planned PSP': '#B0C4DE', 'planned psp': '#B0C4DE',
#     'Storage': '#B0C4DE',
#     'H2 Storage': '#AFEEEE', 'hydrogen': '#AFEEEE', 'h2': '#AFEEEE', 'H2': '#AFEEEE',
#     'Load': '#000000',
#     'Transmission': '#808080', 'Line': '#808080', 'Link': '#A9A9A9',
#     'Losses': '#DC143C',
#     'Other': '#D3D3D3',
#     'Curtailment': '#FF00FF',
#     'Excess': '#FF00FF',
#     'Storage Charge': '#FFA500',
#     'Storage Discharge': '#FFA500',
#     'Store Charge': '#AFEEEE',
#     'Store Discharge': '#AFEEEE',
# }

# PLOTLY_COLOR_CYCLE = px.colors.qualitative.Plotly

# def safe_get_snapshots(n: pypsa.Network) -> Union[pd.DatetimeIndex, pd.MultiIndex]:
#     return n.snapshots

# def get_time_index(index: Union[pd.DatetimeIndex, pd.MultiIndex]) -> pd.DatetimeIndex:
#     if isinstance(index, pd.MultiIndex):
#         time_level = index.get_level_values(-1)
#         if pd.api.types.is_datetime64_any_dtype(time_level):
#             return time_level
#         else:
#             try:
#                 return pd.to_datetime(time_level)
#             except Exception as e:
#                 logging.error(f"Could not convert MultiIndex level 1 to DatetimeIndex: {e}")
#                 raise TypeError("MultiIndex level 1 is not datetime-like.")
#     elif isinstance(index, pd.DatetimeIndex):
#         return index
#     else:
#         try:
#             return pd.to_datetime(index)
#         except Exception as e:
#             logging.error(f"Cannot convert index of type {type(index)} to DatetimeIndex: {e}")
#             raise TypeError(f"Unsupported snapshot index type: {type(index)}")

# def get_period_index(index: Union[pd.DatetimeIndex, pd.MultiIndex]) -> Union[pd.Index, pd.Series]:
#     if isinstance(index, pd.MultiIndex):
#         return index.get_level_values(0)
#     elif isinstance(index, pd.DatetimeIndex):
#         return pd.Series(index.year, index=index)
#     else:
#         logging.warning(f"Cannot determine period index from type {type(index)}. Returning None.")
#         return None

# def get_snapshot_weights(n: pypsa.Network, snapshots_idx: Union[pd.DatetimeIndex, pd.MultiIndex]) -> pd.Series:
#     if hasattr(n, 'snapshot_weightings') and not n.snapshot_weightings.empty and 'objective' in n.snapshot_weightings.columns:
#         weights = n.snapshot_weightings.objective
#         common_index = snapshots_idx.intersection(weights.index)
#         if common_index.empty:
#             logging.warning("No common index between snapshots and snapshot_weightings. Assuming weight 1.0.")
#             return pd.Series(1.0, index=snapshots_idx)
#         else:
#             return weights.reindex(common_index).reindex(snapshots_idx).fillna(1.0)
#     else:
#         logging.warning("Snapshot weights ('objective') not found or empty. Assuming weight 1.0 for all snapshots.")
#         return pd.Series(1.0, index=snapshots_idx)
# def dispatch_data_payload_former(n, snapshots_slice=None, resolution="1H", **kwargs):
#     """Format dispatch data for API response."""
#     gen_dispatch, load_dispatch, storage_difextract_api_network_flow_payload_formerspatch, store_dispatch = get_dispatch_data(
#         n, 
#         _snapshots_slice=snapshots_slice, 
#         resolution=resolution
#     )
    
#     # Get time index for timestamps
#     if snapshots_slice is not None and not snapshots_slice.empty:
#         time_index = get_time_index(snapshots_slice)
#     else:
#         time_index = get_time_index(safe_get_snapshots(n))
    
#     timestamps = [str(ts) for ts in time_index] if time_index is not None and not isinstance(time_index, type(None)) else []
    
#     # Convert load series to dictionary format
#     load_data = []
#     if not load_dispatch.empty and not load_dispatch.isna().all():
#         for idx, val in load_dispatch.items():
#             load_data.append({'timestamp': str(idx) if not isinstance(idx, str) else idx, 'load': val})
    
#     # Convert DataFrames to dictionary records format
#     return {
#         'generation': gen_dispatch.reset_index().to_dict('records') if not gen_dispatch.empty else [],
#         'load': load_data,
#         'storage': storage_dispatch.reset_index().to_dict('records') if not storage_dispatch.empty else [],
#         'store': store_dispatch.reset_index().to_dict('records') if not store_dispatch.empty else [],
#         'timestamps': timestamps,
#         'colors': {}  # Color palette will be added by the API wrapper function
#     }
# def resample_data(data_df, time_index, resolution):
#     if not isinstance(time_index, pd.DatetimeIndex):
#         logging.warning(f"Cannot resample data to {resolution}. Index is not a DatetimeIndex.")
#         return data_df
#     df_resampled = data_df.copy()
#     df_resampled.index = time_index
#     return df_resampled.resample(resolution).mean()
# def resample_data_df(data_df, time_index, resolution):
#     """Resample data frame with time index to desired resolution."""
#     if not isinstance(time_index, pd.DatetimeIndex):
#         logging.warning(f"Cannot resample data to {resolution}. Index is not a DatetimeIndex.")
#         return data_df
    
#     # Create a copy of the DataFrame with datetime index
#     df_resampled = data_df.copy()
#     if not isinstance(df_resampled.index, pd.DatetimeIndex):
#         df_resampled.index = time_index
    
#     # Resample
#     return df_resampled.resample(resolution).mean()

# def extract_api_storage_data_payload_former(n, snapshots_slice, resolution, **kwargs):
#     """Extract and format storage data for API response."""
#     soc_df_full = get_storage_soc(n)
#     soc_df_for_slice = pd.DataFrame()
#     if not soc_df_full.empty and not snapshots_slice.empty:
#         common_idx = soc_df_full.index.intersection(snapshots_slice)
#         if not common_idx.empty:
#             soc_df_for_slice = soc_df_full.loc[common_idx]
    
#     time_comp_slice = get_time_index(snapshots_slice)
#     final_timestamps = [str(ts) for ts in time_comp_slice] if time_comp_slice is not None and not time_comp_slice.empty else []
#     storage_types = soc_df_for_slice.columns.tolist() if not soc_df_for_slice.empty else []

#     # Get storage unit and store dispatch data
#     _, _, storage_units_disp, stores_disp = get_dispatch_data(n, _snapshots_slice=snapshots_slice, resolution=resolution)
#     all_storage_disp = pd.concat([storage_units_disp, stores_disp], axis=1).fillna(0)
    
#     storage_stats = []
#     if not all_storage_disp.empty and not snapshots_slice.empty:
#         weights = get_snapshot_weights(n, snapshots_slice)
#         charge_cols = [c for c in all_storage_disp.columns if 'Charge' in c and all_storage_disp[c].abs().sum() > 1e-3]
#         disch_cols = [c for c in all_storage_disp.columns if 'Discharge' in c and all_storage_disp[c].abs().sum() > 1e-3]
#         processed_bases = set()
        
#         for dcol in disch_cols:
#             base = dcol.replace(" Discharge", "").replace(" (StorageUnit)", "").replace(" (Store)", "").strip()
#             if base in processed_bases:
#                 continue
            
#             ccol_match = next((c for c in charge_cols if base in c), None)
#             if ccol_match:
#                 d_series, ch_series, w_s = all_storage_disp[dcol], all_storage_disp[ccol_match], weights
#                 common_idx_stats = d_series.index.intersection(ch_series.index).intersection(w_s.index)
                
#                 if not common_idx_stats.empty:
#                     d_energy = (d_series.loc[common_idx_stats] * w_s.loc[common_idx_stats]).sum()
#                     ch_energy = abs((ch_series.loc[common_idx_stats] * w_s.loc[common_idx_stats]).sum())
#                     eff = (d_energy / ch_energy * 100) if ch_energy > 1e-6 else np.nan
                    
#                     storage_stats.append({
#                         'Storage_Type': base,
#                         'Charge_MWh': ch_energy,
#                         'Discharge_MWh': d_energy,
#                         'Efficiency_Percent': eff if pd.notna(eff) else None
#                     })
#                     processed_bases.add(base)
    
#     return {
#         'soc': soc_df_for_slice,
#         'stats': storage_stats,
#         'timestamps': final_timestamps,
#         'storage_types': storage_types
#     }

# def emissions_payload_former(n, period_name=None, **kwargs):
#     """Format emissions data for API response."""
#     total_emissions, emissions_by_carrier = calculate_co2_emissions(n)
    
#     if period_name and isinstance(safe_get_snapshots(n), pd.MultiIndex):
#         if 'Period' in total_emissions.columns:
#             total_emissions = total_emissions[total_emissions['Period'] == str(period_name)] 
#         if 'Period' in emissions_by_carrier.columns:
#             emissions_by_carrier = emissions_by_carrier[emissions_by_carrier['Period'] == str(period_name)]
    
#     return {
#         'total': total_emissions,
#         'by_carrier': emissions_by_carrier
#     }

# def combined_metrics_extractor_wrapper(n, snapshots_slice=None, **kwargs):
#     """Combine CUF and curtailment metrics for the API."""
#     return {
#         'cuf': calculate_cuf(n, snapshots_slice=snapshots_slice),
#         'curtailment': calculate_curtailment(n, snapshots_slice=snapshots_slice)
#     }

# def extract_api_prices_data_payload_former(n, resolution="1H", **kwargs):
#     """Extract and format marginal price data for API response."""
#     price_data_full_res = calculate_marginal_prices(n, resolution=resolution)
    
#     if price_data_full_res.empty:
#         return {'available': False, 'message': 'No marginal prices.'}

#     # Get time component from snapshots_slice if provided
#     snapshots_slice = kwargs.get('snapshots_slice')
#     time_component_of_slice = None
#     if snapshots_slice is not None and not snapshots_slice.empty:
#         time_component_of_slice = get_time_index(snapshots_slice)
#         price_data_filtered = price_data_full_res[price_data_full_res.index.isin(time_component_of_slice)]
#     else:
#         price_data_filtered = price_data_full_res
    
#     if price_data_filtered.empty:
#         return {'available': False, 'message': 'No prices for slice.'}
    
#     price_data_resampled = price_data_filtered
#     if resolution != "1H":
#         time_idx_resample = get_time_index(price_data_filtered.index)
#         if time_idx_resample is not None and isinstance(time_idx_resample, pd.DatetimeIndex) and not time_idx_resample.empty:
#             price_data_resampled = resample_data_df(price_data_filtered, time_idx_resample, resolution)
    
#     if price_data_resampled.empty:
#         return {'available': False, 'message': 'No prices after resampling.'}

#     unit_str = "$/MWh"  # Default
#     if hasattr(n, 'buses') and 'unit' in n.buses.columns and not n.buses.unit.empty and pd.notna(n.buses.unit.iloc[0]):
#         unit_str = f"{n.buses.unit.iloc[0]}/MWh"
    
#     avg_s = price_data_resampled.mean().sort_values(ascending=False)
#     min_s = price_data_resampled.min()
#     max_s = price_data_resampled.max()
    
#     avg_list = []
#     for b, p in avg_s.items():
#         avg_list.append({
#             'bus': b,
#             'price': p,
#             'min_price': min_s.get(b),
#             'max_price': max_s.get(b)
#         })
    
#     duration_c = sorted(price_data_resampled.mean(axis=1).dropna().values, reverse=True)
    
#     return {
#         'available': True,
#         'unit': unit_str,
#         'avg_by_bus': avg_list,
#         'duration_curve': [float(p) for p in duration_c],
#         'timestamps': [str(ts) for ts in price_data_resampled.index],
#         'buses': price_data_resampled.columns.tolist()
#     }

# def extract_api_network_flow_payload_former(n, snapshots_slice=None, period_name=None, **kwargs):
#     """Extract and format network flow data for API response."""
#     losses_df = calculate_network_losses(n)
    
#     if period_name and isinstance(safe_get_snapshots(n), pd.MultiIndex) and 'Period' in losses_df.columns:
#         losses_df = losses_df[losses_df['Period'] == str(period_name)]

#     line_loading_list = []
#     if 'lines' in n.components.keys() and hasattr(n, 'lines_t') and 'p0' in n.lines_t and not n.lines_t.p0.empty and \
#        's_nom' in n.lines.columns and not n.lines.empty:
#         p0_all = n.lines_t.p0
#         p0_sliced = p0_all[p0_all.index.isin(snapshots_slice)] if snapshots_slice is not None and not snapshots_slice.empty else p0_all
        
#         if not p0_sliced.empty:
#             s_nom = n.lines.s_nom.reindex(p0_sliced.columns).fillna(1e-6)  # Avoid division by zero
#             loading = (p0_sliced.abs().T / s_nom).T.mean(axis=0) * 100  # Mean loading as percentage
#             loading_f = loading[loading.abs() > 0.1].sort_values(ascending=False)  # Filter insignificant values
            
#             for ln, ld in loading_f.items():
#                 line_loading_list.append({"line": ln, "loading": round(ld, 2)})
    
#     return {
#         'losses': losses_df,
#         'line_loading': line_loading_list
#     }

# def get_color_palette(_n: pypsa.Network) -> Dict[str, str]:
#     logging.info("Generating color palette...")
#     final_colors = DEFAULT_COLORS.copy()
#     color_idx = 0
#     all_keys = set(final_colors.keys())

#     if hasattr(_n, "carriers") and not _n.carriers.empty:
#         carriers_df = _n.carriers
#         carriers_df['nice_name'] = carriers_df.index
#         has_color = "color" in carriers_df.columns
#         has_nice_name = "nice_name" in carriers_df.columns

#         if has_color and carriers_df["color"].notna().any():
#             for idx, row in carriers_df.iterrows():
#                 carrier_name = idx
#                 nice_name = row.get("nice_name") if has_nice_name and pd.notna(row.get("nice_name")) else carrier_name
#                 color = row.get("color") if has_color and pd.notna(row.get("color")) and row.get("color") != "" else None
#                 key_to_use = nice_name

#                 if color:
#                     final_colors[key_to_use] = color
#                     all_keys.add(key_to_use)
#                     if nice_name != carrier_name and carrier_name not in all_keys:
#                         final_colors[carrier_name] = color
#                         all_keys.add(carrier_name)
#                 else:
#                     matched = False
#                     for default_key, default_color in DEFAULT_COLORS.items():
#                         if default_key.lower() in key_to_use.lower() or default_key.lower() in carrier_name.lower():
#                             if key_to_use not in all_keys:
#                                 final_colors[key_to_use] = default_color
#                                 all_keys.add(key_to_use)
#                             if nice_name != carrier_name and carrier_name not in all_keys:
#                                 final_colors[carrier_name] = default_color
#                                 all_keys.add(carrier_name)
#                             matched = True
#                             break
#         else:
#             logging.info("No colors defined in carriers DataFrame. Using default colors.")
#             for carrier in carriers_df.index:
#                 nice_name = carrier
#                 if has_nice_name and pd.notna(carriers_df.loc[carrier, "nice_name"]):
#                     nice_name = carriers_df.loc[carrier, "nice_name"]
#                 matched = False
#                 for default_key, default_color in DEFAULT_COLORS.items():
#                     if default_key.lower() in str(carrier).lower() or (nice_name and default_key.lower() in str(nice_name).lower()):
#                         if carrier not in all_keys:
#                             final_colors[carrier] = default_color
#                             all_keys.add(carrier)
#                         if nice_name != carrier and nice_name not in all_keys:
#                             final_colors[nice_name] = default_color
#                             all_keys.add(nice_name)
#                         matched = True
#                         break
#                 if not matched:
#                     color = PLOTLY_COLOR_CYCLE[color_idx % len(PLOTLY_COLOR_CYCLE)]
#                     if carrier not in all_keys:
#                         final_colors[carrier] = color
#                         all_keys.add(carrier)
#                     if nice_name != carrier and nice_name not in all_keys:
#                         final_colors[nice_name] = color
#                         all_keys.add(nice_name)
#                     color_idx += 1

#     all_used_names = set()
#     for comp_name in ['generators', 'storage_units', 'stores', 'links']:
#         if hasattr(_n, comp_name):
#             df_comp = getattr(_n, comp_name)
#             if not df_comp.empty and 'carrier' in df_comp.columns:
#                 carrier_map = df_comp['carrier']
#                 if hasattr(_n, 'carriers') and 'nice_name' in _n.carriers.columns:
#                     nice_name_map = _n.carriers['nice_name'].dropna()
#                     carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
#                 all_used_names.update(carrier_map.dropna().unique())

#     all_used_names.update(_n.components.keys())
#     for name in sorted(list(all_used_names)):
#         if name not in all_keys:
#             matched = False
#             for default_key, default_color in DEFAULT_COLORS.items():
#                 if default_key.lower() in str(name).lower():
#                     final_colors[name] = default_color
#                     all_keys.add(name)
#                     matched = True
#                     break
#             if not matched:
#                 final_colors[name] = PLOTLY_COLOR_CYCLE[color_idx % len(PLOTLY_COLOR_CYCLE)]
#                 all_keys.add(name)
#                 color_idx += 1
#         is_storage = any(sub in str(name).lower() for sub in ['battery', 'phs', 'hydro', 'h2', 'storage', 'store'])
#         if is_storage:
#             base_color = final_colors[name]
#             if f"{name} Charge" not in all_keys: final_colors[f"{name} Charge"] = base_color
#             if f"{name} Discharge" not in all_keys: final_colors[f"{name} Discharge"] = base_color
#             all_keys.update([f"{name} Charge", f"{name} Discharge"])

#     for key, color in DEFAULT_COLORS.items():
#         if key not in all_keys:
#             final_colors[key] = color

#     logging.info(f"Generated color palette with {len(final_colors)} entries.")
#     return final_colors

# def get_dispatch_data(_n: pypsa.Network, _snapshots_slice: Optional[Union[pd.DatetimeIndex, pd.MultiIndex]] = None, 
#                      resolution: str = "1H") -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.DataFrame]:
#     snapshots = safe_get_snapshots(_n)
#     if _snapshots_slice is not None:
#         snapshots = snapshots[snapshots.isin(_snapshots_slice)]

#     if snapshots.empty:
#         logging.warning("get_dispatch_data called with empty or invalid snapshots slice.")
#         return pd.DataFrame(), pd.Series(dtype=float), pd.DataFrame(), pd.DataFrame()

#     logging.info(f"Extracting dispatch data for {len(snapshots)} snapshots.")
#     time_index = get_time_index(snapshots)

#     def get_carrier_map(comp_df, carriers_df):
#         if 'carrier' not in comp_df.columns: return None
#         carrier_map = comp_df['carrier']
#         if carriers_df is None or carriers_df.empty:
#             carriers_df = pd.DataFrame(index=carrier_map.unique())
#         if 'nice_name' not in carriers_df.columns:
#             carriers_df['nice_name'] = carriers_df.index
#         if isinstance(carriers_df, pd.DataFrame) and 'nice_name' in carriers_df.columns:
#             nice_name_map = carriers_df['nice_name'].dropna()
#             carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
#         return carrier_map

#     carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
#     if not hasattr(carriers_df, 'nice_name'):
#         carriers_df['nice_name'] = carriers_df.index

#     gen_dispatch = pd.DataFrame(index=snapshots)
#     load_dispatch = pd.Series(index=snapshots, dtype=float)
#     storage_dispatch = pd.DataFrame(index=snapshots)
#     store_dispatch = pd.DataFrame(index=snapshots)

#     if 'generators' in _n.components.keys() and hasattr(_n, 'generators_t') and 'p' in _n.generators_t:
#         df_static = _n.generators
#         df_t = _n.generators_t["p"]
#         if not df_t.empty and not df_static.empty:
#             carrier_map = get_carrier_map(df_static, carriers_df)
#             if carrier_map is not None:
#                 valid_gens = df_static.index[carrier_map.notna()]
#                 cols_to_group = df_t.columns.intersection(valid_gens)
#                 if not cols_to_group.empty:
#                     valid_snapshots_idx = snapshots[snapshots.isin(df_t.index)]
#                     if not valid_snapshots_idx.empty:
#                         # Updated groupby operation to avoid deprecation warning
#                         gen_dispatch = df_t.loc[valid_snapshots_idx, cols_to_group].T.groupby(carrier_map.loc[cols_to_group]).sum().T

#     if 'loads' in _n.components.keys() and hasattr(_n, 'loads_t'):
#         load_col = 'p_set' if 'p_set' in _n.loads_t else 'p' if 'p' in _n.loads_t else None
#         if load_col and not _n.loads_t[load_col].empty:
#             valid_snapshots_idx = snapshots[snapshots.isin(_n.loads_t[load_col].index)]
#             if not valid_snapshots_idx.empty:
#                 load_dispatch = _n.loads_t[load_col].loc[valid_snapshots_idx].sum(axis=1)

#     if 'storage_units' in _n.components.keys() and hasattr(_n, 'storage_units_t') and 'p' in _n.storage_units_t:
#         df_static = _n.storage_units
#         df_t = _n.storage_units_t["p"]
#         if not df_t.empty and not df_static.empty:
#             carrier_map = get_carrier_map(df_static, carriers_df) if 'carrier' in df_static.columns else pd.Series('Storage Unit', index=df_static.index)
#             valid_comps = df_static.index[carrier_map.notna()]
#             cols_to_group = df_t.columns.intersection(valid_comps)
#             if not cols_to_group.empty:
#                 valid_snapshots_idx = snapshots[snapshots.isin(df_t.index)]
#                 if not valid_snapshots_idx.empty:
#                     grouped_p = df_t.loc[valid_snapshots_idx, cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
#                     for carrier in grouped_p.columns:
#                         storage_dispatch[f"{carrier} Discharge"] = grouped_p[carrier].clip(lower=0)
#                         storage_dispatch[f"{carrier} Charge"] = grouped_p[carrier].clip(upper=0)

#     if 'stores' in _n.components.keys() and hasattr(_n, 'stores_t') and 'p' in _n.stores_t:
#         df_static = _n.stores
#         df_t = _n.stores_t['p']
#         if not df_t.empty and not df_static.empty:
#             carrier_map = get_carrier_map(df_static, carriers_df) if 'carrier' in df_static.columns else pd.Series('Store', index=df_static.index)
#             valid_comps = df_static.index[carrier_map.notna()]
#             cols_to_group = df_t.columns.intersection(valid_comps)
#             if not cols_to_group.empty:
#                 valid_snapshots_idx = snapshots[snapshots.isin(df_t.index)]
#                 if not valid_snapshots_idx.empty:
#                     grouped_p = df_t.loc[valid_snapshots_idx, cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
#                     for carrier in grouped_p.columns:
#                         store_dispatch[f"{carrier} Discharge"] = grouped_p[carrier].clip(lower=0)
#                         store_dispatch[f"{carrier} Charge"] = grouped_p[carrier].clip(upper=0)

#     gen_dispatch = gen_dispatch.reindex(snapshots).fillna(0)
#     load_dispatch = load_dispatch.reindex(snapshots).fillna(0)
#     storage_dispatch = storage_dispatch.reindex(snapshots).fillna(0)
#     store_dispatch = store_dispatch.reindex(snapshots).fillna(0)

#     gen_dispatch = gen_dispatch.loc[:, (gen_dispatch != 0).any(axis=0)]
#     storage_dispatch = storage_dispatch.loc[:, (storage_dispatch != 0).any(axis=0)]
#     store_dispatch = store_dispatch.loc[:, (store_dispatch != 0).any(axis=0)]

#     if resolution != "1H":
#         if not isinstance(time_index, pd.DatetimeIndex):
#             logging.warning(f"Cannot resample data to {resolution}. Index is not a DatetimeIndex.")
#         else:
#             all_data = pd.concat([gen_dispatch, load_dispatch.rename('Load'), storage_dispatch, store_dispatch], axis=1)
#             all_data.index = time_index
#             resampled_data = all_data.resample(resolution).mean()
#             gen_dispatch = resampled_data.loc[:, gen_dispatch.columns]
#             if 'Load' in resampled_data.columns:
#                 load_dispatch = resampled_data['Load']
#             storage_cols = [col for col in resampled_data.columns if col in storage_dispatch.columns]
#             storage_dispatch = resampled_data.loc[:, storage_cols] if storage_cols else pd.DataFrame()
#             store_cols = [col for col in resampled_data.columns if col in store_dispatch.columns]
#             store_dispatch = resampled_data.loc[:, store_cols] if store_cols else pd.DataFrame()

#     return gen_dispatch, load_dispatch, storage_dispatch, store_dispatch

# def get_carrier_capacity(_n: pypsa.Network, attribute: str = "p_nom_opt", period=None) -> pd.DataFrame:
#     logging.info(f"Calculating capacity for attribute '{attribute}'" + (f" for period '{period}'" if period else ""))
#     capacity_list = []
#     is_multi_period = isinstance(safe_get_snapshots(_n), pd.MultiIndex)
#     carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
#     if not hasattr(carriers_df, 'nice_name'):
#         carriers_df['nice_name'] = carriers_df.index

#     components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}

#     for comp_cls, comp_attr in components_to_check.items():
#         if comp_attr in _n.components.keys():
#             df_comp = getattr(_n, comp_attr)
#             if not df_comp.empty and 'carrier' in df_comp.columns:
#                 if comp_cls == 'Store':
#                     attr_to_use = attribute if attribute in ['e_nom', 'e_nom_opt'] else 'e_nom_opt'
#                 else:
#                     attr_to_use = attribute if attribute in ['p_nom', 'p_nom_opt'] else 'p_nom_opt'

#                 if attr_to_use not in df_comp.columns:
#                     logging.warning(f"Attribute '{attr_to_use}' not found in component '{comp_cls}'. Skipping.")
#                     continue

#                 active_assets_idx = df_comp.index
#                 if is_multi_period and period is not None:
#                     try:
#                         if hasattr(_n, 'get_active_assets'):
#                             active_assets_idx = _n.get_active_assets(comp_cls, period)
#                         elif 'build_year' in df_comp.columns and 'lifetime' in df_comp.columns:
#                             active_assets_idx = df_comp.index[
#                                 (df_comp['build_year'] <= period) &
#                                 (df_comp['build_year'] + df_comp['lifetime'] > period)
#                             ]
#                     except Exception as e:
#                         logging.warning(f"Could not filter active assets for {comp_cls} in period {period}: {e}. Using all.")

#                 df_active = df_comp.loc[active_assets_idx]
#                 if not df_active.empty:
#                     carrier_map = df_active['carrier']
#                     if carriers_df is None or carriers_df.empty:
#                         carriers_df = pd.DataFrame(index=carrier_map.unique())
#                     if 'nice_name' not in carriers_df.columns:
#                         carriers_df['nice_name'] = carriers_df.index
#                     if 'nice_name' in carriers_df.columns:
#                         nice_name_map = carriers_df['nice_name'].dropna()
#                         carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)

#                     comp_capacity = df_active.groupby(carrier_map)[attr_to_use].sum()
#                     capacity_list.append(comp_capacity)

#     if capacity_list:
#         combined_capacity = pd.concat(capacity_list).groupby(level=0).sum()
#         result_df = combined_capacity.reset_index()
#         result_df.columns = ['Carrier', 'Capacity']
#         result_df = result_df[result_df['Capacity'] > 1e-6]
#         return result_df.set_index('Carrier')
#     else:
#         return pd.DataFrame(columns=['Capacity'])

# def get_carrier_capacity_new_addition(_n: pypsa.Network, method='optimization_diff', period=None) -> pd.DataFrame:
#     logging.info(f"Calculating new capacity additions using method '{method}'" + 
#                  (f" for period '{period}'" if period else ""))
    
#     capacity_list = []
#     is_multi_period = isinstance(safe_get_snapshots(_n), pd.MultiIndex)
#     carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
    
#     if not hasattr(carriers_df, 'nice_name'):
#         carriers_df['nice_name'] = carriers_df.index
    
#     components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}
    
#     for comp_cls, comp_attr in components_to_check.items():
#         if comp_attr in _n.components.keys():
#             df_comp = getattr(_n, comp_attr)
            
#             if not df_comp.empty and 'carrier' in df_comp.columns:
#                 if method == 'optimization_diff':
#                     if comp_cls == 'Store':
#                         if 'e_nom_opt' not in df_comp.columns or 'e_nom' not in df_comp.columns:
#                             logging.warning(f"'e_nom_opt' or 'e_nom' not found in {comp_cls}. Skipping.")
#                             continue
#                     else:
#                         if 'p_nom_opt' not in df_comp.columns or 'p_nom' not in df_comp.columns:
#                             logging.warning(f"'p_nom_opt' or 'p_nom' not found in {comp_cls}. Skipping.")
#                             continue
#                 elif method == 'build_year':
#                     if 'build_year' not in df_comp.columns:
#                         logging.warning(f"'build_year' not found in {comp_cls}. Skipping.")
#                         continue
                
#                 active_assets_idx = df_comp.index
#                 if is_multi_period and period is not None:
#                     try:
#                         if hasattr(_n, 'get_active_assets'):
#                             active_assets_idx = _n.get_active_assets(comp_cls, period)
#                         elif 'build_year' in df_comp.columns and 'lifetime' in df_comp.columns:
#                             active_assets_idx = df_comp.index[
#                                 (df_comp['build_year'] <= period) &
#                                 (df_comp['build_year'] + df_comp['lifetime'] > period)
#                             ]
#                     except Exception as e:
#                         logging.warning(f"Could not filter active assets for {comp_cls} in period {period}: {e}. Using all.")
                
#                 df_active = df_comp.loc[active_assets_idx]
                
#                 if not df_active.empty:
#                     carrier_map = df_active['carrier']
#                     if 'nice_name' in carriers_df.columns:
#                         nice_name_map = carriers_df['nice_name'].dropna()
#                         carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
                    
#                     if method == 'optimization_diff':
#                         if comp_cls == 'Store':
#                             df_active['new_capacity'] = df_active['e_nom_opt'] - df_active['e_nom']
#                         else:
#                             df_active['new_capacity'] = df_active['p_nom_opt'] - df_active['p_nom']
                        
#                         df_active = df_active[df_active['new_capacity'] > 1e-6]
                        
#                         if not df_active.empty:
#                             comp_capacity = df_active.groupby(carrier_map)['new_capacity'].sum()
#                             capacity_list.append(comp_capacity)
                    
#                     elif method == 'build_year':
#                         if period is not None:
#                             df_built_this_year = df_active[df_active['build_year'] == period]
                            
#                             if not df_built_this_year.empty:
#                                 if comp_cls == 'Store':
#                                     capacity_attr = 'e_nom_opt' if 'e_nom_opt' in df_built_this_year.columns else 'e_nom'
#                                 else:
#                                     capacity_attr = 'p_nom_opt' if 'p_nom_opt' in df_built_this_year.columns else 'p_nom'
                                
#                                 carrier_map_year = df_built_this_year['carrier']
#                                 if 'nice_name' in carriers_df.columns:
#                                     nice_name_map = carriers_df['nice_name'].dropna()
#                                     carrier_map_year = carrier_map_year.map(nice_name_map).fillna(carrier_map_year)
                                
#                                 comp_capacity = df_built_this_year.groupby(carrier_map_year)[capacity_attr].sum()
#                                 capacity_list.append(comp_capacity)
    
#     if capacity_list:
#         combined_capacity = pd.concat(capacity_list).groupby(level=0).sum()
#         result_df = combined_capacity.reset_index()
#         result_df.columns = ['Carrier', 'New_Capacity']
#         result_df = result_df[result_df['New_Capacity'] > 1e-6]
#         return result_df.set_index('Carrier')
#     else:
#         return pd.DataFrame(columns=['New_Capacity'])

# def get_buses_capacity(_n: pypsa.Network, attribute: str = "p_nom_opt", period=None) -> pd.DataFrame:
#     logging.info(f"Calculating capacity by region for attribute '{attribute}'" + (f" for period '{period}'" if period else ""))
#     capacity_list = []
#     is_multi_period = isinstance(safe_get_snapshots(_n), pd.MultiIndex)
#     components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}

#     for comp_cls, comp_attr in components_to_check.items():
#         if comp_attr in _n.components.keys():
#             df_comp = getattr(_n, comp_attr)
#             if not df_comp.empty and 'bus' in df_comp.columns:
#                 if comp_cls == 'Store':
#                     attr_to_use = attribute if attribute in ['e_nom', 'e_nom_opt'] else 'e_nom_opt'
#                 else:
#                     attr_to_use = attribute if attribute in ['p_nom', 'p_nom_opt'] else 'p_nom_opt'

#                 if attr_to_use not in df_comp.columns:
#                     logging.warning(f"Attribute '{attr_to_use}' not found in component '{comp_cls}'. Skipping.")
#                     continue

#                 active_assets_idx = df_comp.index
#                 if is_multi_period and period is not None:
#                     try:
#                         if hasattr(_n, 'get_active_assets'):
#                             active_assets_idx = _n.get_active_assets(comp_cls, period)
#                         elif 'build_year' in df_comp.columns and 'lifetime' in df_comp.columns:
#                             active_assets_idx = df_comp.index[
#                                 (df_comp['build_year'] <= period) &
#                                 (df_comp['build_year'] + df_comp['lifetime'] > period)
#                             ]
#                     except Exception as e:
#                         logging.warning(f"Could not filter active assets for {comp_cls} in period {period}: {e}. Using all.")

#                 df_active = df_comp.loc[active_assets_idx]
#                 if not df_active.empty:
#                     comp_capacity = df_active.groupby(df_active['bus'])[attr_to_use].sum()
#                     capacity_list.append(comp_capacity)

#     if capacity_list:
#         combined_capacity = pd.concat(capacity_list).groupby(level=0).sum()
#         result_df = combined_capacity.reset_index()
#         result_df.columns = ['Region', 'Capacity']
#         result_df = result_df[result_df['Capacity'] > 1e-6]
#         return result_df.set_index('Region')
#     else:
#         return pd.DataFrame(columns=['Capacity'])

# def get_total_generation_by_period(_n: pypsa.Network) -> pd.DataFrame:
#     logging.info("Calculating total generation by period...")
#     if 'generators' not in _n.components.keys() or not hasattr(_n, 'generators_t') or 'p' not in _n.generators_t:
#         return pd.DataFrame()

#     gen_p = _n.generators_t['p']
#     df_static = _n.generators
#     carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
#     if not hasattr(carriers_df, 'nice_name'):
#         carriers_df['nice_name'] = carriers_df.index

#     if gen_p.empty or df_static.empty or 'carrier' not in df_static.columns:
#         return pd.DataFrame()

#     carrier_map = df_static['carrier']
#     nice_name_map = carriers_df['nice_name'].dropna()
#     carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)

#     valid_gens = df_static.index[carrier_map.notna()]
#     cols_to_group = gen_p.columns.intersection(valid_gens)

#     if not cols_to_group.empty:
#         def get_period_aggregates(data_t: pd.DataFrame) -> pd.DataFrame:
#             snapshots = safe_get_snapshots(_n)
#             periods = get_period_index(snapshots)
#             if periods is None: return pd.DataFrame()
#             weights = get_snapshot_weights(_n, snapshots)
#             data_aligned, weights_aligned = data_t.align(weights, axis=0, join='inner')
#             if data_aligned.empty: return pd.DataFrame()
#             weighted_data = data_aligned.multiply(weights_aligned, axis=0)
#             period_agg = weighted_data.groupby(get_period_index(weighted_data.index)).sum()
#             return period_agg

#         gen_p_by_carrier = gen_p[cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
#         period_generation = get_period_aggregates(gen_p_by_carrier)
#         return period_generation
#     else:
#         return pd.DataFrame()


# def calculate_cuf(n, snapshots_slice=None):
#     """Calculate Capacity Utilization Factors (CUFs) by carrier with optional snapshot filtering."""
#     logging.info("Calculating CUFs...")
#     if 'generators' not in n.components.keys() or n.generators.empty or \
#        not hasattr(n, 'generators_t') or 'p' not in n.generators_t or \
#        not any(c in n.generators.columns for c in ['p_nom_opt', 'p_nom']) or \
#        'carrier' not in n.generators.columns:
#         logging.warning("Missing data for CUF calculation.")
#         return pd.DataFrame(columns=['Carrier', 'CUF'])

#     try:
#         # Use provided snapshots_slice or all snapshots if None
#         snapshots = snapshots_slice if snapshots_slice is not None else safe_get_snapshots(n)
#         if snapshots.empty:
#             return pd.DataFrame(columns=['Carrier', 'CUF'])

#         # Filter snapshots to those available in generators_t.p
#         valid_snapshots = snapshots[snapshots.isin(n.generators_t['p'].index)]
#         if valid_snapshots.empty:
#             return pd.DataFrame(columns=['Carrier', 'CUF'])
            
#         gen_p = n.generators_t['p'].loc[valid_snapshots]
#         p_nom_attr = 'p_nom_opt' if 'p_nom_opt' in n.generators.columns else 'p_nom'
#         gen_p_nom = n.generators[p_nom_attr]

#         weights = get_snapshot_weights(n, valid_snapshots)
#         energy_produced = gen_p.multiply(weights, axis=0).sum()
#         total_weight = weights.sum()

#         potential_energy = gen_p_nom * total_weight
#         cuf_per_generator = (energy_produced / potential_energy).replace([np.inf, -np.inf], np.nan).fillna(0)
#         cuf_per_generator = cuf_per_generator[cuf_per_generator > 0]

#         carrier_map = n.generators['carrier']
#         carriers_df = n.carriers if hasattr(n, 'carriers') else pd.DataFrame()
#         if not hasattr(carriers_df, 'nice_name'):
#             carriers_df['nice_name'] = carriers_df.index
#         if carriers_df is not None and not carriers_df.empty and 'nice_name' in carriers_df.columns:
#             nice_name_map = carriers_df['nice_name'].dropna()
#             carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)

#         cuf_by_carrier = cuf_per_generator.groupby(carrier_map).mean()
#         cuf_df = cuf_by_carrier.reset_index()
#         cuf_df.columns = ['Carrier', 'CUF']
#         return cuf_df[cuf_df['CUF'].notna() & (cuf_df['CUF'] > 1e-6)]

#     except Exception as e:
#         logging.error(f"Error calculating CUFs: {e}", exc_info=True)
#         return pd.DataFrame(columns=['Carrier', 'CUF'])

# def calculate_curtailment(n, snapshots_slice=None):
#     """Calculate renewable curtailment by carrier with optional snapshot filtering."""
#     logging.info("Calculating curtailment...")
#     req_cols = ['p', 'p_max_pu']
#     if 'generators' not in n.components.keys() or n.generators.empty or \
#        not hasattr(n, 'generators_t') or not all(c in n.generators_t for c in req_cols) or \
#        'carrier' not in n.generators.columns or \
#        not any(c in n.generators.columns for c in ['p_nom_opt', 'p_nom']):
#         logging.warning("Missing data for curtailment calculation.")
#         return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

#     try:
#         # Use provided snapshots_slice or all snapshots if None
#         snapshots = snapshots_slice if snapshots_slice is not None else safe_get_snapshots(n)
#         if snapshots.empty:
#             return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

#         renewable_keywords = ['solar', 'wind']
#         renewable_carriers = [c for c in n.generators['carrier'].dropna().unique() if any(k in c.lower() for k in renewable_keywords)]
#         renewable_gens = n.generators[n.generators['carrier'].isin(renewable_carriers)]
        
#         if renewable_gens.empty:
#             return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

#         p_nom_attr = 'p_nom_opt' if 'p_nom_opt' in renewable_gens.columns else 'p_nom'
#         p_nom = renewable_gens[p_nom_attr]

#         # Filter to valid snapshots that exist in both p and p_max_pu
#         valid_snapshots = snapshots[
#             snapshots.isin(n.generators_t['p'].index) & 
#             snapshots.isin(n.generators_t['p_max_pu'].index)
#         ]
#         if valid_snapshots.empty:
#             return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

#         p_actual = n.generators_t['p'].loc[valid_snapshots, renewable_gens.index]
#         p_max_pu = n.generators_t['p_max_pu'].loc[valid_snapshots, renewable_gens.index]
#         weights = get_snapshot_weights(n, valid_snapshots)
#         weights = weights.mean()  # Simplification for curtailment calculation

#         p_potential = p_max_pu.multiply(p_nom.reindex(p_max_pu.columns), axis=1)
#         curtailment_power = (p_potential - p_actual).clip(lower=0)

#         curtailment_energy = (curtailment_power * weights).sum()
#         potential_energy = (p_potential * weights).sum()

#         carrier_map = renewable_gens['carrier']
#         carriers_df = n.carriers if hasattr(n, 'carriers') else pd.DataFrame()
#         if not hasattr(carriers_df, 'nice_name'):
#             carriers_df['nice_name'] = carriers_df.index
#         if carriers_df is not None and not carriers_df.empty and 'nice_name' in carriers_df.columns:
#             nice_name_map = carriers_df['nice_name'].dropna()
#             carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)

#         curtailment_by_carrier = curtailment_energy.groupby(carrier_map).sum()
#         potential_by_carrier = potential_energy.groupby(carrier_map).sum()

#         curtailment_df = pd.DataFrame({
#             'Carrier': curtailment_by_carrier.index,
#             'Curtailment (MWh)': curtailment_by_carrier.values,
#             'Potential (MWh)': potential_by_carrier.reindex(curtailment_by_carrier.index).fillna(0).values
#         })
#         curtailment_df['Curtailment (%)'] = (curtailment_df['Curtailment (MWh)'] / curtailment_df['Potential (MWh)'] * 100).fillna(0)
#         return curtailment_df[curtailment_df['Potential (MWh)'] > 1e-3]
#     except Exception as e:
#         logging.error(f"Error calculating curtailment: {e}", exc_info=True)
#         return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])


# def get_storage_soc(_n: pypsa.Network) -> pd.DataFrame:
#     logging.info("Extracting Storage SoC...")
#     soc_data_list = []
#     snapshots = safe_get_snapshots(_n)
#     if snapshots.empty: return pd.DataFrame()
#     carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
#     if not hasattr(carriers_df, 'nice_name'):
#         carriers_df['nice_name'] = carriers_df.index

#     def process_soc(comp_cls, comp_attr, soc_attr):
#         if comp_cls in _n.components.keys() and hasattr(_n, f"{comp_attr}_t") and soc_attr in getattr(_n, f"{comp_attr}_t"):
#             df_soc_raw = getattr(_n, f"{comp_attr}_t")[soc_attr]
#             df_static = getattr(_n, comp_attr)
#             df_static = df_static.copy()
#             valid_snapshots = snapshots[snapshots.isin(df_soc_raw.index)]
#             if valid_snapshots.empty: return
#             df_soc = df_soc_raw.loc[valid_snapshots]

#             if 'carrier' in df_static.columns:
#                 df_static['carrier'] = df_static['carrier'].fillna(df_static['bus'])
#             else:
#                 df_static['carrier'] = df_static['bus']

#             if not df_soc.empty and not df_static.empty:
#                 carrier_map = df_static['carrier'] if 'carrier' in df_static.columns else pd.Series(comp_cls, index=df_static.index)
#                 if carriers_df is not None and not carriers_df.empty:
#                     if 'nice_name' not in carriers_df.columns:
#                         carriers_df['nice_name'] = carriers_df.index
#                     nice_name_map = carriers_df['nice_name'].dropna()
#                     carrier_map = carrier_map.map(nice_name_map).fillna(carrier_map)
#                 carrier_map = carrier_map.apply(lambda x: f"{x} ({comp_cls})" if isinstance(x, str) else comp_cls)

#                 valid_comps = df_static.index[carrier_map.notna()]
#                 cols_to_group = df_soc.columns.intersection(valid_comps)

#                 if not cols_to_group.empty:
#                     grouped_soc = df_soc[cols_to_group].groupby(carrier_map.loc[cols_to_group], axis=1).sum()
#                     soc_data_list.append(grouped_soc)

#     process_soc('storage_units', 'storage_units', 'state_of_charge')
#     process_soc('stores', 'stores', 'e')

#     if not soc_data_list: return pd.DataFrame()
#     combined_soc = pd.concat(soc_data_list, axis=1, join='outer').reindex(snapshots).fillna(0)
#     return combined_soc.loc[:, (combined_soc != 0).any(axis=0)]

# def calculate_co2_emissions(_n: pypsa.Network) -> Tuple[pd.DataFrame, pd.DataFrame]:
#     logging.info("Calculating CO2 emissions...")
#     total_emissions_df = pd.DataFrame(columns=['Period', 'Total CO2 Emissions (Tonnes)'])
#     emissions_by_carrier_df = pd.DataFrame(columns=['Period', 'Carrier', 'Emissions (Tonnes)'])

#     if 'generators' not in _n.components.keys() or _n.generators.empty or \
#        not hasattr(_n, 'generators_t') or 'p' not in _n.generators_t or \
#        not hasattr(_n, 'carriers') or 'co2_emissions' not in _n.carriers.columns:
#         logging.warning("Missing data for CO2 emissions calculation.")
#         return total_emissions_df, emissions_by_carrier_df

#     try:
#         snapshots = safe_get_snapshots(_n)
#         if snapshots.empty: return total_emissions_df, emissions_by_carrier_df

#         co2_factors = _n.carriers['co2_emissions'].dropna()
#         if co2_factors.empty: return total_emissions_df, emissions_by_carrier_df

#         emitting_gens = _n.generators[_n.generators['carrier'].isin(co2_factors.index)]
#         if emitting_gens.empty: return total_emissions_df, emissions_by_carrier_df

#         valid_snapshots = snapshots[snapshots.isin(_n.generators_t.p.index)]
#         if valid_snapshots.empty: return total_emissions_df, emissions_by_carrier_df

#         gen_p = _n.generators_t.p.loc[valid_snapshots, emitting_gens.index]
#         weights = get_snapshot_weights(_n, valid_snapshots)

#         carrier_map = emitting_gens['carrier']
#         co2_map = carrier_map.map(co2_factors)
#         emissions_t = gen_p.multiply(co2_map, axis=1).multiply(weights, axis=0)

#         periods = get_period_index(valid_snapshots)
#         period_total_emissions = emissions_t.sum(axis=1).groupby(periods).sum()

#         carrier_display_map = carrier_map
#         carriers_df = _n.carriers if hasattr(_n, 'carriers') else pd.DataFrame()
#         if not hasattr(carriers_df, 'nice_name'):
#             carriers_df['nice_name'] = carriers_df.index
#         if carriers_df is not None and not carriers_df.empty and 'nice_name' in carriers_df.columns:
#             nice_name_map = carriers_df['nice_name'].dropna()
#             carrier_display_map = carrier_display_map.map(nice_name_map).fillna(carrier_display_map)

#         emissions_by_carrier_t = emissions_t.groupby(carrier_display_map, axis=1).sum()
#         period_emissions_by_carrier = emissions_by_carrier_t.groupby(periods).sum()

#         if not period_total_emissions.empty:
#             total_emissions_df = period_total_emissions.reset_index()
#             total_emissions_df.columns = ['Period', 'Total CO2 Emissions (Tonnes)']

#         if not period_emissions_by_carrier.empty:
#             period_emissions_by_carrier.index.name = 'Period'
#             emissions_by_carrier_df = period_emissions_by_carrier.reset_index().melt(
#                 id_vars='Period', var_name='Carrier', value_name='Emissions (Tonnes)'
#             )
#             emissions_by_carrier_df = emissions_by_carrier_df[emissions_by_carrier_df['Emissions (Tonnes)'] > 1e-3]

#         return total_emissions_df, emissions_by_carrier_df
#     except Exception as e:
#         logging.error(f"Error calculating CO2 emissions: {e}", exc_info=True)
#         return total_emissions_df, emissions_by_carrier_df

# def calculate_marginal_prices(_n: pypsa.Network, resolution: str = "1H") -> pd.DataFrame:
#     logging.info("Extracting marginal prices...")
#     if not hasattr(_n, "buses_t") or 'marginal_price' not in _n.buses_t:
#         logging.warning("No marginal price data found.")
#         return pd.DataFrame()
#     price_data = _n.buses_t['marginal_price']
#     if price_data.empty:
#         return pd.DataFrame()
#     time_index = get_time_index(price_data.index)
#     if resolution != "1H" and isinstance(time_index, pd.DatetimeIndex):
#         price_data = resample_data(price_data, time_index, resolution)
#     return price_data

# def calculate_network_losses(_n: pypsa.Network) -> pd.DataFrame:
#     logging.info("Calculating network losses...")
#     losses_list = []
#     snapshots = safe_get_snapshots(_n)
#     periods = get_period_index(snapshots)
#     if periods is None: return pd.DataFrame()
#     weights = get_snapshot_weights(_n, snapshots)

#     if 'lines' in _n.components.keys() and hasattr(_n, 'lines_t') and 'p0' in _n.lines_t and 'p1' in _n.lines_t:
#         valid_snapshots = snapshots[snapshots.isin(_n.lines_t.p0.index)]
#         if not valid_snapshots.empty:
#             p0 = _n.lines_t.p0.loc[valid_snapshots]
#             p1 = _n.lines_t.p1.loc[valid_snapshots]
#             line_losses_t = (p0 + p1).sum(axis=1)
#             losses_list.append(line_losses_t)

#     if 'links' in _n.components.keys() and hasattr(_n, 'links_t') and 'p0' in _n.links_t and 'p1' in _n.links_t:
#         valid_snapshots = snapshots[snapshots.isin(_n.links_t.p0.index)]
#         if not valid_snapshots.empty:
#             p0_link = _n.links_t.p0.loc[valid_snapshots]
#             p1_link = _n.links_t.p1.loc[valid_snapshots]
#             link_losses_t = (p0_link + p1_link).sum(axis=1)
#             losses_list.append(link_losses_t)

#     if not losses_list: return pd.DataFrame()
#     total_losses_t = pd.concat(losses_list, axis=1).sum(axis=1)
#     weighted_losses = total_losses_t * weights.reindex(total_losses_t.index)
#     period_losses = weighted_losses.groupby(get_period_index(weighted_losses.index)).sum()
#     period_losses_df = period_losses.reset_index()
#     period_losses_df.columns = ['Period', 'Losses (MWh)']
#     return period_losses_df

# def plot_dispatch_stack(gen_dispatch, load_dispatch, storage_dispatch, store_dispatch, carrier_colors, 
#                         title="Power Dispatch and Load", plot_index=None, resolution="1H"):
#     fig = go.Figure()
#     all_storage = pd.concat([storage_dispatch, store_dispatch], axis=1).fillna(0)
#     if plot_index is None:
#         if not gen_dispatch.empty: plot_index = gen_dispatch.index
#         elif not load_dispatch.empty: plot_index = load_dispatch.index
#         elif not all_storage.empty: plot_index = all_storage.index
#         else: return fig
#     plot_time_index = get_time_index(plot_index)

#     for carrier in sorted(gen_dispatch.columns):
#         color = carrier_colors.get(carrier, None)
#         if color is None:
#             carrier_lower = carrier.lower()
#             matched = False
#             for default_key, default_color in DEFAULT_COLORS.items():
#                 if default_key.lower() in carrier_lower:
#                     color = default_color
#                     matched = True
#                     break
#             if not matched:
#                 color = DEFAULT_COLORS.get('Other', '#D3D3D3')
#         fig.add_trace(go.Scatter(
#             x=plot_time_index, 
#             y=gen_dispatch[carrier], 
#             mode='lines', 
#             name=carrier, 
#             stackgroup='positive', 
#             line=dict(width=0), 
#             fill='tonexty', 
#             fillcolor=color, 
#             hovertemplate='%{x|%Y-%m-%d %H:%M}<br>' + f'{carrier}: %{{y:.1f}} MW<extra></extra>'
#         ))

#     discharge_cols = sorted([c for c in all_storage.columns if 'Discharge' in c and all_storage[c].sum() > 1e-3])
#     for col in discharge_cols:
#         color = carrier_colors.get(col, DEFAULT_COLORS.get('Storage Discharge', '#FFA500'))
#         fig.add_trace(go.Scatter(
#             x=plot_time_index, 
#             y=all_storage[col], 
#             mode='lines', 
#             name=col, 
#             stackgroup='positive', 
#             line=dict(width=0), 
#             fill='tonexty', 
#             fillcolor=color, 
#             hovertemplate='%{x|%Y-%m-%d %H:%M}<br>' + f'{col}: %{{y:.1f}} MW<extra></extra>'
#         ))

#     charge_cols = sorted([c for c in all_storage.columns if 'Charge' in c and all_storage[c].sum() < -1e-3])
#     for col in charge_cols:
#         color = carrier_colors.get(col, DEFAULT_COLORS.get('Storage Charge', '#FFA500'))
#         fig.add_trace(go.Scatter(
#             x=plot_time_index, 
#             y=all_storage[col], 
#             mode='lines', 
#             name=col, 
#             stackgroup='negative', 
#             line=dict(width=0), 
#             fill='tonexty', 
#             fillcolor=color, 
#             hovertemplate='%{x|%Y-%m-%d %H:%M}<br>' + f'{col}: %{{y:.1f}} MW<extra></extra>'
#         ))

#     if not load_dispatch.isna().all() and load_dispatch.sum() > 0:
#         fig.add_trace(go.Scatter(
#             x=plot_time_index, 
#             y=load_dispatch, 
#             mode='lines', 
#             name='Load', 
#             line=dict(color=carrier_colors.get('Load', 'black'), width=2), 
#             hovertemplate='%{x|%Y-%m-%d %H:%M}<br>Load: %{y:.1f} MW<extra></extra>'
#         ))

#     resolution_info = f" ({resolution} resolution)" if resolution != "1H" else ""
#     title_with_resolution = f"{title}{resolution_info}"
#     fig.update_layout(
#         title=title_with_resolution,
#         xaxis_title="Time", 
#         yaxis_title="Power (MW)", 
#         hovermode='x unified', 
#         legend_title="Component/Carrier", 
#         height=600, 
#         yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1)
#     )
#     return fig

# def create_daily_profile_plot(gen_dispatch, load_dispatch, storage_dispatch, store_dispatch, carrier_colors):
#     all_data = pd.concat([gen_dispatch, storage_dispatch, store_dispatch], axis=1)
#     all_data['Load'] = load_dispatch
#     time_idx = get_time_index(all_data.index)
#     if not isinstance(time_idx, pd.DatetimeIndex):
#         return go.Figure()
#     all_data.index = time_idx
#     hourly_avg = all_data.groupby(time_idx.hour).mean()
#     hourly_avg.index.name = 'Hour of Day'
#     df_melted = hourly_avg.reset_index().melt(
#         id_vars='Hour of Day',
#         var_name='Component/Carrier',
#         value_name='Average Power (MW)'
#     )
#     df_melted = df_melted[df_melted['Average Power (MW)'].abs() > 1e-3]
#     if not df_melted.empty:
#         fig = px.line(df_melted, x='Hour of Day', y='Average Power (MW)', 
#                      color='Component/Carrier', title='Average Daily Profile', 
#                      color_discrete_map=carrier_colors)
#         fig.update_layout(xaxis=dict(tickmode='linear', dtick=1), legend_title="Component/Carrier")
#         return fig
#     return go.Figure()

# def create_daily_profile_plot_new(gen_dispatch, load_dispatch, storage_dispatch, store_dispatch, carrier_colors):
#     components_to_stack = pd.concat([gen_dispatch, storage_dispatch, store_dispatch], axis=1)
#     time_idx = get_time_index(components_to_stack.index)
#     if not isinstance(time_idx, pd.DatetimeIndex):
#         return go.Figure()
#     components_to_stack.index = time_idx
#     hourly_avg_stack = components_to_stack.groupby(time_idx.hour).mean()
#     hourly_avg_stack.index.name = 'Hour of Day'
#     load_dispatch.index = time_idx
#     hourly_avg_load = load_dispatch.groupby(time_idx.hour).mean()
#     hourly_avg_load.index.name = 'Hour of Day'
#     df_melted = hourly_avg_stack.reset_index().melt(
#         id_vars='Hour of Day',
#         var_name='Component/Carrier',
#         value_name='Average Power (MW)'
#     )
#     df_positive = df_melted[df_melted['Average Power (MW)'] >= -1e-3].copy()
#     df_negative = df_melted[df_melted['Average Power (MW)'] < -1e-3].copy()
#     fig = go.Figure()
#     if not df_positive.empty:
#         for carrier in df_positive['Component/Carrier'].unique():
#             df_carrier = df_positive[df_positive['Component/Carrier'] == carrier]
#             fig.add_trace(
#                 go.Scatter(
#                     x=df_carrier['Hour of Day'],
#                     y=df_carrier['Average Power (MW)'],
#                     mode='lines',
#                     line=dict(width=0),
#                     fill='tonexty',
#                     name=carrier,
#                     stackgroup='positive_components',
#                     legendgroup=carrier,
#                     showlegend=True,
#                     hoverinfo='x+y+name',
#                     fillcolor=carrier_colors.get(carrier, '#cccccc')
#                 )
#             )
#     if not df_negative.empty:
#         for carrier in df_negative['Component/Carrier'].unique():
#             df_carrier = df_negative[df_negative['Component/Carrier'] == carrier]
#             fig.add_trace(
#                 go.Scatter(
#                     x=df_carrier['Hour of Day'],
#                     y=df_carrier['Average Power (MW)'],
#                     mode='lines',
#                     line=dict(width=0),
#                     fill='tonexty',
#                     name=f'{carrier} (Negative)',
#                     stackgroup='negative_components',
#                     legendgroup=carrier,
#                     showlegend=True,
#                     hoverinfo='x+y+name',
#                     fillcolor=carrier_colors.get(carrier, '#cccccc')
#                 )
#             )
#     if not hourly_avg_load.empty:
#         fig.add_trace(
#             go.Scatter(
#                 x=hourly_avg_load.index,
#                 y=hourly_avg_load.values,
#                 mode='lines',
#                 name='Load',
#                 line=dict(color='black', width=2),
#                 legendgroup='Load',
#                 showlegend=True,
#                 hoverinfo='x+y+name'
#             )
#         )
#     fig.update_layout(
#         xaxis=dict(tickmode='linear', dtick=1),
#         yaxis_title='Average Power (MW)',
#         title='Average Daily Profile (Generation/Storage Stacked, Load as Line)',
#         legend_title="Component/Carrier",
#         hovermode='x unified'
#     )
#     return fig

# def create_duration_curve(data, title="Duration Curve", y_label="Power (MW)"):
#     if data.isna().all() or data.empty:
#         return go.Figure()
#     sorted_data = data.sort_values(ascending=False)
#     x_values = np.linspace(0, 100, len(sorted_data))
#     fig = px.area(x=x_values, y=sorted_data.values, 
#                  labels={'x': 'Duration (%)', 'y': y_label}, 
#                  title=title)
#     return fig

# def plot_hourly_generation_heatmap(hourly_gen_data, carrier_colors, selected_carrier=None):
#     if hourly_gen_data.empty:
#         return go.Figure()
#     if selected_carrier is not None and selected_carrier in hourly_gen_data.columns:
#         plot_data = hourly_gen_data[[selected_carrier]]
#         title = f"Hourly {selected_carrier} Generation Across Periods"
#         colorscale = [[0, 'white'], [1, carrier_colors.get(selected_carrier, 'blue')]]
#     else:
#         plot_data = hourly_gen_data.sum(axis=1).to_frame('Total')
#         title = "Total Hourly Generation Across Periods"
#         colorscale = 'Viridis'
#     if isinstance(hourly_gen_data.index, pd.MultiIndex):
#         periods = hourly_gen_data.index.get_level_values(0).unique()
#         snapshots = hourly_gen_data.index.get_level_values(1)
#         if len(snapshots) > 1000:
#             if hasattr(snapshots, 'date'):
#                 dates = pd.Series([ts.date() for ts in snapshots], index=snapshots)
#                 new_index = pd.MultiIndex.from_tuples(
#                     [(hourly_gen_data.index.get_level_values(0)[i], dates[i]) 
#                      for i in range(len(hourly_gen_data))],
#                     names=['period', 'date']
#                 )
#                 temp_df = plot_data.copy()
#                 temp_df.index = new_index
#                 plot_data = temp_df.groupby(level=[0, 1]).mean()
#                 title = title.replace("Hourly", "Daily Average")
#         if isinstance(plot_data.index, pd.MultiIndex) and plot_data.index.nlevels == 2:
#             pivot_table = pd.pivot_table(
#                 plot_data.reset_index(), 
#                 values=plot_data.columns[0], 
#                 index='snapshot' if 'snapshot' in plot_data.index.names else 'date',
#                 columns='period'
#             )
#         else:
#             pivot_table = plot_data
#         fig = px.imshow(
#             pivot_table, 
#             color_continuous_scale=colorscale,
#             labels={'color': 'Generation (MW)'},
#             title=title
#         )
#         fig.update_layout(
#             xaxis_title="Period",
#             yaxis_title="Time",
#             height=800,
#             coloraxis_colorbar=dict(title="MW")
#         )
#     else:
#         fig = px.line(
#             plot_data, 
#             title=title,
#             labels={'value': 'Generation (MW)', 'index': 'Time'}
#         )
#         fig.update_layout(
#             xaxis_title="Time",
#             yaxis_title="Generation (MW)",
#             height=600
#         )
#     return fig

# def plot_generation_profile_by_period(hourly_gen_data, carrier_colors):
#     if hourly_gen_data.empty:
#         return go.Figure()
#     if isinstance(hourly_gen_data.index, pd.MultiIndex):
#         periods = hourly_gen_data.index.get_level_values(0).unique()
#         fig = make_subplots(
#             rows=len(periods), 
#             cols=1,
#             shared_xaxes=True,
#             subplot_titles=[f"Period {p}" for p in periods],
#             vertical_spacing=0.05
#         )
#         for i, period in enumerate(periods):
#             period_data = hourly_gen_data.loc[period]
#             timestamps = period_data.index
#             if hasattr(timestamps, 'hour'):
#                 hours = timestamps.hour
#                 daily_profile = period_data.groupby(hours).mean()
#                 for carrier in daily_profile.columns:
#                     fig.add_trace(
#                         go.Scatter(
#                             x=daily_profile.index, 
#                             y=daily_profile[carrier],
#                             name=carrier,
#                             line=dict(color=carrier_colors.get(carrier, None)),
#                             showlegend=(i == 0)
#                         ),
#                         row=i+1, 
#                         col=1
#                     )
#         fig.update_layout(
#             height=300 * len(periods),
#             title="Average Daily Generation Profiles by Period",
#             legend_title="Carrier",
#             xaxis_title="Hour of Day",
#         )
#         for i in range(len(periods)):
#             fig.update_yaxes(title_text="Generation (MW)", row=i+1, col=1)
#     else:
#         timestamps = hourly_gen_data.index
#         if hasattr(timestamps, 'hour'):
#             hours = timestamps.hour
#             daily_profile = hourly_gen_data.groupby(hours).mean()
#             fig = px.line(
#                 daily_profile,
#                 labels={'value': 'Generation (MW)', 'index': 'Hour of Day'},
#                 title="Average Daily Generation Profile",
#                 color_discrete_map=carrier_colors
#             )
#             fig.update_layout(
#                 xaxis_title="Hour of Day",
#                 yaxis_title="Generation (MW)",
#                 height=600,
#                 legend_title="Carrier"
#             )
#         else:
#             fig = px.line(
#                 hourly_gen_data,
#                 title="Generation Time Series",
#                 labels={'value': 'Generation (MW)', 'index': 'Time'},
#                 color_discrete_map=carrier_colors
#             )
#     return fig
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

    if 'nice_name' not in carriers_df_internal.columns:
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

# --- Core Data Extraction Functions ---
def get_dispatch_data(_n: pypsa.Network, _snapshots_slice: Optional[Union[pd.DatetimeIndex, pd.MultiIndex, pd.Index]] = None,
                     resolution: str = "1H") -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.DataFrame]:
    """
    Extracts dispatch data for generators, loads, storage units, and stores,
    aligned to effective_snapshots and optionally resampled.
    """
    effective_snapshots = get_effective_snapshots(_n, _snapshots_slice)
    if effective_snapshots.empty:
        logging.warning("get_dispatch_data: Effective snapshots are empty. Returning empty data structures.")
        return pd.DataFrame(), pd.Series(dtype=float), pd.DataFrame(), pd.DataFrame()

    logging.info(f"get_dispatch_data: Extracting dispatch data for {len(effective_snapshots)} effective_snapshots, resolution: {resolution}.")
    
    # Initialize return dataframes/series with the effective_snapshots index to ensure alignment
    gen_dispatch_agg = pd.DataFrame(index=effective_snapshots)
    load_dispatch_sum = pd.Series(0.0, index=effective_snapshots) 
    storage_units_dispatch_agg = pd.DataFrame(index=effective_snapshots)
    stores_dispatch_agg = pd.DataFrame(index=effective_snapshots)

    carriers_df = _n.carriers if hasattr(_n, 'carriers') and isinstance(_n.carriers, pd.DataFrame) else pd.DataFrame()

    # Component processing configuration
    component_configs = {
        'generators': {'df_out': gen_dispatch_agg, 'p_attr': 'p', 'default_carrier': 'Generator'},
        'loads': {'series_out': load_dispatch_sum, 'p_attr': 'p_set', 'fallback_p_attr': 'p'}, # Loads sum up
        'storage_units': {'df_out': storage_units_dispatch_agg, 'p_attr': 'p', 'default_carrier': 'StorageUnit'},
        'stores': {'df_out': stores_dispatch_agg, 'p_attr': 'p', 'default_carrier': 'Store'},
    }

    for comp_name_plural, config in component_configs.items():
        if comp_name_plural in _n.components.keys() and hasattr(_n, f"{comp_name_plural}_t"):
            df_static = getattr(_n, comp_name_plural, pd.DataFrame())
            if df_static.empty: continue

            p_attr_to_use = config['p_attr']
            comp_t_dispatch_data = getattr(_n, f"{comp_name_plural}_t", {}).get(p_attr_to_use)
            if comp_t_dispatch_data is None and 'fallback_p_attr' in config: # Try fallback for loads
                p_attr_to_use = config['fallback_p_attr']
                comp_t_dispatch_data = getattr(_n, f"{comp_name_plural}_t", {}).get(p_attr_to_use)

            if comp_t_dispatch_data is not None and not comp_t_dispatch_data.empty:
                # Align component time-series data with effective_snapshots (index and columns)
                aligned_dispatch_data = comp_t_dispatch_data.reindex(index=effective_snapshots, columns=df_static.index).fillna(0)

                if 'series_out' in config: # For loads
                    config['series_out'].update(aligned_dispatch_data.sum(axis=1))
                elif 'df_out' in config: # For generators, storage_units, stores
                    carrier_map = get_carrier_map(df_static, carriers_df, default_carrier_name=config.get('default_carrier'))
                    if carrier_map is not None:
                        # Ensure carrier_map only contains columns present in aligned_dispatch_data
                        valid_cols_for_grouping = aligned_dispatch_data.columns.intersection(carrier_map.index)
                        if not valid_cols_for_grouping.empty:
                            grouped_dispatch = aligned_dispatch_data[valid_cols_for_grouping].groupby(
                                carrier_map.loc[valid_cols_for_grouping], axis=1
                            ).sum()
                            
                            # For storage-like components, split into Charge/Discharge
                            if comp_name_plural in ['storage_units', 'stores']:
                                for carrier in grouped_dispatch.columns:
                                    config['df_out'][f"{carrier} Discharge"] = grouped_dispatch[carrier].clip(lower=0)
                                    config['df_out'][f"{carrier} Charge"] = grouped_dispatch[carrier].clip(upper=0) # Negative is charge
                            else: # For generators
                                config['df_out'].update(grouped_dispatch)
    
    # Filter out all-zero columns that might have been created
    gen_dispatch_agg = gen_dispatch_agg.loc[:, (gen_dispatch_agg.abs() > 1e-6).any(axis=0)]
    storage_units_dispatch_agg = storage_units_dispatch_agg.loc[:, (storage_units_dispatch_agg.abs() > 1e-6).any(axis=0)]
    stores_dispatch_agg = stores_dispatch_agg.loc[:, (stores_dispatch_agg.abs() > 1e-6).any(axis=0)]
    
    # Resampling if required
    if resolution != "1H":
        time_index_for_resampling = get_time_index(effective_snapshots)
        if time_index_for_resampling is not None and not time_index_for_resampling.empty:
            def resample_if_exists(df_or_series, base_idx):
                if df_or_series.empty: return df_or_series
                temp = df_or_series.copy()
                if not isinstance(temp.index, pd.DatetimeIndex): # Ensure datetime index for resampling
                    temp.index = get_time_index(base_idx) # Use the original effective_snapshots time part
                return temp.resample(resolution).mean()

            gen_dispatch_agg = resample_if_exists(gen_dispatch_agg, effective_snapshots)
            load_dispatch_sum = resample_if_exists(load_dispatch_sum, effective_snapshots)
            storage_units_dispatch_agg = resample_if_exists(storage_units_dispatch_agg, effective_snapshots)
            stores_dispatch_agg = resample_if_exists(stores_dispatch_agg, effective_snapshots)
        else:
            logging.warning(f"Cannot resample data to {resolution}. Valid DatetimeIndex not available from effective_snapshots.")

    return gen_dispatch_agg, load_dispatch_sum, storage_units_dispatch_agg, stores_dispatch_agg

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
    components_to_check = {'Generator': 'generators', 'StorageUnit': 'storage_units', 'Store': 'stores'}

    for comp_class_name, comp_attr_name_in_n in components_to_check.items():
        if comp_attr_name_in_n in _n.components.keys():
            df_component_static = getattr(_n, comp_attr_name_in_n, pd.DataFrame())
            if df_component_static.empty: continue

            # Determine the correct capacity attribute to use (p_nom vs e_nom for Stores)
            attr_to_use = attribute
            if comp_class_name == 'Store' and attribute not in ['e_nom', 'e_nom_opt']:
                attr_to_use = 'e_nom_opt' if 'e_nom_opt' in df_component_static.columns else 'e_nom'
            elif comp_class_name != 'Store' and attribute not in ['p_nom', 'p_nom_opt']:
                attr_to_use = 'p_nom_opt' if 'p_nom_opt' in df_component_static.columns else 'p_nom'

            if attr_to_use not in df_component_static.columns:
                logging.debug(f"Attribute '{attr_to_use}' not found in component '{comp_class_name}'. Skipping.")
                continue
            
            df_active_assets = df_component_static
            # Filter assets if period_val_for_assets is provided (for multi-investment period models)
            if period_val_for_assets is not None and 'build_year' in df_component_static.columns and 'lifetime' in df_component_static.columns:
                try:
                    # Ensure period_val_for_assets is compatible type with build_year
                    typed_period = type(df_component_static['build_year'].iloc[0])(period_val_for_assets)
                    active_mask = (df_component_static['build_year'] <= typed_period) & \
                                  ((df_component_static['build_year'] + df_component_static['lifetime']) > typed_period)
                    df_active_assets = df_component_static[active_mask]
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
        if comp_attr_name_in_n in _n.components.keys():
            df_component_static = getattr(_n, comp_attr_name_in_n, pd.DataFrame())
            if df_component_static.empty or 'bus' not in df_component_static.columns: continue

            attr_to_use = attribute
            if comp_class_name == 'Store' and attribute not in ['e_nom', 'e_nom_opt']:
                attr_to_use = 'e_nom_opt' if 'e_nom_opt' in df_component_static.columns else 'e_nom'
            elif comp_class_name == 'Load': # Loads typically use p_set for demand capacity
                 attr_to_use = 'p_set' if 'p_set' in df_component_static.columns else attribute # Fallback if p_set not there
            elif comp_class_name not in ['Store', 'Load'] and attribute not in ['p_nom', 'p_nom_opt']:
                attr_to_use = 'p_nom_opt' if 'p_nom_opt' in df_component_static.columns else 'p_nom'

            if attr_to_use not in df_component_static.columns:
                logging.debug(f"Attribute '{attr_to_use}' not found in component '{comp_class_name}' for bus capacity. Skipping.")
                continue
            
            df_active_assets = df_component_static
            if period_val_for_assets is not None and 'build_year' in df_component_static.columns and 'lifetime' in df_component_static.columns:
                try:
                    typed_period = type(df_component_static['build_year'].iloc[0])(period_val_for_assets)
                    active_mask = (df_component_static['build_year'] <= typed_period) & \
                                  ((df_component_static['build_year'] + df_component_static['lifetime']) > typed_period)
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
    if 'generators' not in n.components.keys() or n.generators.empty or \
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
    if 'generators' not in n.components.keys() or n.generators.empty or \
       not hasattr(n, 'generators_t') or not all(c in n.generators_t for c in req_cols_t) or \
       'carrier' not in n.generators.columns or \
       not any(c in n.generators.columns for c in ['p_nom_opt', 'p_nom']): # Static capacity needed
        logging.warning("Missing essential data for curtailment calculation (generators, p, p_max_pu, p_nom/p_nom_opt, carrier).")
        return pd.DataFrame(columns=['Carrier', 'Curtailment (MWh)', 'Potential (MWh)', 'Curtailment (%)'])

    try:
        # Identify renewable generators (this might need to be more robust based on your carrier names)
        renewable_keywords = ['solar', 'wind', 'ror'] # Hydro RoR is often considered curtailable
        # Ensure carrier names are strings for matching
        n.generators['carrier_str'] = n.generators['carrier'].astype(str)
        renewable_carriers_names = [c for c in n.generators['carrier_str'].dropna().unique() if any(k in c.lower() for k in renewable_keywords)]
        
        renewable_gens_df = n.generators[n.generators['carrier_str'].isin(renewable_carriers_names)]
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
        if comp_name_plural in n.components.keys() and hasattr(n, f"{comp_name_plural}_t"):
            df_static = getattr(n, comp_name_plural, pd.DataFrame())
            if df_static.empty: continue

            soc_attr_name = config['soc_attr']
            comp_t_soc_data = getattr(n, f"{comp_name_plural}_t", {}).get(soc_attr_name)

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
    
    if 'generators' not in n.components.keys() or n.generators.empty or \
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
    if 'lines' in n.components.keys() and hasattr(n, 'lines_t') and 'p0' in n.lines_t and 'p1' in n.lines_t:
        p0_lines_aligned = n.lines_t.p0.reindex(index=effective_snapshots).fillna(0)
        p1_lines_aligned = n.lines_t.p1.reindex(index=effective_snapshots).fillna(0)
        # Sum of flows into the line from both ends; positive sum means net loss from system perspective.
        line_losses_t_series = (p0_lines_aligned + p1_lines_aligned).sum(axis=1) # Sum losses across all lines for each snapshot
        all_losses_timeseries_list.append(line_losses_t_series)

    # Link losses: Similar logic, but efficiency might be involved for some link types.
    # For simplicity, using p0+p1 for basic links. Transformers might have specific loss parameters.
    # PyPSA often models losses in links by having p0 != -p1 * efficiency.
    if 'links' in n.components.keys() and hasattr(n, 'links_t') and 'p0' in n.links_t and 'p1' in n.links_t:
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
    if 'lines' in n.components.keys()and hasattr(n, 'lines_t') and 'p0' in n.lines_t and not n.lines_t.p0.empty and \
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
        for idx_val, series_val in load_dispatch.items(): # Make sure load_dispatch.items() is appropriate
            load_data_records.append(OrderedDict([('timestamp', str(idx_val)), ('load', series_val if pd.notna(series_val) else 0.0)]))
    
    # Ensure using OrderedDict for consistent key order in JSON for older Python versions if that's a concern
    return {
        'generation': gen_dispatch.reset_index().to_dict('records', into=OrderedDict) if not gen_dispatch.empty else [],
        'load': load_data_records,
        'storage': storage_units_disp.reset_index().to_dict('records', into=OrderedDict) if not storage_units_disp.empty else [],
        'store': stores_disp.reset_index().to_dict('records', into=OrderedDict) if not stores_disp.empty else [],
        'timestamps': timestamps_for_payload,
        # 'colors' are added by the API wrapper in app.py
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

    # Generators
    if 'generators' in _n.components.keys()and hasattr(_n, 'generators_t') and 'p' in _n.generators_t:
        df_static_gens = getattr(_n, 'generators', pd.DataFrame())
        comp_t_data_gens = _n.generators_t.p
        if not df_static_gens.empty and not comp_t_data_gens.empty:
            carrier_map_gens = get_carrier_map(df_static_gens, carriers_df, 'Generator') # Default name if carrier is missing
            if carrier_map_gens is not None:
                aligned_data_gens = comp_t_data_gens.reindex(index=effective_snapshots, columns=df_static_gens.index).fillna(0)
                cols_for_grouping_gens = aligned_data_gens.columns.intersection(carrier_map_gens.index)
                if not cols_for_grouping_gens.empty:
                    # Ensure the carrier_map slice is valid
                    carrier_map_slice_gens = carrier_map_gens.loc[cols_for_grouping_gens]
                    if not carrier_map_slice_gens.empty:
                        gen_dispatch_agg_temp = aligned_data_gens[cols_for_grouping_gens].groupby(
                            carrier_map_slice_gens, axis=1
                        ).sum()
                        for col in gen_dispatch_agg_temp.columns:
                            gen_dispatch_agg[col] = gen_dispatch_agg_temp[col] # Assigns or updates columns

    # Loads
    if 'loads' in _n.components.keys()and hasattr(_n, 'loads_t'):
        df_static_loads = getattr(_n, 'loads', pd.DataFrame())
        load_p_attr = 'p_set' if 'p_set' in _n.loads_t else 'p'
        comp_t_data_loads = _n.loads_t.get(load_p_attr)
        if not df_static_loads.empty and comp_t_data_loads is not None and not comp_t_data_loads.empty:
            # Ensure columns for reindex match static df_static_loads
            aligned_data_loads = comp_t_data_loads.reindex(index=effective_snapshots, columns=df_static_loads.index).fillna(0)
            load_dispatch_sum.update(aligned_data_loads.sum(axis=1)) # Update pre-initialized Series

    # Storage Units and Stores
    for comp_name, df_out, default_suffix in [
        ('storage_units', storage_units_dispatch_agg, 'StorageUnit'),
        ('stores', stores_dispatch_agg, 'Store')
    ]:
        if comp_name in _n.components.keys()and hasattr(_n, f"{comp_name}_t") and 'p' in getattr(_n, f"{comp_name}_t", {}):
            df_static_storage = getattr(_n, comp_name, pd.DataFrame())
            comp_t_data_storage = getattr(_n, f"{comp_name}_t").p # Assuming 'p' exists if hasattr is true
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
                        return df_series # Cannot resample if no time index
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
    # 1. Get State of Charge (SoC) data, already filtered by snapshots_slice internally by get_storage_soc
    soc_df_processed = get_storage_soc(n, snapshots_slice=snapshots_slice)
    
    # Resample SoC data if needed (this happens based on resolution for display consistency)
    time_idx_for_soc_resample = get_time_index(soc_df_processed.index)
    soc_df_final_for_plot = soc_df_processed # Default to processed if no resampling
    if resolution != "1H" and time_idx_for_soc_resample is not None and not time_idx_for_soc_resample.empty:
        soc_df_temp_for_resample = soc_df_processed.copy()
        soc_df_temp_for_resample.index = time_idx_for_soc_resample # Ensure DatetimeIndex
        soc_df_final_for_plot = soc_df_temp_for_resample.resample(resolution).mean()
    
    timestamps_for_soc_payload = [str(ts) for ts in get_time_index(soc_df_final_for_plot.index)] if not soc_df_final_for_plot.empty else []
    storage_types_in_soc_payload = soc_df_final_for_plot.columns.tolist()

    # 2. Get storage charge/discharge dispatch data (already filtered by slice and resampled by get_dispatch_data)
    _, _, storage_units_dispatch, stores_dispatch = get_dispatch_data(n, _snapshots_slice=snapshots_slice, resolution=resolution)
    all_storage_dispatch_data = pd.concat([storage_units_dispatch, stores_dispatch], axis=1).fillna(0)
    
    storage_stats_records = []
    if not all_storage_dispatch_data.empty:
        # Weights should align with the index of all_storage_dispatch_data (which is already resampled if resolution != 1H)
        weights_for_dispatch_stats = get_snapshot_weights(n, all_storage_dispatch_data.index)
        
        charge_columns_in_dispatch = [c for c in all_storage_dispatch_data.columns if 'Charge' in c and all_storage_dispatch_data[c].abs().sum() > 1e-3]
        discharge_columns_in_dispatch = [c for c in all_storage_dispatch_data.columns if 'Discharge' in c and all_storage_dispatch_data[c].abs().sum() > 1e-3]
        processed_storage_bases = set()
        
        for discharge_col_name in discharge_columns_in_dispatch:
            # Extract base carrier name and component type suffix (e.g., "Battery", "(StorageUnit)")
            # Example col name: "Battery (StorageUnit) Discharge"
            base_name_match = discharge_col_name.replace(" Discharge", "") # "Battery (StorageUnit)"
            if base_name_match in processed_storage_bases: continue

            # Find corresponding charge column
            charge_col_match_name = next((c_col for c_col in charge_columns_in_dispatch if c_col.replace(" Charge", "") == base_name_match), None)

            if charge_col_match_name:
                discharge_series = all_storage_dispatch_data[discharge_col_name]
                charge_series = all_storage_dispatch_data[charge_col_match_name] # Charge values are negative

                # Calculate total energy charged and discharged using weights
                total_discharged_energy = (discharge_series * weights_for_dispatch_stats).sum()
                total_charged_energy = abs((charge_series * weights_for_dispatch_stats).sum()) # abs because charge is negative power
                
                efficiency_percent = (total_discharged_energy / total_charged_energy * 100) if total_charged_energy > 1e-6 else np.nan
                
                storage_stats_records.append(OrderedDict([
                    ('Storage_Type', base_name_match), # Use the base name like "Battery (StorageUnit)"
                    ('Charge_MWh', total_charged_energy),
                    ('Discharge_MWh', total_discharged_energy),
                    ('Efficiency_Percent', efficiency_percent if pd.notna(efficiency_percent) else None)
                ]))
                processed_storage_bases.add(base_name_match)
    
    return {
        'soc': soc_df_final_for_plot.reset_index().to_dict('records', into=OrderedDict) if not soc_df_final_for_plot.empty else [],
        'stats': storage_stats_records,
        'timestamps': timestamps_for_soc_payload, # Timestamps for the SoC plot
        'storage_types': storage_types_in_soc_payload # Column names from SoC data
    }

def emissions_payload_former(n, snapshots_slice=None, period_name=None, **kwargs) -> Dict[str, Any]:
    """Formats CO2 emissions data. `period_name` from URL for multi-period asset filtering."""
    # `calculate_co2_emissions` uses snapshots_slice for time-series aggregation.
    # `period_name` could be used if emissions factors change per period, but current `calculate_co2_emissions` doesn't use it directly for factors.
    # The primary use of period_name here is to filter the *output* if the network is multi-period.
    
    total_emissions_df, emissions_by_carrier_df = calculate_co2_emissions(n, snapshots_slice=snapshots_slice)
    
    # If period_name is provided (from URL query param for a multi-period network),
    # filter the already calculated (potentially period-aware) DataFrames.
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
    # `calculate_marginal_prices` handles snapshot slicing and resampling internally.
    price_data_processed = calculate_marginal_prices(n, snapshots_slice=snapshots_slice, resolution=resolution)
    
    if price_data_processed.empty:
        return {'available': False, 'message': 'No marginal prices available for the selected criteria.'}

    unit_str = "currency/MWh" # Default
    # Try to get a more specific currency unit if defined for buses
    if hasattr(n, 'buses') and 'unit' in n.buses.columns and not n.buses.unit.empty:
        bus_unit = n.buses.unit.dropna().iloc[0] if not n.buses.unit.dropna().empty else "currency"
        unit_str = f"{bus_unit}/MWh"
    
    avg_prices_by_bus = price_data_processed.mean(axis=0).sort_values(ascending=False) # Avg price per bus over time
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
    
    # For duration curve, use the system average price at each snapshot (if multiple buses)
    # or the single bus price if only one.
    if price_data_processed.shape[1] > 1: # More than one bus
        system_avg_price_per_snapshot = price_data_processed.mean(axis=1).dropna()
    else: # Single bus
        system_avg_price_per_snapshot = price_data_processed.iloc[:, 0].dropna()
        
    duration_curve_values = sorted(system_avg_price_per_snapshot.values, reverse=True) if not system_avg_price_per_snapshot.empty else []
    
    timestamps_for_payload = [str(ts) for ts in get_time_index(price_data_processed.index)] if not price_data_processed.empty else []

    return {
        'available': True,
        'unit': unit_str,
        'avg_by_bus': avg_price_records,
        'duration_curve': [float(p) for p in duration_curve_values], # Ensure floats for JSON
        'timestamps': timestamps_for_payload, # Timestamps of the (potentially resampled) price data
        'buses': price_data_processed.columns.tolist() # List of bus names
    }

def extract_api_network_flow_payload_former(n, snapshots_slice=None, period_name=None, **kwargs) -> Dict[str, Any]:
    """Formats network flow (losses, line loading) data. `period_name` for multi-period output filtering."""
    # `calculate_network_losses` and `calculate_line_loading` use snapshots_slice internally.
    losses_df = calculate_network_losses(n, snapshots_slice=snapshots_slice)
    line_loading_records = calculate_line_loading(n, snapshots_slice=snapshots_slice)

    # If period_name is given (from URL for a multi-period network), filter the losses DataFrame.
    # Line loading is typically an average over the slice, so less direct period filtering unless calculated per period.
    if period_name:
        if not losses_df.empty and 'Period' in losses_df.columns:
            losses_df = losses_df[losses_df['Period'] == str(period_name)]
    
    return {
        'losses': losses_df.to_dict('records', into=OrderedDict) if not losses_df.empty else [],
        'line_loading': line_loading_records # Already a list of dicts
    }

# --- Color Palette Generation (largely unchanged, minor robustness) ---
def get_color_palette(_n: pypsa.Network) -> Dict[str, str]:
    logging.debug("get_color_palette: Generating color palette...")
    final_colors = DEFAULT_COLORS.copy()
    color_idx_cycle = 0 # Index for Plotly color cycle
    
    # Helper to add a color if not already present, trying to match defaults first
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
        return existing_colors_dict[name] # Return the color (new or existing)

    # 1. Process carriers from n.carriers DataFrame
    if hasattr(_n, "carriers") and isinstance(_n.carriers, pd.DataFrame) and not _n.carriers.empty:
        carriers_df_copy = _n.carriers.copy()
        if 'nice_name' not in carriers_df_copy.columns:
             carriers_df_copy['nice_name'] = carriers_df_copy.index
        
        for carrier_idx, row_data in carriers_df_copy.iterrows():
            original_carrier_name = str(carrier_idx)
            nice_carrier_name = str(row_data.get("nice_name", original_carrier_name))
            
            color_in_df = row_data.get("color") if "color" in row_data and pd.notna(row_data["color"]) and row_data["color"] != "" else None
            
            if color_in_df:
                final_colors[nice_carrier_name] = color_in_df
                if nice_carrier_name != original_carrier_name:
                    final_colors[original_carrier_name] = color_in_df # Also map original name if different
            else:
                # If no color in df, try to assign based on default matches or cycle
                color_for_nice_name = add_color_if_new(nice_carrier_name, final_colors, [color_idx_cycle])
                if nice_carrier_name != original_carrier_name and original_carrier_name not in final_colors:
                    final_colors[original_carrier_name] = color_for_nice_name
    
    # 2. Collect all unique carrier names actually used by components
    all_component_carrier_names = set()
    for comp_type_plural in ['generators', 'storage_units', 'stores', 'links']: # Add more if relevant
        if hasattr(_n, comp_type_plural):
            comp_df = getattr(_n, comp_type_plural)
            if isinstance(comp_df, pd.DataFrame) and not comp_df.empty and 'carrier' in comp_df.columns:
                unique_carriers_in_comp = comp_df['carrier'].dropna().unique()
                for orig_carrier_name_in_comp in unique_carriers_in_comp:
                    # Get its 'nice_name' if available from n.carriers
                    nice_name_from_carriers_df = orig_carrier_name_in_comp # Default to original
                    if hasattr(_n, 'carriers') and isinstance(_n.carriers, pd.DataFrame) and \
                       'nice_name' in _n.carriers.columns and orig_carrier_name_in_comp in _n.carriers.index:
                        val = _n.carriers.loc[orig_carrier_name_in_comp, 'nice_name']
                        if pd.notna(val): nice_name_from_carriers_df = val
                    
                    all_component_carrier_names.add(str(nice_name_from_carriers_df))
                    if str(nice_name_from_carriers_df) != str(orig_carrier_name_in_comp):
                         all_component_carrier_names.add(str(orig_carrier_name_in_comp))


    # 3. Ensure all used component carriers have a color
    for name_to_color in sorted(list(all_component_carrier_names)):
        add_color_if_new(name_to_color, final_colors, [color_idx_cycle])

    # 4. Ensure default keys related to storage charge/discharge are present using their specific default colors
    #    This is for cases where the JS might look for "Storage Charge" generically.
    for charge_discharge_key in ['Storage Charge', 'Storage Discharge', 'Store Charge', 'Store Discharge']:
        if charge_discharge_key not in final_colors and charge_discharge_key in DEFAULT_COLORS:
            final_colors[charge_discharge_key] = DEFAULT_COLORS[charge_discharge_key]
            
    # 5. Add colors for specific storage component names like "Battery (StorageUnit) Charge"
    #    This derives from the base component color if not explicitly set.
    for comp_name_key in final_colors.copy().keys(): # Iterate on copy as dict might change
        base_color_for_comp = final_colors[comp_name_key]
        if any(st_kw in comp_name_key.lower() for st_kw in ['storage', 'store', 'battery', 'psp', 'hydro', 'h2']):
             add_color_if_new(f"{comp_name_key} Charge", final_colors, [color_idx_cycle])
             add_color_if_new(f"{comp_name_key} Discharge", final_colors, [color_idx_cycle])


    logging.debug(f"get_color_palette: Final palette has {len(final_colors)} entries.")
    return final_colors

# Plotting functions remain largely the same as they consume processed data.
# Ensure they use the `carrier_colors` map effectively.
# Minor adjustments for robustness, e.g., checking if data is empty before plotting.

def plot_dispatch_stack(gen_dispatch, load_dispatch, storage_dispatch, store_dispatch, carrier_colors, 
                        title="Power Dispatch and Load", plot_index=None, resolution="1H"):
    fig = go.Figure()
    # Combine all storage-like dispatch for stacking logic
    all_storage_like_dispatch = pd.concat([storage_dispatch, store_dispatch], axis=1).fillna(0)

    # Determine the primary index for plotting (could be from any non-empty df)
    if plot_index is None:
        if not gen_dispatch.empty: plot_index = gen_dispatch.index
        elif not load_dispatch.empty: plot_index = load_dispatch.index
        elif not all_storage_like_dispatch.empty: plot_index = all_storage_like_dispatch.index
        else:
            logging.warning("plot_dispatch_stack: All dispatch data is empty. Cannot create plot.")
            return fig # Return empty figure
    
    plot_time_index = get_time_index(plot_index) # Convert to DatetimeIndex for x-axis
    if plot_time_index is None:
        logging.warning("plot_dispatch_stack: Could not obtain valid time index for plotting.")
        return fig

    # Plotting generation
    for carrier in sorted(gen_dispatch.columns):
        color = carrier_colors.get(carrier, DEFAULT_COLORS.get('Other', '#D3D3D3'))
        fig.add_trace(go.Scatter(
            x=plot_time_index, y=gen_dispatch[carrier].reindex(plot_index).fillna(0), # Reindex to ensure alignment
            mode='lines', name=carrier, stackgroup='positive_generation', 
            line=dict(width=0), fill='tonexty', fillcolor=color,
            hovertemplate='%{x|%Y-%m-%d %H:%M}<br>' + f'{carrier}: %{{y:,.1f}} MW<extra></extra>'
        ))

    # Plotting storage discharge (positive contribution)
    discharge_cols = sorted([c for c in all_storage_like_dispatch.columns if 'Discharge' in c and all_storage_like_dispatch[c].sum() > 1e-3])
    for col_name in discharge_cols:
        # Try to find color for base carrier name (e.g. "Battery" from "Battery Discharge")
        base_carrier_name_for_color = col_name.replace(" Discharge", "")
        color = carrier_colors.get(col_name, carrier_colors.get(base_carrier_name_for_color, DEFAULT_COLORS.get('Storage Discharge', '#50C878')))
        fig.add_trace(go.Scatter(
            x=plot_time_index, y=all_storage_like_dispatch[col_name].reindex(plot_index).fillna(0),
            mode='lines', name=col_name, stackgroup='positive_storage_discharge', # Separate stack group for storage
            line=dict(width=0), fill='tonexty', fillcolor=color,
            hovertemplate='%{x|%Y-%m-%d %H:%M}<br>' + f'{col_name}: %{{y:,.1f}} MW<extra></extra>'
        ))

    # Plotting storage charge (negative contribution, plotted as positive in a negative stack group)
    charge_cols = sorted([c for c in all_storage_like_dispatch.columns if 'Charge' in c and all_storage_like_dispatch[c].sum() < -1e-3])
    for col_name in charge_cols:
        base_carrier_name_for_color = col_name.replace(" Charge", "")
        color = carrier_colors.get(col_name, carrier_colors.get(base_carrier_name_for_color, DEFAULT_COLORS.get('Storage Charge', '#FFA500')))
        # Values are negative, Plotly stacks negative values correctly if stackgroup is different or y is made positive for visual stack
        fig.add_trace(go.Scatter(
            x=plot_time_index, y=all_storage_like_dispatch[col_name].reindex(plot_index).fillna(0), # Keep negative for y-axis
            mode='lines', name=col_name, stackgroup='negative_storage_charge', 
            line=dict(width=0), fill='tonexty', fillcolor=color,
            hovertemplate='%{x|%Y-%m-%d %H:%M}<br>' + f'{col_name}: %{{y:,.1f}} MW (Charge)<extra></extra>'
        ))
    
    # Plotting load
    if not load_dispatch.empty and not load_dispatch.isna().all() and load_dispatch.abs().sum() > 0:
        fig.add_trace(go.Scatter(
            x=plot_time_index, y=load_dispatch.reindex(plot_index).fillna(0),
            mode='lines', name='Load', 
            line=dict(color=carrier_colors.get('Load', 'black'), width=2.5),
            hovertemplate='%{x|%Y-%m-%d %H:%M}<br>Load: %{y:,.1f}} MW<extra></extra>'
        ))

    resolution_info = f" ({resolution} resolution)" if resolution != "1H" and resolution is not None else ""
    title_with_res = f"{title}{resolution_info}"
    
    fig.update_layout(
        title=title_with_res,
        xaxis_title="Time", 
        yaxis_title="Power (MW)", 
        hovermode='x unified', 
        legend_title="Component/Carrier", 
        height=600, 
        yaxis=dict(zeroline=True, zerolinecolor='grey', zerolinewidth=1), # Grey zeroline
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1) # Legend on top
    )
    return fig

# Other plotting functions (create_daily_profile_plot, create_duration_curve, etc.)
# would benefit from similar robustness checks (empty data, valid time index if needed).
# For brevity, I'm not re-listing them here but assume they'd be reviewed.