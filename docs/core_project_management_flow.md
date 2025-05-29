# Application Page-wise Flow and Methodology

## Introduction

This document provides a comprehensive overview of the application's structure, page-wise functionalities, and underlying methodologies. The application is designed around a project-based workflow, where users create or load projects to manage their data and modeling tasks. Each project has its own dedicated directory structure for inputs and results.

The primary functional modules covered in this document include:

1.  **Core Project Management**: Fundamental operations like creating, loading, and managing projects.
2.  **Demand Projection and Visualization**: Forecasting future demand based on historical data and visualizing these projections.
3.  **Load Profile Generation**: Creating detailed temporal load profiles from annual demand figures.
4.  **PyPSA Modeling**: Setting up, running, and managing energy system optimization models using PyPSA.
5.  **PyPSA Results Visualization**: Analyzing and visualizing the outputs of PyPSA model runs.
6.  **Feature Management**: Enabling or disabling specific application features on a per-project basis.
7.  **Helper/Utility Pages**: Supporting pages for user guidance and template downloads.

This document aims to clarify how these modules interact, the data they consume and produce, and the key backend processes and configurations involved.

---

## 1. Core Project Management Flow

This section outlines the core project management functionalities within the application, covering how users interact with projects from the home page, create new projects, and load existing ones.

### 1.1. Home Page (`/`)

The Home Page serves as the primary entry point for the application, providing users with an overview of their recent work and quick access to ongoing projects.

*   **Application Entry Point**: Navigating to the root URL (`/`) lands the user on this page.
*   **Recent Projects**:
    *   Displays a list of recently accessed or created projects.
    *   This list is populated by the `get_recent_projects` function, which likely retrieves data stored by `save_recent_project`.
    *   The recent projects are typically managed via JSON files (e.g., `static/user_uploads/recent_projects/default_user.json`) as handled by `api_recent_projects`.
*   **Recent Activities**:
    *   Shows a feed of recent activities within the application.
    *   Currently, this is based on a placeholder function `get_recent_activities` found in `app.py`.
*   **Current Project Display**:
    *   Clearly indicates the name of the project that is currently loaded and active in the application. This information is typically stored in `app.config['CURRENT_PROJECT']`.

### 1.2. Creating a New Project (`/create_project`)

This flow allows users to initiate new projects within the application.

*   **User Interaction**:
    *   The user triggers this action, usually through a UI element (e.g., a "Create New Project" button).
    *   The user is prompted to provide a **Project Name** for the new project.
    *   The user selects a **Project Location** (a directory on the file system) where the project will be stored.
*   **Backend Process**:
    *   The request is routed to the `/create_project` endpoint, which calls the `create_project` function in `app.py`.
    *   **Name Sanitization**: The provided project name is sanitized using `werkzeug.utils.secure_filename` to ensure it's a valid and safe directory name.
    *   **Directory Structure Creation**:
        *   The `utils.helpers.create_project_structure` function is invoked.
        *   This function creates a standardized directory structure for the project within the chosen Project Location. This path becomes the `app.config['CURRENT_PROJECT_PATH']`.
        *   This structure includes essential subfolders:
            *   `inputs`: For storing input files.
            *   `results`: For storing output and result files.
        *   Template files (e.g., `input_demand_file.xlsx`, `load_curve_template.xlsx`, `pypsa_input_template.xlsx`, etc.) located in the application's `static/templates` directory are copied into the newly created `inputs` folder.
    *   **Recent Project Update**:
        *   The details of this new project (name and path) are saved to a user-specific list of recent projects. This is handled by the `save_recent_project` function, which typically writes to a JSON file like `static/user_uploads/recent_projects/{user_id}.json` (e.g., `default_user.json`).
    *   **Application Context Update**:
        *   The newly created project is set as the current active project in the application's configuration.
        *   `app.config['CURRENT_PROJECT']` is updated with the project's name.
        *   `app.config['CURRENT_PROJECT_PATH']` is updated with the project's file system path.
*   **Outcome**:
    *   A new project directory, complete with the standard subfolders and template files, is created at the specified location.
    *   The application's context switches to this new project, making it the active project for subsequent operations.

### 1.3. Loading an Existing Project (`/load_project`)

This flow enables users to open and work with previously created projects.

*   **User Interaction**:
    *   The user initiates this action, typically through a UI element (e.g., "Load Project" button or selecting from a list of recent projects).
    *   The user provides the file system **path** to an existing project directory.
