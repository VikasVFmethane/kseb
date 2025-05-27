
// static/js/demand_projection.js

document.addEventListener('DOMContentLoaded', function () {
    // Initialize the page
    console.log("Demand Projection: DOMContentLoaded");
    setupSectorTabs();
    setupViewToggles();
    setupForecastButton(); // Moved setupForecastButton here to ensure it's always called
    setupForecastModal(); // Moved setupForecastModal here

    // Load the initial charts for the active sector
    const activeTab = document.querySelector('.sector-button.active');
    if (activeTab) {
        console.log("Demand Projection: Initial active tab found:", activeTab.dataset.sector);
        loadSectorCharts(activeTab.dataset.sector);
    } else {
        console.log("Demand Projection: No initial active tab found.");
    }
});

/**
 * Set up click handlers for sector tabs
 */
function setupSectorTabs() {
    const sectorButtons = document.querySelectorAll('.sector-button');
    console.log("Demand Projection: Setting up sector tabs. Found buttons:", sectorButtons.length);

    sectorButtons.forEach(button => {
        button.addEventListener('click', function () {
            console.log("Demand Projection: Sector button clicked:", this.dataset.sector);
            // Remove active class from all buttons
            sectorButtons.forEach(btn => btn.classList.remove('active'));

            // Add active class to clicked button
            this.classList.add('active');

            // Hide all sector sections
            const sectorSections = document.querySelectorAll('.sector-section');
            sectorSections.forEach(section => section.classList.remove('active'));

            // Show the selected sector section
            const sectorId = this.dataset.sector;
            const sectorSection = document.getElementById(`${sectorId}-section`);
            if (sectorSection) {
                sectorSection.classList.add('active');
                console.log("Demand Projection: Activated sector section:", sectorId);
                // Load charts for this sector
                loadSectorCharts(sectorId);
            } else {
                console.error("Demand Projection: Sector section not found for ID:", sectorId);
            }
        });
    });
}

/**
 * Set up click handlers for view toggles (table/chart/correlation)
 */
function setupViewToggles() {
    const viewButtons = document.querySelectorAll('.view-toggle-button');
    console.log("Demand Projection: Setting up view toggles. Found buttons:", viewButtons.length);

    viewButtons.forEach(button => {
        button.addEventListener('click', function () {
            const sector = this.dataset.sector;
            const view = this.dataset.view;
            console.log(`Demand Projection: View toggle clicked. Sector: ${sector}, View: ${view}`);

            // Get all toggle buttons for this sector
            const sectorButtons = document.querySelectorAll(`.view-toggle-button[data-sector="${sector}"]`);

            // Remove active class from all buttons in this group
            sectorButtons.forEach(btn => btn.classList.remove('active'));

            // Add active class to clicked button
            this.classList.add('active');

            // Hide all views for this sector
            const views = document.querySelectorAll(`#${sector}-table-view, #${sector}-chart-view, #${sector}-correlation-view`);
            views.forEach(v => {
                v.classList.remove('active');
                v.style.display = 'none';
            });

            // Show the selected view
            const selectedView = document.getElementById(`${sector}-${view}-view`);
            if (selectedView) {
                selectedView.classList.add('active');
                selectedView.style.display = 'flex';
                console.log(`Demand Projection: Activated view: ${sector}-${view}-view`);

                // If switching to a chart view, ensure charts are loaded
                if (view === 'chart' || view === 'correlation') {
                    loadSpecificChart(sector, view);
                }
            } else {
                 console.error(`Demand Projection: View content not found for: ${sector}-${view}-view`);
            }
        });
    });
}

/**
 * Load all charts for a given sector
 */
function loadSectorCharts(sector) {
    console.log("Demand Projection: Loading charts for sector:", sector);
    // First check if the time series chart view is visible
    const chartView = document.getElementById(`${sector}-chart-view`);
    if (chartView && chartView.classList.contains('active')) {
        console.log("Demand Projection: Time series chart view is active for", sector);
        loadSpecificChart(sector, 'chart');
    }

    // Then check if correlation view is visible
    const correlationView = document.getElementById(`${sector}-correlation-view`);
    if (correlationView && correlationView.classList.contains('active')) {
        console.log("Demand Projection: Correlation view is active for", sector);
        loadSpecificChart(sector, 'correlation');
    }
}

/**
 * Load a specific chart type for a sector
 */
