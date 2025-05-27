// static/js/demand_projection.js

document.addEventListener('DOMContentLoaded', function () {
    // Initialize the page
    setupSectorTabs();
    setupViewToggles();

    // Load the initial charts for the active sector
    const activeTab = document.querySelector('.sector-button.active');
    if (activeTab) {
        loadSectorCharts(activeTab.dataset.sector);
    }
});

/**
 * Set up click handlers for sector tabs
 */
function setupSectorTabs() {
    const sectorButtons = document.querySelectorAll('.sector-button');

    sectorButtons.forEach(button => {
        button.addEventListener('click', function () {
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

                // Load charts for this sector
                loadSectorCharts(sectorId);
            }
        });
    });
}

/**
 * Set up click handlers for view toggles (table/chart/correlation)
 */
function setupViewToggles() {
    const viewButtons = document.querySelectorAll('.view-toggle-button');

    viewButtons.forEach(button => {
        button.addEventListener('click', function () {
            const sector = this.dataset.sector;
            const view = this.dataset.view;

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

                // If switching to a chart view, ensure charts are loaded
                if (view === 'chart' || view === 'correlation') {
                    loadSpecificChart(sector, view);
                }
            }
        });
    });
}

/**
 * Load all charts for a given sector
 */
function loadSectorCharts(sector) {
    // First check if the time series chart view is visible
    const chartView = document.getElementById(`${sector}-chart-view`);
    if (chartView && chartView.classList.contains('active')) {
        loadSpecificChart(sector, 'chart');
    }

    // Then check if correlation view is visible
    const correlationView = document.getElementById(`${sector}-correlation-view`);
    if (correlationView && correlationView.classList.contains('active')) {
        loadSpecificChart(sector, 'correlation');
    }
}

/**
 * Load a specific chart type for a sector
 */
function loadSpecificChart(sector, chartType) {
    if (chartType === 'chart') {
        // Show loading spinner
        const spinner = document.getElementById(`${sector}ChartSpinner`);
        const chartCanvas = document.getElementById(`${sector}Chart`);
        const errorElement = document.getElementById(`${sector}ChartError`);

        if (spinner) spinner.style.display = 'flex';
        if (chartCanvas) chartCanvas.style.display = 'none';
        if (errorElement) errorElement.style.display = 'none';

        // Fetch data from API
        fetch(`/api/chart_data/${sector}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    // Data received successfully
                    renderTimeSeriesChart(sector, data.data);
                } else {
                    // API returned an error
                    showChartError(sector, 'chart', data.message || 'Failed to load chart data');
                }
            })
            .catch(error => {
                showChartError(sector, 'chart', error.message || 'Error loading chart data');
            })
            .finally(() => {
                if (spinner) spinner.style.display = 'none';
            });
    }
    else if (chartType === 'correlation') {
        // Show loading spinner
        const spinner = document.getElementById(`${sector}CorrelationSpinner`);
        const chartDiv = document.getElementById(`${sector}CorrelationChart`);
        const errorElement = document.getElementById(`${sector}CorrelationError`);
        
        if (spinner) spinner.style.display = 'flex';
        if (chartDiv) chartDiv.style.display = 'none';
        if (errorElement) errorElement.style.display = 'none';
        
        console.log(`Loading correlation data for sector: ${sector}`);
        
        // Fetch data from API
        fetch(`/api/correlation_data/${sector}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Network response was not ok: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log(`Received correlation data:`, data);
                
                if (data.status === 'success' && data.data) {
                    // Data received successfully
                    renderCorrelationChart(sector, data.data);
                } else {
                    // API returned an error
                    showChartError(sector, 'correlation', data.message || 'Failed to load correlation data');
                }
            })
            .catch(error => {
                console.error(`Error fetching correlation data: ${error.message}`);
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
    const canvasElement = document.getElementById(`${sector}Chart`);
    if (!canvasElement) return;

    // Clear any existing chart
    if (canvasElement._chart) {
        canvasElement._chart.destroy();
    }

    // For aggregated view, we have multiple datasets
    if (sector === 'aggregated' && data.datasets) {
        const ctx = canvasElement.getContext('2d');

        const chartData = {
            labels: data.years,
            datasets: data.datasets
        };

        const options = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Electricity Consumption by Sector'
                },
                tooltip: {
                    enabled: true
                },
                legend: {
                    position: 'bottom'
                }
            },
            stacked: true,

            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Year',
                        stacked: true
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Electricity Consumption',
                        stacked: true
                    },
                    beginAtZero: true
                }
            }
        };

        canvasElement._chart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: options
        });

        canvasElement.style.display = 'block';
    }
    // For individual sectors, we have a single line series
    else if (data.years && data.electricity) {
        const ctx = canvasElement.getContext('2d');

        const chartData = {
            labels: data.years,
            datasets: [{
                label: 'Electricity Consumption',
                data: data.electricity,
                borderColor: 'rgb(59, 130, 246)', // Primary blue color
                backgroundColor: 'rgba(59, 130, 246, 0.5)',
                tension: 0.1
            }]
        };

        const options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: `${sector.charAt(0).toUpperCase() + sector.slice(1)} Sector Electricity Consumption`
                },
                tooltip: {
                    enabled: true
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Year'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Electricity Consumption'
                    },
                    beginAtZero: true
                }
            }
        };

        canvasElement._chart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: options
        });

        canvasElement.style.display = 'block';
    } else {
        showChartError(sector, 'chart', 'Unexpected data format received');
    }
}