*   **Backend Process**:
    *   The request is routed to the `/load_project` endpoint, which calls the `load_project` function in `app.py`.
    *   **Project Validation**:
        *   The `utils.helpers.validate_project_structure` function is called to inspect the provided directory.
        *   This function checks if the directory adheres to the expected project structure, specifically looking for the presence of:
            *   `inputs` subfolder.
            *   `results` subfolder.
            *   Essential template files (e.g., `input_demand_file.xlsx`) within the `inputs` folder.
    *   **Template Restoration (if applicable)**:
        *   If the validation step identifies missing template files (and these are considered fixable warnings), the `utils.helpers.copy_missing_templates` function may be called.
        *   This function copies the standard template files from `static/templates` into the project's `inputs` folder to ensure the project is complete.
    *   **Recent Project Update**:
        *   The details of the loaded project are added to the user-specific list of recent projects via the `save_recent_project` function.
    *   **Application Context Update**:
        *   The selected project becomes the current active project.
        *   `app.config['CURRENT_PROJECT']` is updated with the project's name (derived from the directory name).
        *   `app.config['CURRENT_PROJECT_PATH']` is updated with the project's file system path.
*   **Outcome**:
    *   The application's context switches to the selected existing project.
    *   The user can now view, modify, and process data within this loaded project.

---

**Key Project Configuration Variables:**

*   `app.config['CURRENT_PROJECT']`: Stores the name of the currently active project.
*   `app.config['CURRENT_PROJECT_PATH']`: Stores the full file system path to the currently active project's root directory. This path is crucial as all project-specific input and result files are located within subdirectories of this path (e.g., `app.config['CURRENT_PROJECT_PATH']/inputs/`, `app.config['CURRENT_PROJECT_PATH']/results/`).
*   Recent projects are managed via JSON files in `static/user_uploads/recent_projects/`, typically named `{user_id}.json`.

---

## 2. Demand Projection and Visualization Flow

This section details the workflow for creating demand projections, running forecast scenarios, and visualizing the results. This module typically serves as an initial step for generating energy demand figures that can be used in subsequent modules like Load Profile Generation.

### 2.1. Data Input & Initial View (`/demand_projection` page)

This is the starting point for users to input historical data and view it before running forecasts.

*   **Navigation**: User accesses this page via a "Demand Projection" link, typically located in the application's sidebar (if the feature is enabled).
*   **File Requirement**:
    *   The system checks for the presence of `input_demand_file.xlsx` within the `inputs` subdirectory of the currently active project (i.e., `app.config['CURRENT_PROJECT_PATH']/inputs/input_demand_file.xlsx`).
    *   If this file is missing, the user is prompted with a standard file upload interface to provide it.
*   **Data Processing**:
    *   Once `input_demand_file.xlsx` is available, the `utils.data_loading.input_demand_data` function is invoked.
    *   This function is responsible for reading and parsing data from multiple sheets within the Excel file. Key data includes:
        *   Historical demand data for various sectors.
        *   Forecasting parameters such as 'Start\_Year' and 'End\_Year'.
    *   The function processes this raw data and returns structured data: sector-specific dataframes, a dictionary of parameters, and an aggregated electricity demand table.
*   **Display on `/demand_projection` Page**:
    *   **Historical Data Tables**: Sector-specific historical demand data is presented in tabular format.
    *   **Key Parameters**: Important parameters extracted from the input file, like the 'Start Year' and 'End Year' for historical data, are displayed.
    *   **Aggregated Demand**: A table showing the aggregated electricity demand across all sectors for the historical period is shown.
    *   **Initial Charts**: Basic visualizations (charts) of the historical data for each sector may be displayed. These charts are often generated by fetching data from an API endpoint like `/api/chart_data/{sector}`.

### 2.2. Running a New Forecast Scenario

This flow describes how users configure and initiate new forecast scenarios. This is primarily driven by UI interactions, with the backend handling the computation via an API.

*   **User Configuration (on `/demand_projection` page or a dedicated interface)**:
    *   **Scenario Name**: User provides a unique `scenarioName` to identify this specific forecast run.
    *   **Target Year**: User specifies the `targetYear` up to which the forecast should be generated.
    *   **COVID-19 Adjustment**: User chooses whether to `excludeCovidYears` (a boolean value) from the historical data used for modeling, to account for pandemic-related anomalies.
    *   **Sector-Specific Configurations (`sectorConfigs`)**: For each relevant sector, the user configures:
        *   **Models**: Selects one or more forecasting models to apply (e.g., 'MLR' - Multiple Linear Regression, 'SLR' - Simple Linear Regression, 'WAM' - Weighted Average Model, 'TimeSeries' - ARIMA or other time series models).
        *   **Model Parameters**: Provides parameters specific to each chosen model. For example:
            *   For MLR: list of independent variables.
            *   For WAM: window size.