function loadSpecificChart(sector, chartType) {
    console.log(`Demand Projection: Loading specific chart. Sector: ${sector}, Type: ${chartType}`);
    if (chartType === 'chart') {
        // Show loading spinner
        const spinner = document.getElementById(`${sector}ChartSpinner`);
        const chartCanvas = document.getElementById(`${sector}Chart`);
        const errorElement = document.getElementById(`${sector}ChartError`);

        if (spinner) spinner.style.display = 'flex';
        if (chartCanvas) chartCanvas.style.display = 'none';
        if (errorElement) errorElement.style.display = 'none';

        console.log(`Demand Projection: Fetching time series chart data for ${sector}`);
        // Fetch data from API
        fetch(`/demand/api/chart_data/${sector}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log(`Demand Projection: Received time series chart data for ${sector}:`, data);
                if (data.status === 'success') {
                    renderTimeSeriesChart(sector, data.data);
                } else {
                    showChartError(sector, 'chart', data.message || 'Failed to load chart data');
                }
            })
            .catch(error => {
                console.error(`Demand Projection: Error fetching time series chart data for ${sector}:`, error);
                showChartError(sector, 'chart', error.message || 'Error loading chart data');
            })
            .finally(() => {
                if (spinner) spinner.style.display = 'none';
            });
    }
    else if (chartType === 'correlation') {
        const spinner = document.getElementById(`${sector}CorrelationSpinner`);
        const chartDiv = document.getElementById(`${sector}CorrelationChart`);
        const errorElement = document.getElementById(`${sector}CorrelationError`);
        
        if (spinner) spinner.style.display = 'flex';
        if (chartDiv) chartDiv.style.display = 'none'; // Hide previous chart/table
        if (errorElement) errorElement.style.display = 'none';
        
        console.log(`Demand Projection: Fetching correlation data for ${sector}`);
        fetch(`/demand/api/correlation_data/${sector}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log(`Demand Projection: Received correlation data for ${sector}:`, data);
                if (data.status === 'success' && data.data) {
                    renderCorrelationChart(sector, data.data);
                } else {
                    showChartError(sector, 'correlation', data.message || 'Failed to load correlation data');
                }
            })
            .catch(error => {
                console.error(`Demand Projection: Error fetching correlation data for ${sector}:`, error);
                showChartError(sector, 'correlation', error.message || 'Error loading correlation data');
            })
            .finally(() => {
                if (spinner) spinner.style.display = 'none';
            });
    }
}

/**
 * Render a time series chart for the sector
 */
function renderTimeSeriesChart(sector, data) {
    console.log(`Demand Projection: Rendering time series chart for ${sector}`, data);
    const canvasElement = document.getElementById(`${sector}Chart`);
    if (!canvasElement) {
        console.error(`Demand Projection: Canvas element not found for sector ${sector}`);
        return;
    }

    // Clear any existing chart
    if (canvasElement._chart) {
        canvasElement._chart.destroy();
    }

    if (sector === 'aggregated' && data.datasets) {
        const ctx = canvasElement.getContext('2d');
        const chartData = { labels: data.years, datasets: data.datasets };
        const options = {
            responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
            plugins: { title: { display: true, text: 'Electricity Consumption by Sector' }, tooltip: { enabled: true }, legend: { position: 'bottom' } },
            stacked: true,
            scales: { x: { title: { display: true, text: 'Year', stacked: true } }, y: { title: { display: true, text: 'Electricity Consumption', stacked: true }, beginAtZero: true } }
        };
        canvasElement._chart = new Chart(ctx, { type: 'line', data: chartData, options: options });
        canvasElement.style.display = 'block';
        console.log(`Demand Projection: Aggregated chart rendered for ${sector}`);
    }
    else if (data.years && data.electricity) {
        const ctx = canvasElement.getContext('2d');
        const chartData = {
            labels: data.years,
            datasets: [{ label: 'Electricity Consumption', data: data.electricity, borderColor: 'rgb(59, 130, 246)', backgroundColor: 'rgba(59, 130, 246, 0.5)', tension: 0.1 }]
        };
        const options = {
            responsive: true, maintainAspectRatio: false,
            plugins: { title: { display: true, text: `${sector.charAt(0).toUpperCase() + sector.slice(1)} Sector Electricity Consumption` }, tooltip: { enabled: true } },
            scales: { x: { title: { display: true, text: 'Year' } }, y: { title: { display: true, text: 'Electricity Consumption' }, beginAtZero: true } }
        };
        canvasElement._chart = new Chart(ctx, { type: 'line', data: chartData, options: options });
        canvasElement.style.display = 'block';
        console.log(`Demand Projection: Individual sector chart rendered for ${sector}`);
    } else {
        console.error(`Demand Projection: Unexpected data format for sector ${sector}:`, data);
        showChartError(sector, 'chart', 'Unexpected data format received');
    }
}

