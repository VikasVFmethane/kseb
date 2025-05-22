import pandas as pd
from utils.helpers import extract_table,extract_tables_by_markers
def input_demand_data(demand_input_file_path):
    """Process the input demand Excel file."""
    try:
        main_settings = pd.read_excel(demand_input_file_path, sheet_name='main')
        main_settings_parameters = extract_tables_by_markers(main_settings, "~")
        settings = main_settings_parameters.get('Settings')
        
        # Convert to dictionary
        param_dict = dict(zip(settings['Parameters'], settings['Inputs']))
        
        # Access parameters - ensure they're proper integers
        try:
            Start_Year = int(param_dict.get('Start_Year'))
            End_Year = int(param_dict.get('End_Year'))
            print(f"Extracted parameters from settings: Start_Year={Start_Year}, End_Year={End_Year}")
        except (ValueError, TypeError) as e:
            print(f"Error converting year parameters to integers: {e}")
            # Set defaults if conversion fails
            Start_Year = 2006
            End_Year = 2037
            print(f"Using default years: Start_Year={Start_Year}, End_Year={End_Year}")
            
        Econometric_Parameters = param_dict.get('Econometric_Parameters')
        sectors = main_settings_parameters.get('Consumption_Sectors')['Sector_Name'].to_list()
        
        sector_data = {}
        missing_sectors = []
        Aggregated_ele = pd.DataFrame()
        
        # Load Economic Indicators if needed
        Economic_Indicators = None
        if Econometric_Parameters == 'Yes':
            try:
                Economic_Indicators = pd.read_excel(demand_input_file_path, sheet_name='Economic_Indicators')
                print(f"Loaded Economic Indicators with columns: {Economic_Indicators.columns.tolist()}")
            except Exception as e:
                print(f"Failed to load Economic Indicators: {e}")
        
        for sector in sectors:
            try:
                # Load sector data
                sector_data[sector] = pd.read_excel(demand_input_file_path, sheet_name=sector)
                print(f"Loaded sector {sector} with columns: {sector_data[sector].columns.tolist()}")
                
                # Process economic parameters if enabled
                if Econometric_Parameters == 'Yes' and Economic_Indicators is not None:
                    try:
                        # Get parameters for this sector
                        Econometric_Parameters_sector_wise = main_settings_parameters.get('Econometric_Parameters')[sector].dropna().to_list()
                        print(f"Economic parameters for {sector}: {Econometric_Parameters_sector_wise}")
                        
                        # If Economic_Indicators has a Year column, do year-by-year mapping
                        if 'Year' in Economic_Indicators.columns:
                            for indicator in Econometric_Parameters_sector_wise:
                                if indicator in Economic_Indicators.columns:
                                    # Create mapping of years to indicator values
                                    year_to_value = dict(zip(Economic_Indicators['Year'], Economic_Indicators[indicator]))
                                    
                                    # Apply mapping only to years that exist in the data
                                    sector_data[sector][indicator] = sector_data[sector]['Year'].map(
                                        lambda year: year_to_value.get(year) if year in year_to_value else None
                                    )
                                    print(f"Mapped {indicator} values by year for {sector}")
                                else:
                                    print(f"Warning: Indicator {indicator} not found in Economic Indicators columns: {Economic_Indicators.columns.tolist()}")
                        else:
                            # No Year column - just use first row values
                            print("Economic Indicators has no Year column, using first row values for all years")
                            for indicator in Econometric_Parameters_sector_wise:
                                if indicator in Economic_Indicators.columns and not Economic_Indicators[indicator].empty:
                                    first_value = Economic_Indicators[indicator].iloc[0]
                                    sector_data[sector][indicator] = first_value
                                    print(f"Applied constant value {first_value} for {indicator} in {sector}")
                                else:
                                    print(f"Warning: Indicator {indicator} not found or empty in Economic Indicators")
                    except Exception as e:
                        print(f"Error processing economic parameters for {sector}: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Merge electricity values by year for aggregation
                if 'Year' in sector_data[sector].columns and 'Electricity' in sector_data[sector].columns:
                    sector_electricity = sector_data[sector][['Year', 'Electricity']].copy()
                    
                    if Aggregated_ele.empty:
                        Aggregated_ele = sector_electricity.copy()
                        Aggregated_ele.rename(columns={'Electricity': sector}, inplace=True)
                    else:
                        # Use outer join to include all years
                        Aggregated_ele = pd.merge(
                            Aggregated_ele,
                            sector_electricity.rename(columns={'Electricity': sector}),
                            on='Year',
                            how='outer'
                        )
                else:
                    print(f"Warning: Sector {sector} missing Year or Electricity columns")
            except Exception as e:
                print(f"Error processing sector {sector}: {e}")
                import traceback
                traceback.print_exc()
                missing_sectors.append(sector)
        
        # Calculate total electricity, handling NaN values
        if not Aggregated_ele.empty and 'Year' in Aggregated_ele.columns:
            # Fill NaN values with 0 for calculation
            calc_df = Aggregated_ele.fillna(0)
            # Calculate total excluding the Year column
            data_columns = [col for col in calc_df.columns if col != 'Year']
            if data_columns:
                Aggregated_ele['Total'] = calc_df[data_columns].sum(axis=1)
                print(f"Calculated Total column for aggregated data")
        
        # Add Start_Year and End_Year to param_dict for use in forecasting
        param_dict['Start_Year'] = Start_Year
        param_dict['End_Year'] = End_Year
        
        return sectors, missing_sectors, param_dict, sector_data, Aggregated_ele
    except Exception as e:
        print(f"Error processing input file: {e}")
        import traceback
        traceback.print_exc()
        return [], [], {}, {}, pd.DataFrame()