*   **API Call**:
    *   The UI gathers all the user-defined configurations.
    *   A POST request is sent to the `/api/run_forecast` endpoint, with the configuration data in the request body.
*   **Backend Processing**:
    *   The `/api/run_forecast` endpoint triggers the `run_multiple_forecasts_job` function (likely located in `app.py` or a dedicated jobs module).
    *   **Job Tracking**: A unique `job_id` is generated to monitor the progress of this asynchronous forecasting task.
    *   **Asynchronous Execution**: `run_multiple_forecasts_job` is typically executed in a separate thread to prevent blocking the main application and allow the user to continue interacting with the UI.
    *   **Core Forecasting Logic**: Inside the job, for each sector included in the `sectorConfigs`:
        *   The `models.forecasting.Main_forecasting_function` is called.
        *   This function takes the historical data for the sector, the selected models, and their respective parameters.
        *   It performs the actual forecasting calculations for each model.
        *   It may leverage previously processed or cached data if available and relevant to optimize computation.
    *   **Output Storage**:
        *   Forecast results are saved within the project's directory structure, under `app.config['CURRENT_PROJECT_PATH']/results/demand_projection/{scenarioName}/`.
        *   For each sector, an Excel file (e.g., `{sector_name}.xlsx`) is created. This file typically contains a 'Results' sheet with columns for 'Year' and the forecasted values from each model applied to that sector.
        *   A `summary.json` file is also generated in the scenario directory. This file stores metadata about the forecast run, such as the scenario name, target year, models used, and other relevant parameters.
*   **Monitoring Forecast Progress**:
    *   The UI can periodically poll the `/api/forecast_status/{job_id}` endpoint.
    *   This API returns the current status of the forecasting job (e.g., "running", "completed", "failed") and potentially progress details.

### 2.3. Visualizing Forecast Scenarios (`/demand_visualization` page)

Once forecast scenarios are generated, this page allows users to view, compare, and analyze the results.

*   **Navigation**: User accesses this page via a "Demand Visualization" link, often from the sidebar (if the feature is enabled).
*   **Scenario Selection**:
    *   The page automatically scans the `app.config['CURRENT_PROJECT_PATH']/results/demand_projection/` directory to find all available forecast scenarios (by identifying the subdirectories, each representing a scenario).
    *   These scenario names are populated into a dropdown list or a similar selection UI element, allowing the user to choose which scenario's results to display.
*   **Data Fetching and Display**:
    *   Upon selecting a scenario, the frontend makes a request to `/api/forecast_data/{scenario}`.
    *   This API endpoint reads the sector-specific Excel files from the selected scenario's results directory.
    *   The fetched data is then used to render:
        *   **Comparative Charts**: Visualizations (e.g., line charts) comparing the forecasted values from different models for each sector.
        *   **Data Tables**: Tables displaying the numerical forecasted values.
        *   **Interactive Filters**: Users are typically provided with options to:
            *   Select or deselect specific sectors to include in the charts and tables.
            *   Select or deselect specific models to compare.
            *   Adjust the start and end years for the visualization range to focus on particular periods.
*   **Data Consolidation and Download (Optional Features)**:
    *   **Consolidation**:
        *   Users might have an option to consolidate forecast data for specific models across multiple sectors.
        *   This could trigger an API call like `/api/save_consolidated_data/{scenario}`.
        *   This API would process the scenario's results and save a `consolidated_results.csv` file in the scenario's directory (`app.config['CURRENT_PROJECT_PATH']/results/demand_projection/{scenarioName}/consolidated_results.csv`), containing the combined data. This consolidated file can be a key input for other modules.
    *   **Comparison Download**:
        *   The `/api/download_comparison_data` endpoint may be available to download a CSV file that compares data across multiple selected scenarios, facilitating a broader analysis.

---

**Methodology Notes (Demand Projection):**