/**
 * Render a correlation chart (now a table) for the sector
 */
function renderCorrelationChart(sector, data) {
    console.log(`Demand Projection: Rendering correlation table for sector ${sector}`, data);
    const chartElement = document.getElementById(`${sector}CorrelationChart`);
    if (!chartElement) {
        console.error(`Demand Projection: Correlation chart/table element not found for ${sector}`);
        return;
    }
    
    if (!data || !data.variables || !data.correlations || data.variables.length === 0) {
        console.warn(`Demand Projection: No correlation data available for Electricity in sector ${sector}`);
        showChartError(sector, 'correlation', 'No correlation data available for Electricity');
        return;
    }
    
    try {
        chartElement.innerHTML = ''; // Clear previous content
        const table = document.createElement('table');
        table.className = 'table table-striped table-hover table-sm';
        
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        ['Variable', 'Correlation with Electricity', 'Strength'].forEach(text => {
            const th = document.createElement('th');
            th.textContent = text;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        const tbody = document.createElement('tbody');
        for (let i = 0; i < data.variables.length; i++) {
            const row = document.createElement('tr');
            
            const varCell = document.createElement('td');
            varCell.textContent = data.variables[i];
            row.appendChild(varCell);
            
            const valueCell = document.createElement('td');
            const corrValue = typeof data.correlations[i] === 'object' ? data.correlations[i].value : data.correlations[i];
            valueCell.textContent = parseFloat(corrValue).toFixed(3); // Format to 3 decimal places
            
            const absValue = Math.abs(corrValue);
            if (absValue >= 0.7) valueCell.className = 'text-success fw-bold';
            else if (absValue >= 0.4) valueCell.className = 'text-primary';
            else valueCell.className = 'text-muted';
            row.appendChild(valueCell);
            
            const strengthCell = document.createElement('td');
            const strength = typeof data.correlations[i] === 'object' ? data.correlations[i].strength : (absValue >= 0.7 ? "Strong" : absValue >= 0.4 ? "Moderate" : "Weak");
            strengthCell.textContent = strength;
            strengthCell.className = valueCell.className; // Match color
            row.appendChild(strengthCell);
            
            tbody.appendChild(row);
        }
        table.appendChild(tbody);
        chartElement.appendChild(table);
        chartElement.style.display = 'block'; // Ensure it's visible
        console.log(`Demand Projection: Correlation table rendered for ${sector}`);
    } catch (error) {
        console.error(`Demand Projection: Error rendering correlation table for ${sector}:`, error);
        showChartError(sector, 'correlation', `Error rendering correlation data: ${error.message}`);
    }
}

/**
 * Display an error message when chart loading fails
 */
function showChartError(sector, chartType, message) {
    console.error(`Demand Projection: Chart error for Sector: ${sector}, Type: ${chartType}, Message: ${message}`);
    let errorElement;
    if (chartType === 'chart') errorElement = document.getElementById(`${sector}ChartError`);
    else if (chartType === 'correlation') errorElement = document.getElementById(`${sector}CorrelationError`);

    if (errorElement) {
        errorElement.textContent = `Error: ${message}`;
        errorElement.style.display = 'block';
    } else {
        console.error(`Demand Projection: Error element not found for ${sector}-${chartType}Error`);
    }
}


// Forecast Model Configuration Handling
let forecastModalTrigger = null; // To store the element that opened the modal

function setupForecastButton() {
    const runForecastBtnContainer = document.querySelector('.run-forecast-btn'); // Assuming the button itself is the container
    console.log("Demand Projection: Setting up main forecast button.");
    if (runForecastBtnContainer) {
        runForecastBtnContainer.addEventListener('click', function () {
            console.log("Demand Projection: Main 'Run Forecast Model' button clicked.");
            forecastModalTrigger = this; // Store the trigger
            openForecastModal();
        });
    } else {
        console.error("Demand Projection: Main 'Run Forecast Model' button not found.");
    }
}

/**
 * Setup the forecast configuration modal controls
 */
function setupForecastModal() {
    console.log("Demand Projection: Setting up forecast modal.");
    const defaultModelCheckboxes = document.querySelectorAll('.default-model-checkbox');
    defaultModelCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            console.log(`Demand Projection: Default model checkbox changed: ${this.value}, Checked: ${this.checked}`);
        });
    });

    const applyToAllSectorsBtn = document.getElementById('applyToAllSectorsBtn');
    if (applyToAllSectorsBtn) {
        applyToAllSectorsBtn.addEventListener('click', function () {
            console.log("Demand Projection: 'Apply to All Sectors' button clicked.");
            const selectedDefaultModels = Array.from(document.querySelectorAll('.default-model-checkbox:checked')).map(cb => cb.value);
            document.querySelectorAll('.sector-config').forEach(sectorElement => {
                const sector = sectorElement.dataset.sector;
                document.querySelectorAll(`input[name="forecastModel_${sector}"]`).forEach(modelCheckbox => {
                    modelCheckbox.checked = selectedDefaultModels.includes(modelCheckbox.value);
                    const modelType = modelCheckbox.value;
                    const configSection = document.getElementById(`${modelType.toLowerCase()}Config_${sector}`);
                    if (configSection) configSection.style.display = modelCheckbox.checked ? 'block' : 'none';
                });
                localStorage.setItem(`forecast_models_${sector}`, JSON.stringify(selectedDefaultModels));
            });
            showGlobalAlert('Default model selections applied to all sectors.', 'success');
        });
    }

    const sectorModelCheckboxes = document.querySelectorAll('.sector-model-checkbox');
    sectorModelCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            const sector = this.dataset.sector;
            const modelType = this.value;
            console.log(`Demand Projection: Sector model checkbox changed. Sector: ${sector}, Model: ${modelType}, Checked: ${this.checked}`);
            const configSection = document.getElementById(`${modelType.toLowerCase()}Config_${sector}`);
            if (configSection) configSection.style.display = this.checked ? 'block' : 'none';
            const selectedModels = Array.from(document.querySelectorAll(`input[name="forecastModel_${sector}"]:checked`)).map(cb => cb.value);
            localStorage.setItem(`forecast_models_${sector}`, JSON.stringify(selectedModels));
        });
    });

    document.querySelectorAll('.sector-config').forEach(sectorElement => {
        const sector = sectorElement.dataset.sector;
        const windowRadios = document.querySelectorAll(`input[name="windowSize_${sector}"]`);
        const customWindowContainer = document.getElementById(`customWindowContainer_${sector}`);
        windowRadios.forEach(radio => {
            radio.addEventListener('change', function () {
                if (customWindowContainer) customWindowContainer.style.display = (this.value === 'custom' && this.checked) ? 'block' : 'none';
            });
        });
        loadIndependentVariables(sector);
    });

    const runForecastBtnModal = document.getElementById('runForecastBtn'); // This is the button inside the modal
    if (runForecastBtnModal) {
        runForecastBtnModal.addEventListener('click', startForecast);
    } else {
         console.error("Demand Projection: 'Run Forecast' button inside modal not found.");
    }

    const cancelForecastBtnModal = document.getElementById('cancelForecastBtn');
    if (cancelForecastBtnModal) {
        cancelForecastBtnModal.addEventListener('click', cancelForecast);
    } else {
        console.error("Demand Projection: 'Cancel Forecast' button inside progress modal not found.");
    }

    const viewResultsBtnModal = document.getElementById('viewResultsBtn');
    if (viewResultsBtnModal) {
        viewResultsBtnModal.addEventListener('click', function (e) {
            e.preventDefault();
            const scenarioName = document.getElementById('summaryScenario').textContent || 'Base_Scenario';
            console.log("Demand Projection: 'View Results' button clicked. Redirecting to visualization for scenario:", scenarioName);
            window.location.href = `/demand/visualization?scenario=${encodeURIComponent(scenarioName)}`;
        });
    } else {
        console.error("Demand Projection: 'View Results' button inside complete modal not found.");
    }
    
    const forecastConfigModalEl = document.getElementById('forecastConfigModal');
    if (forecastConfigModalEl) {
        forecastConfigModalEl.addEventListener('hidden.bs.modal', function () {
            console.log("Demand Projection: Forecast config modal hidden.");
            if (forecastModalTrigger && typeof forecastModalTrigger.focus === 'function') {
                forecastModalTrigger.focus(); // Return focus
            }
            forecastModalTrigger = null; // Reset trigger
        });
    }
}

