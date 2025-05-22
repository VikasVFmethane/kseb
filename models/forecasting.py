def Main_forecasting_function(sheet_name, forecast_path, main_df, selected_models=None, model_params=None, target_year=2037, exclude_covid=True):
    """
    Main forecasting function for generating electricity demand projections.
    
    Args:
        sheet_name (str): Name of the sheet/sector being processed
        forecast_path (str): Path to save forecast results
        main_df (pd.DataFrame): Input DataFrame containing the data
        selected_models (list, optional): Models to use (e.g., ['MLR', 'SLR', 'WAM', 'TimeSeries'])
        model_params (dict, optional): Parameters for specific models, structured as {'ModelName': {param_dict}}
        target_year (int, optional): Target year for forecast. Defaults to 2037.
        exclude_covid (bool, optional): Whether to exclude COVID years. Defaults to True.
    
    Returns:
        dict: Results and status information
    """
    import os
    import warnings
    import numpy as np
    import pandas as pd
    from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_percentage_error
    from sklearn.linear_model import LinearRegression
    from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
    import xlsxwriter
    
    # Suppress warnings
    warnings.filterwarnings('ignore')
    
    # Initialize parameters with defaults
    selected_models = selected_models or ['MLR', 'SLR', 'WAM', 'TimeSeries']
    model_params = model_params or {}
    
    # Extract model-specific parameters
    mlr_params = model_params.get('MLR', {})
    wam_params = model_params.get('WAM', {})
    
    # Get parameters with defaults
    independent_vars = mlr_params.get('independent_vars', [])
    window_size = int(wam_params.get('window_size', 10))
    
    # Constants
    COVID_YEARS = [2021, 2022]
    SCENARIO_NAME = forecast_path
    TARGET_YEAR = target_year
    
    # Create a copy of the original dataframe to preserve it
    main_with_covid = main_df.copy()
    
    # Check if this data can be forecast and if we already have data up to target year
    if 'Year' in main_df.columns and 'Electricity' in main_df.columns:
        # Check latest year with valid electricity data
        electricity_df = main_df[['Year', 'Electricity']].dropna()
        
        if not electricity_df.empty:
            electricity_max_year = electricity_df['Year'].max()
            electricity_min_year = electricity_df['Year'].min()
            
            # If data already exists up to target year, use it instead of forecasting
            if electricity_max_year >= TARGET_YEAR:
                print(f"Sector {sheet_name} already has electricity data up to {electricity_max_year}")
                
                # Save the existing data with "User Data" as model name
                result_df = main_df[['Year', 'Electricity']].copy()
                result_df.rename(columns={'Electricity': 'User Data'}, inplace=True)
                
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(f'{SCENARIO_NAME}/{sheet_name}.xlsx'), exist_ok=True)
                
                # Save to Excel with all required sheets
                with pd.ExcelWriter(f'{SCENARIO_NAME}/{sheet_name}.xlsx', engine='xlsxwriter') as writer:
                    main_df.to_excel(writer, sheet_name='Inputs', index=False)
                    result_df.to_excel(writer, sheet_name='Results', index=False)
                    
                    # Create a sheet with only correlations against Electricity
                    try:
                        numeric_df = main_df.select_dtypes(include=['number'])
                        if 'Electricity' in numeric_df.columns and not numeric_df.empty:
                            corr_matrix = numeric_df.corr()
                            # Extract only correlations with Electricity
                            elec_corr = pd.DataFrame({
                                'Variable': corr_matrix.index,
                                'Correlation_with_Electricity': corr_matrix['Electricity']
                            })
                            elec_corr = elec_corr[elec_corr['Variable'] != 'Electricity']  # Remove self-correlation
                            elec_corr = elec_corr.sort_values('Correlation_with_Electricity', ascending=False)
                            elec_corr.to_excel(writer, sheet_name='Correlations', index=False)
                    except Exception as e:
                        print(f"Error creating correlation sheet: {e}")
                
                return {
                    "status": "success",
                    "message": f"Used existing data for {sheet_name} (up to {electricity_max_year})",
                    "used_existing_data": True
                }
        
        # Create a copy of the main dataframe for forecasting
        if exclude_covid:
            # Filter out COVID years if requested
            main_df = main_df[~main_df['Year'].isin(COVID_YEARS)].copy()
        
        def weighted_average_forecast(df, forecast_years, window_size):
            """Calculate weighted average forecast based on historical data."""
            if window_size < 2:
                raise ValueError("window_size must be at least 2")
            
            df = df.sort_values(by='Year').reset_index(drop=True)
            df["% increase"] = (df["Electricity"]/df["Electricity"].shift(1))**(1/(df["Year"]-df["Year"].shift(1)))-1
            
            # Skip NaN values (first row)
            df_filtered = df.dropna(subset=["% increase"])
            
            # Adjust window size if not enough data
            actual_window_size = min(window_size, len(df_filtered))
            if actual_window_size < window_size:
                print(f"Warning: Not enough data for window size {window_size}, using {actual_window_size} instead")
            
            weights = np.array([i/sum(range(1, actual_window_size + 1)) for i in range(1, actual_window_size + 1)])
            last_n_years = df_filtered["% increase"].tail(actual_window_size).values
            weighted_growth_rate = np.average(last_n_years, weights=weights)
            
            last_year = df['Year'].max()
            last_value = df.loc[df['Year'] == last_year, 'Electricity'].values[0]
            forecast_df = pd.DataFrame({'Year': range(last_year + 1, forecast_years + 1)})
            
            forecast_values = [last_value]
            for _ in range(len(forecast_df)):
                next_value = forecast_values[-1] * (1 + weighted_growth_rate)
                forecast_values.append(next_value)
            
            forecast_df['Electricity'] = forecast_values[1:]
            result_df = pd.concat([df, forecast_df], ignore_index=True)
            
            return result_df[['Year', 'Electricity']]
        
        def prepare_data(df):
            """
            Prepare data by splitting into training and testing sets based on year.
            """
            # Create a copy to avoid modifying the original
            df = df.copy()
            
            # Find the min and max years in the data
            min_year = df['Year'].min()
            max_year = df['Year'].max()
            
            # Calculate split year as 75% of the data range (ensures sufficient training data)
            data_range = max_year - min_year
            split_year = min_year + int(data_range * 0.75)
            print(f"Using data from {min_year} to {max_year}, with split_year: {split_year}")
            
            # Drop Connected Load if it exists
            if 'Connected Load' in df.columns:
                df = df.drop('Connected Load', axis=1)
            
            # Check if we have any independent variables other than Year and Electricity
            all_independent_variables = [col for col in df.columns if col not in ['Year', 'Electricity']]
            
            # Check data completeness for independent variables
            valid_independent_vars = []
            
            for var in all_independent_variables:
                # Check if variable has any data
                var_df = df[['Year', var]].dropna()
                if var_df.empty:
                    print(f"Warning: Variable {var} has no valid data, removing from model")
                    continue
                
                # Check if variable has sufficient data for training
                training_data = var_df[var_df['Year'] < split_year]
                if len(training_data) < 2:  # Need at least 2 points for training
                    print(f"Warning: Variable {var} has insufficient training data, removing from model")
                    continue
                
                valid_independent_vars.append(var)
            
            # If we have specific independent variables requested, use only those
            independent_variables = []
            if independent_vars and len(independent_vars) > 0:
                for var in independent_vars:
                    if var in valid_independent_vars:
                        independent_variables.append(var)
                    else:
                        print(f"Warning: Requested variable '{var}' not found or not valid")
                
                if not independent_variables:
                    print(f"Warning: None of the specified independent variables {independent_vars} are valid. Using all valid variables.")
                    independent_variables = valid_independent_vars
            else:
                independent_variables = valid_independent_vars
            
            print(f"Final independent variables for model: {independent_variables}")
            
            # Make sure we have at least one independent variable
            if not independent_variables:
                print("Warning: No valid independent variables found. Falling back to using Year only.")
                independent_variables = ['Year']
                # If 'Year' isn't in the dataframe, we need to add it
                if 'Year' not in df.columns:
                    df['Year'] = df.index
            
            # Create a copy of df with only Year, Electricity, and the selected independent variables
            columns_to_use = list(set(['Year', 'Electricity'] + independent_variables))
            df_filtered = df[columns_to_use].copy()
            
            # Fill NaN values with mean for each column (except Year)
            for col in df_filtered.columns:
                if col != 'Year':
                    mean_value = df_filtered[col].mean()
                    if pd.isna(mean_value):  # If mean is also NaN (all values are NaN)
                        mean_value = 0
                    df_filtered[col] = df_filtered[col].fillna(mean_value)
            
            # Split data for training and testing
            df_train = df_filtered[df_filtered['Year'] < split_year].copy()
            df_test = df_filtered[df_filtered['Year'] >= split_year].copy()
            
            # Verify we have training data
            if df_train.empty:
                print("ERROR: No training data available. Adjusting split year.")
                # Adjust split year to ensure at least 70% of data is in training
                num_years = len(df_filtered['Year'].unique())
                training_size = max(2, int(num_years * 0.7))  # At least 2 years or 70%
                sorted_years = sorted(df_filtered['Year'].unique())
                if len(sorted_years) <= training_size:
                    # Use all but the last year for training
                    new_split_year = sorted_years[-1]
                else:
                    new_split_year = sorted_years[training_size]
                
                print(f"Adjusted split_year from {split_year} to {new_split_year}")
                df_train = df_filtered[df_filtered['Year'] < new_split_year].copy()
                df_test = df_filtered[df_filtered['Year'] >= new_split_year].copy()
            
            # For MLR, use the independent variables (excluding Year unless it's the only one)
            mlr_independent_vars = [var for var in independent_variables if var != 'Year'] or ['Year']
            X_train = df_train[mlr_independent_vars].copy()
            y_train = df_train['Electricity'].copy()
            
            # For testing, use the same variables as training
            X_test = df_test[mlr_independent_vars].copy()
            y_test = df_test['Electricity'].copy() if not df_test.empty else pd.Series()
            
            # For SLR, always use Year as the predictor
            X_train_slr = df_train['Year'].values.reshape(-1, 1)
            X_test_slr = df_test['Year'].values.reshape(-1, 1) if not df_test.empty else np.array([]).reshape(0, 1)
            
            # For full dataset (for final model)
            X = df_filtered[mlr_independent_vars].copy()
            y = df_filtered['Electricity'].copy()
            X_slr = df_filtered['Year'].values.reshape(-1, 1)
            
            return X_train, X_test, y_train, y_test, X_train_slr, X_test_slr, df_test, X, y, X_slr, mlr_independent_vars
        
        def train_models(X_train, X_train_slr, y_train, models_to_train=None):
            """Train models using GridSearchCV with TimeSeriesSplit."""
            param_grids = {
                'MLR': {'fit_intercept': [True, False]},
                'SLR': {'fit_intercept': [True, False]}
            }
            
            # Determine which models to train
            if models_to_train is None:
                models_to_train = ['MLR', 'SLR']
            elif isinstance(models_to_train, str):
                models_to_train = [models_to_train]
                
            # Ensure we have enough samples for cross-validation
            n_splits = min(5, len(X_train) - 1)  # Ensure at least 1 sample per fold
            if n_splits < 2:
                print("Warning: Not enough samples for cross-validation. Using default parameters.")
                models = {}
                
                if 'MLR' in models_to_train and X_train.shape[0] > 0:
                    print(f"Training MLR with {X_train.shape[0]} samples")
                    mlr = LinearRegression()
                    mlr.fit(X_train, y_train)
                    models['MLR'] = mlr
                
                if 'SLR' in models_to_train and X_train_slr.shape[0] > 0:
                    print(f"Training SLR with {X_train_slr.shape[0]} samples")
                    slr = LinearRegression()
                    slr.fit(X_train_slr, y_train)
                    models['SLR'] = slr
                
                return models
            
            # If we have enough samples, use cross-validation
            tscv = TimeSeriesSplit(n_splits=n_splits)
            models = {}
            
            # Train models as requested
            if 'MLR' in models_to_train and X_train.shape[0] > 0 and X_train.shape[1] > 0:
                print(f"Training Multiple Linear Regression for {sheet_name} with {X_train.shape[0]} samples and {X_train.shape[1]} features")
                try:
                    mlr_grid = GridSearchCV(
                        LinearRegression(), 
                        param_grids['MLR'],
                        cv=tscv, 
                        scoring='r2'
                    )
                    mlr_grid.fit(X_train, y_train)
                    models['MLR'] = mlr_grid
                    print(f"MLR training complete. Best params: {mlr_grid.best_params_}")
                except Exception as e:
                    print(f"Error training MLR: {str(e)}")
                    print("Using default parameters for MLR.")
                    mlr = LinearRegression()
                    mlr.fit(X_train, y_train)
                    models['MLR'] = mlr
            
            if 'SLR' in models_to_train and X_train_slr.shape[0] > 0:
                print(f"Training Simple Linear Regression for {sheet_name} with {X_train_slr.shape[0]} samples")
                try:
                    slr_grid = GridSearchCV(
                        LinearRegression(), 
                        param_grids['SLR'],
                        cv=tscv, 
                        scoring='r2'
                    )
                    slr_grid.fit(X_train_slr, y_train)
                    models['SLR'] = slr_grid
                    print(f"SLR training complete. Best params: {slr_grid.best_params_}")
                except Exception as e:
                    print(f"Error training SLR: {str(e)}")
                    print("Using default parameters for SLR.")
                    slr = LinearRegression()
                    slr.fit(X_train_slr, y_train)
                    models['SLR'] = slr
            
            return models
        
        def evaluate_model(y_true, y_pred):
            """Evaluate model performance using various metrics."""
            if len(y_true) == 0 or len(y_pred) == 0:
                return {
                    'MSE': np.nan,
                    'R²': np.nan,
                    'MAPE (%)': np.nan
                }
                
            mse = mean_squared_error(y_true, y_pred)
            r2 = r2_score(y_true, y_pred)
            
            # Avoid division by zero in MAPE calculation
            if (y_true == 0).any():
                mape = np.nan
            else:
                mape = mean_absolute_percentage_error(y_true, y_pred) * 100
            
            return {
                'MSE': mse,
                'R²': r2,
                'MAPE (%)': mape
            }
        
        def time_series_forecast(df, col, target_year=TARGET_YEAR):
            """Time Series Decomposition and Forecasting using SARIMA and Prophet."""
            try:
                # Attempt to import necessary packages
                try:
                    from statsmodels.tsa.statespace.sarimax import SARIMAX
                    from prophet import Prophet
                except ImportError:
                    print("Warning: Could not import Prophet or SARIMAX. Using simple forecasting method.")
                    # Use simple linear trend as fallback
                    df = df.copy()
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    df = df[['Year', col]].dropna()
                    
                    if len(df) < 2:
                        print(f"Insufficient data points for column {col}, using zeros")
                        future_years = range(df['Year'].max() + 1 if not df.empty else 2023, target_year + 1)
                        return np.zeros(len(future_years))
                    
                    X = df['Year'].values.reshape(-1, 1)
                    y = df[col].values
                    
                    model = LinearRegression()
                    model.fit(X, y)
                    
                    future_years = np.array(range(df['Year'].max() + 1, target_year + 1)).reshape(-1, 1)
                    if len(future_years) == 0:  # No years to forecast
                        return np.array([])
                        
                    forecasted_values = model.predict(future_years)
                    return forecasted_values
                
                df = df.copy()
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df[['Year', col]].dropna()
                
                if len(df) < 2:
                    print(f"Insufficient data points for column {col}, using zeros")
                    future_years = range(df['Year'].max() + 1 if not df.empty else 2023, target_year + 1)
                    return np.zeros(len(future_years))
                
                # Check if we already have data up to the target year
                if target_year <= df['Year'].max():
                    print(f'Already have {col} data up to {df["Year"].max()}')
                    # Find which years are already covered
                    existing_years = df['Year'].tolist()
                    future_years = [y for y in range(df['Year'].min(), target_year + 1) if y not in existing_years]
                    
                    if not future_years:  # If no future years to forecast
                        return np.array([])  # Return empty array since nothing to forecast
                
                # Determine years to forecast
                last_year = df['Year'].max()
                forecast_years = range(last_year + 1, target_year + 1)
                
                if not forecast_years:  # Nothing to forecast
                    return np.array([])
                
                # Prepare time series data
                ts_data = pd.Series(
                    df[col].values,
                    index=pd.date_range(
                        start=f"{df['Year'].min()}-01-01",
                        periods=len(df),
                        freq='Y'
                    )
                ).astype(float)
                
                # Try SARIMA model
                sarima_forecast = None
                try:
                    model = SARIMAX(ts_data, order=(1, 1, 1))
                    fitted = model.fit(disp=False)
                    sarima_forecast = fitted.forecast(steps=len(forecast_years))
                except Exception as e:
                    print(f"SARIMA failed for {col}: {str(e)}")
                
                # Try Prophet model
                prophet_forecast = None
                try:
                    prophet_data = pd.DataFrame({
                        'ds': ts_data.index,
                        'y': ts_data.values
                    })
                    prophet_model = Prophet(yearly_seasonality=True)
                    prophet_model.fit(prophet_data)
                    future_dates = prophet_model.make_future_dataframe(
                        periods=len(forecast_years),
                        freq='Y'
                    )
                    prophecy = prophet_model.predict(future_dates)
                    prophet_forecast = prophecy['yhat'].tail(len(forecast_years)).values
                except Exception as e:
                    print(f"Prophet failed for {col}: {str(e)}")
                
                # Decide which forecast to use
                if sarima_forecast is not None and prophet_forecast is not None:
                    # Use average of both forecasts
                    y_predict = (sarima_forecast.values + prophet_forecast) / 2
                elif sarima_forecast is not None:
                    y_predict = sarima_forecast.values
                elif prophet_forecast is not None:
                    y_predict = prophet_forecast
                else:
                    # Both models failed, use linear regression as fallback
                    print(f"Using linear regression fallback for {col}")
                    X = df['Year'].values.reshape(-1, 1)
                    y = df[col].values
                    
                    model = LinearRegression()
                    model.fit(X, y)
                    
                    if len(forecast_years) == 0:
                        return np.array([])
                        
                    future_years = np.array(range(last_year + 1, target_year + 1)).reshape(-1, 1)
                    y_predict = model.predict(future_years)
                
                return y_predict
            
            except Exception as e:
                print(f"Error in forecasting {col}: {str(e)}")
                # Return zeros as a safe fallback
                future_years = range(df['Year'].max() + 1 if 'Year' in df.columns and not df.empty else 2023, 
                                     target_year + 1)
                return np.zeros(len(future_years))
        def save_results(sheet_name, main_df, result_df_final, evaluation_test_df, models, X_forecast, independent_variables):
            """Save results to Excel file."""
            df = main_with_covid.copy()
            
            # If no explicit results provided (when no forecasting needed), create results from main data
            if result_df_final is None or result_df_final.empty:
                result_df_final = main_df[['Year', 'Electricity']].copy()
                result_df_final.rename(columns={'Electricity': 'User Data'}, inplace=True)
            
            # Calculate correlation with Electricity
            try:
                numeric_df = df.select_dtypes(include=['number'])
                if 'Electricity' in numeric_df.columns and not numeric_df.empty:
                    corr_matrix = numeric_df.corr()
                    # Extract only correlations with Electricity
                    elec_corr = pd.DataFrame({
                        'Variable': corr_matrix.index,
                        'Correlation_with_Electricity': corr_matrix['Electricity']
                    })
                    elec_corr = elec_corr[elec_corr['Variable'] != 'Electricity']  # Remove self-correlation
                    
                    # Add correlation strength description
                    def get_corr_strength(corr_value):
                        abs_corr = abs(corr_value)
                        if abs_corr >= 0.7:
                            return 'Strong'
                        elif abs_corr >= 0.4:
                            return 'Moderate'
                        else:
                            return 'Weak'
                    
                    elec_corr['Strength'] = elec_corr['Correlation_with_Electricity'].apply(get_corr_strength)
                    elec_corr = elec_corr.sort_values('Correlation_with_Electricity', key=abs, ascending=False)
                else:
                    elec_corr = pd.DataFrame()
            except Exception as e:
                print(f"Error calculating correlation matrix: {str(e)}")
                elec_corr = pd.DataFrame()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(f'{SCENARIO_NAME}/{sheet_name}.xlsx'), exist_ok=True)
            
            # Save to Excel
            try:
                with pd.ExcelWriter(f'{SCENARIO_NAME}/{sheet_name}.xlsx', engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Inputs', index=False)
                    result_df_final.to_excel(writer, sheet_name='Results', index=False)
                    
                    # Save correlation with Electricity
                    if not elec_corr.empty:
                        elec_corr.to_excel(writer, sheet_name='Correlations', index=False)
                    
                    # Save other metadata
                    if isinstance(X_forecast, pd.DataFrame) and not X_forecast.empty:
                        X_forecast.to_excel(writer, sheet_name='Independent Parameters', index=False)
                    
                    if isinstance(evaluation_test_df, pd.DataFrame) and not evaluation_test_df.empty:
                        evaluation_test_df.to_excel(writer, sheet_name='Test Results', index=False)
                
                print(f"Results saved to {SCENARIO_NAME}/{sheet_name}.xlsx")
            except Exception as e:
                print(f"Error saving Excel file: {str(e)}")

        # Main execution
        print(f"\nProcessing sector: {sheet_name}")
        
        # Prepare data and train models with improved error handling
        try:
            X_train, X_test, y_train, y_test, X_train_slr, X_test_slr, df_test, X, y, X_slr, independent_variables = prepare_data(main_df)
            
            # Train the selected models
            models = train_models(X_train, X_train_slr, y_train, selected_models)
            
            # Generate future predictions
            df_train = main_df.copy()
            last_year = df_train['Year'].max()
            
            # Create DataFrame with future years
            future_years = list(range(int(last_year) + 1, TARGET_YEAR + 1))

# Inside Main_forecasting_function
            if not future_years:
                print(f"No future years to forecast (last_year={last_year}, TARGET_YEAR={TARGET_YEAR})")
                
                # Still create results file with existing data labeled as "User Data"
                result_df = main_df[['Year', 'Electricity']].copy()
                result_df.rename(columns={'Electricity': 'User Data'}, inplace=True)
                
                # Save results using an empty DataFrame for future forecasts
                save_results(sheet_name, main_df, result_df, pd.DataFrame(), 
                            pd.DataFrame(), independent_variables)
                
                print(f"Saved existing data for {sheet_name} (data already available up to {last_year})")
                
                return {
                    "status": "success",
                    "message": f"No forecasting needed for {sheet_name} - data already available to target year",
                    "used_existing_data": True
                }
                
            X_test1 = pd.DataFrame({'Year': future_years})
            
            # Time series predictions for independent variables
            for col in main_df.columns:
                if col != 'Year' and col != 'Electricity' and col in independent_variables:
                    # Check if we already have data for this independent variable
                    col_df = main_df[['Year', col]].dropna()
                    col_max_year = col_df['Year'].max() if not col_df.empty else 0
                    
                    if col_max_year >= TARGET_YEAR:
                        # Use existing values for future years
                        for year in future_years:
                            if year in col_df['Year'].values:
                                X_test1.loc[X_test1['Year'] == year, col] = col_df[col_df['Year'] == year][col].values[0]
                    else:
                        # Need to forecast missing values
                        missing_years = [year for year in future_years if year > col_max_year]
                        if missing_years:
                            y_predict_time = time_series_forecast(main_df, col, TARGET_YEAR)
                            
                            if y_predict_time is not None and len(y_predict_time) > 0:
                                # Map predictions to corresponding years
                                for i, year in enumerate(missing_years):
                                    if i < len(y_predict_time):
                                        X_test1.loc[X_test1['Year'] == year, col] = y_predict_time[i]
                        
                        # For years we already have data for
                        existing_years = [year for year in future_years if year <= col_max_year]
                        for year in existing_years:
                            if year in col_df['Year'].values:
                                X_test1.loc[X_test1['Year'] == year, col] = col_df[col_df['Year'] == year][col].values[0]
            
            # Get time series forecast for Electricity
            # This is used for TimeSeries model
            electricity_forecast = None
            if 'TimeSeries' in selected_models:
                electricity_forecast = time_series_forecast(main_df, 'Electricity', TARGET_YEAR)
                if electricity_forecast is not None and len(electricity_forecast) > 0:
                    # Store it for later use
                    X_test1['TimeSeries'] = np.zeros(len(X_test1))
                    for i in range(min(len(electricity_forecast), len(X_test1))):
                        X_test1.loc[i, 'TimeSeries'] = electricity_forecast[i]
            
            # Prepare predictors for forecast
            X_forecast = X_test1.copy()
            if 'TimeSeries' in X_forecast.columns:
                X_forecast = X_forecast.drop(['TimeSeries'], axis=1)
                
            # Prepare input for SLR (which only uses Year)
            X_forecast_slr = X_test1['Year'].values.reshape(-1, 1)
            
            # Prepare X_forecast_mlr for MLR model
            if independent_variables and any(var != 'Year' for var in independent_variables):
                # Use only the non-Year independent variables for MLR
                mlr_vars = [var for var in independent_variables if var != 'Year']
                # Check if all variables exist in X_forecast
                missing_vars = [var for var in mlr_vars if var not in X_forecast.columns]
                if missing_vars:
                    print(f"Warning: Variables {missing_vars} not in forecast data. Using only available variables.")
                    mlr_vars = [var for var in mlr_vars if var in X_forecast.columns]
                
                if mlr_vars:
                    X_forecast_mlr = X_forecast[mlr_vars].copy()
                else:
                    print("No valid independent variables for MLR forecast. Using Year.")
                    X_forecast_mlr = X_forecast_slr
            else:
                # If no independent variables, use Year for MLR too
                X_forecast_mlr = X_forecast_slr
            
            # Handle any remaining NaN values in X_forecast_mlr
            if isinstance(X_forecast_mlr, pd.DataFrame):
                X_forecast_mlr = X_forecast_mlr.fillna(0)
            
            # Initialize results DataFrame for forecasts
            result_df_future = pd.DataFrame({'Year': X_test1['Year']})
            
            # Make predictions for each model
            if 'MLR' in models and 'MLR' in selected_models:
                try:
                    mlr_regressor = models['MLR']
                    if hasattr(mlr_regressor, 'best_params_'):
                        mlr_params = mlr_regressor.best_params_
                        mlr_regressor = LinearRegression(**mlr_params)
                        mlr_regressor.fit(X, y)
                    y_pred_mlr = mlr_regressor.predict(X_forecast_mlr)
                    result_df_future['MLR'] = y_pred_mlr
                except Exception as e:
                    print(f"Error generating MLR predictions: {str(e)}")
                    # Use zeros as fallback
                    result_df_future['MLR'] = np.zeros(len(result_df_future))
            
            if 'SLR' in models and 'SLR' in selected_models:
                try:
                    slr_regressor = models['SLR']
                    if hasattr(slr_regressor, 'best_params_'):
                        slr_params = slr_regressor.best_params_
                        slr_regressor = LinearRegression(**slr_params)
                        slr_regressor.fit(X_slr, y)
                    y_pred_slr = slr_regressor.predict(X_forecast_slr)
                    result_df_future['SLR'] = y_pred_slr
                except Exception as e:
                    print(f"Error generating SLR predictions: {str(e)}")
                    # Use zeros as fallback
                    result_df_future['SLR'] = np.zeros(len(result_df_future))
            
            # WAM forecast
            if 'WAM' in selected_models:
                try:
                    wam = weighted_average_forecast(df_train[['Year', 'Electricity']], TARGET_YEAR, window_size=window_size)
                    # Extract only the future years
                    wam_future = wam[wam['Year'] > last_year]
                    if not wam_future.empty:
                        # Create mapping between years and values
                        wam_map = dict(zip(wam_future['Year'], wam_future['Electricity']))
                        # Apply mapping to result_df_future
                        result_df_future['WAM'] = result_df_future['Year'].map(wam_map)
                    else:
                        print("WAM forecast returned no future years")
                        result_df_future['WAM'] = np.zeros(len(result_df_future))
                except Exception as e:
                    print(f"Error generating WAM predictions: {str(e)}")
                    # Use zeros as fallback
                    result_df_future['WAM'] = np.zeros(len(result_df_future))
            
            # Time Series forecast from earlier
            if electricity_forecast is not None and 'TimeSeries' in selected_models and len(electricity_forecast) > 0:
                if len(electricity_forecast) >= len(future_years):
                    result_df_future['TimeSeries'] = electricity_forecast[:len(future_years)]
                else:
                    print(f"Warning: TimeSeries results don't match future years ({len(electricity_forecast)} vs {len(future_years)})")
                    # Fill with zeros and then add available forecasts
                    result_df_future['TimeSeries'] = np.zeros(len(future_years))
                    result_df_future.loc[:len(electricity_forecast)-1, 'TimeSeries'] = electricity_forecast
            elif 'TimeSeries' in selected_models:
                # Add zeros if TimeSeries model was selected but no forecast was generated
                result_df_future['TimeSeries'] = np.zeros(len(result_df_future))
            
            # Create DataFrame with actual historical data
            actual_df = pd.DataFrame({'Year': main_with_covid['Year']})
            
            # Add actual electricity as a column for each model
            for col in result_df_future.columns:
                if col != 'Year':
                    actual_df[col] = main_with_covid['Electricity']
            
            # Filter to only include historical years (before forecast period)
            actual_df = actual_df[actual_df['Year'] <= last_year]
            
            # Combine historical and forecasted data
            consolidated_df = pd.concat([actual_df, result_df_future], ignore_index=True)
            
            # Evaluate models on testing data
            print("Evaluating models on testing data...")
            evaluation_results = []
            
            # Check if we have testing data
            if not df_test.empty and len(y_test) > 0:
                # Evaluate MLR if available
                if 'MLR' in models:
                    try:
                        mlr_regressor = models['MLR']
                        if hasattr(mlr_regressor, 'best_params_'):
                            mlr_regressor = LinearRegression(**mlr_regressor.best_params_)
                            mlr_regressor.fit(X_train, y_train)
                        y_pred_test_mlr = mlr_regressor.predict(X_test)
                        evaluation_test_mlr = evaluate_model(y_test, y_pred_test_mlr)
                        evaluation_results.append({'Model': 'MLR', **evaluation_test_mlr})
                    except Exception as e:
                        print(f"Error evaluating MLR: {str(e)}")
                
                # Evaluate SLR if available
                if 'SLR' in models:
                    try:
                        slr_regressor = models['SLR']
                        if hasattr(slr_regressor, 'best_params_'):
                            slr_regressor = LinearRegression(**slr_regressor.best_params_)
                            slr_regressor.fit(X_train_slr, y_train)
                        y_pred_test_slr = slr_regressor.predict(X_test_slr)
                        evaluation_test_slr = evaluate_model(y_test, y_pred_test_slr)
                        evaluation_results.append({'Model': 'SLR', **evaluation_test_slr})
                    except Exception as e:
                        print(f"Error evaluating SLR: {str(e)}")
            
            evaluation_test_df = pd.DataFrame(evaluation_results)
            
            # Save results to Excel
            save_results(sheet_name, main_df, consolidated_df, evaluation_test_df, models, X_forecast, independent_variables)
            
            return {
                "status": "success",
                "message": f"Forecast completed for {sheet_name}",
                "used_existing_data": False,
                "models_used": selected_models
            }
        except Exception as e:
            print(f"Error in forecasting process: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "status": "error",
                "message": f"Error forecasting {sheet_name}: {str(e)}",
                "error": str(e)
            }
    
    else:
        # For data without the required columns, just save as is
        print(f"\nProcessing sheet (non-forecast): {sheet_name}")
        data_frame = pd.DataFrame({'Year': range(2006, TARGET_YEAR + 1)})
        main_dataframe = pd.merge(data_frame, main_df, on='Year', how='left')
        # Replace NaN with 0 for numeric columns
        main_dataframe = main_dataframe.fillna(0)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(f'{SCENARIO_NAME}/{sheet_name}.xlsx'), exist_ok=True)
        
        # Save to Excel
        try:
            with pd.ExcelWriter(f'{SCENARIO_NAME}/{sheet_name}.xlsx', engine='xlsxwriter') as writer:
                main_df.to_excel(writer, sheet_name='Inputs', index=False)
                main_dataframe.to_excel(writer, sheet_name='Results', index=False)
                
                # Try to create a correlation matrix if possible
                try:
                    numeric_df = main_df.select_dtypes(include=['number'])
                    if not numeric_df.empty:
                        corr_matrix = numeric_df.corr()
                        corr_matrix = corr_matrix.fillna(0)  # Replace NaN with 0
                        corr_matrix.to_excel(writer, sheet_name='Correlations', index=True)
                except Exception as e:
                    print(f"Error creating correlation matrix: {e}")
        except Exception as e:
            print(f"Error saving Excel file: {str(e)}")
        
        return {
            "status": "warning",
            "message": f"Sheet {sheet_name} doesn't have required columns for forecasting",
            "used_existing_data": False,
            "required_columns_missing": True
        }