*   The primary forecasting algorithms and logic are encapsulated within `models/forecasting.py` (specifically the `Main_forecasting_function`).
*   Initial parsing and structuring of the input Excel data (`input_demand_file.xlsx`) are handled by functions in `utils/data_loading.py` (e.g., `input_demand_data`).
*   Forecast results are systematically stored in separate directories for each scenario, enabling easy access, comparison between different runs, and revisitation of past results.
*   The "Demand Visualization" page is designed to be highly interactive, leveraging multiple API endpoints (e.g., `/api/forecast_data`, `/api/chart_data`) to dynamically fetch and update the displayed data based on user selections.

---

## 3. Load Profile Generation Flow

This section describes the process of generating detailed load profiles based on historical data and future demand projections. Generated load profiles (often timeseries CSV files) are crucial inputs for the PyPSA Modeling module.

### 3.1. Data Input & Initial View (`/load_profile_creation` page)

This page is the starting point for creating load profiles.

*   **Navigation**: Users navigate to the "Load Profile" page (if the feature is enabled), which directs them to the `/load_profile_creation` URL.
*   **File Requirement**:
    *   The system critically requires the `load_curve_template.xlsx` file to be present in the `app.config['CURRENT_PROJECT_PATH']/inputs/` directory.
    *   This Excel file must contain a sheet named 'Past_Hourly_Demand', which holds historical load data, typically with timestamped demand values.
    *   If the file is not found, the user is presented with a file upload interface. The upload is handled by the `_handle_file_upload` function (triggered by a POST request to `/load_profile_creation`), which uses `LoadProfileManager.save_uploaded_file` to save the file to the correct location.
*   **Initial Display (rendered by `_render_load_profile_page` function)**:
    *   **Template File Information**: Displays details about the `load_curve_template.xlsx` file.
    *   **Forecast Scenarios**: Lists available demand forecast scenarios (found by scanning `app.config['CURRENT_PROJECT_PATH']/results/demand_projection/`). Users can select one of these scenarios to provide future annual demand totals (typically from a `consolidated_results.csv` within the scenario) for the load profile generation.
    *   **Historical Years**: Populates a list of available historical years extracted from the 'Past_Hourly_Demand' sheet in the `load_curve_template.xlsx`. This is used if the 'base_year' method is selected.
    *   **Generated Profiles**: Shows a list of previously generated load profiles (CSV files from `app.config['CURRENT_PROJECT_PATH']/results/load_profiles/`) for the current project.

### 3.2. Configuring Load Profile Generation (on `/load_profile_creation` page)

Users configure the parameters for the load profile generation process through a form on this page.

*   **User-Defined Parameters**:
    *   **`method`**:
        *   `base_year`: This method uses historical load patterns from a selected `base_year`.
    *   **`forecast_scenario`**: Users can select a demand forecast scenario. The annual demand projections (e.g., from its `consolidated_results.csv`) will be used to scale the load profiles. If no scenario is selected, the system may use annual total demand data provided within the `load_curve_template.xlsx` itself.
    *   **`start_year` and `end_year`**: Define the time period for which the load profile will be generated.
    *   **`output_frequency`**: Specifies the desired temporal resolution (e.g., 'Hourly', 'Half-hourly').
    *   **`output_unit`**: Defines the unit for the demand values (e.g., 'MW', 'kW').
    *   **Load Factor Adjustments**: Various options to adjust load factors.
*   **Input Validation**: The `validate_load_profile_form` function in `app.py` validates these inputs.

### 3.3. Generating the Load Profile (`/api/generate_load_profiles` API endpoint)

This API endpoint handles the actual generation of the load profile.

*   **API Call**: The UI sends a POST request to `/api/generate_load_profiles` with the configured parameters.
*   **Backend Processing**:
    *   Handled by the `_generate_load_profile` internal function in `app.py`.
    *   **Parameter Extraction**: `_extract_generation_parameters` parses the form data.
    *   **Core Logic (`utils.create_load_curve.create_load_curve`)**:
        *   If a `forecast_scenario_name` is provided, `load_scenario_data` fetches the consolidated annual demand data from that scenario's `consolidated_results.csv`.
        *   The `create_load_curve` function:
            *   Reads historical hourly demand from `load_curve_template.xlsx`.
            *   Determines future annual demand totals (from selected forecast scenario or the template).
            *   Scales historical load patterns based on these future totals and applies load factor adjustments.
            *   Generates the profile for the specified period and frequency.
    *   **Unit Conversion**: `_apply_unit_conversion` converts the 'Demand' column to the selected `output_unit`.
    *   **Output Storage**:
        *   The generated load profile (timeseries demand) is saved as a CSV file (e.g., `{profile_id}.csv`) in `app.config['CURRENT_PROJECT_PATH']/results/load_profiles/`. The `profile_id` is generated by `LoadProfileManager.generate_profile_id`.

