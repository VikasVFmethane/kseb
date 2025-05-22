

document.addEventListener('DOMContentLoaded', function() {
    // Current state
    const state = {
        currentNetworkPath: null,
        isMultiPeriod: false,
        currentPeriod: null, 
        periods: [],         
        networkInfo: {},
        startDate: null,
        endDate: null,
        resolution: '1H',
        dispatchData: null,
        capacityData: null,
        metricsData: null,
        storageData: null,
        emissionsData: null,
        pricesData: null,
        networkFlowData: null,
        colorPalette: {}, 
        extractedNetworkPath: null,
        allNcFiles: [] 
    };

    // Initialize UI elements
    const scenarioSelect = document.getElementById('scenarioSelect');
    const networkFileSelect = document.getElementById('networkFileSelect');
    const networkInfoContainer = document.getElementById('networkInfoContainer');
    const networkUploadForm = document.getElementById('networkUploadForm');
    const analysisDashboard = document.getElementById('analysisDashboard');
    const periodControlContainer = document.getElementById('periodControlContainer');
    const periodSelect = document.getElementById('periodSelect');
    const extractPeriodBtn = document.getElementById('extractPeriodBtn');
    const dateFilterContainer = document.getElementById('dateFilterContainer');
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    const resolutionSelectEl = document.getElementById('resolutionSelect'); 
    const applyFilterBtn = document.getElementById('applyFilterBtn');
    const backToSelectionBtn = document.getElementById('backToSelectionBtn');

    const initialNcFilesOptions = Array.from(document.querySelectorAll('#networkFileSelect option'));
    if (initialNcFilesOptions.length > 1) { 
        state.allNcFiles = initialNcFilesOptions
            .filter(opt => opt.value)
            .map(opt => ({
                path: opt.value,
                filename: opt.textContent,
                scenario: opt.dataset.scenario
            }));
    }
    
    // =====================
    // Event Listeners
    // =====================
    
    scenarioSelect.addEventListener('change', function() {
        const selectedScenario = this.value;
        networkFileSelect.innerHTML = '<option value="">Select a network file...</option>';
        if (selectedScenario) {
            networkFileSelect.disabled = false;
            populateNetworkFiles(selectedScenario);
        } else {
            networkFileSelect.disabled = true;
        }
        networkInfoContainer.style.display = 'none';
    });
    
    networkFileSelect.addEventListener('change', function() {
        const selectedNetworkPath = this.value;
        if (selectedNetworkPath) {
            fetchNetworkInfo(selectedNetworkPath);
        } else {
            networkInfoContainer.style.display = 'none';
        }
    });
    
    networkUploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        const uploadBtn = document.getElementById('uploadBtn');
        const originalBtnText = uploadBtn.innerHTML;
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Uploading...';
        
        fetch('/api/pypsa/upload_network', { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = originalBtnText;
                if (data.status === 'success') {
                    showGlobalAlert(`Network file uploaded to scenario "${formData.get('scenario')}"!`, 'success');
                    refreshNetworkFiles(); 
                    networkUploadForm.reset();
                } else {
                    showGlobalAlert(`Error: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = originalBtnText;
                showGlobalAlert(`Upload Error: ${error.message}`, 'danger');
            });
    });
        
    backToSelectionBtn.addEventListener('click', function() {
        analysisDashboard.style.display = 'none';
        document.getElementById('networkSelectionSection').style.display = 'block';
        document.getElementById('networkComparisonSection').style.display = 'none';
        state.currentNetworkPath = null; 
        state.networkInfo = {};
    });
    
    extractPeriodBtn.addEventListener('click', function() {
        if (state.currentNetworkPath && state.isMultiPeriod && state.currentPeriod) {
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Extracting...';
            extractPeriod(state.currentNetworkPath, state.currentPeriod);
        }
    });
    
    applyFilterBtn.addEventListener('click', function() {
        const startDateVal = startDateInput.value ? new Date(startDateInput.value) : null;
        const endDateVal = endDateInput.value ? new Date(endDateInput.value) : null;
        const resolutionVal = resolutionSelectEl.value;
        
        if (startDateVal && endDateVal && startDateVal > endDateVal) {
            showGlobalAlert('Start date must be before end date.', 'warning');
            return;
        }
        
        state.startDate = startDateVal ? startDateVal.toISOString().split('T')[0] : null;
        state.endDate = endDateVal ? endDateVal.toISOString().split('T')[0] : null;
        state.resolution = resolutionVal;
        
        this.disabled = true;
        this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Applying...';
        
        showLoadingIndicators(['dispatchStackPlot', 'dailyProfilePlot', 'loadDurationPlot', 'avgPriceByBusPlot', 'priceDurationPlot']);

        Promise.all([
            fetchDispatchData(state.currentNetworkPath), 
            fetchPricesData(state.currentNetworkPath)    
        ])
        .then(() => {
            updateDispatchTab(); 
            updatePricesTab();   
            showGlobalAlert('Filters applied successfully.', 'success');
        })
        .catch(error => {
            showGlobalAlert(`Error applying filters: ${error.message}`, 'danger');
        })
        .finally(() => {
            this.disabled = false;
            this.innerHTML = '<i class="fas fa-filter me-1"></i> Apply Filter';
            hideLoadingIndicators(['dispatchStackPlot', 'dailyProfilePlot', 'loadDurationPlot', 'avgPriceByBusPlot', 'priceDurationPlot']);
        });
    });
    
    periodSelect.addEventListener('change', function() {
        state.currentPeriod = this.value;
        showLoadingIndicatorsForDashboard();
        reloadAllData(state.currentNetworkPath, state.networkInfo)
         .catch(error => {
            showGlobalAlert(`Error reloading data for period ${state.currentPeriod}: ${error.message}`, 'danger');
        })
        .finally(() => {
            hideLoadingIndicatorsForDashboard();
        });
    });
    
    document.getElementById('capacityAttributeSelect').addEventListener('change', function() {
        showLoadingIndicators(['capacityByCarrierPlot', 'capacityByRegionPlot']);
        fetchCapacityData(state.currentNetworkPath, this.value)
            .then(updateCapacityTab)
            .catch(error => showGlobalAlert(`Error fetching capacity data: ${error.message}`, 'danger'))
            .finally(() => hideLoadingIndicators(['capacityByCarrierPlot', 'capacityByRegionPlot']));
    });
    
    document.getElementById('loadExtractedPeriodBtn').addEventListener('click', function() {
        const modalEl = document.getElementById('periodExtractionModal');
        const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
        modal.hide();
        
        if (state.extractedNetworkPath) {
            fetchNetworkInfo(state.extractedNetworkPath, true); 
        }
    });
    
    initializeComparison();
    
    const analysisTabs = document.querySelectorAll('#analysisTabs .nav-link');
    analysisTabs.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(e) {
            const targetPaneId = e.target.getAttribute('data-bs-target');
            if (targetPaneId) {
                const plotContainers = document.querySelector(targetPaneId).querySelectorAll('.plot-container > div:not(.loading-indicator)');
                plotContainers.forEach(pc => {
                    if (pc.id && typeof Plotly !== 'undefined' && pc.data) { 
                         setTimeout(() => Plotly.Plots.resize(pc.id), 50);
                    }
                });
            }
            setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
        });
    });

    document.querySelectorAll('.download-btn').forEach(button => {
        button.addEventListener('click', function() {
            const chartId = this.dataset.chart;
            const plotContainerId = getPlotContainerIdForChart(chartId); 
            if (plotContainerId) {
                const plotEl = document.getElementById(plotContainerId);
                if (plotEl && typeof Plotly !== 'undefined' && plotEl.data) { 
                    Plotly.downloadImage(plotEl, {format: 'png', filename: chartId});
                } else {
                    showGlobalAlert(`Chart '${chartId}' (plot ID '${plotContainerId}') not found or not ready for download.`, 'warning');
                }
            } else {
                 showGlobalAlert(`No plot container defined for chart ID '${chartId}'.`, 'warning');
            }
        });
    });
    
    // =====================
    // Helper Functions
    // =====================

    function getPlotContainerIdForChart(chartId) {
        const map = { 
            'dispatchStack': 'dispatchStackPlot',
            'dailyProfile': 'dailyProfilePlot',
            'loadDuration': 'loadDurationPlot',
            'capacityByCarrier': 'capacityByCarrierPlot',
            'capacityByRegion': 'capacityByRegionPlot',
            'cufPlot': 'cufPlot',
            'curtailmentPlot': 'curtailmentPlot',
            'socPlot': 'socPlot',
            'storageUtilizationPlot': 'storageUtilizationPlot',
            'emissionsByCarrier': 'emissionsByCarrierPlot',
            'avgPriceByBus': 'avgPriceByBusPlot',
            'priceDuration': 'priceDurationPlot',
            'lineLoading': 'lineLoadingPlot',
        };
        return map[chartId];
    }

    function showLoadingIndicators(plotIds) {
        plotIds.forEach(id => {
            const plotContainer = document.getElementById(id);
            if (plotContainer) {
                plotContainer.innerHTML = '<div class="loading-indicator" style="display: flex;"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
            }
        });
    }
    function hideLoadingIndicators(plotIds) {
         plotIds.forEach(id => {
            const plotContainer = document.getElementById(id);
            if (plotContainer) {
                const loader = plotContainer.querySelector('.loading-indicator');
                if(loader) loader.style.display = 'none';
            }
        });
    }
    function showLoadingIndicatorsForDashboard() {
        document.querySelectorAll('.plot-container').forEach(pc => {
            pc.innerHTML = '<div class="loading-indicator" style="display: flex;"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
        });
        document.querySelectorAll('.stats-value').forEach(el => el.textContent = '-');
        document.querySelectorAll('.table-responsive tbody').forEach(el => el.innerHTML = '<tr><td colspan="100%" class="text-center">Loading...</td></tr>');
    }
    function hideLoadingIndicatorsForDashboard() {
         document.querySelectorAll('.plot-container .loading-indicator').forEach(el => {
            if (el.parentElement.childElementCount === 1) { // Only hide if it's the only thing there
                 el.style.display = 'none';
            }
         });
    }

    function populateNetworkFiles(scenario) {
        const filesForScenario = state.allNcFiles.filter(file => file.scenario === scenario);
        networkFileSelect.innerHTML = '<option value="">Select a network file...</option>'; 
        filesForScenario.forEach(file => {
            const option = document.createElement('option');
            option.value = file.path;
            option.textContent = file.filename;
            option.dataset.scenario = file.scenario;
            networkFileSelect.appendChild(option);
        });
    }
    
    function fetchNetworkInfo(networkPath, autoLoadAfterFetch = false) {
        networkInfoContainer.style.display = 'block';
        networkInfoContainer.innerHTML = `<div class="card"><div class="card-body text-center py-4"><i class="fas fa-spinner fa-spin me-2"></i> Loading network information...</div></div>`;
        
        fetch(`/api/pypsa/network_info/${networkPath}`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    networkInfoContainer.innerHTML = `
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="mb-0">Network Information</h5>
                                <button type="button" class="btn btn-sm btn-primary" id="loadNetworkBtnInner">
                                    <i class="fas fa-chart-line me-1"></i> Load Network for Analysis
                                </button>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <p><strong>Name:</strong> <span id="networkNameInner"></span></p>
                                        <p><strong>Components:</strong> <span id="networkComponentsInner"></span></p>
                                        <p><strong>Carriers:</strong> <span id="networkCarriersInner"></span></p>
                                    </div>
                                    <div class="col-md-6">
                                        <p><strong>Snapshots:</strong> <span id="networkSnapshotsInner"></span></p>
                                        <p><strong>Period Type:</strong> <span id="networkPeriodTypeInner"></span></p>
                                        <p><strong>Optimization Status:</strong> <span id="networkOptStatusInner"></span></p>
                                    </div>
                                </div>
                            </div>
                        </div>`;
                    
                    document.getElementById('loadNetworkBtnInner').addEventListener('click', function() {
                        this.disabled = true;
                        this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Loading...';
                        loadNetworkForAnalysis(networkPath, data.network_info);
                    });

                    displayNetworkInfo(data.network_info, 'Inner');
                    state.networkInfo = data.network_info;

                    if (autoLoadAfterFetch) {
                        const btn = document.getElementById('loadNetworkBtnInner');
                        if(btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Loading...';}
                        loadNetworkForAnalysis(networkPath, data.network_info);
                    }
                } else {
                    networkInfoContainer.innerHTML = `<div class="alert alert-danger">Error: ${data.message}</div>`;
                }
            })
            .catch(error => {
                console.error("Error fetching network info:", error);
                networkInfoContainer.innerHTML = `<div class="alert alert-danger">Error fetching network info: ${error.message}</div>`;
            });
    }
    
    function displayNetworkInfo(info, suffix = '') {
        document.getElementById('networkName' + suffix).textContent = info.name || 'N/A';
        const componentsText = info.components && Object.keys(info.components).length > 0 
            ? Object.entries(info.components).map(([comp, count]) => `${comp}: ${count}`).join(', ') 
            : 'N/A';
        document.getElementById('networkComponents' + suffix).textContent = componentsText;
        document.getElementById('networkCarriers' + suffix).textContent = (info.carriers && info.carriers.length > 0) ? info.carriers.join(', ') : 'N/A';

        const snapshots = info.snapshots || {};
        document.getElementById('networkSnapshots' + suffix).textContent = snapshots.count ? `${snapshots.count} (From: ${snapshots.start || 'N/A'} To: ${snapshots.end || 'N/A'})` : 'N/A';
        document.getElementById('networkPeriodType' + suffix).textContent = snapshots.is_multi_period ? 'Multi-period' : 'Single period';
        document.getElementById('networkOptStatus' + suffix).textContent = info.optimization_status || 'N/A';
    }
    
    function refreshNetworkFiles() {
        scenarioSelect.disabled = true;
        networkFileSelect.disabled = true;
        
        fetch('/api/pypsa/scan_files')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    state.allNcFiles = data.files; 
                    updateScenariosDropdown(data.scenarios);
                    
                    scenarioSelect.disabled = false;
                    const currentScenarioVal = scenarioSelect.value; 
                    if (currentScenarioVal) {
                        populateNetworkFiles(currentScenarioVal);
                        networkFileSelect.disabled = false;
                    } else {
                        networkFileSelect.disabled = true;
                        networkFileSelect.innerHTML = '<option value="">Select a network file...</option>';
                    }
                    if (document.getElementById('networkComparisonSection').style.display === 'block') {
                        loadNetworksForComparison();
                    }
                } else {
                    showGlobalAlert(`Error refreshing files: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                showGlobalAlert(`Error refreshing files: ${error.message}`, 'danger');
            });
    }
    
    function updateScenariosDropdown(scenarios) {
        const currentScenario = scenarioSelect.value;
        scenarioSelect.innerHTML = '<option value="">Select a scenario...</option>';
        scenarios.forEach(scenario => {
            const option = document.createElement('option');
            option.value = scenario;
            option.textContent = scenario;
            scenarioSelect.appendChild(option);
        });
        if (currentScenario && scenarios.includes(currentScenario)) {
            scenarioSelect.value = currentScenario;
        } else {
             scenarioSelect.value = ""; 
        }
    }
        
    function loadNetworkForAnalysis(networkPath, networkInfoFull) {
        state.currentNetworkPath = networkPath;
        state.networkInfo = networkInfoFull; 

        document.getElementById('currentNetworkName').textContent = networkInfoFull.name;
        analysisDashboard.style.display = 'block';
        document.getElementById('networkSelectionSection').style.display = 'none';
        document.getElementById('networkComparisonSection').style.display = 'none';

        const loadBtnInner = document.getElementById('loadNetworkBtnInner');
        if (loadBtnInner) { 
            loadBtnInner.disabled = false;
            loadBtnInner.innerHTML = '<i class="fas fa-chart-line me-1"></i> Load Network for Analysis';
        }
        
        setupPeriodControls(networkInfoFull);
        setupDateFilter(networkInfoFull); 
        
        showLoadingIndicatorsForDashboard();
        reloadAllData(networkPath, networkInfoFull)
            .then(() => {
                showGlobalAlert('Network loaded successfully.', 'success');
            })
            .catch(error => {
                showGlobalAlert(`Error loading network data: ${error.message}`, 'danger');
            })
            .finally(() => {
                 hideLoadingIndicatorsForDashboard();
            });
    }
    
    function setupPeriodControls(networkInfoFull) {
        state.isMultiPeriod = networkInfoFull.snapshots.is_multi_period;
        state.periods = networkInfoFull.periods || [];
        
        if (state.isMultiPeriod && state.periods.length > 0) {
            periodControlContainer.style.display = 'flex'; // Use flex for better alignment
            periodSelect.innerHTML = '';
            state.periods.forEach(periodVal => { 
                const option = document.createElement('option');
                option.value = periodVal;
                option.textContent = `Period ${periodVal}`;
                periodSelect.appendChild(option);
            });
            state.currentPeriod = state.periods[0]; 
            periodSelect.value = state.currentPeriod;
            extractPeriodBtn.style.display = 'inline-block';
        } else {
            periodControlContainer.style.display = 'none';
            state.currentPeriod = null; 
            extractPeriodBtn.style.display = 'none';
        }
    }
    
    function setupDateFilter(networkInfoFull) {
        const snapshotsInfo = networkInfoFull.snapshots;
        if (snapshotsInfo && snapshotsInfo.start && snapshotsInfo.end && 
            (String(snapshotsInfo.start).includes('T') || String(snapshotsInfo.start).includes(' ') || String(snapshotsInfo.start).match(/^\d{4}-\d{2}-\d{2}$/))) {
            
            dateFilterContainer.style.display = 'flex'; 

            const startDateStr = String(snapshotsInfo.start).split(/[T ]/)[0];
            const endDateStr = String(snapshotsInfo.end).split(/[T ]/)[0];
            
            startDateInput.min = startDateStr;
            startDateInput.max = endDateStr;
            endDateInput.min = startDateStr;
            endDateInput.max = endDateStr;
            
            startDateInput.value = startDateStr;
            endDateInput.value = endDateStr;
            state.startDate = startDateStr;
            state.endDate = endDateStr;
        } else {
            dateFilterContainer.style.display = 'none';
            state.startDate = null;
            state.endDate = null;
        }
        resolutionSelectEl.value = '1H'; 
        state.resolution = '1H';
    }
    
    function extractPeriod(networkPath, periodToExtract) {
        fetch(`/api/pypsa/extract_period/${networkPath}/${periodToExtract}`)
            .then(response => response.json())
            .then(data => {
                extractPeriodBtn.disabled = false;
                extractPeriodBtn.innerHTML = '<i class="fas fa-file-export me-1"></i> Extract Period';
                if (data.status === 'success') {
                    state.extractedNetworkPath = data.file_info.path;
                    document.getElementById('extractedPeriodFilePath').textContent = data.file_info.filename;
                    const modalEl = document.getElementById('periodExtractionModal');
                    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                    modal.show();
                    refreshNetworkFiles(); 
                } else {
                    showGlobalAlert(`Error extracting period: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                extractPeriodBtn.disabled = false;
                extractPeriodBtn.innerHTML = '<i class="fas fa-file-export me-1"></i> Extract Period';
                showGlobalAlert(`Error extracting period: ${error.message}`, 'danger');
            });
    }
    
    async function reloadAllData(networkPath) { 
        try {
            state.dispatchData = null; state.capacityData = null; state.metricsData = null;
            state.storageData = null; state.emissionsData = null; state.pricesData = null;
            state.networkFlowData = null; 
            // Color palette might be updated by individual fetches if the API returns it
            // Or, have a separate call to fetch a "master" palette for the network if that's how it's designed.
            // For now, let's assume individual API calls might return and merge colors.

            await Promise.all([
                fetchDispatchData(networkPath),
                fetchCapacityData(networkPath, document.getElementById('capacityAttributeSelect').value),
                fetchMetricsData(networkPath),
                fetchStorageData(networkPath),
                fetchEmissionsData(networkPath),
                fetchPricesData(networkPath),
                fetchNetworkFlowData(networkPath)
            ]);
            
            updateAllTabs(); 
            return true;
        } catch (error) {
            console.error("Error in reloadAllData:", error);
            showGlobalAlert(`Error loading data: ${error.message}`, 'danger');
            throw error; 
        }
    }

    function updateAllTabs() {
        updateDispatchTab();
        updateCapacityTab();
        updateMetricsTab();
        updateStorageTab();
        updateEmissionsTab();
        updatePricesTab();
        updateNetworkFlowTab();
    }

    function buildApiUrl(basePath, queryParams = {}) {
        let url = basePath;
        const params = new URLSearchParams();

        if (state.currentPeriod) { // For multi-period networks
            params.append('period', state.currentPeriod);
        }
        
        // Add date and resolution filters if they are relevant (e.g., for dispatch, prices)
        // The calling function should decide which params are relevant.
        // Example: if 'start_date' is in queryParams and state.startDate is set:
        if (queryParams.hasOwnProperty('start_date') && state.startDate) {
            params.append('start_date', state.startDate);
        }
        if (queryParams.hasOwnProperty('end_date') && state.endDate) {
            params.append('end_date', state.endDate);
        }
        if (queryParams.hasOwnProperty('resolution') && state.resolution) {
            params.append('resolution', state.resolution);
        }

        // Add other specific query params passed to the function
        for (const key in queryParams) {
            // Avoid re-adding already handled params if they were just markers
            if (key === 'start_date' || key === 'end_date' || key === 'resolution') continue;
            
            if (queryParams[key] !== null && queryParams[key] !== undefined && String(queryParams[key]).trim() !== "") {
                params.append(key, queryParams[key]);
            }
        }
        
        const queryString = params.toString();
        if (queryString) {
            url += `?${queryString}`;
        }
        console.log("Built API URL:", url); 
        return url;
    }
    
    async function fetchData(endpoint, processDataCallback) {
        try {
            const response = await fetch(endpoint);
            if (!response.ok) { 
                 const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
                 throw new Error(errorData.details || errorData.message || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            if (data.status === 'success') {
                if (data.colors) { 
                    Object.assign(state.colorPalette, data.colors);
                }
                processDataCallback(data); 
                return data; 
            } else {
                throw new Error(data.details || data.message || 'API returned non-success status without a message.');
            }
        } catch (error) {
            console.error(`Error fetching ${endpoint}:`, error);
            throw error; 
        }
    }

    // --- Specific data fetching functions ---
    async function fetchDispatchData(networkPath) {
        // Dispatch is affected by date and resolution
        const queryParams = { 
            start_date: state.startDate, // Pass these keys to indicate they are relevant
            end_date: state.endDate,
            resolution: state.resolution 
        };
        const url = buildApiUrl(`/api/pypsa/dispatch_data/${networkPath}`, queryParams);
        return fetchData(url, (data) => {
            state.dispatchData = data.dispatch_data_data; // API wrapper uses a nested key
            if (data.colors) Object.assign(state.colorPalette, data.colors);
        });
    }

    async function fetchCapacityData(networkPath, attribute = 'p_nom_opt') {
        // Capacity is typically for a period, not sliced by sub-period dates or resolution.
        // 'period' will be added by buildApiUrl if state.currentPeriod is set.
        const url = buildApiUrl(`/api/pypsa/capacity_data/${networkPath}`, { attribute });
        return fetchData(url, (data) => {
            state.capacityData = data.carrier_capacity_data; // API wrapper uses a nested key
            if (data.colors) Object.assign(state.colorPalette, data.colors);
        });
    }

    async function fetchMetricsData(networkPath) {
        // Metrics like CUF and Curtailment are usually for the selected period.
        // Date/resolution filters from the main bar might not apply directly here,
        // or the backend needs to know how to interpret them for these metrics.
        // For now, assume they apply to the whole 'currentPeriod'.
        const queryParams = { 
            start_date: state.startDate, // Pass them, backend can decide to use or ignore
            end_date: state.endDate,
        };
        const url = buildApiUrl(`/api/pypsa/metrics_data/${networkPath}`, queryParams);
        return fetchData(url, (data) => {
            state.metricsData = data.combined_metrics_extractor_data; // API wrapper uses a nested key
            if (data.colors) Object.assign(state.colorPalette, data.colors);
        });
    }

    async function fetchStorageData(networkPath) {
        // Storage SoC is time-series, so date/resolution might apply.
        const queryParams = { 
            start_date: state.startDate,
            end_date: state.endDate,
            resolution: state.resolution 
        };
        const url = buildApiUrl(`/api/pypsa/storage_data/${networkPath}`, queryParams);
        return fetchData(url, (data) => {
            state.storageData = data.extract_api_storage_data_data; // API wrapper uses a nested key
            if (data.colors) Object.assign(state.colorPalette, data.colors);
        });
    }

    async function fetchEmissionsData(networkPath) {
        // Emissions are typically for the whole period.
        const url = buildApiUrl(`/api/pypsa/emissions_data/${networkPath}`);
        return fetchData(url, (data) => {
            state.emissionsData = data.emissions_data; // API wrapper uses a nested key
            if (data.colors) Object.assign(state.colorPalette, data.colors);
        });
    }

    async function fetchPricesData(networkPath) {
        // Prices are time-series and can be resampled. Date filters also apply.
        const queryParams = { 
            start_date: state.startDate,
            end_date: state.endDate,
            resolution: state.resolution 
        };
        const url = buildApiUrl(`/api/pypsa/prices_data/${networkPath}`, queryParams);
        return fetchData(url, (data) => {
            state.pricesData = data.extract_api_prices_data_data; // API wrapper uses a nested key
             // Prices API does not typically return a 'colors' field specific to prices themselves
        });
    }

    async function fetchNetworkFlowData(networkPath) {
        // Network flow (losses, line loading) might be for the whole period.
        // Or, if time-series of line flows are analyzed, then date/resolution could apply.
        // Assuming backend provides aggregated results for the period for now.
        const queryParams = { 
            start_date: state.startDate, // Pass for backend to decide
            end_date: state.endDate,
        };
        const url = buildApiUrl(`/api/pypsa/network_flow/${networkPath}`, queryParams);
        return fetchData(url, (data) => {
            state.networkFlowData = data.extract_api_network_flow_data; // API wrapper uses a nested key
        });
    }


    // =====================
    // Update Tab Functions
    // =====================
    
    function updateDispatchTab() {
        const plotContainer = document.getElementById('dispatchStackPlot');
        hideLoadingIndicators(['dispatchStackPlot', 'dailyProfilePlot', 'loadDurationPlot']); // Hide before checking data

        if (!state.dispatchData || !state.dispatchData.timestamps || state.dispatchData.timestamps.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No dispatch data available for selected criteria.</div>';
            clearPlot('dailyProfilePlot');
            clearPlot('loadDurationPlot');
            clearTable('generationSummaryTable');
            document.getElementById('totalLoadValue').textContent = '-';
            document.getElementById('peakLoadValue').textContent = '-';
            document.getElementById('minLoadValue').textContent = '-';
            return;
        }
        
        createDispatchStackPlot();
        createDailyProfilePlot();
        createLoadDurationCurve();
        updateGenerationSummaryTable();
        updateLoadStatistics();
    }
    
    function updateCapacityTab() {
        const plotContainer = document.getElementById('capacityByCarrierPlot');
        hideLoadingIndicators(['capacityByCarrierPlot', 'capacityByRegionPlot']);

        if (!state.capacityData || (!state.capacityData.by_carrier || state.capacityData.by_carrier.length === 0)) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No capacity data available.</div>';
            clearPlot('capacityByRegionPlot');
            clearTable('capacityTable');
            return;
        }
        
        createCapacityByCarrierPlot();
        createCapacityByRegionPlot();
        updateCapacityTable();
    }
    
    function updateMetricsTab() {
        hideLoadingIndicators(['cufPlot', 'curtailmentPlot']);

        if (!state.metricsData || (!state.metricsData.cuf && !state.metricsData.curtailment) ) {
            document.getElementById('cufPlot').innerHTML = '<div class="alert alert-warning m-3">No CUF data available.</div>';
            document.getElementById('curtailmentPlot').innerHTML = '<div class="alert alert-warning m-3">No curtailment data available.</div>';
            clearTable('cufTable');
            clearTable('curtailmentTable');
            return;
        }
        
        createCUFPlot();
        createCurtailmentPlot();
        updateCUFTable();
        updateCurtailmentTable();
    }
    
    function updateStorageTab() {
        hideLoadingIndicators(['socPlot', 'storageUtilizationPlot']);

        if (!state.storageData || (!state.storageData.soc && !state.storageData.stats)) {
            document.getElementById('socPlot').innerHTML = '<div class="alert alert-warning m-3">No storage SoC data available.</div>';
            document.getElementById('storageUtilizationPlot').innerHTML = '<div class="alert alert-warning m-3">No storage utilization data.</div>';
            clearTable('storageUtilizationTable');
            return;
        }
        
        createSOCPlot();
        createStorageUtilizationPlot();
        updateStorageUtilizationTable();
    }
    
    function updateEmissionsTab() {
        hideLoadingIndicators(['emissionsByCarrierPlot']);
        const totalValEl =  document.getElementById('totalEmissionsValue');
        const totalConvEl = document.getElementById('totalEmissionsConverted');

        if (!state.emissionsData || (!state.emissionsData.total && !state.emissionsData.by_carrier)) {
            totalValEl.textContent = '-';
            totalConvEl.textContent = '-';
            document.getElementById('emissionsByCarrierPlot').innerHTML = '<div class="alert alert-warning m-3">No emissions data available.</div>';
            clearTable('emissionsTable');
            return;
        }
        
        updateEmissionsValues();
        createEmissionsByCarrierPlot();
        updateEmissionsTable();
    }
    
    function updatePricesTab() {
        const priceDataContainer = document.getElementById('priceDataContainer');
        const noPriceDataContainer = document.getElementById('noPriceDataContainer');
        hideLoadingIndicators(['avgPriceByBusPlot', 'priceDurationPlot']);

        if (!state.pricesData || !state.pricesData.available) {
            priceDataContainer.style.display = 'none';
            noPriceDataContainer.style.display = 'block';
            return;
        }
        priceDataContainer.style.display = 'block';
        noPriceDataContainer.style.display = 'none';
        
        createAvgPriceByBusPlot();
        createPriceDurationCurve();
        updatePriceTable();
    }
    
    function updateNetworkFlowTab() {
        hideLoadingIndicators(['lineLoadingPlot']);
        if (!state.networkFlowData || (!state.networkFlowData.losses && !state.networkFlowData.line_loading)) {
            document.getElementById('totalLossesValue').textContent = '-';
            document.getElementById('totalLossesGWh').textContent = '-';
            document.getElementById('lineLoadingPlot').innerHTML = '<div class="alert alert-warning m-3">No network flow data available.</div>';
            clearTable('lineLoadingTable');
            return;
        }
        
        updateLossesValues();
        createLineLoadingPlot();
        updateLineLoadingTable();
    }

    function clearPlot(plotId) {
        const plotContainer = document.getElementById(plotId);
        if (plotContainer) {
            // Keep the loading indicator structure but hide it if no data will be plotted
            plotContainer.innerHTML = `<div class="loading-indicator" style="display: none;"><i class="fas fa-spinner fa-spin"></i> Loading...</div>`;
        }
    }
    function clearTable(tableId) {
        const table = document.getElementById(tableId);
        if (table) {
            const tbody = table.querySelector('tbody');
            if (tbody) tbody.innerHTML = '<tr><td colspan="100%" class="text-center">No data available.</td></tr>';
        }
    }

    // =====================
    // Chart Creation Functions
    // =====================
    
    function createDispatchStackPlot() {
        const plotContainerId = 'dispatchStackPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = ''; 
    
        const { generation, load, storage, store, timestamps } = state.dispatchData;
    
        if (!timestamps || timestamps.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No timestamp data available for dispatch.</div>';
            return;
        }
    
        const traces = [];
        const xValues = timestamps.map(ts => new Date(ts)); 
    
        if (generation && generation.length > 0) {
            const carriers = Object.keys(generation[0]).filter(key => key !== 'index' && key !== 'timestamp'); // index is from reset_index
            carriers.forEach(carrier => {
                const yValues = generation.map(item => item[carrier] || 0);
                if (yValues.some(v => Math.abs(v) > 1e-6)) { 
                    traces.push({
                        x: xValues, y: yValues, name: carrier, stackgroup: 'positive',
                        fillcolor: state.colorPalette[carrier] || getRandomColor(),
                        line: { width: 0 }, hovertemplate: `%{x|%Y-%m-%d %H:%M}<br>${carrier}: %{y:,.1f} MW<extra></extra>`
                    });
                }
            });
        }
    
        [storage, store].forEach(sourceData => {
            if (sourceData && sourceData.length > 0) {
                const componentKeys = Object.keys(sourceData[0]).filter(key => key !== 'index' && key !== 'timestamp');
                const dischargeCols = componentKeys.filter(key => key.includes('Discharge'));
                const chargeCols = componentKeys.filter(key => key.includes('Charge'));

                dischargeCols.forEach(col => {
                    const yValues = sourceData.map(item => item[col] || 0);
                    if (yValues.some(v => v > 1e-6)) {
                        traces.push({
                            x: xValues, y: yValues, name: col, stackgroup: 'positive',
                            fillcolor: state.colorPalette[col.split(' ')[0]] || state.colorPalette[col] || getRandomColor(), // Try base carrier color first
                            line: { width: 0 }, hovertemplate: `%{x|%Y-%m-%d %H:%M}<br>${col}: %{y:,.1f} MW<extra></extra>`
                        });
                    }
                });
                 chargeCols.forEach(col => {
                    const yValues = sourceData.map(item => (item[col] || 0) * -1); // Negative for stacking below
                    if (yValues.some(v => v < -1e-6)) { 
                        traces.push({
                            x: xValues, y: yValues, name: col, stackgroup: 'negative',
                            fillcolor: state.colorPalette[col.split(' ')[0]] || state.colorPalette[col] || getRandomColor(),
                            line: { width: 0 }, hovertemplate: `%{x|%Y-%m-%d %H:%M}<br>${col}: %{y:,.1f} MW<extra></extra>`
                        });
                    }
                });
            }
        });
    
        if (load && load.length > 0) {
            const loadValues = load.map(item => item.load);
            traces.push({
                x: xValues, y: loadValues, name: 'Load', mode: 'lines',
                line: { color: state.colorPalette['Load'] || 'black', width: 2 },
                hovertemplate: `%{x|%Y-%m-%d %H:%M}<br>Load: %{y:,.1f} MW<extra></extra>`
            });
        }
    
        const layout = {
            title: `Generation Dispatch${state.resolution ? ` (${state.resolution} resolution)` : ''}`,
            xaxis: { title: 'Time', automargin: true }, yaxis: { title: 'Power (MW)', zeroline: true, zerolinecolor: 'black', zerolinewidth: 1},
            hovermode: 'x unified', legend: { orientation: 'h', y: -0.3, yanchor: 'bottom' },
            height: 600, margin: { l: 70, r: 30, t: 50, b: 150 },
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, traces, layout, { responsive: true });
    }

    function createDailyProfilePlot() {
        const plotContainerId = 'dailyProfilePlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
    
        if (!state.dispatchData || !state.dispatchData.timestamps || state.dispatchData.timestamps.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No data for daily profile.</div>';
            return;
        }
    
        const { generation, load, storage, store, timestamps } = state.dispatchData;
        const allComponentsData = {}; // Store summed data by hour for each component
        const hoursData = Array.from({ length: 24 }, () => ({ count: 0 })); // [ {comp1: sum, comp2: sum, count: N}, ... for 24 hours ]
    
        // Initialize sums for each component in hoursData
        const allComponentNames = new Set();
        if (generation && generation.length > 0) Object.keys(generation[0]).filter(k => k !=='timestamp' && k !=='index').forEach(k => allComponentNames.add(k));
        if (load && load.length > 0) allComponentNames.add('Load');
        [storage, store].forEach(s => {
            if (s && s.length > 0) Object.keys(s[0]).filter(k => k !=='timestamp' && k !=='index').forEach(k => allComponentNames.add(k));
        });
        allComponentNames.forEach(name => hoursData.forEach(h => h[name] = 0));

        timestamps.forEach((ts, i) => {
            const date = new Date(ts);
            const hour = date.getHours();
            hoursData[hour].count++;

            if (generation && generation[i]) {
                Object.keys(generation[i]).filter(k => k !=='timestamp' && k !=='index').forEach(carrier => {
                    hoursData[hour][carrier] += (generation[i][carrier] || 0);
                });
            }
            if (load && load[i]) {
                hoursData[hour]['Load'] += (load[i].load || 0);
            }
            [storage, store].forEach(sourceData => {
                if (sourceData && sourceData[i]) {
                    Object.keys(sourceData[i]).filter(k => k !=='timestamp' && k !=='index').forEach(key => {
                         if (key.includes('Discharge')) {
                            hoursData[hour][key] += (sourceData[i][key] || 0);
                        } else if (key.includes('Charge')) {
                            hoursData[hour][key] -= (sourceData[i][key] || 0); // Negative for charge visualization
                        }
                    });
                }
            });
        });
    
        const traces = [];
        const xHours = Array.from({ length: 24 }, (_, i) => i);
    
        allComponentNames.forEach(compName => {
            const yValues = xHours.map(hour => hoursData[hour][compName] / (hoursData[hour].count || 1));
            const isLoad = compName === 'Load';
            const isCharge = compName.includes('Charge');

            if (yValues.some(v => Math.abs(v) > 1e-3)) { // Only plot if significant values
                if (isLoad) {
                     traces.push({
                        x: xHours, y: yValues, name: 'Load', mode: 'lines',
                        line: { color: state.colorPalette['Load'] || 'black', width: 2 },
                        hovertemplate: `Hour %{x}<br>Load: %{y:,.1f} MW<extra></extra>`
                    });
                } else {
                    traces.push({
                        x: xHours, y: yValues, name: compName, 
                        stackgroup: isCharge ? 'negative' : 'positive',
                        fillcolor: state.colorPalette[compName.split(' ')[0]] || state.colorPalette[compName] || getRandomColor(),
                        line: { width: 0 }, hovertemplate: `Hour %{x}<br>${compName}: %{y:,.1f} MW<extra></extra>`
                    });
                }
            }
        });
            
        const layout = {
            title: 'Average Daily Profile',
            xaxis: { title: 'Hour of Day', tickmode: 'linear', tick0: 0, dtick: 2, automargin: true },
            yaxis: { title: 'Average Power (MW)', zeroline: true, zerolinecolor: 'black', zerolinewidth: 1 },
            hovermode: 'x unified', legend: { orientation: 'h', y: -0.3, yanchor: 'bottom' },
            height: 450, margin: { l: 70, r: 30, t: 50, b: 150 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, traces, layout, { responsive: true });
    }

    function createLoadDurationCurve() {
        const plotContainerId = 'loadDurationPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
    
        if (!state.dispatchData || !state.dispatchData.load || state.dispatchData.load.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No load data for duration curve.</div>';
            return;
        }
    
        const loadValues = state.dispatchData.load.map(item => item.load).filter(val => val !== null && !isNaN(val));
        if (loadValues.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">Load data is empty or invalid.</div>';
            return;
        }
        loadValues.sort((a, b) => b - a); // Sort descending
        const xValues = loadValues.map((_, i) => (i / (loadValues.length -1 + 1e-9)) * 100); // Avoid div by zero for single point
    
        const trace = {
            x: xValues, y: loadValues, type: 'scatter', fill: 'tozeroy',
            fillcolor: 'rgba(0,128,255,0.2)', line: { color: 'rgba(0,128,255,0.8)' },
            hovertemplate: 'Duration: %{x:.1f}%<br>Load: %{y:,.1f} MW<extra></extra>'
        };
        const layout = {
            title: 'Load Duration Curve',
            xaxis: { title: 'Duration (%)', range: [0, 100], automargin: true }, yaxis: { title: 'Load (MW)' },
            height: 450, margin: { l: 70, r: 30, t: 50, b: 60 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace], layout, { responsive: true });
    }

    function updateGenerationSummaryTable() {
        const tbody = document.getElementById('generationSummaryTable').querySelector('tbody');
        tbody.innerHTML = ''; 
    
        if (!state.dispatchData || !state.dispatchData.generation || state.dispatchData.generation.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center">No generation data.</td></tr>';
            return;
        }
    
        const generationByCarrier = {};
        const generationData = state.dispatchData.generation; // This is an array of objects
        const carriers = Object.keys(generationData[0]).filter(key => key !== 'index' && key !== 'timestamp');
        const numSnapshots = state.dispatchData.timestamps.length; // Assuming timestamps match generation data length

        // Assuming generation data is power (MW) and timestamps represent intervals (e.g., 1 hour)
        // For energy, multiply by interval duration (assuming 1 hour for simplicity here, adjust if resolution implies otherwise)
        const intervalHours = state.resolution.includes('H') ? parseFloat(state.resolution.replace('H','')) : (state.resolution === '1D' ? 24 : (state.resolution === '1W' ? 24*7 : 1));


        carriers.forEach(carrier => {
            // Sum of (power * interval_duration) for each snapshot
            generationByCarrier[carrier] = generationData.reduce((sum, item) => sum + (item[carrier] || 0), 0) * intervalHours;
        });
    
        const sortedCarriers = Object.entries(generationByCarrier)
            .filter(([_, energy]) => energy > 1e-3) 
            .sort(([, a], [, b]) => b - a);
    
        const totalGeneration = sortedCarriers.reduce((sum, [, energy]) => sum + energy, 0);
    
        sortedCarriers.forEach(([carrier, energy]) => {
            const percentage = totalGeneration > 0 ? (energy / totalGeneration) * 100 : 0;
            const row = tbody.insertRow();
            row.insertCell().textContent = carrier;
            row.insertCell().textContent = energy.toLocaleString(undefined, { maximumFractionDigits: 1 });
            row.cells[1].className = 'text-end';
            row.insertCell().textContent = percentage.toLocaleString(undefined, { maximumFractionDigits: 1 }) + '%';
            row.cells[2].className = 'text-end';
        });
    
        if (totalGeneration > 0) {
            const totalRow = tbody.insertRow();
            totalRow.classList.add('table-active', 'fw-bold');
            totalRow.insertCell().textContent = 'Total';
            totalRow.insertCell().textContent = totalGeneration.toLocaleString(undefined, { maximumFractionDigits: 1 });
            totalRow.cells[1].className = 'text-end';
            totalRow.insertCell().textContent = '100.0%';
            totalRow.cells[2].className = 'text-end';
        }
    }

    function updateLoadStatistics() {
        if (!state.dispatchData || !state.dispatchData.load || state.dispatchData.load.length === 0) {
            document.getElementById('totalLoadValue').textContent = '-';
            document.getElementById('peakLoadValue').textContent = '-';
            document.getElementById('minLoadValue').textContent = '-';
            return;
        }
        const loadValues = state.dispatchData.load.map(item => item.load); // These are power values (MW)
        const intervalHours = state.resolution.includes('H') ? parseFloat(state.resolution.replace('H','')) : (state.resolution === '1D' ? 24 : (state.resolution === '1W' ? 24*7 : 1));

        const totalLoadEnergy = loadValues.reduce((sum, loadP) => sum + (loadP * intervalHours), 0); // MWh
        const peakLoadPower = Math.max(...loadValues); // MW
        const minLoadPower = Math.min(...loadValues); // MW
    
        document.getElementById('totalLoadValue').textContent = totalLoadEnergy.toLocaleString(undefined, { maximumFractionDigits: 1 });
        document.getElementById('peakLoadValue').textContent = peakLoadPower.toLocaleString(undefined, { maximumFractionDigits: 1 });
        document.getElementById('minLoadValue').textContent = minLoadPower.toLocaleString(undefined, { maximumFractionDigits: 1 });
    }

    function createCapacityByCarrierPlot() {
        const plotContainerId = 'capacityByCarrierPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
    
        if (!state.capacityData || !state.capacityData.by_carrier || state.capacityData.by_carrier.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No capacity by carrier data.</div>';
            return;
        }
    
        const capacityData = [...state.capacityData.by_carrier].sort((a, b) => b.Capacity - a.Capacity);
        const attribute = document.getElementById('capacityAttributeSelect').value;
        const unit = capacityData.length > 0 && capacityData[0].Unit ? capacityData[0].Unit : (attribute.startsWith('e_nom') ? 'MWh' : 'MW');

        const trace = {
            x: capacityData.map(item => item.Carrier),
            y: capacityData.map(item => item.Capacity),
            type: 'bar',
            marker: { color: capacityData.map(item => state.colorPalette[item.Carrier] || getRandomColor()) },
            hovertemplate: `%{x}<br>Capacity: %{y:,.1f} ${unit}<extra></extra>`
        };
        const layout = {
            title: `Installed Capacity by Carrier (${attribute})`,
            xaxis: { title: 'Carrier', automargin: true },
            yaxis: { title: `Capacity (${unit})` },
            height: 400, margin: { l: 70, r: 30, t: 50, b: 100 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace], layout, { responsive: true });
    }

    function createCapacityByRegionPlot() {
        const plotContainerId = 'capacityByRegionPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
    
        if (!state.capacityData || !state.capacityData.by_region || state.capacityData.by_region.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No capacity by region data.</div>';
            return;
        }
    
        const capacityData = [...state.capacityData.by_region].sort((a, b) => b.Capacity - a.Capacity);
        const attribute = document.getElementById('capacityAttributeSelect').value;
        const unit = capacityData.length > 0 && capacityData[0].Unit ? capacityData[0].Unit : (attribute.startsWith('e_nom') ? 'MWh' : 'MW');


        const trace = {
            x: capacityData.map(item => item.Region),
            y: capacityData.map(item => item.Capacity),
            type: 'bar',
            marker: { color: 'rgb(158,202,225)', line: { color: 'rgb(8,48,107)', width: 1.5 } },
            hovertemplate: `%{x}<br>Capacity: %{y:,.1f} ${unit}<extra></extra>`
        };
        const layout = {
            title: `Capacity by Region (${attribute})`,
            xaxis: { title: 'Region', tickangle: -45, automargin: true },
            yaxis: { title: `Capacity (${unit})` },
            height: 450, margin: { l: 70, r: 30, t: 50, b: 120 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace], layout, { responsive: true });
    }

    function updateCapacityTable() {
        const tbody = document.getElementById('capacityTable').querySelector('tbody');
        tbody.innerHTML = '';
        const attribute = document.getElementById('capacityAttributeSelect').value;
        // Default unit based on attribute, but prefer unit from data if available
        let defaultUnit = attribute.startsWith('e_nom') ? 'MWh' : 'MW';

        if (!state.capacityData || !state.capacityData.by_carrier || state.capacityData.by_carrier.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center">No capacity data.</td></tr>';
            return;
        }
        const capacityData = [...state.capacityData.by_carrier].sort((a, b) => b.Capacity - a.Capacity);
        let totalCapacity = 0;
    
        capacityData.forEach(item => {
            const unit = item.Unit || defaultUnit; // Use item's unit if present
            const row = tbody.insertRow();
            row.insertCell().textContent = item.Carrier;
            row.insertCell().textContent = item.Capacity.toLocaleString(undefined, { maximumFractionDigits: 1 });
            row.cells[1].className = 'text-end';
            row.insertCell().textContent = unit; 
            totalCapacity += item.Capacity;
        });
    
        if (totalCapacity > 0 && capacityData.length > 0) {
            const overallUnit = capacityData[0].Unit || defaultUnit; // Use unit of first item for total, or default
            const totalRow = tbody.insertRow();
            totalRow.classList.add('table-active', 'fw-bold');
            totalRow.insertCell().textContent = 'Total';
            totalRow.insertCell().textContent = totalCapacity.toLocaleString(undefined, { maximumFractionDigits: 1 });
            totalRow.cells[1].className = 'text-end';
            totalRow.insertCell().textContent = overallUnit;
        }
    }

    function createCUFPlot() {
        const plotContainerId = 'cufPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
        if (!state.metricsData || !state.metricsData.cuf || state.metricsData.cuf.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No CUF data.</div>';
            return;
        }
        const cufData = [...state.metricsData.cuf].sort((a, b) => b.CUF - a.CUF);
        const trace = {
            x: cufData.map(item => item.Carrier),
            y: cufData.map(item => item.CUF * 100), 
            type: 'bar',
            marker: { color: cufData.map(item => state.colorPalette[item.Carrier] || getRandomColor()) },
            hovertemplate: `%{x}<br>CUF: %{y:.1f}%<extra></extra>`
        };
        const layout = {
            title: 'Capacity Utilization Factor (CUF)',
            xaxis: { title: 'Carrier', automargin: true }, yaxis: { title: 'CUF (%)', tickformat: '.1f' },
            height: 350, margin: { l: 60, r: 20, t: 40, b: 100 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace], layout, { responsive: true });
    }

    function updateCUFTable() {
        const tbody = document.getElementById('cufTable').querySelector('tbody');
        tbody.innerHTML = '';
        if (!state.metricsData || !state.metricsData.cuf || state.metricsData.cuf.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="text-center">No CUF data.</td></tr>';
            return;
        }
        const cufData = [...state.metricsData.cuf].sort((a, b) => b.CUF - a.CUF);
        cufData.forEach(item => {
            const row = tbody.insertRow();
            row.insertCell().textContent = item.Carrier;
            row.insertCell().textContent = (item.CUF * 100).toLocaleString(undefined, { maximumFractionDigits: 1 }) + '%';
            row.cells[1].className = 'text-end';
        });
    }

    function createCurtailmentPlot() {
        const plotContainerId = 'curtailmentPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
        if (!state.metricsData || !state.metricsData.curtailment || state.metricsData.curtailment.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No curtailment data.</div>';
            return;
        }
        const curtailmentData = [...state.metricsData.curtailment].sort((a, b) => b['Curtailment (%)'] - a['Curtailment (%)']);
        const trace = {
            x: curtailmentData.map(item => item.Carrier),
            y: curtailmentData.map(item => item['Curtailment (%)']),
            type: 'bar',
            marker: { color: curtailmentData.map(item => state.colorPalette[item.Carrier] || getRandomColor()) },
            hovertemplate: `%{x}<br>Curtailment: %{y:.1f}%<extra></extra>`
        };
        const layout = {
            title: 'Renewable Curtailment',
            xaxis: { title: 'Carrier', automargin: true }, yaxis: { title: 'Curtailment (%)' },
            height: 350, margin: { l: 60, r: 20, t: 40, b: 100 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace], layout, { responsive: true });
    }

    function updateCurtailmentTable() {
        const tbody = document.getElementById('curtailmentTable').querySelector('tbody');
        tbody.innerHTML = '';
        if (!state.metricsData || !state.metricsData.curtailment || state.metricsData.curtailment.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center">No curtailment data.</td></tr>';
            return;
        }
        const curtailmentData = [...state.metricsData.curtailment].sort((a, b) => b['Curtailment (%)'] - a['Curtailment (%)']);
        curtailmentData.forEach(item => {
            const row = tbody.insertRow();
            row.insertCell().textContent = item.Carrier;
            row.insertCell().textContent = (item['Curtailment (MWh)'] || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
            row.cells[1].className = 'text-end';
            row.insertCell().textContent = (item['Potential (MWh)'] || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
            row.cells[2].className = 'text-end';
            row.insertCell().textContent = (item['Curtailment (%)'] || 0).toLocaleString(undefined, { maximumFractionDigits: 1 }) + '%';
            row.cells[3].className = 'text-end';
        });
    }

    function createSOCPlot() {
        const plotContainerId = 'socPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
        if (!state.storageData || !state.storageData.soc || state.storageData.soc.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No SoC data.</div>';
            return;
        }
        const socDataRecords = state.storageData.soc; 
        const timestamps = state.storageData.timestamps.map(ts => new Date(ts));
        const storageTypes = state.storageData.storage_types; // These are the column headers from the soc data (excluding 'index' or 'timestamp')
        const traces = [];

        storageTypes.forEach(type => {
            const yValues = socDataRecords.map(item => item[type] || 0);
            if (yValues.some(v => Math.abs(v) > 1e-3)) {
                traces.push({
                    x: timestamps, y: yValues, name: type, mode: 'lines',
                    line: { color: state.colorPalette[type.split(' ')[0]] || state.colorPalette[type] || getRandomColor(), width: 2 },
                    hovertemplate: `%{x|%Y-%m-%d %H:%M}<br>${type} SoC: %{y:,.1f} MWh<extra></extra>`
                });
            }
        });

        const layout = {
            title: 'Storage State of Charge (SoC)',
            xaxis: { title: 'Time', automargin: true }, yaxis: { title: 'Energy (MWh)' },
            hovermode: 'x unified', legend: { orientation: 'h', y: -0.3, yanchor: 'bottom' },
            height: 400, margin: { l: 70, r: 30, t: 50, b: 150 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, traces, layout, { responsive: true });
    }

    function createStorageUtilizationPlot() {
        const plotContainerId = 'storageUtilizationPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
        if (!state.storageData || !state.storageData.stats || state.storageData.stats.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No storage utilization data.</div>';
            return;
        }
        const storageStats = [...state.storageData.stats].sort((a,b) => a.Storage_Type.localeCompare(b.Storage_Type));
        const trace1 = {
            x: storageStats.map(item => item.Storage_Type),
            y: storageStats.map(item => item.Charge_MWh),
            name: 'Charge (MWh)', type: 'bar', marker: { color: state.colorPalette['Storage Charge'] || 'rgba(255,165,0,0.8)' }
        };
        const trace2 = {
            x: storageStats.map(item => item.Storage_Type),
            y: storageStats.map(item => item.Discharge_MWh),
            name: 'Discharge (MWh)', type: 'bar', marker: { color: state.colorPalette['Storage Discharge'] || 'rgba(50,205,50,0.8)' }
        };
        const layout = {
            title: 'Storage Energy Throughput',
            xaxis: { title: 'Storage Type', automargin: true }, yaxis: { title: 'Energy (MWh)' },
            barmode: 'group', bargap: 0.15, bargroupgap: 0.1,
            height: 350, margin: { l: 70, r: 30, t: 50, b: 100 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace1, trace2], layout, { responsive: true });
    }

    function updateStorageUtilizationTable() {
        const tbody = document.getElementById('storageUtilizationTable').querySelector('tbody');
        tbody.innerHTML = '';
        if (!state.storageData || !state.storageData.stats || state.storageData.stats.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center">No storage utilization data.</td></tr>';
            return;
        }
        const storageStats = [...state.storageData.stats].sort((a,b) => a.Storage_Type.localeCompare(b.Storage_Type));
        storageStats.forEach(item => {
            const row = tbody.insertRow();
            row.insertCell().textContent = item.Storage_Type;
            row.insertCell().textContent = (item.Charge_MWh || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
            row.cells[1].className = 'text-end';
            row.insertCell().textContent = (item.Discharge_MWh || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
            row.cells[2].className = 'text-end';
            row.insertCell().textContent = item.Efficiency_Percent !== null && !isNaN(item.Efficiency_Percent) ? item.Efficiency_Percent.toLocaleString(undefined, { maximumFractionDigits: 1 }) + '%' : '-';
            row.cells[3].className = 'text-end';
        });
    }

    function updateEmissionsValues() {
        const totalValEl =  document.getElementById('totalEmissionsValue');
        const totalConvEl = document.getElementById('totalEmissionsConverted');
        if (!state.emissionsData || !state.emissionsData.total || state.emissionsData.total.length === 0) {
            totalValEl.textContent = '-';
            totalConvEl.textContent = '-';
            return;
        }
        // Assuming 'total' is an array, take the first item if multiple periods were aggregated, or the only item.
        const totalEmissionsItem = state.emissionsData.total[0];
        const totalEmissions = totalEmissionsItem ? totalEmissionsItem['Total CO2 Emissions (Tonnes)'] : 0;

        totalValEl.textContent = totalEmissions.toLocaleString(undefined, { maximumFractionDigits: 0 });
        totalConvEl.textContent = (totalEmissions / 1e6).toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    function createEmissionsByCarrierPlot() {
        const plotContainerId = 'emissionsByCarrierPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
        if (!state.emissionsData || !state.emissionsData.by_carrier || state.emissionsData.by_carrier.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No emissions by carrier data.</div>';
            return;
        }
        const emissionsData = [...state.emissionsData.by_carrier]
            .filter(item => item['Emissions (Tonnes)'] > 1)
            .sort((a, b) => b['Emissions (Tonnes)'] - a['Emissions (Tonnes)']);

        const trace = {
            x: emissionsData.map(item => item.Carrier),
            y: emissionsData.map(item => item['Emissions (Tonnes)']),
            type: 'bar',
            marker: { color: emissionsData.map(item => state.colorPalette[item.Carrier] || getRandomColor()) },
            hovertemplate: `%{x}<br>Emissions: %{y:,.0f} tonnes CO₂<extra></extra>`
        };
        const layout = {
            title: 'CO₂ Emissions by Carrier',
            xaxis: { title: 'Carrier', automargin: true }, yaxis: { title: 'Emissions (Tonnes CO₂)' },
            height: 350, margin: { l: 70, r: 30, t: 50, b: 100 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace], layout, { responsive: true });
    }

    function updateEmissionsTable() {
        const tbody = document.getElementById('emissionsTable').querySelector('tbody');
        tbody.innerHTML = '';
        if (!state.emissionsData || !state.emissionsData.by_carrier || state.emissionsData.by_carrier.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center">No emissions data.</td></tr>';
            return;
        }
        const emissionsData = [...state.emissionsData.by_carrier]
            .filter(item => item['Emissions (Tonnes)'] > 1)
            .sort((a, b) => b['Emissions (Tonnes)'] - a['Emissions (Tonnes)']);
        const totalEmissions = emissionsData.reduce((sum, item) => sum + item['Emissions (Tonnes)'], 0);

        emissionsData.forEach(item => {
            const percentage = totalEmissions > 0 ? (item['Emissions (Tonnes)'] / totalEmissions) * 100 : 0;
            const row = tbody.insertRow();
            row.insertCell().textContent = item.Carrier;
            row.insertCell().textContent = (item['Emissions (Tonnes)'] || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
            row.cells[1].className = 'text-end';
            row.insertCell().textContent = percentage.toLocaleString(undefined, { maximumFractionDigits: 1 }) + '%';
            row.cells[2].className = 'text-end';
        });
        if (totalEmissions > 0) {
            const totalRow = tbody.insertRow();
            totalRow.classList.add('table-active', 'fw-bold');
            totalRow.insertCell().textContent = 'Total';
            totalRow.insertCell().textContent = totalEmissions.toLocaleString(undefined, { maximumFractionDigits: 0 });
            totalRow.cells[1].className = 'text-end';
            totalRow.insertCell().textContent = '100.0%';
            totalRow.cells[2].className = 'text-end';
        }
    }

    function createAvgPriceByBusPlot() {
        const plotContainerId = 'avgPriceByBusPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
        if (!state.pricesData || !state.pricesData.avg_by_bus || state.pricesData.avg_by_bus.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No average price data by bus.</div>';
            return;
        }
        const priceData = [...state.pricesData.avg_by_bus].sort((a, b) => b.price - a.price);
        const unit = state.pricesData.unit || '$/MWh';
        const trace = {
            x: priceData.map(item => item.bus), y: priceData.map(item => item.price),
            type: 'bar', marker: { color: 'rgba(158,202,225,0.8)', line: { color: 'rgb(8,48,107)', width: 1.5 } },
            hovertemplate: `%{x}<br>Price: %{y:,.2f} ${unit}<extra></extra>`
        };
        const layout = {
            title: 'Average Marginal Price by Bus',
            xaxis: { title: 'Bus', tickangle: -45, automargin: true }, yaxis: { title: `Price (${unit})` },
            height: 350, margin: { l: 70, r: 30, t: 50, b: 120 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace], layout, { responsive: true });
    }

    function createPriceDurationCurve() {
        const plotContainerId = 'priceDurationPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
        if (!state.pricesData || !state.pricesData.duration_curve || state.pricesData.duration_curve.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No price duration data.</div>';
            return;
        }
        const durationCurve = state.pricesData.duration_curve; 
        const unit = state.pricesData.unit || '$/MWh';
        const xValues = durationCurve.map((_, i) => (i / (durationCurve.length -1 + 1e-9)) * 100);
        const trace = {
            x: xValues, y: durationCurve, type: 'scatter', fill: 'tozeroy',
            fillcolor: 'rgba(255,0,0,0.2)', line: { color: 'red' },
            hovertemplate: `Duration: %{x:.1f}%<br>Price: %{y:,.2f} ${unit}<extra></extra>`
        };
        const layout = {
            title: 'Price Duration Curve',
            xaxis: { title: 'Duration (%)', range: [0, 100], automargin: true }, yaxis: { title: `Price (${unit})` },
            height: 350, margin: { l: 70, r: 30, t: 50, b: 60 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace], layout, { responsive: true });
    }

    function updatePriceTable() {
        const tbody = document.getElementById('priceTable').querySelector('tbody');
        tbody.innerHTML = '';
        if (!state.pricesData || !state.pricesData.avg_by_bus || state.pricesData.avg_by_bus.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center">No price data.</td></tr>';
            return;
        }
        const priceData = [...state.pricesData.avg_by_bus].sort((a, b) => b.price - a.price); 
        const unit = state.pricesData.unit || '$/MWh';

        priceData.forEach(item => {
            const row = tbody.insertRow();
            row.insertCell().textContent = item.bus;
            row.insertCell().textContent = (item.price !== null && item.price !== undefined) ? item.price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '-';
            row.cells[1].className = 'text-end';
            row.insertCell().textContent = (item.min_price !== null && item.min_price !== undefined) ? item.min_price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '-';
            row.cells[2].className = 'text-end';
            row.insertCell().textContent = (item.max_price !== null && item.max_price !== undefined) ? item.max_price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '-';
            row.cells[3].className = 'text-end';
            row.insertCell().textContent = unit;
        });
    }

    function updateLossesValues() {
        const totalValEl = document.getElementById('totalLossesValue');
        const totalGwhEl = document.getElementById('totalLossesGWh');
        if (!state.networkFlowData || !state.networkFlowData.losses || state.networkFlowData.losses.length === 0) {
            totalValEl.textContent = '-';
            totalGwhEl.textContent = '-';
            return;
        }
        // Assuming losses is an array of objects, take the first for "Overall" or the relevant period's sum
        const totalLossesItem = state.networkFlowData.losses[0];
        const totalLossesMWh = totalLossesItem ? (totalLossesItem['Losses (MWh)'] || 0) : 0;

        totalValEl.textContent = totalLossesMWh.toLocaleString(undefined, { maximumFractionDigits: 1 });
        totalGwhEl.textContent = (totalLossesMWh / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    function createLineLoadingPlot() {
        const plotContainerId = 'lineLoadingPlot';
        const plotContainer = document.getElementById(plotContainerId);
        plotContainer.innerHTML = '';
        if (!state.networkFlowData || !state.networkFlowData.line_loading || state.networkFlowData.line_loading.length === 0) {
            plotContainer.innerHTML = '<div class="alert alert-warning m-3">No line loading data.</div>';
            return;
        }
        const lineLoadingData = [...state.networkFlowData.line_loading].sort((a, b) => b.loading - a.loading).slice(0, 20); // Top 20
        const trace = {
            x: lineLoadingData.map(item => item.line),
            y: lineLoadingData.map(item => item.loading),
            type: 'bar',
            marker: {
                color: lineLoadingData.map(item => {
                    if (item.loading > 90) return 'rgba(220,53,69,0.8)'; 
                    if (item.loading > 70) return 'rgba(255,193,7,0.8)'; 
                    return 'rgba(25,135,84,0.8)'; 
                })
            },
            hovertemplate: `%{x}<br>Loading: %{y:.1f}%<extra></extra>`
        };
        const layout = {
            title: 'Line Loading (Top 20)',
            xaxis: { title: 'Line', tickangle: -45, automargin: true }, yaxis: { title: 'Loading (%)' },
            height: 350, margin: { l: 70, r: 30, t: 50, b: 120 }
        };
        if (typeof Plotly !== 'undefined') Plotly.newPlot(plotContainerId, [trace], layout, { responsive: true });
    }

    function updateLineLoadingTable() {
        const tbody = document.getElementById('lineLoadingTable').querySelector('tbody');
        tbody.innerHTML = '';
        if (!state.networkFlowData || !state.networkFlowData.line_loading || state.networkFlowData.line_loading.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" class="text-center">No line loading data.</td></tr>';
            return;
        }
        const lineLoadingData = [...state.networkFlowData.line_loading].sort((a, b) => b.loading - a.loading);
        lineLoadingData.forEach(item => {
            const row = tbody.insertRow();
            let loadingClass = '';
            if (item.loading > 90) loadingClass = 'table-danger';
            else if (item.loading > 70) loadingClass = 'table-warning';
            if (loadingClass) row.classList.add(loadingClass);
            
            row.insertCell().textContent = item.line;
            row.insertCell().textContent = (item.loading || 0).toLocaleString(undefined, { maximumFractionDigits: 1 }) + '%';
            row.cells[1].className = 'text-end';
        });
    }
    
    // =====================
    // Comparison Functions
    // =====================
    
    function initializeComparison() {
        const comparisonBtn = document.createElement('button');
        comparisonBtn.className = 'btn btn-sm btn-outline-primary ms-3';
        comparisonBtn.innerHTML = '<i class="fas fa-chart-bar me-1"></i> Network Comparison';
        comparisonBtn.id = 'networkComparisonToggleBtn';
        comparisonBtn.addEventListener('click', function() {
            analysisDashboard.style.display = 'none';
            document.getElementById('networkSelectionSection').style.display = 'none'; // Hide selection too
            document.getElementById('networkComparisonSection').style.display = 'block';
            loadNetworksForComparison();
        });
        const controlsContainer = document.querySelector('.analysis-controls');
        if (controlsContainer) {
            controlsContainer.prepend(comparisonBtn);
        }


        document.getElementById('backToDashboardBtn').addEventListener('click', function() {
            document.getElementById('networkComparisonSection').style.display = 'none';
            // Only show analysis dashboard if a network was previously loaded
            if (state.currentNetworkPath) {
                 analysisDashboard.style.display = 'block';
            } else {
                 document.getElementById('networkSelectionSection').style.display = 'block';
            }
        });
        document.getElementById('runComparisonBtn').addEventListener('click', runComparison);
    }
    
    function loadNetworksForComparison() {
        const container = document.getElementById('networkSelectContainer');
        container.innerHTML = '<div class="text-center py-3"><i class="fas fa-spinner fa-spin me-2"></i> Loading networks...</div>';
        
        if (state.allNcFiles.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No networks found. Please upload network files first or ensure they are scanned.</div>';
            return;
        }
        container.innerHTML = ''; 

        state.allNcFiles.forEach((network, index) => {
            const div = document.createElement('div');
            div.className = 'network-checkbox form-check';
            const isChecked = network.path === state.currentNetworkPath && state.currentNetworkPath !== null; // Auto-check current if it's part of analysis
            if (isChecked) div.classList.add('selected');

            div.innerHTML = `
                <input class="form-check-input network-checkbox-input" type="checkbox" value="${network.path}" id="compNet-${index}" data-filename="${network.filename}" data-scenario="${network.scenario}" ${isChecked ? 'checked' : ''}>
                <label class="form-check-label" for="compNet-${index}">
                    <strong>${network.scenario}</strong> / ${network.filename}
                </label>
            `;
            // Event listener to toggle 'selected' class on the div itself for styling
            div.addEventListener('click', function(e) {
                const checkbox = this.querySelector('input[type="checkbox"]');
                if (e.target !== checkbox) { // If label or div is clicked, toggle checkbox
                    checkbox.checked = !checkbox.checked;
                }
                this.classList.toggle('selected', checkbox.checked);
            });
            container.appendChild(div);
        });
    }
    
    function runComparison() {
        const selectedCheckboxes = Array.from(document.querySelectorAll('#networkSelectContainer .network-checkbox-input:checked'));
        const selectedNetworkPaths = selectedCheckboxes.map(cb => cb.value);
        
        if (selectedNetworkPaths.length < 1) { // Allow single "comparison" for consistency, though 2+ is typical
            showGlobalAlert('Please select at least one network for comparison.', 'warning');
            return;
        }

        const labels = {};
        selectedCheckboxes.forEach(cb => {
            labels[cb.value] = `${cb.dataset.scenario} / ${cb.dataset.filename}`;
        });

        const comparisonType = document.getElementById('comparisonTypeSelect').value;
        const resultsContainer = document.getElementById('comparisonResults');
        const mainPlotContainer = document.getElementById('comparisonMainPlot');
        const secondaryPlotContainer = document.getElementById('comparisonSecondaryPlot');
        const secondaryRow = document.getElementById('comparisonSecondaryRow');
        
        resultsContainer.style.display = 'block';
        mainPlotContainer.innerHTML = '<div class="loading-indicator" style="display: flex;"><i class="fas fa-spinner fa-spin"></i> Generating comparison...</div>';
        secondaryPlotContainer.innerHTML = '';
        secondaryRow.style.display = 'none';

        fetch('/api/pypsa/compare_networks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_paths: selectedNetworkPaths,
                labels: labels, 
                comparison_type: comparisonType,
                attribute: comparisonType === 'capacity' ? document.getElementById('capacityAttributeSelect').value : undefined // Pass capacity attribute if relevant
            })
        })
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success') {
                renderComparisonPlot(result.comparison_data, mainPlotContainer, secondaryPlotContainer, secondaryRow);
            } else {
                mainPlotContainer.innerHTML = `<div class="alert alert-danger">${result.message}</div>`;
            }
        })
        .catch(error => {
            mainPlotContainer.innerHTML = `<div class="alert alert-danger">Error running comparison: ${error.message}</div>`;
        });
    }

    function renderComparisonPlot(comparisonResult, mainPlotContainer, secondaryPlotContainer, secondaryRow) {
        mainPlotContainer.innerHTML = ''; 
        secondaryPlotContainer.innerHTML = '';
        secondaryRow.style.display = 'none';

        const { type, data, colors, unit, label_name } = comparisonResult;
        document.getElementById('comparisonResultsTitle').textContent = `Comparison: ${type.charAt(0).toUpperCase() + type.slice(1)}`;

        if (type === 'capacity' || type === 'generation') {
            const plotData = [];
            Object.entries(data).forEach(([networkLabel, items]) => {
                if(items.error) { // Skip errored networks in plot
                    console.warn(`Skipping errored network ${networkLabel} in comparison plot: ${items.error}`);
                    return;
                }
                items.forEach(item => {
                    plotData.push({
                        [label_name]: networkLabel, 
                        Carrier: item.Carrier || item.index, 
                        Value: item.Capacity || item.Generation 
                    });
                });
            });
            if (plotData.length === 0) {
                 mainPlotContainer.innerHTML = '<div class="alert alert-info m-3">No data to display for this comparison. One or more networks might have had processing errors.</div>';
                 return;
            }
            const yAxisTitle = type === 'capacity' ? `Capacity (${unit})` : `Generation (${unit || 'MWh'})`;
            const fig = Plotly.graphObjectToFigure(px.bar(plotData, {
                x: label_name, y: 'Value', color: 'Carrier', barmode: 'stack',
                title: `${type.charAt(0).toUpperCase() + type.slice(1)} Comparison`,
                labels: { 'Value': yAxisTitle }, color_discrete_map: colors || state.colorPalette
            }));
            if (typeof Plotly !== 'undefined') Plotly.newPlot(mainPlotContainer, fig.data, fig.layout, {responsive: true});

        } else if (type === 'metrics') {
            const cufPlotData = [];
            if (data.cuf) {
                 Object.entries(data.cuf).forEach(([networkLabel, items]) => {
                    if(items.error) return;
                    items.forEach(item => cufPlotData.push({ [label_name]: networkLabel, Carrier: item.Carrier, Value: item.CUF * 100 }));
                });
            }
            if (cufPlotData.length > 0) {
                const figCuf = Plotly.graphObjectToFigure(px.bar(cufPlotData, {
                    x: label_name, y: 'Value', color: 'Carrier', barmode: 'group',
                    title: 'Capacity Utilization Factor (CUF) Comparison',
                    labels: { 'Value': 'CUF (%)' }, color_discrete_map: colors || state.colorPalette
                }));
                if (typeof Plotly !== 'undefined') Plotly.newPlot(mainPlotContainer, figCuf.data, figCuf.layout, {responsive: true});
            } else {
                mainPlotContainer.innerHTML = '<div class="alert alert-info m-3">No CUF data to compare.</div>';
            }

            const curtPlotData = [];
            if (data.curtailment) {
                Object.entries(data.curtailment).forEach(([networkLabel, items]) => {
                     if(items.error) return;
                    items.forEach(item => curtPlotData.push({ [label_name]: networkLabel, Carrier: item.Carrier, Value: item['Curtailment (%)'] }));
                });
            }
            if (curtPlotData.length > 0) {
                secondaryRow.style.display = 'flex';
                const figCurt = Plotly.graphObjectToFigure(px.bar(curtPlotData, {
                    x: label_name, y: 'Value', color: 'Carrier', barmode: 'group',
                    title: 'Curtailment (%) Comparison',
                    labels: { 'Value': 'Curtailment (%)' }, color_discrete_map: colors || state.colorPalette
                }));
                if (typeof Plotly !== 'undefined') Plotly.newPlot(secondaryPlotContainer, figCurt.data, figCurt.layout, {responsive: true});
            } else {
                secondaryPlotContainer.innerHTML = '<div class="alert alert-info m-3">No curtailment data to compare.</div>';
                secondaryRow.style.display = 'flex'; // Still show it to display message
            }
        } else if (type === 'emissions') {
            const totalEmissionsPlotData = [];
            if (data.total) {
                Object.entries(data.total).forEach(([networkLabel, items]) => {
                    if(items.error) return;
                    if (items && items.length > 0) {
                        totalEmissionsPlotData.push({ [label_name]: networkLabel, Value: items[0]['Total CO2 Emissions (Tonnes)'] });
                    }
                });
            }
            if (totalEmissionsPlotData.length > 0) {
                 const figTotalEm = Plotly.graphObjectToFigure(px.bar(totalEmissionsPlotData, {
                    x: label_name, y: 'Value',
                    title: 'Total CO₂ Emissions Comparison',
                    labels: { 'Value': `Total CO₂ Emissions (${unit || 'Tonnes'})` }
                }));
                 if (typeof Plotly !== 'undefined') Plotly.newPlot(mainPlotContainer, figTotalEm.data, figTotalEm.layout, {responsive: true});
            } else {
                 mainPlotContainer.innerHTML = '<div class="alert alert-info m-3">No total emissions data to compare.</div>';
            }
            
            const byCarrierPlotData = [];
            if (data.by_carrier) {
                Object.entries(data.by_carrier).forEach(([networkLabel, items]) => {
                    if(items.error) return;
                    items.forEach(item => byCarrierPlotData.push({ [label_name]: networkLabel, Carrier: item.Carrier, Value: item['Emissions (Tonnes)'] }));
                });
            }
            if (byCarrierPlotData.length > 0) {
                secondaryRow.style.display = 'flex';
                const figCarrierEm = Plotly.graphObjectToFigure(px.bar(byCarrierPlotData, {
                    x: label_name, y: 'Value', color: 'Carrier', barmode: 'stack',
                    title: 'CO₂ Emissions by Carrier Comparison',
                    labels: { 'Value': `Emissions (${unit || 'Tonnes'})` }, color_discrete_map: colors || state.colorPalette
                }));
                 if (typeof Plotly !== 'undefined') Plotly.newPlot(secondaryPlotContainer, figCarrierEm.data, figCarrierEm.layout, {responsive: true});
            } else {
                secondaryPlotContainer.innerHTML = '<div class="alert alert-info m-3">No emissions by carrier data to compare.</div>';
                secondaryRow.style.display = 'flex';
            }
        } else {
            mainPlotContainer.innerHTML = `<div class="alert alert-info">Comparison type "${type}" is not yet fully implemented for plotting.</div>`;
        }
    }


    // General utility functions
    function showGlobalAlert(message, category = 'info', duration = 5000) {
        const container = document.querySelector('.flash-messages-container');
        if (!container) {
            console.warn("Flash messages container not found. Alert:", message);
            alert(`${category.toUpperCase()}: ${message}`); 
            return;
        }
        
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${category} alert-dismissible fade show`;
        alertDiv.setAttribute('role', 'alert');
        
        let iconClass = 'fa-info-circle';
        if (category === 'success') iconClass = 'fa-check-circle';
        else if (category === 'danger' || category === 'warning') iconClass = 'fa-exclamation-triangle';

        alertDiv.innerHTML = `
            <i class="fas ${iconClass} alert-icon"></i>
            <div class="alert-content">${message}</div>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        container.appendChild(alertDiv);
        
        if (duration > 0 && (category === 'info' || category === 'success')) {
            setTimeout(() => {
                const bsAlert = bootstrap.Alert.getInstance(alertDiv);
                if (bsAlert) bsAlert.close();
                else if (alertDiv.parentElement) alertDiv.remove(); // Fallback removal
            }, duration);
        }
    }

    function getRandomColor() {
        const letters = '0123456789ABCDEF';
        let color = '#';
        for (let i = 0; i < 6; i++) {
            color += letters[Math.floor(Math.random() * 16)];
        }
        return color;
    }

    // Initial population of scenarios and files
    refreshNetworkFiles(); 

});