/**
 * Open forecast modal and prepare it
 */
function openForecastModal() {
    console.log("Demand Projection: Opening forecast modal.");
    document.querySelectorAll('.sector-config').forEach(sectorElement => {
        const sector = sectorElement.dataset.sector;
        const savedModels = JSON.parse(localStorage.getItem(`forecast_models_${sector}`) || '[]');
        
        document.querySelectorAll(`input[name="forecastModel_${sector}"]`).forEach(checkbox => {
            checkbox.checked = savedModels.includes(checkbox.value);
            const modelType = checkbox.value;
            const configSection = document.getElementById(`${modelType.toLowerCase()}Config_${sector}`);
            if (configSection) configSection.style.display = checkbox.checked ? 'block' : 'none';
        });
        
        // Set default WAM if no saved models
        if (savedModels.length === 0) {
            const wamCheckbox = document.querySelector(`#modelWAM_${sector}`);
            if (wamCheckbox) {
                 wamCheckbox.checked = true;
                 const wamConfig = document.getElementById(`wamConfig_${sector}`);
                 if (wamConfig) wamConfig.style.display = 'block';
                 localStorage.setItem(`forecast_models_${sector}`, JSON.stringify(['WAM']));
            }
        }
    });

    const forecastModalEl = document.getElementById('forecastConfigModal');
    if (forecastModalEl) {
        const forecastModal = new bootstrap.Modal(forecastModalEl);
        forecastModal.show();
        console.log("Demand Projection: Forecast modal shown.");
    } else {
        console.error("Demand Projection: Forecast config modal element not found.");
    }
}