### 3.4. Viewing and Analyzing Generated Load Profiles (on `/load_profile_creation` page and via API)

Users can inspect and analyze the generated load profiles.

*   **Profile List**: The `/load_profile_creation` page refreshes its list of generated load profiles.
*   **Metadata Display**: Selecting a profile calls `/api/load_profile_metadata/{profile_id}`. `LoadProfileManager.get_profile_metadata` reads the CSV, calculates statistics (peak/average/min demand, load factor), and returns JSON.
*   **Chart Display**: To visualize, the UI calls `/api/load_profile_data/{profile_id}/{year}`. `LoadProfileManager.get_profile_year_data` reads the CSV, filters for the year, and returns timeseries data for charting.

---

**Methodology Notes (Load Profile Generation):**

*   The `LoadProfileManager` class in `app.py` manages load profile files (saving templates, generating IDs, retrieving data/metadata).
*   Core logic is in `utils.create_load_curve.py` (`create_load_curve` function).
*   Strong dependency on `load_curve_template.xlsx` for historical data.
*   Integrates with "Demand Projection" by using its `consolidated_results.csv` from a chosen scenario to scale historical patterns for future load profiles.

---

## 4. PyPSA Modeling Flow

This section details the workflow for setting up, running, and monitoring energy system models using PyPSA. This module typically uses load profiles generated by the 'Load Profile Generation Flow' as one of its key inputs.

### 4.1. Data Input & Initial View (`/pypsa_modeling` page)

This page serves as the primary interface for interacting with the PyPSA modeling capabilities.

*   **Navigation**: Users navigate to the "PyPSA Modeling" section (if the feature is enabled), which directs them to the `/pypsa_modeling` URL.
*   **File Requirement**:
    *   Relies heavily on `pypsa_input_template.xlsx` located in `app.config['CURRENT_PROJECT_PATH']/inputs/`.
    *   This Excel workbook contains sheets defining network components, techno-economic parameters, constraints, and scenario settings.
    *   If missing, a warning is displayed.
*   **Settings Display**:
    *   The page may display current settings read from `pypsa_input_template.xlsx` via `/api/get_pypsa_settings_from_excel`. This API reads the 'Settings' sheet (table marked `~Main_Settings`).

### 4.2. Configuring PyPSA Model Run (on `/pypsa_modeling` page)

Users configure the specifics of the PyPSA model run.

*   **User Interaction**:
    *   **`scenarioName`**: User provides a unique `scenarioName` for the model run. This name dictates the output subfolder.
    *   **Review and Override Settings**: Users review settings from the Excel file and can override some via the UI (e.g., `Run Pypsa Model on`, `Weightings`, `Base_Year`, `Multi Year Investment`, `Generator Cluster`).
*   **Load Profile Specification**:
    *   The load profile (e.g., a `{profile_id}.csv` file from the 'Load Profile Generation Flow') to be used by PyPSA is typically referenced within `pypsa_input_template.xlsx`. The path specified in the Excel should point to the CSV file located in `app.config['CURRENT_PROJECT_PATH']/results/load_profiles/`.

### 4.3. Running the PyPSA Model (`/api/run_pypsa_model` API endpoint)

This API endpoint initiates and manages the PyPSA model execution.

*   **API Call**: UI sends a POST request to `/api/run_pypsa_model` with `scenarioName` and any overridden settings.
*   **Backend Processing (primarily via `utils.pypsa_runner.run_pypsa_model_core`)**:
    *   **Job Initialization**: A unique `job_id` is generated. Active jobs are tracked (e.g., in `pypsa_jobs` dictionary).
    *   **Asynchronous Execution**: `utils.pypsa_runner.run_pypsa_model_core` is launched in a background thread.
    *   **Core Logic in `run_pypsa_model_core`**:
        *   Reads `pypsa_input_template.xlsx` from `app.config['CURRENT_PROJECT_PATH']/inputs/`.
        *   Constructs a PyPSA network object (`n = pypsa.Network()`) by parsing data from Excel sheets (components, parameters, constraints, load series from the referenced CSV, renewable profiles).
        *   Applies UI-overridden settings.
        *   Solves the optimization problem (e.g., `n.lopf()`).
        *   **Output Storage**:
            *   **Primary Network File**: The solved PyPSA network is saved as a NetCDF file (`.nc`). The output path is `app.config['CURRENT_PROJECT_PATH']/results/PyPSA_Modeling/{scenarioName}/{scenarioName}.nc`.
            *   **Additional Result Files**: May include CSV exports of specific dataframes, potentially in subdirectories for multi-year models.
    *   **Logging**: Progress and errors are logged and associated with the `job_id`.

