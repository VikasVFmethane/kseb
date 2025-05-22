from flask import jsonify, request
import pandas as pd
import numpy as np
import os
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import joblib
from utils.create_load_curve import create_load_curve, check_total_demand_data, load_scenario_data

# Add this to the existing app.py or create a new ml_weather.py file to import

logger = logging.getLogger(__name__)

def get_or_create_weather_data(project_path: str, start_year: int, end_year: int) -> pd.DataFrame:
    """
    Get historical weather data or create synthetic weather data for the project.
    
    Parameters:
    -----------
    project_path : str
        Path to the project directory
    start_year : int
        Start year for the data
    end_year : int
        End year for the data
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with weather data
    """
    # Check if weather data exists
    weather_path = os.path.join(project_path, 'inputs', 'weather_data.csv')
    
    if os.path.exists(weather_path):
        logger.info(f"Loading existing weather data from {weather_path}")
        try:
            weather_data = pd.read_csv(weather_path)
            weather_data['datetime'] = pd.to_datetime(weather_data['datetime'])
            return weather_data
        except Exception as e:
            logger.error(f"Error loading weather data: {e}")
    
    logger.info("No existing weather data found, generating synthetic data")
    
    # Generate synthetic weather data
    date_range = pd.date_range(
        start=f'{start_year}-01-01',
        end=f'{end_year}-12-31 23:00',
        freq='H'
    )
    
    # Create DataFrame with datetime
    weather_df = pd.DataFrame({'datetime': date_range})
    
    # Extract month and hour
    weather_df['month'] = weather_df['datetime'].dt.month
    weather_df['hour'] = weather_df['datetime'].dt.hour
    
    # Generate synthetic temperature data
    # Base temperature by month (northern hemisphere)
    base_temp_by_month = {
        1: 5, 2: 7, 3: 10, 4: 15, 5: 20, 6: 25,
        7: 30, 8: 28, 9: 23, 10: 18, 11: 12, 12: 8
    }
    
    # Daily temperature pattern
    hourly_pattern = {
        0: -3, 1: -3.5, 2: -4, 3: -4.5, 4: -5, 5: -4.5,
        6: -4, 7: -3, 8: -1, 9: 1, 10: 2, 11: 3,
        12: 3.5, 13: 4, 14: 4.5, 15: 4, 16: 3, 17: 2,
        18: 1, 19: 0, 20: -1, 21: -1.5, 22: -2, 23: -2.5
    }
    
    # Generate temperature with some randomness for each year
    weather_df['temperature'] = weather_df.apply(
        lambda row: base_temp_by_month[row['month']] + hourly_pattern[row['hour']] + 
                   np.random.normal(0, 1.5) + 
                   # Add slight year-on-year warming trend
                   (row['datetime'].year - start_year) * 0.05,
        axis=1
    )
    
    # Generate humidity (inversely related to temperature)
    weather_df['humidity'] = 80 - 0.5 * weather_df['temperature'] + np.random.normal(0, 5, size=len(weather_df))
    weather_df['humidity'] = weather_df['humidity'].clip(10, 100)
    
    # Generate wind speed (more in winter, less in summer)
    seasonal_factor = weather_df['month'].map({
        1: 1.3, 2: 1.2, 3: 1.1, 4: 1, 5: 0.9, 6: 0.8,
        7: 0.7, 8: 0.8, 9: 0.9, 10: 1, 11: 1.1, 12: 1.2
    })
    weather_df['wind_speed'] = 10 * seasonal_factor + np.random.exponential(2, size=len(weather_df))
    
    # Generate cloud cover (more in winter, less in summer)
    weather_df['cloud_cover'] = 50 * seasonal_factor + np.random.normal(0, 20, size=len(weather_df))
    weather_df['cloud_cover'] = weather_df['cloud_cover'].clip(0, 100)
    
    # Drop month and hour columns used for generation
    weather_df = weather_df.drop(columns=['month', 'hour'])
    
    # Save to file for future use
    os.makedirs(os.path.dirname(weather_path), exist_ok=True)
    weather_df.to_csv(weather_path, index=False)
    logger.info(f"Generated and saved synthetic weather data to {weather_path}")
    
    return weather_df