/**
 * Load independent variables for the selected sector
 */
function loadIndependentVariables(sector) {
    console.log(`Demand Projection: Loading independent variables for sector: ${sector}`);
    const container = document.getElementById(`independentVarsContainer_${sector}`);
    if (!container) {
        console.error(`Demand Projection: Independent vars container not found for sector: ${sector}`);
        return;
    }
    if (container.dataset.loaded === 'true') {
        console.log(`Demand Projection: Independent variables already loaded for sector: ${sector}`);
        return;
    }
    container.innerHTML = `<div class="alert alert-secondary"><i class="fas fa-spinner fa-spin me-2"></i>Loading available variables...</div>`;
    fetch(`/demand/api/independent_variables/${sector}`)
        .then(response => {
            if (!response.ok) throw new Error(`Network response was not ok: ${response.status}`);
            return response.json();
        })
        .then(data => {
            console.log(`Demand Projection: Received independent variables for ${sector}:`, data);
            if (data.status === 'success') {
                renderIndependentVariables(container, data.variables, data.correlations);
                container.dataset.loaded = 'true';
            } else {
                container.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>${data.message || 'Failed to load variables'}</div>`;
            }
        })
        .catch(error => {
            console.error(`Demand Projection: Error loading independent variables for ${sector}:`, error);
            container.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>Error: ${error.message}</div>`;
        });
}

/**
 * Render independent variables checkboxes with correlation info
 */
function renderIndependentVariables(container, variables, correlations) {
    console.log(`Demand Projection: Rendering independent variables. Variables: ${variables.length}, Correlations:`, correlations);
    if (!variables || variables.length === 0) {
        container.innerHTML = `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle me-2"></i>No independent variables available for this sector.</div>`;
        return;
    }
    let html = '<div class="row">';
    variables.forEach(variable => {
        if (variable === 'Year' || variable === 'Electricity') return;
        const correlation = correlations[variable] || 0;
        const correlationAbs = Math.abs(correlation);
        let correlationClass = 'text-muted';
        let correlationText = 'Weak';
        if (correlationAbs >= 0.7) { correlationClass = 'text-success fw-bold'; correlationText = 'Strong'; }
        else if (correlationAbs >= 0.4) { correlationClass = 'text-primary'; correlationText = 'Moderate'; }
        html += `
            <div class="col-md-6 mb-2">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="independentVars_${container.id.split('_')[1]}" 
                           id="var_${variable}_${container.id.split('_')[1]}" value="${variable}" ${correlationAbs >= 0.4 ? 'checked' : ''}>
                    <label class="form-check-label" for="var_${variable}_${container.id.split('_')[1]}">
                        ${variable} <span class="ms-2 ${correlationClass}">(${correlation.toFixed(2)}, ${correlationText})</span>
                    </label>
                </div>
            </div>`;
    });
    html += '</div>';
    container.innerHTML = html;
}

let currentForecastJobId = null;
let forecastPollingInterval = null;
let forecastPollingRetries = 0;
const MAX_POLLING_RETRIES = 5; // Max retries if status endpoint fails

function startForecast() {
    console.log("Demand Projection: Starting forecast process.");
    
    const taskName = "Demand Forecast";
    if (window.ActiveProcessManager && window.ActiveProcessManager.isTaskPrefixRunning(taskName)) {
        showGlobalAlert(`A '${taskName}' is already in progress. Please wait for it to complete or cancel it from notifications.`, 'warning');
        return;
    }

    const configModalEl = document.getElementById('forecastConfigModal');
    if (configModalEl) {
        const configModal = bootstrap.Modal.getInstance(configModalEl);
        if (configModal) configModal.hide();
    }

    const form = document.getElementById('forecastConfigForm');
    const formData = new FormData(form);
    const targetYear = formData.get('targetYear');
    const scenarioName = formData.get('scenarioName') || 'DefaultScenario';
    const excludeCovidYears = formData.get('excludeCovidYears') === 'on';

    const sectorConfigs = {};
    document.querySelectorAll('.sector-config').forEach(sectorElement => {
        const sector = sectorElement.dataset.sector;
        const selectedModels = Array.from(document.querySelectorAll(`input[name="forecastModel_${sector}"]:checked`)).map(cb => cb.value);
        if (selectedModels.length === 0) return;

        const sectorConfig = { models: selectedModels };
        if (selectedModels.includes('MLR')) {
            sectorConfig.independentVars = Array.from(document.querySelectorAll(`input[name="independentVars_${sector}"]:checked`)).map(cb => cb.value);
        }
        if (selectedModels.includes('WAM')) {
            const wamRadio = document.querySelector(`input[name="windowSize_${sector}"]:checked`);
            if (wamRadio) {
                let windowSize = wamRadio.value;
                if (windowSize === 'custom') windowSize = document.getElementById(`customWindowSize_${sector}`).value;
                sectorConfig.windowSize = parseInt(windowSize) || 10;
            } else {
                sectorConfig.windowSize = 10; // Default
            }
        }
        sectorConfigs[sector] = sectorConfig;
    });

    console.log("Demand Projection: Final sector configs:", sectorConfigs);
    if (Object.keys(sectorConfigs).length === 0) {
        showGlobalAlert('Please select at least one model for at least one sector.', 'warning');
        return;
    }

    const requestData = { scenarioName, targetYear: parseInt(targetYear), excludeCovidYears, sectorConfigs };
    console.log("Demand Projection: Final request data for forecast:", requestData);

    const progressModalEl = document.getElementById('forecastProgressModal');
     if (progressModalEl) {
        const progressModal = new bootstrap.Modal(progressModalEl);
        progressModal.show();
    }
    
    updateProgressBar(5, 'Initiating...'); // Initial progress
    const firstSector = Object.keys(sectorConfigs)[0];
    const progressSectorNameEl = document.getElementById('progressSectorName');
    if(progressSectorNameEl) progressSectorNameEl.textContent = firstSector ? (firstSector.charAt(0).toUpperCase() + firstSector.slice(1)) : 'All Sectors';

    sendForecastRequest(requestData, scenarioName);
}

function sendForecastRequest(requestData, scenarioNameForTask) {
    console.log("Demand Projection: Sending forecast request to /demand/api/run_forecast");
    currentForecastJobId = null; // Reset previous job ID
    forecastPollingRetries = 0; // Reset retries
    
    const taskDisplayName = `Demand Forecast (${scenarioNameForTask})`;

    fetch('/demand/api/run_forecast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        if (!response.ok) { // Check for HTTP errors first
             return response.json().then(errData => { // Try to parse error JSON
                throw new Error(errData.message || `HTTP error ${response.status}`);
            }).catch(() => { // Fallback if error JSON parsing fails
                throw new Error(`HTTP error ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log("Demand Projection: Response from /demand/api/run_forecast:", data);
        if (data.status === 'started' && data.jobId) {
            currentForecastJobId = data.jobId;
            document.getElementById('forecastProgressModal').dataset.jobId = currentForecastJobId;
            
            if (window.ActiveProcessManager) {
                window.ActiveProcessManager.add(currentForecastJobId, taskDisplayName, () => cancelForecast(currentForecastJobId));
            }

            if (forecastPollingInterval) clearInterval(forecastPollingInterval);
            forecastPollingInterval = setInterval(pollForecastStatus, 2500); // Poll every 2.5 seconds
            pollForecastStatus(); // Initial poll
        } else {
            throw new Error(data.message || 'Failed to start forecast job. No Job ID received.');
        }
    })
    .catch(error => {
        console.error("Demand Projection: Error starting forecast:", error);
        showForecastError(error.message);
        if (window.ActiveProcessManager && currentForecastJobId) {
             window.ActiveProcessManager.updateStatus(currentForecastJobId, 'failed', error.message);
        } else if (window.ActiveProcessManager) {
            // If job ID was never received, we can't link it. Maybe add a generic error task.
            window.ActiveProcessManager.add(`forecast-error-${Date.now()}`, taskDisplayName, null);
            window.ActiveProcessManager.updateStatus(`forecast-error-${Date.now()}`, 'failed', `Failed to initiate: ${error.message}`);
        }
    });
}

function pollForecastStatus() {
    if (!currentForecastJobId) {
        console.warn("Demand Projection: Polling attempted without a job ID.");
        return;
    }
    console.log(`Demand Projection: Polling status for job ID: ${currentForecastJobId}`);
    const taskDisplayName = `Demand Forecast (${document.getElementById('scenarioName').value || 'DefaultScenario'})`;

    fetch(`/demand/api/forecast_status/${currentForecastJobId}`)
        .then(response => {
            if (response.status === 404) {
                forecastPollingRetries++;
                if (forecastPollingRetries >= MAX_POLLING_RETRIES) {
                    clearInterval(forecastPollingInterval);
                    const errorMsg = `Forecast status endpoint not found or job ID ${currentForecastJobId} is invalid after ${MAX_POLLING_RETRIES} attempts. Please check backend.`;
                    showForecastError(errorMsg);
                     if (window.ActiveProcessManager) window.ActiveProcessManager.updateStatus(currentForecastJobId, 'error', errorMsg);
                } else {
                    console.warn(`Demand Projection: Status endpoint 404, retry ${forecastPollingRetries}/${MAX_POLLING_RETRIES}.`);
                }
                return null; // Stop further processing for this poll
            }
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (!data) return; // Skip if response was null (e.g. from 404 handling)

            console.log("Demand Projection: Received forecast status:", data);
            forecastPollingRetries = 0; // Reset retries on successful poll

            const progressSectorNameEl = document.getElementById('progressSectorName');
            if (data.currentSector && progressSectorNameEl) {
                progressSectorNameEl.textContent = data.currentSector.charAt(0).toUpperCase() + data.currentSector.slice(1);
            }

            if (data.status === 'running' || data.status === 'queued' || data.status.toLowerCase().includes('processing')) {
                updateProgressBar(data.progress, data.status);
                 if (window.ActiveProcessManager) window.ActiveProcessManager.updateStatus(currentForecastJobId, data.status, data.message || `Processing ${data.currentSector || ''}...`);
            } else if (data.status === 'completed') {
                clearInterval(forecastPollingInterval);
                updateProgressBar(100, 'Completed');
                 if (window.ActiveProcessManager) window.ActiveProcessManager.updateStatus(currentForecastJobId, 'completed', data.message || 'Forecast completed successfully.');
                setTimeout(() => showForecastCompleteModal(data.result), 1000);
            } else if (data.status === 'failed') {
                clearInterval(forecastPollingInterval);
                showForecastError(data.error || 'Unknown error during forecast.');
                 if (window.ActiveProcessManager) window.ActiveProcessManager.updateStatus(currentForecastJobId, 'failed', data.error || 'Forecast failed.');
            } else if (data.status === 'cancelled'){
                clearInterval(forecastPollingInterval);
                showGlobalAlert('Forecast was cancelled.', 'warning');
                 if (window.ActiveProcessManager) window.ActiveProcessManager.updateStatus(currentForecastJobId, 'cancelled', 'Forecast cancelled by user.');
                 const progressModalEl = document.getElementById('forecastProgressModal');
                 if (progressModalEl) {
                    const progressModal = bootstrap.Modal.getInstance(progressModalEl);
                    if (progressModal) progressModal.hide();
                }
            }
        })
        .catch(error => {
            console.error("Demand Projection: Error checking forecast status:", error);
            forecastPollingRetries++;
            if (forecastPollingRetries >= MAX_POLLING_RETRIES) {
                clearInterval(forecastPollingInterval);
                const errorMsg = `Error polling status after ${MAX_POLLING_RETRIES} retries: ${error.message}. Stopping polling.`;
                showForecastError(errorMsg);
                 if (window.ActiveProcessManager && currentForecastJobId) window.ActiveProcessManager.updateStatus(currentForecastJobId, 'error', errorMsg);
            } else {
                 console.warn(`Demand Projection: Error polling status, retry ${forecastPollingRetries}/${MAX_POLLING_RETRIES}.`);
            }
        });
}


function cancelForecast(jobIdToCancel = null) {
    const jobId = jobIdToCancel || document.getElementById('forecastProgressModal').dataset.jobId || currentForecastJobId;
    console.log(`Demand Projection: Attempting to cancel forecast job ID: ${jobId}`);

    if (!jobId) {
        showGlobalAlert('No active forecast job ID found to cancel.', 'warning');
        const progressModalEl = document.getElementById('forecastProgressModal');
        if (progressModalEl) {
             const progressModal = bootstrap.Modal.getInstance(progressModalEl);
             if (progressModal) progressModal.hide();
        }
        return;
    }
    
    if (!confirm('Are you sure you want to cancel the forecast?')) return;

    fetch(`/demand/api/cancel_forecast/${jobId}`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log("Demand Projection: Response from /api/cancel_forecast:", data);
            if (data.status === 'cancelled' || data.message.toLowerCase().includes('cancelled')) {
                showGlobalAlert('Forecast cancellation requested.', 'info');
                if (window.ActiveProcessManager) window.ActiveProcessManager.updateStatus(jobId, 'cancelling', 'Cancellation requested...');
                // Polling will pick up the final 'cancelled' state
            } else {
                showGlobalAlert(`Could not cancel forecast: ${data.message || 'Unknown error'}`, 'danger');
                 if (window.ActiveProcessManager) window.ActiveProcessManager.updateStatus(jobId, 'error', `Cancellation failed: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Demand Projection: Error cancelling forecast:', error);
            showGlobalAlert(`Error requesting forecast cancellation: ${error.message}`, 'danger');
             if (window.ActiveProcessManager) window.ActiveProcessManager.updateStatus(jobId, 'error', `Cancellation error: ${error.message}`);
        });
}

/**
 * Update the forecast progress bar
 */
function updateProgressBar(progress, statusText = '') {
    const progressBar = document.getElementById('forecastProgressBar');
    const progressPercentageSpan = document.querySelector('.progress-percentage'); // Assuming you have this span

    if (progressBar) {
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
        progressBar.textContent = `${progress}% ${statusText ? `- ${statusText}` : ''}`;
    }
    if (progressPercentageSpan) {
         progressPercentageSpan.textContent = `${progress}%`;
    }
     console.log(`Demand Projection: Progress bar updated to ${progress}%. Status: ${statusText}`);
}


/**
 * Show the forecast complete modal with results
 */
function showForecastCompleteModal(result) {
    console.log("Demand Projection: Forecast complete. Showing results modal:", result);
    const progressModalEl = document.getElementById('forecastProgressModal');
    if (progressModalEl) {
        const progressModal = bootstrap.Modal.getInstance(progressModalEl);
        if (progressModal) progressModal.hide();
    }

    if (result) {
        const summaryScenarioEl = document.getElementById('summaryScenario');
        const summaryTargetYearEl = document.getElementById('summaryTargetYear');
        const summaryTotalSectorsEl = document.getElementById('summaryTotalSectors');
        const summaryFilePathEl = document.getElementById('summaryFilePath');

        if(summaryScenarioEl) summaryScenarioEl.textContent = result.scenarioName || 'N/A';
        if(summaryTargetYearEl) summaryTargetYearEl.textContent = result.targetYear || 'N/A';
        if(summaryTotalSectorsEl) summaryTotalSectorsEl.textContent = result.totalSectors || (result.sectors_forecasted ? result.sectors_forecasted.length : 'N/A');
        if(summaryFilePathEl) summaryFilePathEl.textContent = result.filePath || `results/demand_projection/${result.scenarioName || 'unknown'}`;
    } else {
        console.warn("Demand Projection: Forecast complete but no result data provided to modal.");
    }

    const completeModalEl = document.getElementById('forecastCompleteModal');
    if (completeModalEl) {
        const completeModal = new bootstrap.Modal(completeModalEl);
        completeModal.show();
    } else {
        console.error("Demand Projection: Forecast complete modal element not found.");
    }
}

/**
 * Show forecast error notification
 */
function showForecastError(errorMessage) {
    console.error("Demand Projection: Forecast error:", errorMessage);
    const progressModalEl = document.getElementById('forecastProgressModal');
    if (progressModalEl) {
        const progressModal = bootstrap.Modal.getInstance(progressModalEl);
        if (progressModal) progressModal.hide();
    }
    showGlobalAlert(`Forecast Error: ${errorMessage}`, 'danger', 10000); // Longer duration for errors
}

/**
 * Show a global notification (toast) to the user.
 * Relies on showGlobalAlert from sidebar.js
 */
// function showNotification(message, type = 'info') {
//     console.log(`Demand Projection: showNotification called. Type: ${type}, Message: ${message}`);
//     if (typeof showGlobalAlert === 'function') {
//         try {
//             showGlobalAlert(message, type);
//         } catch (error) {
//             console.warn('Demand Projection: Error showing global alert:', error, ". Fallback to window.alert.");
//             window.alert(`${type.toUpperCase()}: ${message}`);
//         }
//     } else {
//         console.warn("Demand Projection: showGlobalAlert function not found. Fallback to window.alert.");
//         window.alert(`${type.toUpperCase()}: ${message}`);
//     }
// }