### 4.4. Monitoring PyPSA Model Run (`/api/pypsa_model_status/{job_id}` API endpoint)

Allows the UI to track the progress of an ongoing PyPSA model run.

*   **Polling**: UI sends GET requests to `/api/pypsa_model_status/{job_id}`.
*   **Status Updates**: API returns JSON with `status` (e.g., `running`, `completed`), `progress`, `logs`, `current_step`, and `result_files` (list of output file paths upon completion).

---

**Methodology Notes (PyPSA Modeling):**

*   Configuration is data-driven via `pypsa_input_template.xlsx`.
*   `utils.pypsa_runner.py` orchestrates model setup, execution, and result handling.
*   Relies on the PyPSA library for core modeling and optimization.
*   **Output Path Clarification**: The `run_pypsa_model_core` function saves its primary output (`.nc` file) to the `app.config['CURRENT_PROJECT_PATH']/results/PyPSA_Modeling/{scenarioName}/` directory. This is distinct from the directory used by the "PyPSA Results Visualization" module.

---

## 5. PyPSA Results Visualization Flow

This section outlines how users can visualize and analyze the results of PyPSA model runs.

### 5.1. Accessing the Visualization Page (`/pypsa_results`)

This page is the central hub for viewing PyPSA network results.

*   **Navigation**: Users navigate to the "PyPSA Results" page (if the feature is enabled), corresponding to `/pypsa_results`.
*   **File Discovery/Listing**:
    *   Frontend calls `/api/pypsa/scan_files`.
    *   `api_scan_pypsa_files_route` (using `get_pypsa_results_folder`) scans `app.config['CURRENT_PROJECT_PATH']/results/Pypsa_results/` for sub-directories (scenarios) containing `.nc` files.
    *   Returns a JSON list of scenarios and their `.nc` files for UI display.
*   **File Upload Option**:
    *   UI allows uploading `.nc` files via `/api/pypsa/upload_network`.
    *   `api_upload_pypsa_network_route` saves uploaded files into a scenario subfolder within `app.config['CURRENT_PROJECT_PATH']/results/Pypsa_results/`.
*   **Clarification on File Paths for Visualization**:
    *   This visualization module primarily interacts with `.nc` files located within `app.config['CURRENT_PROJECT_PATH']/results/Pypsa_results/`.
    *   As noted in the "PyPSA Modeling Flow", the modeling module outputs its results to `app.config['CURRENT_PROJECT_PATH']/results/PyPSA_Modeling/{scenarioName}/`.
    *   **Therefore, to visualize results from a model run, users must either**:
        1.  Manually copy or move the desired `.nc` file from its output location in `results/PyPSA_Modeling/{scenarioName}/` to a scenario folder under `results/Pypsa_results/`.
        2.  Use the file upload feature on the `/pypsa_results` page to place the `.nc` file into the `results/Pypsa_results/` directory structure.
    *   No automatic transfer mechanism between these two distinct result directories (`PyPSA_Modeling` and `Pypsa_results`) is implicitly handled by the application.

### 5.2. Selecting a Network and Viewing Basic Info

Once a `.nc` file is chosen, the application displays its fundamental characteristics.

*   **User Selection**: User selects a `.nc` file (path relative to `Pypsa_results` folder).
*   **Fetching Network Information**:
    *   UI calls `/api/pypsa/network_info/{path_to_nc_file}`.
    *   `api_get_network_info_route` loads the network (`pypsa.Network()`) and extracts general info (name, component counts, carriers, snapshot details, investment periods, objective).
    *   Returns JSON for display.
*   **Period Extraction (for multi-period networks)**:
    *   If multi-period, UI may offer extraction via `/api/pypsa/extract_period/{path_to_nc_file}/{period_name}`.
    *   `api_extract_period_route` loads the network, extracts data for the specified period, creates a new single-period network, and saves it (e.g., in `results/Pypsa_results/ScenarioA/extracted_periods/network_YYYY.nc`).

### 5.3. Interactive Dashboards and Data Visualization

Users explore various interactive dashboards for the selected network.