def prepare_historical_demand_with_weather(project_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Prepare historical demand data with weather features for ML training.
    
    Parameters:
    -----------
    project_path : str
        Path to the project directory
        
    Returns:
    --------
    Tuple[pd.DataFrame, pd.DataFrame]
        Tuple containing historical demand data and weather data
    """
    # Load historical demand data
    input_file_path = os.path.join(project_path, 'inputs', 'load_curve_template.xlsx')
    
    if not os.path.exists(input_file_path):
        logger.error(f"Input file not found: {input_file_path}")
        raise FileNotFoundError(f"Input file not found: {input_file_path}")
    
    # Read historical demand
    historical_demand = pd.read_excel(input_file_path, sheet_name='Past_Hourly_Demand')
    
    # Convert datetime
    historical_demand['datetime'] = pd.to_datetime(
        historical_demand['date'].astype(str) + ' ' + historical_demand['time'].astype(str)
    )
    
    # Extract years to get weather data for
    start_year = historical_demand['datetime'].dt.year.min()
    end_year = historical_demand['datetime'].dt.year.max() + 15  # Extend for forecast period
    
    # Get or create weather data
    weather_data = get_or_create_weather_data(project_path, start_year, end_year)
    
    return historical_demand, weather_data


def train_weather_demand_model(historical_demand: pd.DataFrame, weather_data: pd.DataFrame) -> Any:
    """
    Train a machine learning model for demand forecasting with weather.
    
    Parameters:
    -----------
    historical_demand : pd.DataFrame
        Historical demand data
    weather_data : pd.DataFrame
        Weather data
        
    Returns:
    --------
    Any
        Trained model object
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    
    # Merge demand and weather data
    demand_data = historical_demand[['datetime', 'demand']]
    
    # Merge on datetime
    combined_data = pd.merge(demand_data, weather_data, on='datetime', how='inner')
    
    # Add time features
    combined_data['hour'] = combined_data['datetime'].dt.hour
    combined_data['dayofweek'] = combined_data['datetime'].dt.dayofweek
    combined_data['month'] = combined_data['datetime'].dt.month
    combined_data['year'] = combined_data['datetime'].dt.year
    combined_data['is_weekend'] = combined_data['dayofweek'].isin([5, 6]).astype(int)
    
    # Add cyclical features
    combined_data['hour_sin'] = np.sin(2 * np.pi * combined_data['hour'] / 24)
    combined_data['hour_cos'] = np.cos(2 * np.pi * combined_data['hour'] / 24)
    combined_data['month_sin'] = np.sin(2 * np.pi * combined_data['month'] / 12)
    combined_data['month_cos'] = np.cos(2 * np.pi * combined_data['month'] / 12)
    combined_data['day_sin'] = np.sin(2 * np.pi * combined_data['dayofweek'] / 7)
    combined_data['day_cos'] = np.cos(2 * np.pi * combined_data['dayofweek'] / 7)
    
    # Define features
    features = [
        'temperature', 'humidity', 'wind_speed', 'cloud_cover',
        'hour_sin', 'hour_cos', 'month_sin', 'month_cos', 'day_sin', 'day_cos',
        'is_weekend'
    ]
    
    # Ensure all features exist
    features = [f for f in features if f in combined_data.columns]
    
    # Split data
    X = combined_data[features]
    y = combined_data['demand']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train model
    model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train_scaled, y_train)
    
    # Evaluate model
    train_score = model.score(X_train_scaled, y_train)
    test_score = model.score(X_test_scaled, y_test)
    
    logger.info(f"Model R² score: {test_score:.4f} (train: {train_score:.4f})")
    
    # Save model files
    model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    os.makedirs(model_dir, exist_ok=True)
    
    joblib.dump(model, os.path.join(model_dir, 'weather_demand_model.joblib'))
    joblib.dump(scaler, os.path.join(model_dir, 'weather_demand_scaler.joblib'))
    joblib.dump(features, os.path.join(model_dir, 'weather_demand_features.joblib'))
    
    # Return tuple with model, scaler, and features
    return model, scaler, features


