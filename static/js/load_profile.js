// static/js/load_profile.js - Optimized Version

/**
 * Load Profile Management System
 * Optimized for better performance, maintainability, and user experience
 */

class LoadProfileManager {
    constructor() {
        this.currentVisualizationChart = null;
        this.currentVizProfileData = null;
        this.projectedFutureDataForModal = null;
        this.currentBaseYearPatternData = null;
        this.generationProgressInterval = null;
        
        // Configuration
        this.config = {
            apiEndpoints: {
                monthlyPatterns: '/load_profile/api/monthly_patterns',
                projectedMetrics: '/load_profile/api/projected_future_metrics',
                scenarioDetails: '/demand/api/scenario_details',
                generateProfiles: '/load_profile/api/generate_load_profiles',
                profileMetadata: '/load_profile/api/metadata',
                profileData: '/load_profile/api/data'
            },
            chartDefaults: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                }
            }
        };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.initializeUI();
        this.checkUrlParamsAndLoad();
    }
    
    setupEventListeners() {
        // Form and UI event listeners
        this.bindFormEvents();
        this.bindVisualizationEvents();
        this.bindModalEvents();
    }
    
    bindFormEvents() {
        // Method selection
        const methodRadios = document.querySelectorAll('input[name="method"]');
        methodRadios.forEach(radio => {
            radio.addEventListener('change', (e) => this.toggleMethodOptions(e.target.value));
        });
        
        // Base year selection
        const baseYearSelect = document.getElementById('baseYear');
        if (baseYearSelect) {
            baseYearSelect.addEventListener('change', (e) => this.handleBaseYearChange(e.target.value));
        }
        
        // Forecast scenario selection
        const forecastScenarioSelect = document.getElementById('forecastScenario');
        if (forecastScenarioSelect) {
            forecastScenarioSelect.addEventListener('change', (e) => this.handleScenarioChange(e.target.value));
        }
        
        // Constraints toggle
        const useConstraintsCheckbox = document.getElementById('useConstraints');
        if (useConstraintsCheckbox) {
            useConstraintsCheckbox.addEventListener('change', (e) => this.toggleConstraintOptions(e.target.checked));
        }
        
        // Load factor UI
        this.setupLoadFactorUI();
        
        // File upload
        this.setupFileUpload();
        
        // Generate button
        const generateBtn = document.getElementById('generateProfilesBtn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generateLoadProfiles());
        }
    }
    
    bindVisualizationEvents() {
        // Profile selection for visualization
        const profileSelect = document.getElementById('profileSelect');
        if (profileSelect) {
            profileSelect.addEventListener('change', () => this.loadProfileDataForVisualization());
        }
        
        // Year selection
        const yearSelect = document.getElementById('yearSelect');
        if (yearSelect) {
            yearSelect.addEventListener('change', () => this.handleYearSelectionChange());
        }
        
        // Visualization type
        const vizTypeSelect = document.getElementById('visualizationType');
        if (vizTypeSelect) {
            vizTypeSelect.addEventListener('change', () => this.updateVisualizationPlot());
        }
        
        // Export buttons
        this.bindExportEvents();
    }
    
    bindExportEvents() {
        const exportEvents = [
            { id: 'downloadBtn', handler: () => this.downloadVisualizationImage() },
            { id: 'reportBtn', handler: () => this.generatePdfReport() },
            { id: 'exportCsvBtn', handler: () => this.exportVisualizationData('csv') },
            { id: 'exportExcelBtn', handler: () => this.exportVisualizationData('xlsx') }
        ];
        
        exportEvents.forEach(({ id, handler }) => {
            const element = document.getElementById(id);
            if (element) element.addEventListener('click', handler);
        });
    }
    
    bindModalEvents() {
        // Modal event listeners can be added here
    }
    
    initializeUI() {
        // Initialize Bootstrap components
        this.initializeBootstrapComponents();
        
        // Setup initial UI state
        this.setupInitialState();
        
        // Load initial data
        this.loadInitialData();
    }
    
    initializeBootstrapComponents() {
        // Initialize tabs
        const triggerTabList = document.querySelectorAll('#loadProfileTabs button[data-bs-toggle="tab"]');
        triggerTabList.forEach(triggerEl => new bootstrap.Tab(triggerEl));
        
        // Initialize tooltips
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }
    
    setupInitialState() {
        // Set initial method options visibility
        const currentMethod = document.querySelector('input[name="method"]:checked');
        if (currentMethod) {
            this.toggleMethodOptions(currentMethod.value);
        }
        
        // Set initial constraint options visibility
        const constraintsCheckbox = document.getElementById('useConstraints');
        if (constraintsCheckbox) {
            this.toggleConstraintOptions(constraintsCheckbox.checked);
        }
    }
    
    loadInitialData() {
        // Load scenario info if a scenario is pre-selected
        const forecastScenarioSelect = document.getElementById('forecastScenario');
        if (forecastScenarioSelect && forecastScenarioSelect.value) {
            this.handleScenarioChange(forecastScenarioSelect.value);
        }
        
        // Load base year patterns if base year is selected
        const baseYearSelect = document.getElementById('baseYear');
        if (baseYearSelect && baseYearSelect.value && document.getElementById('baseYearMethod')?.checked) {
            this.handleBaseYearChange(baseYearSelect.value);
        }
    }
    
    checkUrlParamsAndLoad() {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('profile_id')) {
            const profileId = urlParams.get('profile_id');
            this.switchToVisualizationTab();
            
            const profileSelect = document.getElementById('profileSelect');
            if (profileSelect && this.isValidProfileOption(profileSelect, profileId)) {
                profileSelect.value = profileId;
                this.loadProfileDataForVisualization();
            } else {
                this.showNotification(`Profile ID "${profileId}" from URL not found.`, "warning");
            }
        }
    }
    
    // =============================================================================
    // METHOD AND SCENARIO HANDLING
    // =============================================================================
    
    toggleMethodOptions(selectedMethod) {
        const baseYearOptions = document.getElementById('baseYearOptions');
        const mlOptions = document.getElementById('mlOptions');
        
        if (baseYearOptions) {
            baseYearOptions.style.display = selectedMethod === 'base_year' ? 'block' : 'none';
        }
        
        if (mlOptions) {
            mlOptions.style.display = selectedMethod === 'ml_weather' ? 'block' : 'none';
        }
        
        this.clearBaseYearPatternsDisplay();
        
        if (selectedMethod === 'base_year') {
            const baseYearValue = document.getElementById('baseYear')?.value;
            if (baseYearValue) {
                this.handleBaseYearChange(baseYearValue);
            }
        }
    }
    
    toggleConstraintOptions(useConstraints) {
        const constraintOptions = document.getElementById('constraintOptions');
        if (constraintOptions) {
            constraintOptions.style.display = useConstraints ? 'block' : 'none';
        }
    }
    
    handleBaseYearChange(baseYear) {
        if (document.getElementById('baseYearMethod')?.checked && baseYear) {
            this.fetchBaseYearPatterns(baseYear);
        } else {
            this.clearBaseYearPatternsDisplay();
        }
    }
    
    handleScenarioChange(scenarioName) {
        this.fetchAndDisplayScenarioInfo(scenarioName);
        
        // Refresh base year patterns if base year method is selected
        const baseYearSelect = document.getElementById('baseYear');
        if (document.getElementById('baseYearMethod')?.checked && baseYearSelect?.value) {
            this.fetchBaseYearPatterns(baseYearSelect.value);
        }
    }
    
    // =============================================================================
    // BASE YEAR PATTERNS
    // =============================================================================
    
    async fetchBaseYearPatterns(baseYear) {
        const container = this.getOrCreatePatternsContainer();
        this.showLoadingInContainer(container, `Fetching patterns for FY ${baseYear}...`);
        
        try {
            const response = await fetch(`${this.config.apiEndpoints.monthlyPatterns}/${baseYear}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            if (data.status === 'success') {
                this.displayMonthlyPatternsHeatmap(container, baseYear, data);
                this.currentBaseYearPatternData = data;
            } else {
                throw new Error(data.message || 'Failed to fetch patterns');
            }
        } catch (error) {
            console.error('Error fetching base year patterns:', error);
            this.showErrorInContainer(container, `Failed to fetch patterns: ${error.message}`);
        }
    }
    
    getOrCreatePatternsContainer() {
        let container = document.getElementById('baseYearPatternsContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'baseYearPatternsContainer';
            container.className = 'mt-3 p-3 border rounded bg-light shadow-sm';
            document.getElementById('baseYearOptions')?.appendChild(container);
        }
        return container;
    }
    
    showLoadingInContainer(container, message) {
        container.innerHTML = `
            <div class="text-center my-3">
                <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
                <span class="ms-2">${message}</span>
            </div>
        `;
    }
    
    showErrorInContainer(container, message) {
        container.innerHTML = `<div class="alert alert-danger">${message}</div>`;
    }
    
    displayMonthlyPatternsHeatmap(container, baseYear, apiData) {
        const { months, patternData, yearlyLoadFactor, calculatedFromExcel } = apiData;
        
        const tableHtml = this.generatePatternsTable(baseYear, months, patternData, yearlyLoadFactor, calculatedFromExcel);
        container.innerHTML = tableHtml;
    }
    
    generatePatternsTable(baseYear, months, patternData, yearlyLoadFactor, calculatedFromExcel) {
        let html = `
            <h6 class="mb-1">
                Monthly Patterns (Base FY ${baseYear})
                ${calculatedFromExcel ? '<span class="badge bg-info-subtle text-info-emphasis rounded-pill ms-2">From Excel</span>' : ''}
            </h6>
            <p class="small text-muted mb-2">
                Overall Load Factor for FY ${baseYear}: <strong>${yearlyLoadFactor}%</strong>
            </p>
            <div class="table-responsive">
                <table class="table table-sm table-bordered table-hover heatmap-style">
                    <thead class="table-light">
                        <tr>
                            <th>Metric</th>
                            ${months.map(m => `<th>${m}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        for (const metricKey in patternData) {
            html += `<tr><td>${metricKey}</td>`;
            const values = patternData[metricKey];
            const { minValue, maxValue } = this.getValueRange(values);
            
            values.forEach(val => {
                const style = this.generateHeatmapStyle(val, minValue, maxValue, metricKey);
                html += `<td style="${style}">${this.formatValue(val)}</td>`;
            });
            html += `</tr>`;
        }
        
        html += `
                    </tbody>
                </table>
            </div>
            <div class="mt-2 d-flex justify-content-end">
                <button class="btn btn-sm btn-outline-primary" type="button" 
                        onclick="loadProfileManager.showFutureYearsDemandModal(${baseYear})">
                    <i class="fas fa-chart-line me-1"></i> Project Future Metrics
                </button>
            </div>
        `;
        
        return html;
    }
    
    getValueRange(values) {
        const numericValues = values.map(v => parseFloat(v)).filter(v => !isNaN(v));
        return {
            minValue: numericValues.length ? Math.min(...numericValues) : 0,
            maxValue: numericValues.length ? Math.max(...numericValues) : 0
        };
    }
    
    generateHeatmapStyle(value, minValue, maxValue, metricKey) {
        if (maxValue <= minValue || isNaN(parseFloat(value))) {
            return '';
        }
        
        const normalizedValue = (parseFloat(value) - minValue) / (maxValue - minValue);
        const alpha = 0.05 + normalizedValue * 0.65;
        
        const colorMap = {
            'Load Factor': '25, 135, 84',   // Green
            'Max Demand': '220, 53, 69',    // Red
            'Share': '255, 193, 7',         // Yellow
            default: '0, 123, 255'          // Blue
        };
        
        let rgb = colorMap.default;
        for (const [key, color] of Object.entries(colorMap)) {
            if (key !== 'default' && metricKey.includes(key)) {
                rgb = color;
                break;
            }
        }
        
        let style = `background-color: rgba(${rgb}, ${alpha.toFixed(2)});`;
        
        // Adjust text color for readability
        if (normalizedValue > 0.7 && rgb !== colorMap['Share']) {
            style += 'color: white;';
        } else if (rgb === colorMap['Share'] && normalizedValue > 0.5) {
            style += 'color: #333;';
        }
        
        return style;
    }
    
    formatValue(value) {
        return value !== null && value !== undefined ? value : 'N/A';
    }
    
    clearBaseYearPatternsDisplay() {
        const container = document.getElementById('baseYearPatternsContainer');
        if (container) {
            container.innerHTML = '';
        }
    }
    
    // =============================================================================
    // FUTURE YEARS DEMAND MODAL
    // =============================================================================
    
    async showFutureYearsDemandModal(baseYear) {
        const scenario = document.getElementById('forecastScenario')?.value || null;
        const startYear = parseInt(document.getElementById('startYear').value);
        const endYear = parseInt(document.getElementById('endYear').value);
        
        const modal = this.createFutureYearsModal(baseYear, scenario);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        try {
            await this.loadFutureMetricsData(baseYear, startYear, endYear, scenario);
        } catch (error) {
            this.showErrorInModal(error.message);
        }
    }
    
    createFutureYearsModal(baseYear, scenario) {
        const modalId = 'futureYearsDemandModal';
        let modalEl = document.getElementById(modalId);
        if (modalEl) modalEl.remove();
        
        modalEl = document.createElement('div');
        modalEl.className = 'modal fade';
        modalEl.id = modalId;
        modalEl.setAttribute('tabindex', '-1');
        modalEl.innerHTML = this.getFutureYearsModalHTML(baseYear, scenario);
        document.body.appendChild(modalEl);
        
        return modalEl;
    }
    
    getFutureYearsModalHTML(baseYear, scenario) {
        const scenarioText = scenario && scenario !== "null" && scenario !== "undefined" 
            ? scenario.split('/').pop().replace('.csv', '') 
            : "Using 'Total Demand' Excel sheet";
            
        return `
            <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header bg-primary text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-calendar-alt me-2"></i>
                            Projected Future Metrics (from FY ${baseYear} patterns)
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div id="futureMetricsSpinnerModal" class="text-center my-3">
                            <div class="spinner-border text-primary" role="status"></div>
                            <span class="ms-2">Loading projected data...</span>
                        </div>
                        <div id="futureMetricsContentModal" style="display:none;">
                            <div class="row mb-3 align-items-end bg-light p-2 rounded">
                                <div class="col-md-5">
                                    <label for="futureMetricSelectModal" class="form-label form-label-sm">
                                        Metric to Display:
                                    </label>
                                    <select class="form-select form-select-sm" id="futureMetricSelectModal"></select>
                                </div>
                                <div class="col-md-7">
                                    <p class="small text-muted mb-0 text-md-end">
                                        Annual Demand Source: <strong class="text-primary">${scenarioText}</strong>
                                    </p>
                                </div>
                            </div>
                            <div id="futureYearTableContainerModal" class="table-responsive"></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" id="applyProjectionsToLfBtnModal">
                            <i class="fas fa-check-circle me-1"></i>Apply Yearly LFs to Form
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    
    async loadFutureMetricsData(baseYear, startYear, endYear, scenario) {
        const apiUrl = `${this.config.apiEndpoints.projectedMetrics}/${baseYear}/${startYear}/${endYear}${
            scenario && scenario !== "null" && scenario !== "undefined" 
                ? `?forecast_scenario=${encodeURIComponent(scenario)}` 
                : ''
        }`;
        
        try {
            const response = await fetch(apiUrl);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.hideModalSpinner();
            
            if (result.status === 'success' && result.data && result.data.length > 0) {
                this.projectedFutureDataForModal = result.data;
                this.setupFutureMetricsModal();
            } else {
                throw new Error(result.message || 'No projected data available.');
            }
        } catch (error) {
            this.hideModalSpinner();
            throw error;
        }
    }
    
    hideModalSpinner() {
        const spinner = document.getElementById('futureMetricsSpinnerModal');
        const content = document.getElementById('futureMetricsContentModal');
        
        if (spinner) spinner.style.display = 'none';
        if (content) content.style.display = 'block';
    }
    
    showErrorInModal(message) {
        const container = document.getElementById('futureYearTableContainerModal');
        if (container) {
            container.innerHTML = `<div class="alert alert-danger">Error: ${message}</div>`;
        }
    }
    
    setupFutureMetricsModal() {
        const metricSelect = document.getElementById('futureMetricSelectModal');
        const applyButton = document.getElementById('applyProjectionsToLfBtnModal');
        
        if (!metricSelect || !this.projectedFutureDataForModal) return;
        
        // Populate metric dropdown
        this.populateMetricSelect(metricSelect);
        
        // Set default selection and update table
        metricSelect.value = 'loadFactor_Percent';
        metricSelect.addEventListener('change', () => this.updateFutureYearTableInModal());
        
        // Setup apply button
        if (applyButton) {
            applyButton.addEventListener('click', () => this.applyYearlyLoadFactorsFromModal());
        }
        
        this.updateFutureYearTableInModal();
    }
    
    populateMetricSelect(metricSelect) {
        metricSelect.innerHTML = '';
        
        if (this.projectedFutureDataForModal.length > 0) {
            const sampleMetrics = this.projectedFutureDataForModal[0].monthlyData[0];
            Object.keys(sampleMetrics)
                .filter(key => key !== 'month')
                .forEach(key => {
                    const displayName = key.replace(/_/g, ' ').replace(/(GWh|MW|Percent)/, '($1)');
                    metricSelect.add(new Option(displayName, key));
                });
        }
    }
    
    updateFutureYearTableInModal() {
        const selectedMetric = document.getElementById('futureMetricSelectModal').value;
        const container = document.getElementById('futureYearTableContainerModal');
        
        if (!container || !this.projectedFutureDataForModal) return;
        
        const tableHTML = this.generateFutureYearsTable(selectedMetric);
        container.innerHTML = tableHTML;
    }
    
    generateFutureYearsTable(selectedMetric) {
        const data = this.projectedFutureDataForModal;
        const months = data[0].monthlyData.map(md => md.month);
        
        let html = `
            <table class="table table-sm table-bordered table-hover heatmap-style-modal">
                <thead class="table-light">
                    <tr>
                        <th>FY</th>
                        ${months.map(m => `<th>${m}</th>`).join('')}
                        <th>Annual Aggregate</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        // Calculate value range for heatmap
        const allValues = data.flatMap(yd => 
            yd.monthlyData.map(md => parseFloat(md[selectedMetric]))
        ).filter(v => !isNaN(v));
        
        const minValue = allValues.length ? Math.min(...allValues) : 0;
        const maxValue = allValues.length ? Math.max(...allValues) : 0;
        
        data.forEach(yearData => {
            html += `<tr><td>${yearData.year}</td>`;
            
            // Monthly values
            yearData.monthlyData.forEach(monthDetail => {
                const value = parseFloat(monthDetail[selectedMetric]);
                const style = this.generateHeatmapStyle(value, minValue, maxValue, selectedMetric);
                const formattedValue = isNaN(value) ? 'N/A' : this.formatMetricValue(value, selectedMetric);
                html += `<td style="${style}">${formattedValue}</td>`;
            });
            
            // Annual aggregate
            const annualValue = this.calculateAnnualAggregate(yearData, selectedMetric);
            html += `<td class="fw-bold">${annualValue}</td>`;
            
            html += `</tr>`;
        });
        
        html += `</tbody></table>`;
        return html;
    }
    
    formatMetricValue(value, metricKey) {
        if (metricKey.includes('Factor') || metricKey.includes('Percent')) {
            return value.toFixed(1);
        }
        return value.toFixed(2);
    }
    
    calculateAnnualAggregate(yearData, selectedMetric) {
        if (selectedMetric.includes('totalDemand_GWh')) {
            return yearData.annualTotal_GWh !== undefined 
                ? `${yearData.annualTotal_GWh.toFixed(2)} GWh` 
                : "N/A";
        }
        
        if (selectedMetric.includes('maxDemand_MW')) {
            const monthlyMax = Math.max(
                ...yearData.monthlyData.map(md => parseFloat(md[selectedMetric])).filter(v => !isNaN(v))
            );
            return monthlyMax !== -Infinity ? `${monthlyMax.toFixed(2)} MW` : "N/A";
        }
        
        if (selectedMetric.includes('loadFactor_Percent')) {
            return yearData.yearlyLoadFactor_Percent !== undefined 
                ? `${yearData.yearlyLoadFactor_Percent.toFixed(1)}%` 
                : "N/A";
        }
        
        // Average for other metrics
        const validValues = yearData.monthlyData
            .map(md => parseFloat(md[selectedMetric]))
            .filter(v => !isNaN(v));
            
        if (validValues.length === 0) return "N/A";
        
        const average = validValues.reduce((sum, val) => sum + val, 0) / validValues.length;
        const unit = selectedMetric.includes('avgDemand_MW') ? " MW (Avg)" : " (Avg)";
        return `${average.toFixed(2)}${unit}`;
    }
    
    applyYearlyLoadFactorsFromModal() {
        try {
            this.enableLoadFactorImprovements();
            this.clearCustomLoadFactors();
            this.addProjectedLoadFactors();
            this.hideModal();
            this.showNotification("Yearly load factors from projection applied to the form.", "success");
        } catch (error) {
            console.error('Error applying load factors:', error);
            this.showNotification("Could not apply load factors: " + error.message, "danger");
        }
    }
    
    enableLoadFactorImprovements() {
        const toggle = document.getElementById('useImprovedLoadFactors');
        const options = document.getElementById('loadFactorOptions');
        
        if (!toggle || !options) {
            throw new Error('Load factor UI elements not found');
        }
        
        toggle.checked = true;
        options.style.display = 'block';
    }
    
    clearCustomLoadFactors() {
        const container = document.getElementById('customLoadFactorsContainer');
        if (container) {
            container.innerHTML = '';
        }
    }
    
    addProjectedLoadFactors() {
        if (!this.projectedFutureDataForModal) return;
        
        this.projectedFutureDataForModal.forEach(yearData => {
            if (yearData.yearlyLoadFactor_Percent !== undefined) {
                this.addCustomLoadFactorRow(yearData.year, yearData.yearlyLoadFactor_Percent.toFixed(1));
            }
        });
    }
    
    hideModal() {
        const modal = document.getElementById('futureYearsDemandModal');
        if (modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) bsModal.hide();
        }
    }
    
    // =============================================================================
    // SCENARIO INFORMATION
    // =============================================================================
    
    async fetchAndDisplayScenarioInfo(scenarioName) {
        const infoDiv = document.getElementById('scenarioInfo');
        if (!infoDiv) return;
        
        if (!scenarioName || scenarioName === "null" || scenarioName === "undefined" || scenarioName === "") {
            this.displayNoScenarioMessage(infoDiv);
            return;
        }
        
        this.showScenarioLoadingMessage(infoDiv, scenarioName);
        
        try {
            const response = await fetch(`${this.config.apiEndpoints.scenarioDetails}/${scenarioName}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            if (data.status === 'success') {
                this.displayScenarioInfo(infoDiv, data);
            } else {
                throw new Error(data.message || 'Failed to load scenario details');
            }
        } catch (error) {
            console.error("Error fetching scenario details:", error);
            this.displayScenarioError(infoDiv, error.message);
        }
    }
    
    displayNoScenarioMessage(infoDiv) {
        infoDiv.innerHTML = `
            <p class="small text-muted my-1">
                No forecast scenario selected. Annual totals will be based on "Total Demand" sheet in Excel.
            </p>
        `;
        infoDiv.style.display = 'block';
    }
    
    showScenarioLoadingMessage(infoDiv, scenarioName) {
        infoDiv.innerHTML = `
            <div class="text-center my-1">
                <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
                <span class="ms-1">Loading '${scenarioName}' info...</span>
            </div>
        `;
        infoDiv.style.display = 'block';
    }
    
    displayScenarioInfo(infoDiv, data) {
        infoDiv.innerHTML = `
            <ul class="list-unstyled small mb-0">
                <li><strong>Scenario:</strong> <span class="text-primary">${data.scenario_name}</span></li>
                <li><strong>Sectors:</strong> ${data.sectors.length > 0 ? data.sectors.join(', ') : 'N/A'}</li>
                <li><strong>Target Year:</strong> ${data.target_year || 'N/A'}</li>
            </ul>
        `;
    }
    
    displayScenarioError(infoDiv, message) {
        infoDiv.innerHTML = `
            <p class="small text-danger my-1">Failed to load scenario details: ${message}</p>
        `;
    }
    
    // =============================================================================
    // LOAD FACTOR UI MANAGEMENT
    // =============================================================================
    
    setupLoadFactorUI() {
        const constraintOptions = document.getElementById('constraintOptions');
        if (!constraintOptions || document.getElementById('useImprovedLoadFactors')) {
            return; // Already initialized
        }
        
        constraintOptions.insertAdjacentHTML('beforeend', this.getLoadFactorHTML());
        this.bindLoadFactorEvents();
        this.addCustomLoadFactorRow(); // Add initial row
    }
    
    getLoadFactorHTML() {
        return `
            <div class="form-check form-switch mt-3">
                <input class="form-check-input" type="checkbox" id="useImprovedLoadFactors" name="use_improved_load_factors">
                <label class="form-check-label fw-bold" for="useImprovedLoadFactors">
                    Specify Future Year Load Factors
                </label>
            </div>
            <div id="loadFactorOptions" class="mt-2 p-3 border rounded bg-light shadow-sm" style="display: none;">
                <div class="mb-3">
                    <label for="loadFactorImprovement" class="form-label form-label-sm">
                        Default Year-on-Year Improvement (%):
                    </label>
                    <input type="number" class="form-control form-control-sm" id="loadFactorImprovement" 
                           name="load_factor_improvement" value="0.2" min="0" max="5" step="0.1">
                    <div class="form-text form-text-sm">
                        Applied annually if no specific factor is set for a year.
                    </div>
                </div>
                <div class="mb-3">
                    <label class="form-label form-label-sm">Specific Load Factors by Financial Year:</label>
                    <div id="customLoadFactorsContainer" class="mb-2"></div>
                    <button type="button" class="btn btn-outline-secondary btn-sm" id="addLoadFactorRowBtn">
                        <i class="fas fa-plus me-1"></i>Add Year/Factor
                    </button>
                </div>
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="useExcelLoadFactors" name="use_excel_load_factors">
                    <label class="form-check-label form-label-sm" for="useExcelLoadFactors">
                        Prioritize LFs from 'load_factors' Excel sheet
                    </label>
                </div>
                <div class="form-check mt-2">
                    <input class="form-check-input" type="checkbox" id="useMonthlyExcelLoadFactors" name="use_monthly_excel_load_factors">
                    <label class="form-check-label form-label-sm" for="useMonthlyExcelLoadFactors">
                        Apply Monthly LFs from 'monthly_load_factors' Excel sheet
                    </label>
                </div>
            </div>
        `;
    }
    
    bindLoadFactorEvents() {
        const toggle = document.getElementById('useImprovedLoadFactors');
        const addButton = document.getElementById('addLoadFactorRowBtn');
        
        if (toggle) {
            toggle.addEventListener('change', (e) => {
                const options = document.getElementById('loadFactorOptions');
                if (options) {
                    options.style.display = e.target.checked ? 'block' : 'none';
                }
            });
        }
        
        if (addButton) {
            addButton.addEventListener('click', () => this.addCustomLoadFactorRow());
        }
    }
    
    addCustomLoadFactorRow(year = '', factor = '') {
        const container = document.getElementById('customLoadFactorsContainer');
        if (!container) return;
        
        const currentYear = new Date().getFullYear();
        const rowDiv = document.createElement('div');
        rowDiv.className = 'row g-2 mb-2 custom-load-factor-row align-items-center';
        
        rowDiv.innerHTML = `
            <div class="col-md-5">
                <input type="number" class="form-control form-control-sm custom-year" 
                       placeholder="FY (e.g. ${currentYear + 1})" value="${year}" 
                       min="${currentYear - 10}" max="${currentYear + 30}">
            </div>
            <div class="col-md-5">
                <input type="number" class="form-control form-control-sm custom-factor" 
                       placeholder="LF (%)" value="${factor}" min="1" max="99" step="0.1">
            </div>
            <div class="col-md-2 text-end">
                <button type="button" class="btn btn-outline-danger btn-sm remove-lf-row" title="Remove">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </div>
        `;
        
        container.appendChild(rowDiv);
        
        // Bind remove event
        const removeBtn = rowDiv.querySelector('.remove-lf-row');
        if (removeBtn) {
            removeBtn.addEventListener('click', () => rowDiv.remove());
        }
    }
    
    // =============================================================================
    // FILE UPLOAD
    // =============================================================================
    
    setupFileUpload() {
        const replaceFileBtn = document.getElementById('replaceFileBtn');
        const fileInput = document.getElementById('profileFile');
        
        if (!replaceFileBtn || !fileInput) return;
        
        replaceFileBtn.addEventListener('click', (e) => {
            e.preventDefault();
            
            if (fileInput.disabled) {
                // First click - enable file input
                fileInput.disabled = false;
                replaceFileBtn.innerHTML = '<i class="fas fa-upload me-1"></i>Upload New File';
                replaceFileBtn.classList.remove('btn-outline-secondary');
                replaceFileBtn.classList.add('btn-success');
            } else {
                // Second click - submit form
                document.getElementById('uploadForm').submit();
            }
        });
        
        // Set initial button state
        this.setInitialFileUploadState();
    }
    
    setInitialFileUploadState() {
        const fileInput = document.getElementById('profileFile');
        const replaceBtn = document.getElementById('replaceFileBtn');
        
        if (!fileInput || !replaceBtn) return;
        
        const fileExists = fileInput.dataset.exists === "true";
        
        if (fileExists) {
            replaceBtn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Replace Existing File';
            replaceBtn.classList.add('btn-outline-secondary');
            replaceBtn.classList.remove('btn-success');
            fileInput.disabled = true;
        } else {
            replaceBtn.innerHTML = '<i class="fas fa-upload me-1"></i>Upload File';
            replaceBtn.classList.remove('btn-outline-secondary');
            replaceBtn.classList.add('btn-primary');
            fileInput.disabled = false;
        }
    }
    
    // =============================================================================
    // LOAD PROFILE GENERATION
    // =============================================================================
    
    async generateLoadProfiles() {
        if (!this.validateGenerationForm()) {
            return;
        }
        
        const formData = this.prepareFormData();
        this.showGenerationProgress();
        
        try {
            const response = await fetch('/api/generate_load_profiles', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.handleGenerationResponse(data);
        } catch (error) {
            this.handleGenerationError(error);
        } finally {
            this.hideGenerationProgress();
        }
    }
    
    validateGenerationForm() {
        const method = document.querySelector('input[name="method"]:checked')?.value;
        
        if (!method) {
            this.showNotification('Please select a generation method.', 'warning');
            return false;
        }
        
        if (method === 'base_year') {
            const baseYear = document.getElementById('baseYear')?.value;
            if (!baseYear) {
                this.showNotification('Please select a base year.', 'warning');
                return false;
            }
        }
        
        return true;
    }
    
    prepareFormData() {
        const form = document.getElementById('profileOptions');
        const formData = new FormData(form);
        
        // Add checkbox states explicitly
        formData.set('use_constraints', document.getElementById('useConstraints').checked.toString());
        
        const useImprovedLF = document.getElementById('useImprovedLoadFactors').checked;
        formData.set('use_improved_load_factors', useImprovedLF.toString());
        
        if (useImprovedLF) {
            formData.set('use_excel_load_factors', document.getElementById('useExcelLoadFactors').checked.toString());
            formData.set('use_monthly_excel_load_factors', document.getElementById('useMonthlyExcelLoadFactors').checked.toString());
            
            // Collect custom load factors
            const customLFs = this.collectCustomLoadFactors();
            formData.set('custom_load_factors', JSON.stringify(customLFs));
        }
        
        // Handle forecast scenario
        const forecastScenario = formData.get('forecast_scenario');
        if (forecastScenario === "null" || forecastScenario === "undefined" || forecastScenario === "") {
            formData.delete('forecast_scenario');
        }
        
        return formData;
    }
    
    collectCustomLoadFactors() {
        const customLFs = {};
        const rows = document.querySelectorAll('#customLoadFactorsContainer .custom-load-factor-row');
        
        rows.forEach(row => {
            const year = row.querySelector('.custom-year').value;
            const factor = row.querySelector('.custom-factor').value;
            if (year && factor) {
                customLFs[year] = factor;
            }
        });
        
        return customLFs;
    }
    
    showGenerationProgress() {
        const modal = document.getElementById('processingModal');
        if (!modal) return;
        
        const bsModal = bootstrap.Modal.getOrCreateInstance(modal);
        bsModal.show();
        
        this.resetProgressIndicators();
        this.startProgressAnimation();
    }
    
    resetProgressIndicators() {
        const statusEl = document.getElementById('processingStatus');
        const progressEl = document.getElementById('processingProgress');
        const messageEl = document.getElementById('processingMessage');
        
        if (statusEl) statusEl.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Generating Load Profiles...';
        if (progressEl) {
            progressEl.style.width = '0%';
            progressEl.setAttribute('aria-valuenow', '0');
            progressEl.textContent = '0%';
        }
        if (messageEl) messageEl.textContent = 'Initiating process...';
    }
    
    startProgressAnimation() {
        let currentProgress = 0;
        
        this.generationProgressInterval = setInterval(() => {
            currentProgress += Math.floor(Math.random() * 5) + 5;
            currentProgress = Math.min(currentProgress, 95);
            
            const progressEl = document.getElementById('processingProgress');
            const messageEl = document.getElementById('processingMessage');
            
            if (progressEl) {
                progressEl.style.width = `${currentProgress}%`;
                progressEl.setAttribute('aria-valuenow', currentProgress);
                progressEl.textContent = `${currentProgress}%`;
            }
            
            if (messageEl) {
                messageEl.textContent = `Processing... Current step ${Math.ceil(currentProgress / 10)} of 10.`;
            }
            
            if (currentProgress >= 95) {
                clearInterval(this.generationProgressInterval);
            }
        }, 400);
    }
    
    handleGenerationResponse(data) {
        this.completeProgress();
        
        if (data.status === 'success') {
            this.showSuccessModal(data);
            this.refreshGeneratedProfilesList(data.profiles);
            this.showNotification(data.message, 'success');
        } else {
            this.showNotification(data.message || 'Error generating profiles', 'danger');
        }
    }
    
    handleGenerationError(error) {
        console.error('Error generating load profiles:', error);
        this.showNotification('Error: ' + error.message, 'danger');
        
        const statusEl = document.getElementById('processingStatus');
        if (statusEl) {
            statusEl.innerHTML = `<i class="fas fa-times-circle text-danger me-2"></i>Failed: ${error.message}`;
        }
    }
    
    completeProgress() {
        if (this.generationProgressInterval) {
            clearInterval(this.generationProgressInterval);
        }
        
        const progressEl = document.getElementById('processingProgress');
        if (progressEl) {
            progressEl.style.width = '100%';
            progressEl.setAttribute('aria-valuenow', '100');
            progressEl.textContent = '100%';
        }
    }
    
    hideGenerationProgress() {
        const modal = document.getElementById('processingModal');
        if (modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) bsModal.hide();
        }
    }
    
    showSuccessModal(data) {
        const messageEl = document.getElementById('successMessage');
        const detailEl = document.getElementById('profileDetailMessage');
        
        if (messageEl) messageEl.textContent = data.message;
        if (detailEl) detailEl.textContent = data.details || '';
        
        const modal = document.getElementById('successModal');
        if (modal) {
            const bsModal = bootstrap.Modal.getOrCreateInstance(modal);
            bsModal.show();
        }
    }
    
    refreshGeneratedProfilesList(profiles) {
        const container = document.getElementById('generatedProfilesContainer');
        if (!container) {
            window.location.reload();
            return;
        }
        
        this.updateProfilesList(profiles);
        this.updateVisualizationProfileSelect(profiles);
    }
    
    updateProfilesList(profiles) {
        const listContainer = document.getElementById('generatedProfilesList');
        const noProfilesMsg = document.getElementById('noProfilesMessage');
        
        if (!listContainer || !noProfilesMsg) return;
        
        listContainer.innerHTML = '';
        
        if (profiles && profiles.length > 0) {
            profiles.sort((a, b) => b.id.localeCompare(a.id));
            
            profiles.forEach(profile => {
                const listItem = this.createProfileListItem(profile);
                listContainer.appendChild(listItem);
            });
            
            listContainer.style.display = 'block';
            noProfilesMsg.style.display = 'none';
        } else {
            listContainer.style.display = 'none';
            noProfilesMsg.style.display = 'block';
        }
    }
    
    createProfileListItem(profile) {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center flex-wrap';
        
        li.innerHTML = `
            <div class="me-auto">
                <h6 class="mb-0 text-primary">${profile.name}</h6>
                <small class="text-muted d-block">Created: ${profile.created}</small>
                <small class="text-muted d-block">ID: ${profile.id}</small>
            </div>
            <div class="btn-group mt-2 mt-sm-0" role="group">
                <button class="btn btn-sm btn-outline-primary" 
                        onclick="loadProfileManager.viewProfileVisualization('${profile.id}')" title="Visualize">
                    <i class="fas fa-chart-bar"></i> 
                    <span class="d-none d-md-inline">Visualize</span>
                </button>
                <button class="btn btn-sm btn-outline-danger" 
                        onclick="loadProfileManager.deleteGeneratedProfile('${profile.id}', '${profile.name.replace(/'/g, "\\'")}')" title="Delete">
                    <i class="fas fa-trash-alt"></i> 
                    <span class="d-none d-md-inline">Delete</span>
                </button>
            </div>
        `;
        
        return li;
    }
    
    updateVisualizationProfileSelect(profiles) {
        const profileSelect = document.getElementById('profileSelect');
        if (!profileSelect) return;
        
        const currentValue = profileSelect.value;
        profileSelect.innerHTML = '<option value="">- Select a Profile -</option>';
        
        profiles.forEach(profile => {
            profileSelect.add(new Option(profile.name, profile.id));
        });
        
        // Restore selection or select newest
        if (this.isValidProfileOption(profileSelect, currentValue)) {
            profileSelect.value = currentValue;
        } else if (profiles.length > 0) {
            profileSelect.value = profiles[0].id;
            this.loadProfileDataForVisualization();
        }
    }
    
    isValidProfileOption(selectElement, value) {
        return Array.from(selectElement.options).some(opt => opt.value === value);
    }
    
    // =============================================================================
    // PROFILE MANAGEMENT
    // =============================================================================
    
    viewProfileVisualization(profileId) {
        this.switchToVisualizationTab();
        
        const profileSelect = document.getElementById('profileSelect');
        if (profileSelect) {
            profileSelect.value = profileId;
            this.loadProfileDataForVisualization();
        }
        
        this.scrollToVisualization();
    }
    
    switchToVisualizationTab() {
        const vizTabButton = document.getElementById('visualize-tab');
        if (vizTabButton) {
            new bootstrap.Tab(vizTabButton).show();
        }
    }
    
    scrollToVisualization() {
        const vizSection = document.getElementById('visualizationSection');
        if (vizSection) {
            vizSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
    
    deleteGeneratedProfile(profileId, profileName) {
        if (!confirm(`Are you sure you want to delete profile "${profileName}" (ID: ${profileId})? This cannot be undone from the UI.`)) {
            return;
        }
        
        // In a real implementation, this would call a backend API
        this.showNotification(`Simulating deletion for "${profileName}". In a real app, this would call a backend API.`, "warning");
        
        // Remove from UI
        this.removeProfileFromUI(profileId);
    }
    
    removeProfileFromUI(profileId) {
        // Remove from list
        const listItem = Array.from(document.querySelectorAll('#generatedProfilesList li'))
            .find(li => li.innerHTML.includes(profileId));
        if (listItem) listItem.remove();
        
        // Remove from select
        const profileSelect = document.getElementById('profileSelect');
        const optionToRemove = profileSelect?.querySelector(`option[value="${profileId}"]`);
        if (optionToRemove) optionToRemove.remove();
        
        // Update UI state
        if (document.querySelectorAll('#generatedProfilesList li').length === 0) {
            document.getElementById('noProfilesMessage').style.display = 'block';
        }
        
        // Clear visualization if deleted profile was being viewed
        if (profileSelect?.value === profileId) {
            profileSelect.value = "";
            this.loadProfileDataForVisualization();
        }
    }
    
    // =============================================================================
    // VISUALIZATION
    // =============================================================================
    
    async loadProfileDataForVisualization() {
        const profileId = document.getElementById('profileSelect')?.value;
        
        if (!profileId) {
            this.resetVisualizationUI();
            return;
        }
        
        this.showVisualizationLoading();
        
        try {
            const metadata = await this.fetchProfileMetadata(profileId);
            if (metadata) {
                this.updateVisualizationUI(metadata);
                if (metadata.available_years.length > 0) {
                    await this.loadYearData(profileId, metadata.available_years[0]);
                }
            }
        } catch (error) {
            console.error('Error loading profile data:', error);
            this.showNotification("Failed to load profile metadata: " + error.message, "danger");
        } finally {
            this.hideVisualizationLoading();
        }
    }
    
    resetVisualizationUI() {
        const elements = {
            stats: document.getElementById('profileStats'),
            yearSelect: document.getElementById('yearSelect'),
            vizTypeSelect: document.getElementById('visualizationType'),
            dataTableBody: document.getElementById('profileDataTable')?.querySelector('tbody'),
            exportButtons: document.querySelectorAll('#downloadBtn, #reportBtn, #exportCsvBtn, #exportExcelBtn')
        };
        
        if (elements.stats) {
            elements.stats.innerHTML = '<p class="text-muted text-center">Select a profile to view statistics.</p>';
        }
        
        if (elements.yearSelect) {
            elements.yearSelect.innerHTML = '<option value="">-</option>';
            elements.yearSelect.disabled = true;
        }
        
        if (elements.vizTypeSelect) elements.vizTypeSelect.disabled = true;
        
        if (this.currentVisualizationChart) {
            this.currentVisualizationChart.destroy();
            this.currentVisualizationChart = null;
        }
        
        if (elements.dataTableBody) {
            elements.dataTableBody.innerHTML = '<tr><td colspan="4" class="text-center">Select a profile.</td></tr>';
        }
        
        elements.exportButtons.forEach(btn => btn.disabled = true);
        
        this.showNoDataMessage();
    }
    
    showVisualizationLoading() {
        const loadingIndicator = document.getElementById('loadingIndicator');
        const noDataMessage = document.getElementById('noDataMessage');
        
        if (loadingIndicator) loadingIndicator.style.display = 'flex';
        if (noDataMessage) noDataMessage.style.display = 'none';
        
        // Enable export buttons
        document.querySelectorAll('#downloadBtn, #reportBtn, #exportCsvBtn, #exportExcelBtn')
            .forEach(btn => btn.disabled = false);
    }
    
    hideVisualizationLoading() {
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) loadingIndicator.style.display = 'none';
    }
    
    showNoDataMessage() {
        const noDataMessage = document.getElementById('noDataMessage');
        if (noDataMessage) noDataMessage.style.display = 'block';
    }
    
    async fetchProfileMetadata(profileId) {
        const response = await fetch(`${this.config.apiEndpoints.profileMetadata}/${profileId}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        if (data.status !== 'success') {
            throw new Error(data.message || 'Failed to fetch metadata');
        }
        
        return data;
    }
    
    updateVisualizationUI(metadata) {
        this.updateProfileStats(metadata.profile_stats);
        this.updateYearSelect(metadata.available_years);
        this.enableVisualizationControls();
    }
    
    updateProfileStats(stats) {
        const profileStatsDiv = document.getElementById('profileStats');
        if (!profileStatsDiv || !stats) return;
        
        profileStatsDiv.innerHTML = `
            <div class="row g-2">
                <div class="col-md-6">
                    <div class="card shadow-sm h-100">
                        <div class="card-body p-2">
                            <small class="text-body-secondary d-block mb-1">Peak Demand</small>
                            <h6 class="mb-0">${stats.peak_demand?.toFixed(2)} MW</h6>
                            <em class="small text-body-secondary">${new Date(stats.peak_date).toLocaleString()}</em>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card shadow-sm h-100">
                        <div class="card-body p-2">
                            <small class="text-body-secondary d-block mb-1">Average Demand</small>
                            <h6 class="mb-0">${stats.avg_demand?.toFixed(2)} MW</h6>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card shadow-sm h-100">
                        <div class="card-body p-2">
                            <small class="text-body-secondary d-block mb-1">Minimum Demand</small>
                            <h6 class="mb-0">${stats.min_demand?.toFixed(2)} MW</h6>
                            <em class="small text-body-secondary">${new Date(stats.min_date).toLocaleString()}</em>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card shadow-sm h-100">
                        <div class="card-body p-2">
                            <small class="text-body-secondary d-block mb-1">Load Factor</small>
                            <h6 class="mb-0">${stats.load_factor?.toFixed(2)}%</h6>
                        </div>
                    </div>
                </div>
            </div>
            <div class="card shadow-sm mt-2">
                <div class="card-body p-2">
                    <small class="text-body-secondary d-block mb-1">Summary</small>
                    <p class="small mb-0">${stats.summary || 'N/A'}</p>
                </div>
            </div>
        `;
    }
    
    updateYearSelect(availableYears) {
        const yearSelect = document.getElementById('yearSelect');
        if (!yearSelect) return;
        
        yearSelect.innerHTML = availableYears.map(year => `<option value="${year}">${year}</option>`).join('');
        yearSelect.disabled = false;
        
        if (availableYears.length > 0) {
            yearSelect.value = availableYears[0];
        }
    }
    
    enableVisualizationControls() {
        const vizTypeSelect = document.getElementById('visualizationType');
        if (vizTypeSelect) vizTypeSelect.disabled = false;
    }
    
    async handleYearSelectionChange() {
        const profileId = document.getElementById('profileSelect')?.value;
        const year = document.getElementById('yearSelect')?.value;
        
        if (profileId && year) {
            await this.loadYearData(profileId, parseInt(year));
        }
    }
    
    async loadYearData(profileId, year) {
        this.showVisualizationLoading();
        
        try {
            const response = await fetch(`${this.config.apiEndpoints.profileData}/${profileId}/${year}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            if (data.status === 'success') {
                this.currentVizProfileData = data.profile_data;
                this.updateVisualizationPlot();
                this.updateVisualizationDataTable(data.profile_data);
            } else {
                throw new Error(data.message || 'Failed to load year data');
            }
        } catch (error) {
            console.error('Error loading year data:', error);
            this.showNotification("Failed to load yearly data: " + error.message, "danger");
        } finally {
            this.hideVisualizationLoading();
        }
    }
    
    updateVisualizationPlot() {
        if (!this.currentVizProfileData) return;
        
        const vizType = document.getElementById('visualizationType').value;
        const chartConfig = this.prepareChartData(vizType, this.currentVizProfileData);
        
        if (chartConfig) {
            this.renderVisualizationChart(chartConfig.data, chartConfig.options);
        } else if (this.currentVisualizationChart) {
            this.currentVisualizationChart.destroy();
            this.currentVisualizationChart = null;
        }
    }
    
    prepareChartData(vizType, profileData) {
        const prepareMethods = {
            'daily': () => this.prepareDataForDailyView(profileData),
            'weekly': () => this.prepareDataForWeeklyView(profileData),
            'monthly': () => this.prepareDataForMonthlyView(profileData),
            'yearly': () => this.prepareDataForYearlyView(profileData),
            'duration': () => this.prepareDataForDurationCurve(profileData)
        };
        
        const prepareMethod = prepareMethods[vizType] || prepareMethods['weekly'];
        return prepareMethod();
    }
    
    prepareDataForDailyView(profileData) {
        const sampleDayData = profileData.slice(0, 24);
        if (sampleDayData.length === 0) return null;
        
        return {
            data: {
                labels: sampleDayData.map(d => new Date(d.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })),
                datasets: [{
                    label: 'Demand (MW)',
                    data: sampleDayData.map(d => d.demand),
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1,
                    fill: true,
                    backgroundColor: 'rgba(75, 192, 192, 0.2)'
                }]
            },
            options: {
                ...this.config.chartDefaults,
                plugins: {
                    ...this.config.chartDefaults.plugins,
                    title: {
                        display: true,
                        text: `Daily Load Profile (${new Date(sampleDayData[0].timestamp).toLocaleDateString()})`
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Time of Day' } },
                    y: { title: { display: true, text: 'Demand (MW)' }, beginAtZero: true }
                }
            }
        };
    }
    
    prepareDataForWeeklyView(profileData) {
        const sampleWeekData = profileData.slice(0, 24 * 7);
        if (sampleWeekData.length === 0) return null;
        
        return {
            data: {
                labels: sampleWeekData.map(d => new Date(d.timestamp).toLocaleString([], { weekday: 'short', day: 'numeric', hour: 'numeric' })),
                datasets: [{
                    label: 'Demand (MW)',
                    data: sampleWeekData.map(d => d.demand),
                    borderColor: 'rgb(54, 162, 235)',
                    tension: 0.1,
                    fill: true,
                    backgroundColor: 'rgba(54, 162, 235, 0.2)'
                }]
            },
            options: {
                ...this.config.chartDefaults,
                plugins: {
                    ...this.config.chartDefaults.plugins,
                    title: {
                        display: true,
                        text: 'Weekly Load Profile (First Week Sample)'
                    }
                },
                scales: {
                    x: {
                        title: { display: true, text: 'Time' },
                        ticks: { autoSkip: true, maxTicksLimit: 28, maxRotation: 45, minRotation: 30 }
                    },
                    y: { title: { display: true, text: 'Demand (MW)' }, beginAtZero: true }
                }
            }
        };
    }
    
    prepareDataForMonthlyView(profileData) {
        if (profileData.length === 0) return null;
        
        const dailyAgg = {};
        profileData.forEach(d => {
            const dateStr = new Date(d.timestamp).toISOString().split('T')[0];
            if (!dailyAgg[dateStr]) {
                dailyAgg[dateStr] = { sum: 0, count: 0, date: new Date(d.timestamp) };
            }
            dailyAgg[dateStr].sum += d.demand;
            dailyAgg[dateStr].count++;
        });
        
        const dailyAverages = Object.values(dailyAgg)
            .sort((a, b) => a.date - b.date)
            .map(data => ({
                date: data.date.toLocaleDateString([], { month: 'short', day: 'numeric' }),
                avgDemand: data.sum / data.count
            }))
            .slice(0, 31);
        
        return {
            data: {
                labels: dailyAverages.map(d => d.date),
                datasets: [{
                    label: 'Avg. Daily Demand (MW)',
                    data: dailyAverages.map(d => d.avgDemand),
                    borderColor: 'rgb(255, 159, 64)',
                    tension: 0.1,
                    fill: true,
                    backgroundColor: 'rgba(255, 159, 64, 0.2)'
                }]
            },
            options: {
                ...this.config.chartDefaults,
                plugins: {
                    ...this.config.chartDefaults.plugins,
                    title: {
                        display: true,
                        text: 'Monthly Load Profile (Avg. Daily Demand - First Month Sample)'
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Day of Month' } },
                    y: { title: { display: true, text: 'Avg. Demand (MW)' }, beginAtZero: true }
                }
            }
        };
    }
    
    prepareDataForYearlyView(profileData) {
        if (profileData.length === 0) return null;
        
        const monthlyAgg = Array(12).fill(null).map(() => ({ sum: 0, count: 0 }));
        profileData.forEach(d => {
            const monthIdx = new Date(d.timestamp).getMonth();
            monthlyAgg[monthIdx].sum += d.demand;
            monthlyAgg[monthIdx].count++;
        });
        
        const monthlyAverages = monthlyAgg.map(m => m.count > 0 ? m.sum / m.count : 0);
        const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        
        return {
            data: {
                labels: monthLabels,
                datasets: [{
                    label: 'Avg. Monthly Demand (MW)',
                    data: monthlyAverages,
                    borderColor: 'rgb(153, 102, 255)',
                    backgroundColor: 'rgba(153, 102, 255, 0.6)'
                }]
            },
            options: {
                ...this.config.chartDefaults,
                plugins: {
                    ...this.config.chartDefaults.plugins,
                    title: {
                        display: true,
                        text: 'Yearly Load Profile (Avg. Monthly Demand)'
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Month' } },
                    y: { title: { display: true, text: 'Avg. Demand (MW)' }, beginAtZero: true }
                }
            }
        };
    }
    
    prepareDataForDurationCurve(profileData) {
        if (profileData.length === 0) return null;
        
        const sortedDemand = [...profileData.map(d => d.demand)].sort((a, b) => b - a);
        const labels = sortedDemand.map((_, i) => (i / sortedDemand.length * 100).toFixed(1));
        
        return {
            data: {
                labels: labels,
                datasets: [{
                    label: 'Demand (MW)',
                    data: sortedDemand,
                    borderColor: 'rgb(255, 99, 132)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.1
                }]
            },
            options: {
                ...this.config.chartDefaults,
                plugins: {
                    ...this.config.chartDefaults.plugins,
                    title: {
                        display: true,
                        text: 'Load Duration Curve'
                    }
                },
                scales: {
                    x: {
                        title: { display: true, text: 'Percentage of Hours (%)' },
                        ticks: {
                            autoSkip: true,
                            maxTicksLimit: 10,
                            callback: function(value, index, values) {
                                return value + '%';
                            }
                        }
                    },
                    y: { title: { display: true, text: 'Demand (MW)' }, beginAtZero: true }
                }
            }
        };
    }
    
    renderVisualizationChart(chartData, chartOptions) {
        const canvas = document.getElementById('loadProfileChart');
        if (!canvas) return;
        
        if (this.currentVisualizationChart) {
            this.currentVisualizationChart.destroy();
        }
        
        this.currentVisualizationChart = new Chart(canvas, {
            type: chartOptions.type || 'line',
            data: chartData,
            options: chartOptions
        });
    }
    
    updateVisualizationDataTable(profileData) {
        const tableElem = $('#profileDataTable');
        
        // Destroy existing DataTable if it exists
        if ($.fn.DataTable.isDataTable(tableElem)) {
            tableElem.DataTable().clear().destroy();
        }
        
        const tbody = tableElem.find('tbody');
        tbody.empty();
        
        if (!profileData || profileData.length === 0) {
            tbody.append('<tr><td colspan="4" class="text-center text-muted">No data for selected year.</td></tr>');
            return;
        }
        
        const peakValue = Math.max(...profileData.map(d => d.demand), 0);
        
        // Show first 500 rows for performance
        profileData.slice(0, 500).forEach(row => {
            const timestamp = new Date(row.timestamp);
            const percentPeak = peakValue > 0 ? (row.demand / peakValue * 100).toFixed(1) : 0;
            
            let category = 'Low';
            if (percentPeak >= 90) category = 'Peak';
            else if (percentPeak >= 70) category = 'High';
            else if (percentPeak >= 40) category = 'Medium';
            
            tbody.append(`
                <tr>
                    <td>${timestamp.toLocaleString()}</td>
                    <td>${row.demand.toFixed(2)}</td>
                    <td>${percentPeak}%</td>
                    <td>${category}</td>
                </tr>
            `);
        });
        
        if (profileData.length > 500) {
            tbody.append(`
                <tr>
                    <td colspan="4" class="text-center text-muted small">
                        Showing first 500 of ${profileData.length} rows. Export for full data.
                    </td>
                </tr>
            `);
        }
        
        // Initialize DataTable
        tableElem.DataTable({
            pageLength: 10,
            lengthMenu: [10, 25, 50, 100],
            responsive: true,
            destroy: true
        });
    }
    
    // =============================================================================
    // EXPORT FUNCTIONS
    // =============================================================================
    
    downloadVisualizationImage() {
        if (!this.currentVisualizationChart) {
            this.showNotification("No chart to download.", "warning");
            return;
        }
        
        const profileId = document.getElementById('profileSelect')?.value || "profile";
        const year = document.getElementById('yearSelect')?.value || "year";
        const vizType = document.getElementById('visualizationType')?.value || "chart";
        
        const link = document.createElement('a');
        link.download = `load_profile_${profileId}_${year}_${vizType}.png`;
        link.href = this.currentVisualizationChart.toBase64Image('image/png', 1.0);
        link.click();
        
        this.showNotification("Chart image downloaded.", "success");
    }
    
    generatePdfReport() {
        this.showNotification("PDF report generation is complex and usually server-side. This is a placeholder.", "info");
    }
    
    exportVisualizationData(format) {
        if (!this.currentVizProfileData) {
            this.showNotification("No data to export.", "warning");
            return;
        }
        
        const profileId = document.getElementById('profileSelect')?.value || "profile";
        const year = document.getElementById('yearSelect')?.value || "year";
        
        if (format === 'csv') {
            this.exportAsCSV(profileId, year);
        } else if (format === 'xlsx') {
            this.showNotification("XLSX export is best handled server-side. This is a placeholder.", "info");
        } else {
            this.showNotification(`Unsupported export format: ${format}`, "warning");
        }
    }
    
    exportAsCSV(profileId, year) {
        let csvContent = "Timestamp,Demand_MW\n";
        
        this.currentVizProfileData.forEach(row => {
            csvContent += `"${row.timestamp}",${row.demand.toFixed(3)}\n`;
        });
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", `load_profile_data_${profileId}_${year}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }
        
        this.showNotification("Data exported as CSV.", "success");
    }
    
    // =============================================================================
    // UTILITY FUNCTIONS
    // =============================================================================
    
    showNotification(message, type = 'info', duration = 5000) {
        const containerId = 'globalAlertPlaceholder';
        let container = document.getElementById(containerId);
        
        if (!container) {
            container = document.createElement('div');
            container.id = containerId;
            Object.assign(container.style, {
                position: 'fixed',
                top: '20px',
                right: '20px',
                zIndex: '1090',
                width: 'auto',
                maxWidth: '400px'
            });
            document.body.appendChild(container);
        }
        
        const alertId = `alert-${Date.now()}`;
        const alertHtml = `
            <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show shadow-lg" role="alert" style="min-width: 300px;">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        
        container.insertAdjacentHTML('beforeend', alertHtml);
        
        if (duration) {
            setTimeout(() => {
                const alertElement = document.getElementById(alertId);
                if (alertElement) {
                    const bsAlert = bootstrap.Alert.getOrCreateInstance(alertElement);
                    if (bsAlert) bsAlert.close();
                }
            }, duration);
        }
    }
    
    switchToVisualizationIfProfileExists() {
        const vizTabButton = document.getElementById('visualize-tab');
        if (vizTabButton) {
            new bootstrap.Tab(vizTabButton).show();
        }
    }
}

// Global instance and initialization
let loadProfileManager;

document.addEventListener('DOMContentLoaded', function() {
    loadProfileManager = new LoadProfileManager();
});

// Export for global access
window.loadProfileManager = loadProfileManager;