*   **Data Fetching Mechanism**:
    *   Most data is fetched via API calls routed through `_api_data_wrapper` in `app.py`. This wrapper takes the network path, a data extraction function name (from `utils.pypsa_analysis_utils`, aliased `pau`), and optional filters.
    *   The wrapper loads the network, filters snapshots (using `_get_snapshots_for_period`), and calls the specified `pau` function.
*   **Common Visualizations and Backend API Calls** (prefixed `/api/pypsa/`, include network path):
    *   **Dispatch Data (`.../dispatch_data/...`)**: `pau.dispatch_data_payload_former` (generation, load, storage dispatch/store).
    *   **Capacity Data (`.../capacity_data/...`)**: `pau.get_carrier_capacity` (installed capacities).
    *   **Metrics Data (`.../metrics_data/...`)**: `pau.combined_metrics_extractor_wrapper` (CUF, curtailment).
    *   **Storage Data (`.../storage_data/...`)**: `pau.extract_api_storage_data_payload_former` (state of charge, power).
    *   **Emissions Data (`.../emissions_data/...`)**: `pau.emissions_payload_former` (CO2 emissions per carrier).
    *   **Prices Data (`.../prices_data/...`)**: `pau.extract_api_prices_data_payload_former` (LMPs).
    *   **Network Flow Data (`.../network_flow/...`)**: `pau.extract_api_network_flow_payload_former` (line flows, loading).
*   **Filtering**: Users can filter by period, date range, and resolution. `_get_snapshots_for_period` helps apply these.
*   **Methodology**: Backend APIs load `.nc` files, use `utils.pypsa_analysis_utils.py` functions to extract/process data, serialize to JSON, and send to frontend for rendering with charting libraries. `pau.get_color_palette` provides consistent chart colors.

### 5.4. Comparing Multiple Networks (`/api/pypsa/compare_networks`)

Supports comparing key results across several PyPSA network files.

*   **User Interaction**: UI allows selecting multiple `.nc` files from `Pypsa_results`.
*   **API Call**: POST to `/api/pypsa/compare_networks` with network paths, labels, and comparison type (e.g., 'capacity', 'generation').
*   **Backend Processing**: `api_compare_pypsa_networks_route` loads each network, extracts data based on `comparison_type` using `pau` functions, and aggregates results for comparative visualization.
*   **Display**: UI receives aggregated data and presents comparative charts or tables.

---

**Methodology Notes (PyPSA Results Visualization):**

*   Relies heavily on `pypsa` library and `utils.pypsa_analysis_utils.py` (aliased `pau`) for data extraction and processing from `.nc` files.
*   `_api_data_wrapper` in `app.py` is a central handler for visualization data requests.
*   Frontend renders JSON data using charting libraries.
*   **Crucial File Path Management**: Users must be aware of the distinction between the `results/PyPSA_Modeling/` output directory and the `results/Pypsa_results/` directory used by this visualization module, and the need to move or upload files accordingly.

---

## 6. Feature Management Flow

This section describes how application features can be enabled or disabled on a per-project basis, allowing customization of available tools for each project.

### 6.1. Accessing Feature Management (`/admin/features` page)

This page provides the interface for managing feature flags.

*   **Navigation**: Administrators access this page, likely from an admin menu.
*   **Project Requirement**: Functional only when a project is loaded (`app.config['CURRENT_PROJECT_PATH']` is set). Otherwise, prompts to load a project.
*   **Context Display**: Displays the name of the `current_project` (`app.config['CURRENT_PROJECT']`).

### 6.2. Displaying Features and Their Status

Lists all available features and their current state for the active project.

*   **API Call**: GET request to `/api/features` on page load.
*   **Backend Processing (`app.feature_manager`)**:
    *   `api_get_features` calls `app.feature_manager.get_merged_features(project_path)`.
    *   `FeatureManager.get_merged_features` (from `utils.features_manager.py`):
        1.  Loads global defaults from `config/features.json` (master list: id, name, description, enabled_by_default, feature_group).
        2.  Loads project-specific overrides from `app.config['CURRENT_PROJECT_PATH']/project_features.json` if it exists.
        3.  Merges configurations: project settings override global defaults.
    *   API returns JSON list of all features with their effective `enabled` status for the project.
*   **UI Display**: Renders the list, possibly grouped by `feature_group`, with toggles indicating current status.

### 6.3. Enabling or Disabling a Feature

Users can change the enabled status of any feature for the current project.