def generate_load_profiles_ml(project_path: str, 
                            forecast_scenario: Optional[str] = None,
                            apply_constraints: bool = True, 
                            constraint_options: Optional[Dict] = None,
                            weather_data_option: str = 'historical',
                            output_frequency: str = 'hourly',
                            output_unit: str = 'MW',
                            start_year: int = 2023,
                            end_year: int = 2037,
                            improved_load_factor: Optional[float] = None,
                            custom_load_factors: Optional[Dict] = None,
                            use_excel_load_factors: bool = False) -> pd.DataFrame:
    """
    Generate load profiles using machine learning with weather data.
    
    Parameters:
    -----------
    project_path : str
        Path to the project directory
    forecast_scenario : str, optional
        Name of the forecast scenario to use for constraints
    apply_constraints : bool, default True
        Whether to apply constraints to the forecast
    constraint_options : Dict, optional
        Options for which constraints to apply
    weather_data_option : str, default 'historical'
        Option for weather data ('historical', 'forecast', or 'none')
    output_frequency : str, default 'hourly'
        Output frequency ('hourly', 'half_hourly', or '15min')
    output_unit : str, default 'MW'
        Output unit ('MW', 'kW', or 'GW')
    start_year : int, default 2023
        Start year for forecast
    end_year : int, default 2037
        End year for forecast
    improved_load_factor : float, optional
        Year-on-year improvement percentage for load factors
    custom_load_factors : Dict, optional
        Dictionary with custom load factors by year
    use_excel_load_factors : bool, default False
        Whether to use load factors from Excel
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with generated load profiles
    """
    input_file_path = os.path.join(project_path, 'inputs', 'load_curve_template.xlsx')
    
    if not os.path.exists(input_file_path):
        logger.error(f"Input file not found: {input_file_path}")
        raise FileNotFoundError(f"Input file not found: {input_file_path}")
    
    # Prepare historical demand and weather data
    historical_demand, weather_data = prepare_historical_demand_with_weather(project_path)
    
    # Filter weather data based on option
    if weather_data_option == 'historical':
        # Use historical weather patterns
        pass  # Already loaded
    elif weather_data_option == 'forecast':
        # Use forecasted weather data if available, otherwise use historical
        forecast_weather_path = os.path.join(project_path, 'inputs', 'forecast_weather_data.csv')
        if os.path.exists(forecast_weather_path):
            try:
                forecast_weather = pd.read_csv(forecast_weather_path)
                forecast_weather['datetime'] = pd.to_datetime(forecast_weather['datetime'])
                
                # Merge historical and forecast
                weather_data = pd.concat([
                    weather_data[weather_data['datetime'] < f"{start_year}-01-01"],
                    forecast_weather[forecast_weather['datetime'] >= f"{start_year}-01-01"]
                ])
            except Exception as e:
                logger.error(f"Error loading forecast weather data: {e}")
    elif weather_data_option == 'none':
        # Use only temperature, drop other weather features
        weather_columns_to_keep = ['datetime', 'temperature']
        weather_data = weather_data[weather_columns_to_keep]
    
    # Train ML model
    logger.info("Training machine learning model with weather data")
    model, scaler, features = train_weather_demand_model(historical_demand, weather_data)
    
    # Load scenario data if needed
    scenario_data = None
    if forecast_scenario:
        scenario_data = load_scenario_data(project_path, forecast_scenario)
    
    # Set up constraint options
    if constraint_options is None:
        constraint_options = {
            'monthly_max': True,
            'monthly_avg': True,
            'seasonal_pattern': True,
            'weekday_weekend': True
        }
    
    # Set up future load factors
    future_load_factors = None
    if custom_load_factors:
        future_load_factors = custom_load_factors
    
    # Set up year range
    year_range = {'Start_Year': start_year, 'End_Year': end_year}
    
    # Call the main function
    logger.info("Generating load profiles with ML weather method")
    result, validation_results = create_load_curve(
        excel_file_path=input_file_path,
        year_range=year_range,
        method='ml_weather',
        scenario_data=scenario_data,
        weather_data=weather_data,
        apply_constraints=apply_constraints,
        constraint_options=constraint_options,
        improved_load_factor=improved_load_factor,
        future_load_factors=future_load_factors,
        output_frequency=output_frequency
    )
    
    return result, validation_results