/**
 * Render a correlation heatmap using Plotly
 */
function renderCorrelationChart(sector, data) {
    const chartElement = document.getElementById(`${sector}CorrelationChart`);
    if (!chartElement) {
        console.error(`Chart element not found: ${sector}CorrelationChart`);
        return;
    }
    
    console.log("Rendering correlation data:", data);
    
    // Check if we have valid correlation data
    if (!data || !data.variables || !data.correlations || data.variables.length === 0) {
        showChartError(sector, 'correlation', 'No correlation data available for Electricity');
        return;
    }
    
    try {
        // Clear any existing content
        chartElement.innerHTML = '';
        
        // Create a table for correlations
        const table = document.createElement('table');
        table.className = 'table table-striped table-hover';
        
        // Add header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        
        ['Variable', 'Correlation with Electricity', 'Strength'].forEach(text => {
            const th = document.createElement('th');
            th.textContent = text;
            headerRow.appendChild(th);
        });
        
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Add body
        const tbody = document.createElement('tbody');
        
        for (let i = 0; i < data.variables.length; i++) {
            const row = document.createElement('tr');
            
            // Variable cell
            const varCell = document.createElement('td');
            varCell.textContent = data.variables[i];
            row.appendChild(varCell);
            
            // Correlation value cell
            const valueCell = document.createElement('td');
            
            // Make sure we're accessing the value property correctly
            const corrValue = typeof data.correlations[i] === 'object' ? 
                              data.correlations[i].value : data.correlations[i];
            valueCell.textContent = corrValue;
            
            // Add styling based on correlation strength
            const absValue = Math.abs(corrValue);
            if (absValue >= 0.7) {
                valueCell.className = 'text-success fw-bold';
            } else if (absValue >= 0.4) {
                valueCell.className = 'text-primary';
            } else {
                valueCell.className = 'text-muted';
            }
            
            row.appendChild(valueCell);
            
            // Strength cell
            const strengthCell = document.createElement('td');
            const strength = typeof data.correlations[i] === 'object' ? 
                            data.correlations[i].strength : 
                            (absValue >= 0.7 ? "Strong" : absValue >= 0.4 ? "Moderate" : "Weak");
            strengthCell.textContent = strength;
            strengthCell.className = valueCell.className;
            row.appendChild(strengthCell);
            
            tbody.appendChild(row);
        }
        
        table.appendChild(tbody);
        chartElement.appendChild(table);
        chartElement.style.display = 'block';
    } catch (error) {
        console.error("Error rendering correlation chart:", error);
        showChartError(sector, 'correlation', `Error rendering correlation data: ${error.message}`);
    }
}
/**
 * Display an error message when chart loading fails
 */
function showChartError(sector, chartType, message) {
    let errorElement;

    if (chartType === 'chart') {
        errorElement = document.getElementById(`${sector}ChartError`);
    } else if (chartType === 'correlation') {
        errorElement = document.getElementById(`${sector}CorrelationError`);
    }

    if (errorElement) {
        errorElement.textContent = `Error: ${message}`;
        errorElement.style.display = 'block';
    }
}


// Forecast Model Configuration Handling
document.addEventListener('DOMContentLoaded', function () {
    // Initialize forecast related elements
    setupForecastButton();
    setupForecastModal();
});

/**
 * Set up click handler for the forecast button
 */
function setupForecastButton() {
    // Main "Run Forecast Model" button
    const runForecastBtn = document.querySelector('.run-forecast-btn');
    if (runForecastBtn) {
        runForecastBtn.addEventListener('click', function () {
            openForecastModal();
        });
    }
}