*   **User Interaction**: User clicks a feature's toggle switch.
*   **API Call**: PUT request to `/api/features/{feature_id}` with `{"enabled": true/false}`.
*   **Backend Processing (`app.feature_manager.set_feature_enabled`)**:
    *   `api_set_feature` calls `app.feature_manager.set_feature_enabled(feature_id, enabled_status, project_path)`.
    *   `FeatureManager.set_feature_enabled` loads project's `project_features.json` (or initializes if new), updates the feature's status, and saves the file.
    *   API returns success/error message.
*   **UI Update**: Toggle updates. Application behavior (UI elements, routes) may change based on how flags are checked.

### 6.4. Using Feature Flags in the Application

Feature flags conditionally control application parts.

*   **Context Processor (`feature_processor`)**: Registered during `init_feature_manager`. Makes `is_used(feature_id)` and `get_enabled_features()` available globally in Jinja2 templates.
    *   `is_used(feature_id)` calls `app.feature_manager.is_feature_enabled(feature_id, app.config.get('CURRENT_PROJECT_PATH'))`.
*   **Template Usage**: Templates use `is_used('some-feature-id')` to conditionally render UI elements (e.g., sidebar links, buttons).
*   **Backend Usage (Conceptual)**: Python code (e.g., Flask routes) could call `app.feature_manager.is_feature_enabled(feature_id, project_path)` for conditional logic (e.g., enabling/disabling APIs, modifying data/behavior).

---

**Methodology Notes (Feature Management):**

*   Enables per-project customization of application functionalities.
*   Uses global `config/features.json` for defaults and project-specific `project_features.json` for overrides.
*   `FeatureManager` class (`utils/features_manager.py`) is central to feature flag logic.
*   `is_used(feature_id)` in Jinja2 templates is the primary method for UI control.

---

## 7. Helper/Utility Pages

This section covers various helper pages and utility functions that provide supporting resources and template downloads for the user.

### 7.1. User Guide Page (`/user_guide`)

Displays the main user guide for the application.

*   **Access**: Via "User Guide" link.
*   **Functionality**: `user_guide()` function renders `user_guide.html`.
*   **Content**: `user_guide.html` could contain content directly, embed a PDF, or link to external documentation.

### 7.2. Template Downloads (`/download_template/<template_type>`)

Allows users to download various Excel template files.

*   **Access**: Links/buttons within relevant application sections.
*   **Functionality**: `download_template(template_type)` serves files based on `template_type`.
*   **`template_type` Values**:
    *   `'data_input'`: Downloads `data_input_template.xlsx` (for demand projection, likely an alias or version of `input_demand_file.xlsx`).
    *   `'load_curve'`: Downloads `load_curve_template.xlsx` (for load profile generation).
    *   `'pypsa_input'`: Downloads `pypsa_input_template.xlsx` (for PyPSA modeling).
*   **File Location**: `app.config['TEMPLATE_FOLDER']` (initialized to `static/templates/`).
*   **Error Handling**: Flashes warning and redirects if template type is invalid or file not found. `create_template_files()` is called, likely to ensure template existence.
*   **Output**: Serves the requested Excel template file for download.

### 7.3. User Guide Download (`/download_user_guide`)

Provides a direct download for the user guide PDF.

*   **Access**: Via button/link (e.g., on `/user_guide` page).
*   **Functionality**: `download_user_guide()` serves `user_guide.pdf`.
*   **File Location**: `app.config['TEMPLATE_FOLDER']/user_guide.pdf`.
*   **Output**: Serves `user_guide.pdf` for download.

### 7.4. Methodology Document Download (`/download_methodology`)

Provides a direct download for the methodology document PDF.

*   **Access**: Via button/link.
*   **Functionality**: `download_methodology()` serves `methodology.pdf`.
*   **File Location**: `app.config['TEMPLATE_FOLDER']/methodology.pdf`.
*   **Output**: Serves `methodology.pdf` for download.

### 7.5. Tutorials Page (`/tutorials`)

Intended to host tutorial materials.

*   **Access**: Via "Tutorials" link.
*   **Functionality**: `tutorials()` function.
*   **Content**: Currently a placeholder; flashes "is coming soon!" and redirects to home. Intended for step-by-step guides, videos, etc.

---

**Methodology Notes (Helper/Utility Pages):**

*   Provide essential user support (documentation, templates, learning resources).
*   Mainly serve static files (Excel, PDF) from `static/templates/`.
*   Basic error handling for template downloads ensures graceful failure.
*   `create_template_files()` suggests a mechanism to ensure template availability.

---