# Add this to app.py to handle the API route
@app.route('/api/ml_weather_details', methods=['GET'])
def get_ml_weather_details():
    """API endpoint to get details about the ML weather model."""
    if not app.config['CURRENT_PROJECT_PATH']:
        return jsonify({
            'status': 'error',
            'message': 'No project selected'
        })
    
    try:
        # Get or create weather data to estimate coverage
        historical_demand, weather_data = prepare_historical_demand_with_weather(app.config['CURRENT_PROJECT_PATH'])
        
        # Calculate overlap between historical demand and weather data
        historical_min = historical_demand['datetime'].min()
        historical_max = historical_demand['datetime'].max()
        weather_min = weather_data['datetime'].min()
        weather_max = weather_data['datetime'].max()
        
        # Calculate overlap percentage
        historical_dates = set(historical_demand['datetime'].dt.date)
        weather_dates = set(weather_data['datetime'].dt.date)
        overlap_dates = historical_dates.intersection(weather_dates)
        
        overlap_percentage = len(overlap_dates) / len(historical_dates) * 100 if historical_dates else 0
        
        # Get weather features
        weather_features = [col for col in weather_data.columns if col != 'datetime']
        
        # Get model features if model exists
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'weather_demand_features.joblib')
        model_features = []
        if os.path.exists(model_path):
            try:
                model_features = joblib.load(model_path)
            except Exception as e:
                logger.error(f"Error loading model features: {e}")
        
        return jsonify({
            'status': 'success',
            'data': {
                'weather_data_start': weather_min.strftime('%Y-%m-%d'),
                'weather_data_end': weather_max.strftime('%Y-%m-%d'),
                'historical_demand_start': historical_min.strftime('%Y-%m-%d'),
                'historical_demand_end': historical_max.strftime('%Y-%m-%d'),
                'data_overlap_percentage': round(overlap_percentage, 2),
                'available_weather_features': weather_features,
                'model_features': model_features,
                'weather_data_points': len(weather_data),
                'demand_data_points': len(historical_demand)
            }
        })
    except Exception as e:
        logger.exception(f"Error getting ML weather details: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        })


# Modify the existing load profile generation route to handle ML method
@app.route('/api/generate_load_profiles', methods=['POST'])
def generate_load_profiles():
    """API endpoint to generate load profiles."""
    logger.info("Processing API request to generate_load_profiles")
    
    try:
        # Extract form data
        method = request.form.get('method')
        forecast_scenario = request.form.get('forecast_scenario')
        
        logger.debug(f"Load profile generation request: method={method}, scenario={forecast_scenario}")
        
        # Validate base year if method is base_year
        if method == 'base_year':
            base_year = request.form.get('base_year')
            if not base_year:
                logger.warning("Base year must be selected")
                return jsonify({
                    'status': 'error',
                    'message': 'Base year must be selected'
                })
            logger.debug(f"Using base year: {base_year}")
        else:
            weather_data_option = request.form.get('weather_data', 'historical')
            logger.debug(f"Using weather data option: {weather_data_option}")
        
        use_constraints = request.form.get('use_constraints') == 'true'
        
        # Process constraints
        constraint_options = {}
        if use_constraints:
            constraint_options = {
                'monthly_max': request.form.get('monthly_max') == 'true',
                'monthly_avg': request.form.get('monthly_avg') == 'true',
                'seasonal_pattern': request.form.get('seasonal_pattern') == 'true',
                'weekday_weekend': request.form.get('weekday_weekend') == 'true'
            }
        
        # Get load factor improvements
        improved_load_factor = None
        custom_load_factors = None
        use_excel_load_factors = False
        
        if use_constraints and request.form.get('use_improved_load_factors') == 'true':
            improved_load_factor = float(request.form.get('load_factor_improvement', 0.5))
            use_excel_load_factors = request.form.get('use_excel_load_factors') == 'true'
            
            # Parse custom load factors
            if request.form.get('custom_load_factors'):
                custom_load_factors = json.loads(request.form.get('custom_load_factors'))
        
        # Get advanced options
        output_frequency = request.form.get('output_frequency', 'hourly')
        output_unit = request.form.get('output_unit', 'MW')
        start_year = int(request.form.get('start_year', 2023))
        end_year = int(request.form.get('end_year', 2037))
        
        # Generate profiles based on method
        if method == 'base_year':
            # Use the original load curve function
            input_file_path = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'inputs', 'load_curve_template.xlsx')
            
            # Check if the Excel file has valid Total Demand data
            has_valid_total_demand = check_total_demand_data(input_file_path)
            
            # Get scenario data only if needed and scenario is provided
            scenario_data = None
            if forecast_scenario and not has_valid_total_demand:
                scenario_data = load_scenario_data(app.config['CURRENT_PROJECT_PATH'], forecast_scenario)
            
            # Pass the year range to avoid dependency on app.config
            year_range = {'Start_Year': start_year, 'End_Year': end_year}
            
            # Call the load curve generation function
            load_forecast, validation_results = create_load_curve(
                input_file_path,
                year_range=year_range,
                base_year=int(base_year) if method == 'base_year' else None,
                scenario_data=scenario_data,
                apply_constraints=use_constraints,
                constraint_options=constraint_options,
                improved_load_factor=improved_load_factor,
                future_load_factors=custom_load_factors,
                output_frequency=output_frequency
            )
        else:
            # Use ML with weather method
            load_forecast, validation_results = generate_load_profiles_ml(
                project_path=app.config['CURRENT_PROJECT_PATH'],
                forecast_scenario=forecast_scenario,
                apply_constraints=use_constraints,
                constraint_options=constraint_options,
                weather_data_option=weather_data_option,
                output_frequency=output_frequency,
                output_unit=output_unit,
                start_year=start_year,
                end_year=end_year,
                improved_load_factor=improved_load_factor,
                custom_load_factors=custom_load_factors,
                use_excel_load_factors=use_excel_load_factors
            )
        
        if load_forecast is None:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate load profile'
            })
        
        # Save the forecast to CSV
        results_folder = os.path.join(app.config['CURRENT_PROJECT_PATH'], 'results')
        load_profiles_folder = os.path.join(results_folder, 'load_profiles')
        os.makedirs(load_profiles_folder, exist_ok=True)
        
        # Create a profile ID based on method and timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        if method == 'base_year':
            profile_id = f"{forecast_scenario or 'excel'}_base_year_{base_year}_{timestamp}"
        else:
            profile_id = f"{forecast_scenario or 'excel'}_ml_weather_{weather_data_option}_{timestamp}"
        
        output_path = os.path.join(load_profiles_folder, f"{profile_id}.csv")
        load_forecast.to_csv(output_path, index=False)
        
        logger.info(f"Successfully generated load profile: {profile_id}")
        
        # Get the updated list of profiles
        generated_profiles = []
        for filename in os.listdir(load_profiles_folder):
            if filename.endswith('.csv'):
                profile_path = os.path.join(load_profiles_folder, filename)
                created_date = datetime.fromtimestamp(os.path.getctime(profile_path)).strftime('%Y-%m-%d')
                
                generated_profiles.append({
                    'id': filename.replace('.csv', ''),
                    'name': filename.replace('.csv', '').replace('_', ' ').title(),
                    'created': created_date,
                    'path': profile_path
                })
        
        return jsonify({
            'status': 'success',
            'message': 'Load profiles generated successfully',
            'profile_id': profile_id,
            'details': f'Generated {output_frequency} load profile for years {start_year}-{end_year} in {output_unit}',
            'profiles': generated_profiles,
            'validation': validation_results
        })
    except Exception as e:
        logger.exception(f"Error generating load profiles: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error generating load profiles: {str(e)}'
        })