/**
 * Setup the forecast configuration modal controls
 */
function setupForecastModal() {
    // Default model checkboxes
    const defaultModelCheckboxes = document.querySelectorAll('.default-model-checkbox');
    defaultModelCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            // For now, we don't automatically sync with sector-specific checkboxes
            // as users might want different configurations for each sector
        });
    });

    // "Apply to All Sectors" button
    const applyToAllSectorsBtn = document.getElementById('applyToAllSectorsBtn');
    if (applyToAllSectorsBtn) {
        applyToAllSectorsBtn.addEventListener('click', function () {
            // Get all selected default models
            const selectedDefaultModels = [];
            document.querySelectorAll('.default-model-checkbox:checked').forEach(checkbox => {
                selectedDefaultModels.push(checkbox.value);
            });

            // Apply to all sector checkboxes
            document.querySelectorAll('.sector-config').forEach(sectorElement => {
                const sector = sectorElement.dataset.sector;

                // Update each model checkbox for this sector
                document.querySelectorAll(`input[name="forecastModel_${sector}"]`).forEach(modelCheckbox => {
                    // Check/uncheck based on whether it's in the selected default models
                    modelCheckbox.checked = selectedDefaultModels.includes(modelCheckbox.value);

                    // Show/hide the model config based on checkbox state
                    const modelType = modelCheckbox.value;
                    const configSection = document.getElementById(`${modelType.toLowerCase()}Config_${sector}`);
                    if (configSection) {
                        configSection.style.display = modelCheckbox.checked ? 'block' : 'none';
                    }
                });

                // Save these selections in localStorage
                localStorage.setItem(`forecast_models_${sector}`, JSON.stringify(selectedDefaultModels));
            });

            // Show confirmation
            showNotification('Default model selections applied to all sectors', 'success');
        });
    }

    // Sector-specific model checkboxes
    const sectorModelCheckboxes = document.querySelectorAll('.sector-model-checkbox');
    sectorModelCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            const sector = this.dataset.sector;
            const modelType = this.value;

            // Show/hide the model config based on checkbox state
            const configSection = document.getElementById(`${modelType.toLowerCase()}Config_${sector}`);
            if (configSection) {
                configSection.style.display = this.checked ? 'block' : 'none';
            }

            // Save current selections for this sector in localStorage
            const selectedModels = [];
            document.querySelectorAll(`input[name="forecastModel_${sector}"]:checked`).forEach(cb => {
                selectedModels.push(cb.value);
            });
            localStorage.setItem(`forecast_models_${sector}`, JSON.stringify(selectedModels));
        });
    });
    // WAM window size radios for each sector
    document.querySelectorAll('.sector-config').forEach(sectorElement => {
        const sector = sectorElement.dataset.sector;

        // Get window size radios for this sector
        const windowRadios = document.querySelectorAll(`input[name="windowSize_${sector}"]`);
        const customWindowContainer = document.getElementById(`customWindowContainer_${sector}`);

        windowRadios.forEach(radio => {
            radio.addEventListener('change', function () {
                if (this.value === 'custom' && this.checked) {
                    customWindowContainer.style.display = 'block';
                } else {
                    customWindowContainer.style.display = 'none';
                }
            });
        });
    });

    // Load independent variables for each sector
    document.querySelectorAll('.sector-config').forEach(sectorElement => {
        const sector = sectorElement.dataset.sector;
        loadIndependentVariables(sector);
    });

    // Run forecast button
    const runForecastBtn = document.getElementById('runForecastBtn');
    if (runForecastBtn) {
        runForecastBtn.addEventListener('click', startForecast);
    }

    // Cancel forecast button
    const cancelForecastBtn = document.getElementById('cancelForecastBtn');
    if (cancelForecastBtn) {
        cancelForecastBtn.addEventListener('click', cancelForecast);
    }

    // View results button
    const viewResultsBtn = document.getElementById('viewResultsBtn');
    if (viewResultsBtn) {
        viewResultsBtn.addEventListener('click', function (e) {
            e.preventDefault();
            window.location.href = '/demand_visualization';
        });
    }

    // Tab change event - load independent variables when tab becomes active
    const sectorTabs = document.querySelectorAll('button[data-bs-toggle="tab"]');
    sectorTabs.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function (e) {
            const sectorId = e.target.id.replace('-tab', '');
            if (sectorId !== 'all-sectors') {
                loadIndependentVariables(sectorId);
            }
        });
    });
}

/**
 * Open forecast modal and prepare it
 */
function openForecastModal() {
    // Initialize sector tabs
    document.querySelectorAll('.sector-config').forEach(sectorElement => {
        const sector = sectorElement.dataset.sector;

        // Check if we have a saved model preference
        const savedModel = localStorage.getItem(`forecast_model_${sector}`);
        if (savedModel) {
            // Select the saved model
            const modelRadio = document.querySelector(`#model${savedModel}_${sector}`);
            if (modelRadio) {
                modelRadio.checked = true;
                updateModelConfigVisibility(sector, savedModel);
            }
        } else {
            // Default to MLR
            const mlrRadio = document.querySelector(`#modelMLR_${sector}`);
            if (mlrRadio) {
                mlrRadio.checked = true;
                updateModelConfigVisibility(sector, 'MLR');
            }
        }
    });

    // Show the modal
    const forecastModal = new bootstrap.Modal(document.getElementById('forecastConfigModal'));
    forecastModal.show();
}

/**
 * Load independent variables for the selected sector
 */
function loadIndependentVariables(sector) {
    const container = document.getElementById(`independentVarsContainer_${sector}`);
    if (!container) return;

    // Check if we've already loaded variables
    if (container.dataset.loaded === 'true') {
        return;
    }

    // Show loading indicator
    container.innerHTML = `
        <div class="alert alert-warning">
            <i class="fas fa-spinner fa-spin me-2"></i>
            Loading available variables...
        </div>
    `;

    // Fetch data from API
    fetch(`/demand/api/independent_variables/${sector}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                renderIndependentVariables(container, data.variables, data.correlations);
                container.dataset.loaded = 'true';
            } else {
                container.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        ${data.message || 'Failed to load variables'}
                    </div>
                `;
            }
        })
        .catch(error => {
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error: ${error.message}
                </div>
            `;
        });
}

/**
 * Render independent variables checkboxes with correlation info
 */
function renderIndependentVariables(container, variables, correlations) {
    if (!variables || variables.length === 0) {
        container.innerHTML = `
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle me-2"></i>
                No independent variables available for this sector.
            </div>
        `;
        return;
    }

    let html = '<div class="row">';

    variables.forEach(variable => {
        if (variable === 'Year' || variable === 'Electricity') {
            return; // Skip Year and Electricity
        }

        const correlation = correlations[variable] || 0;
        const correlationAbs = Math.abs(correlation);
        let correlationClass = 'text-muted';
        let correlationText = 'Weak';

        if (correlationAbs >= 0.7) {
            correlationClass = 'text-success fw-bold';
            correlationText = 'Strong';
        } else if (correlationAbs >= 0.4) {
            correlationClass = 'text-primary';
            correlationText = 'Moderate';
        }

        html += `
            <div class="col-md-6 mb-2">
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="independentVars_${container.id.split('_')[1]}" 
                           id="var_${variable}_${container.id.split('_')[1]}" value="${variable}" 
                           ${correlationAbs >= 0.4 ? 'checked' : ''}>
                    <label class="form-check-label" for="var_${variable}_${container.id.split('_')[1]}">
                        ${variable}
                        <span class="ms-2 ${correlationClass}">
                            (${correlation.toFixed(2)}, ${correlationText})
                        </span>
                    </label>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

/**
 * Update which model configuration section is visible for a sector
 */
function updateModelConfigVisibility(sector, selectedModel) {
    const configSections = document.querySelectorAll(`#mlrConfig_${sector}, #slrConfig_${sector}, #wamConfig_${sector}, #tsConfig_${sector}`);

    configSections.forEach(section => {
        section.style.display = 'none';
    });

    // Show the selected model's config section
    document.getElementById(`${selectedModel.toLowerCase()}Config_${sector}`).style.display = 'block';
}

/**
 * Start the forecast process
 */
// Enhanced startForecast function with improved sector handling

function startForecast() {
    // Hide config modal
    const configModal = bootstrap.Modal.getInstance(document.getElementById('forecastConfigModal'));
    configModal.hide();

    // Get form data
    const form = document.getElementById('forecastConfigForm');
    const formData = new FormData(form);

    // Get general settings
    const targetYear = formData.get('targetYear');
    const scenarioName = formData.get('scenarioName');
    const excludeCovidYears = formData.get('excludeCovidYears') === 'on';

    // Prepare sector configurations
    const sectorConfigs = {};

    // Get all sector tabs and process each one
    document.querySelectorAll('.sector-config').forEach(sectorElement => {
        const sector = sectorElement.dataset.sector;
        console.log(`Processing config for sector: ${sector}`);
        
        // DEBUG: Log sector element details
        console.log(`Sector element:`, sectorElement);
        
        // Get all selected models for this sector
        const selectedModels = [];
        const modelCheckboxes = document.querySelectorAll(`input[name="forecastModel_${sector}"]:checked`);
        
        // DEBUG: Log how many checkboxes we found
        console.log(`Found ${modelCheckboxes.length} selected model checkboxes for ${sector}`);
        
        modelCheckboxes.forEach(checkbox => {
            selectedModels.push(checkbox.value);
            console.log(`  Selected model: ${checkbox.value}`);
        });

        // Skip if no models are selected
        if (selectedModels.length === 0) {
            console.log(`No models selected for ${sector}, skipping`);
            
            // DEBUG: Check if all checkbox elements exist
            const allCheckboxes = document.querySelectorAll(`input[name="forecastModel_${sector}"]`);
            console.log(`All checkboxes for ${sector}:`, allCheckboxes);
            
            return;
        }

        const sectorConfig = {
            models: selectedModels,
        };

        // Add model-specific parameters
        // MLR parameters
        if (selectedModels.includes('MLR')) {
            const independentVars = [];
            const checkboxes = document.querySelectorAll(`input[name="independentVars_${sector}"]:checked`);
            console.log(`Found ${checkboxes.length} independent variables for ${sector}`);
            
            checkboxes.forEach(checkbox => {
                independentVars.push(checkbox.value);
                console.log(`  Selected var: ${checkbox.value}`);
            });
            sectorConfig.independentVars = independentVars;
        }

        // WAM parameters
        if (selectedModels.includes('WAM')) {
            const wamRadio = document.querySelector(`input[name="windowSize_${sector}"]:checked`);
            if (wamRadio) {
                let windowSize = wamRadio.value;
                console.log(`  WAM window size type: ${windowSize}`);
                
                if (windowSize === 'custom') {
                    windowSize = document.getElementById(`customWindowSize_${sector}`).value;
                    console.log(`  Custom window size: ${windowSize}`);
                }
                sectorConfig.windowSize = parseInt(windowSize) || 10;
            } else {
                console.log(`  No window size radio selected, using default`);
                sectorConfig.windowSize = 10; // Default window size
            }
        }

        // Add this sector to the config
        sectorConfigs[sector] = sectorConfig;
        console.log(`Added sector ${sector} to config:`, sectorConfig);
    });

    console.log("Final sector configs:", sectorConfigs);

    // Check if we have any valid sector configurations
    if (Object.keys(sectorConfigs).length === 0) {
        showNotification('Please select at least one model for at least one sector.', 'warning');
        return;
    }

    // Prepare the complete request data
    const requestData = {
        scenarioName: scenarioName,
        targetYear: parseInt(targetYear),
        excludeCovidYears: excludeCovidYears,
        sectorConfigs: sectorConfigs
    };

    console.log("Final request data:", requestData);

    // Update progress modal with initial sector
    const firstSector = Object.keys(sectorConfigs)[0];
    document.getElementById('progressSectorName').textContent = 
        firstSector.charAt(0).toUpperCase() + firstSector.slice(1);

    // Update forecast progress bar
    const progressBar = document.getElementById('forecastProgressBar');
    progressBar.style.width = '5%';
    progressBar.setAttribute('aria-valuenow', 5);
    progressBar.textContent = '5%';

    // Show progress modal
    const progressModal = new bootstrap.Modal(document.getElementById('forecastProgressModal'));
    progressModal.show();

    // Send the forecast request
    sendForecastRequest(requestData);
}

/**
 * Send forecast request to the API
 */
function sendForecastRequest(requestData) {
    // Keep track of the forecast job
    let forecastJobId = null;
    let progressInterval = null;

    // Set up progress monitoring
    const updateProgress = () => {
        if (!forecastJobId) return;

        fetch(`/api/forecast_status/${forecastJobId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'running') {
                    updateProgressBar(data.progress);
                    if (data.currentSector) {
                        document.getElementById('progressSectorName').textContent =
                            data.currentSector.charAt(0).toUpperCase() + data.currentSector.slice(1);
                    }
                } else if (data.status === 'completed') {
                    clearInterval(progressInterval);
                    updateProgressBar(100);
                    setTimeout(() => {
                        showForecastCompleteModal(data.result);
                    }, 1000);
                } else if (data.status === 'failed') {
                    clearInterval(progressInterval);
                    showForecastError(data.error);
                }
            })
            .catch(error => {
                console.error('Error checking forecast status:', error);
            });
    };

    // Send the forecast request
    fetch('/demand/api/run_forecast', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'started') {
                forecastJobId = data.jobId;

                // Save the job ID in the modal for cancellation
                document.getElementById('forecastProgressModal').dataset.jobId = forecastJobId;

                // Start progress monitoring
                progressInterval = setInterval(updateProgress, 2000);

                // Initial progress update
                updateProgress();
            } else {
                showForecastError(data.message || 'Failed to start forecast job');
            }
        })
        .catch(error => {
            showForecastError(error.message || 'Error starting forecast');
        });
}

/**
 * Cancel the current forecast job
 */
function cancelForecast() {
    // Confirmation dialog
    if (!confirm('Are you sure you want to cancel the forecast? All progress will be lost.')) {
        return;
    }

    // Get the job ID from the modal
    const jobId = document.getElementById('forecastProgressModal').dataset.jobId;
    if (!jobId) {
        // No job ID, just hide the modal
        const progressModal = bootstrap.Modal.getInstance(document.getElementById('forecastProgressModal'));
        progressModal.hide();
        return;
    }

    // Cancel the job on the server
    fetch(`/api/cancel_forecast/${jobId}`, {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            // Hide progress modal
            const progressModal = bootstrap.Modal.getInstance(document.getElementById('forecastProgressModal'));
            progressModal.hide();

            if (data.status === 'cancelled') {
                showNotification('Forecast cancelled successfully', 'warning');
            } else {
                showNotification('Could not cancel forecast: ' + (data.message || 'Unknown error'), 'danger');
            }
        })
        .catch(error => {
            console.error('Error cancelling forecast:', error);

            // Hide progress modal even if there's an error
            const progressModal = bootstrap.Modal.getInstance(document.getElementById('forecastProgressModal'));
            if (progressModal) {
                progressModal.hide();
            }

            showNotification('Error cancelling forecast: ' + error.message, 'danger');
        });
}

/**
 * Update the forecast progress bar
 */
function updateProgressBar(progress) {
    const progressBar = document.getElementById('forecastProgressBar');
    progressBar.style.width = `${progress}%`;
    progressBar.setAttribute('aria-valuenow', progress);
    progressBar.textContent = `${progress}%`;
}

/**
 * Show the forecast complete modal with results
 */
function showForecastCompleteModal(result) {
    // Hide progress modal
    const progressModal = bootstrap.Modal.getInstance(document.getElementById('forecastProgressModal'));
    progressModal.hide();

    // Fill in complete modal details
    document.getElementById('summaryTotalSectors').textContent = result.totalSectors || 0;
    document.getElementById('summaryScenario').textContent = result.scenarioName || 'Base Scenario';
    document.getElementById('summaryTargetYear').textContent = result.targetYear || 2037;
    document.getElementById('summaryFilePath').textContent = result.filePath || 'results/demand_projection/';

    // Configure the View Results button to go to the results page
    const viewResultsBtn = document.getElementById('viewResultsBtn');
    viewResultsBtn.href = `/demand_visualization?scenario=${encodeURIComponent(result.scenarioName || 'Base Scenario')}`;

    // Show complete modal
    const completeModal = new bootstrap.Modal(document.getElementById('forecastCompleteModal'));
    completeModal.show();
}

/**
 * Show forecast error notification
 */
function showForecastError(errorMessage) {
    // Hide progress modal
    const progressModal = bootstrap.Modal.getInstance(document.getElementById('forecastProgressModal'));
    if (progressModal) {
        progressModal.hide();
    }

    // Show error notification
    showNotification(`Forecast Error: ${errorMessage}`, 'danger');
}

/**
 * Show a notification to the user
 */
function showNotification(message, type = 'info') {
    // Use the global alert function if available
    if (typeof showGlobalAlert === 'function') {
        try {
            showGlobalAlert(message, type);
        } catch (error) {
            // Fallback if the global alert function fails
            console.warn('Error showing notification:', error);
            alert(message); // Simple fallback
        }
    } else {
        // Create a simple Bootstrap alert if showGlobalAlert is not available
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        document.body.appendChild(alertDiv);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alertDiv.classList.remove('show');
            setTimeout(() => alertDiv.remove(), 300);
        }, 5000);
    }
}