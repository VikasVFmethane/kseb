// static/js/enhanced_load_profile.js - Enhanced Version
// Updated JavaScript for the enhanced load profile generation system

/**
 * Enhanced Load Profile Management System
 * Integrated with robust constraint validation and error handling
 */

class EnhancedLoadProfileManager {
    constructor() {
        this.currentVisualizationChart = null;
        this.currentVizProfileData = null;
        this.projectedFutureDataForModal = null;
        this.currentBaseYearPatternData = null;
        this.generationProgressInterval = null;
        this.validationResults = null;

        // Enhanced configuration with better error handling
        this.config = {
            apiEndpoints: {
                monthlyPatterns: '/load_profile/api/monthly_patterns',
                projectedMetrics: '/load_profile/api/projected_future_metrics',
                scenarioDetails: '/demand/api/scenario_details',
                generateProfiles: '/load_profile/api/generate_load_profiles',
                profileMetadata: '/load_profile/api/metadata',
                profileData: '/load_profile/api/data',
                validateInputFile: '/load_profile/api/validate_input_file'
            },
            validation: {
                yearlyTolerancePct: 0.01,
                monthlyTolerancePct: 0.1,
                loadFactorTolerancePct: 1.0
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
        this.validateInputFileOnLoad();
    }

    setupEventListeners() {
        this.bindFormEvents();
        this.bindVisualizationEvents();
        this.bindModalEvents();
        this.bindValidationEvents();
    }

    bindFormEvents() {
        // Method selection with enhanced validation
        const methodRadios = document.querySelectorAll('input[name="method"]');
        methodRadios.forEach(radio => {
            radio.addEventListener('change', (e) => this.toggleMethodOptions(e.target.value));
        });

        // Base year selection with validation
        const baseYearSelect = document.getElementById('baseYear');
        if (baseYearSelect) {
            baseYearSelect.addEventListener('change', (e) => this.handleBaseYearChange(e.target.value));
        }

        // Forecast scenario selection
        const forecastScenarioSelect = document.getElementById('forecastScenario');
        if (forecastScenarioSelect) {
            forecastScenarioSelect.addEventListener('change', (e) => this.handleScenarioChange(e.target.value));
        }

        // Enhanced constraints toggle
        const useConstraintsCheckbox = document.getElementById('useConstraints');
        if (useConstraintsCheckbox) {
            useConstraintsCheckbox.addEventListener('change', (e) => this.toggleConstraintOptions(e.target.checked));
        }

        // Load factor UI with validation
        this.setupEnhancedLoadFactorUI();

        // File upload with validation
        this.setupEnhancedFileUpload();

        // Generate button with enhanced validation
        const generateBtn = document.getElementById('generateProfilesBtn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generateEnhancedLoadProfiles());
        }

        // Add real-time form validation
        this.setupRealTimeValidation();
    }

    bindValidationEvents() {
        // Add validation button
        const validateBtn = document.getElementById('validateInputBtn');
        if (validateBtn) {
            validateBtn.addEventListener('click', () => this.validateInputFile());
        }
    }

    setupRealTimeValidation() {
        // Year range validation
        const startYearInput = document.getElementById('startYear');
        const endYearInput = document.getElementById('endYear');

        if (startYearInput && endYearInput) {
            [startYearInput, endYearInput].forEach(input => {
                input.addEventListener('blur', () => this.validateYearRange());
            });
        }

        // Load factor validation
        const lfImprovementInput = document.getElementById('loadFactorImprovement');
        if (lfImprovementInput) {
            lfImprovementInput.addEventListener('blur', () => this.validateLoadFactorImprovement());
        }
    }

    validateYearRange() {
        const startYear = parseInt(document.getElementById('startYear')?.value);
        const endYear = parseInt(document.getElementById('endYear')?.value);

        let isValid = true;
        let message = '';

        if (isNaN(startYear) || isNaN(endYear)) {
            isValid = false;
            message = 'Years must be valid numbers';
        } else if (startYear >= endYear) {
            isValid = false;
            message = 'End year must be greater than start year';
        } else if (endYear - startYear > 50) {
            isValid = false;
            message = 'Year range cannot exceed 50 years';
        } else if (startYear < 2020 || endYear > 2070) {
            isValid = false;
            message = 'Years must be between 2020 and 2070';
        }

        this.updateValidationStatus('yearRange', isValid, message);
        return isValid;
    }

    validateLoadFactorImprovement() {
        const lfInput = document.getElementById('loadFactorImprovement');
        if (!lfInput) return true;

        const value = parseFloat(lfInput.value);
        let isValid = true;
        let message = '';

        if (lfInput.value && (isNaN(value) || value < 0 || value > 10)) {
            isValid = false;
            message = 'Load factor improvement must be between 0 and 10%';
        }

        this.updateValidationStatus('loadFactorImprovement', isValid, message);
        return isValid;
    }

    updateValidationStatus(field, isValid, message) {
        const element = document.getElementById(field === 'yearRange' ? 'startYear' : field);
        if (!element) return;

        // Remove existing validation classes
        element.classList.remove('is-valid', 'is-invalid');

        // Add appropriate class
        element.classList.add(isValid ? 'is-valid' : 'is-invalid');

        // Update or create feedback element
        let feedback = element.parentNode.querySelector('.invalid-feedback, .valid-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            element.parentNode.appendChild(feedback);
        }

        feedback.className = isValid ? 'valid-feedback' : 'invalid-feedback';
        feedback.textContent = message;
        feedback.style.display = message ? 'block' : 'none';
    }

    setupEnhancedLoadFactorUI() {
        const constraintOptions = document.getElementById('constraintOptions');
        if (!constraintOptions || document.getElementById('useImprovedLoadFactors')) {
            return; // Already initialized
        }

        constraintOptions.insertAdjacentHTML('beforeend', this.getEnhancedLoadFactorHTML());
        this.bindEnhancedLoadFactorEvents();
        this.addCustomLoadFactorRow(); // Add initial row
    }

    getEnhancedLoadFactorHTML() {
        return `
            <div class="form-check form-switch mt-3">
                <input class="form-check-input" type="checkbox" id="useImprovedLoadFactors" name="use_improved_load_factors">
                <label class="form-check-label fw-bold" for="useImprovedLoadFactors">
                    Enhanced Load Factor Controls
                </label>
                <small class="form-text text-muted d-block">
                    Specify future load factors with strict validation and constraint application
                </small>
            </div>
            <div id="loadFactorOptions" class="mt-2 p-3 border rounded bg-light shadow-sm" style="display: none;">
                <div class="alert alert-info alert-sm">
                    <i class="fas fa-info-circle me-1"></i>
                    Enhanced system ensures load factors are precisely applied while preserving energy totals
                </div>
                
                <div class="mb-3">
                    <label for="loadFactorImprovement" class="form-label form-label-sm">
                        Default Year-on-Year Improvement (%):
                    </label>
                    <input type="number" class="form-control form-control-sm" id="loadFactorImprovement" 
                           name="load_factor_improvement" value="0.2" min="0" max="5" step="0.1">
                    <div class="form-text form-text-sm">
                        Applied annually if no specific factor is set. Enhanced validation ensures realistic values.
                    </div>
                </div>
                
                <div class="mb-3">
                    <label class="form-label form-label-sm">Specific Load Factors by Financial Year:</label>
                    <div id="customLoadFactorsContainer" class="mb-2"></div>
                    <button type="button" class="btn btn-outline-secondary btn-sm" id="addLoadFactorRowBtn">
                        <i class="fas fa-plus me-1"></i>Add Year/Factor
                    </button>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="useExcelLoadFactors" name="use_excel_load_factors">
                            <label class="form-check-label form-label-sm" for="useExcelLoadFactors">
                                Use Excel 'load_factors' sheet
                            </label>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="useMonthlyExcelLoadFactors" name="use_monthly_excel_load_factors">
                            <label class="form-check-label form-label-sm" for="useMonthlyExcelLoadFactors">
                                Apply monthly load factors
                            </label>
                        </div>
                    </div>
                </div>
                
                <div class="mt-2">
                    <small class="text-muted">
                        <strong>Enhanced Features:</strong> Hierarchical constraint application, energy conservation, 
                        and validation with {this.config.validation.loadFactorTolerancePct}% tolerance.
                    </small>
                </div>
            </div>
        `;
    }

    bindEnhancedLoadFactorEvents() {
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
            <div class="col-md-4">
                <input type="number" class="form-control form-control-sm custom-year" 
                       placeholder="FY (e.g. ${currentYear + 1})" value="${year}" 
                       min="${currentYear - 10}" max="${currentYear + 50}">
            </div>
            <div class="col-md-4">
                <input type="number" class="form-control form-control-sm custom-factor" 
                       placeholder="LF (%)" value="${factor}" min="10" max="95" step="0.1">
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-outline-danger btn-sm remove-lf-row" title="Remove">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </div>
            <div class="col-md-2">
                <div class="validation-indicator" style="display: none;">
                    <i class="fas fa-check-circle text-success" title="Valid"></i>
                    <i class="fas fa-exclamation-triangle text-warning" title="Warning" style="display: none;"></i>
                </div>
            </div>
        `;

        container.appendChild(rowDiv);

        // Bind events
        const removeBtn = rowDiv.querySelector('.remove-lf-row');
        const yearInput = rowDiv.querySelector('.custom-year');
        const factorInput = rowDiv.querySelector('.custom-factor');

        if (removeBtn) {
            removeBtn.addEventListener('click', () => rowDiv.remove());
        }

        // Add validation for custom load factor inputs
        if (yearInput && factorInput) {
            [yearInput, factorInput].forEach(input => {
                input.addEventListener('blur', () => this.validateCustomLoadFactorRow(rowDiv));
            });
        }
    }

    validateCustomLoadFactorRow(rowDiv) {
        const yearInput = rowDiv.querySelector('.custom-year');
        const factorInput = rowDiv.querySelector('.custom-factor');
        const indicator = rowDiv.querySelector('.validation-indicator');

        if (!yearInput || !factorInput || !indicator) return;

        const year = parseInt(yearInput.value);
        const factor = parseFloat(factorInput.value);
        const currentYear = new Date().getFullYear();

        let isValid = true;
        let hasWarning = false;
        let message = '';

        // Validate year
        if (yearInput.value && (isNaN(year) || year < currentYear - 10 || year > currentYear + 50)) {
            isValid = false;
            message = 'Invalid year range';
        }

        // Validate load factor
        if (factorInput.value && (isNaN(factor) || factor < 10 || factor > 95)) {
            isValid = false;
            message = 'Load factor must be between 10% and 95%';
        }

        // Check for realistic values
        if (isValid && factor > 85) {
            hasWarning = true;
            message = 'Very high load factor - ensure this is realistic';
        }

        // Update visual indicators
        yearInput.classList.toggle('is-invalid', !isValid && yearInput.value);
        factorInput.classList.toggle('is-invalid', !isValid && factorInput.value);
        yearInput.classList.toggle('is-valid', isValid && yearInput.value);
        factorInput.classList.toggle('is-valid', isValid && factorInput.value);

        // Update indicator
        if (yearInput.value || factorInput.value) {
            indicator.style.display = 'block';
            const successIcon = indicator.querySelector('.fa-check-circle');
            const warningIcon = indicator.querySelector('.fa-exclamation-triangle');

            successIcon.style.display = isValid && !hasWarning ? 'inline' : 'none';
            warningIcon.style.display = hasWarning ? 'inline' : 'none';

            indicator.title = message;
        } else {
            indicator.style.display = 'none';
        }

        return isValid;
    }

    setupEnhancedFileUpload() {
        const replaceFileBtn = document.getElementById('replaceFileBtn');
        const fileInput = document.getElementById('profileFile');

        if (!replaceFileBtn || !fileInput) return;

        replaceFileBtn.addEventListener('click', (e) => {
            e.preventDefault();

            if (fileInput.disabled) {
                // First click - enable file input and show validation info
                fileInput.disabled = false;
                replaceFileBtn.innerHTML = '<i class="fas fa-upload me-1"></i>Upload New File';
                replaceFileBtn.classList.remove('btn-outline-secondary');
                replaceFileBtn.classList.add('btn-success');

                // Show enhanced upload info
                this.showEnhancedUploadInfo();
            } else {
                // Second click - submit form with validation
                if (this.validateFileSelection()) {
                    document.getElementById('uploadForm').submit();
                }
            }
        });

        // Add file selection validation
        if (fileInput) {
            fileInput.addEventListener('change', () => this.validateFileSelection());
        }

        this.setInitialFileUploadState();
    }

    showEnhancedUploadInfo() {
        const helpText = document.getElementById('profileFileHelp');
        if (helpText) {
            helpText.innerHTML = `
                <div class="enhanced-upload-info">
                    <strong>Enhanced Validation Requirements:</strong>
                    <ul class="small mb-1">
                        <li><strong>Required sheets:</strong> Past_Hourly_Demand, Total Demand, max_demand</li>
                        <li><strong>Data validation:</strong> Automatic detection of missing values, gaps, and anomalies</li>
                        <li><strong>Format flexibility:</strong> Supports various column naming conventions</li>
                        <li><strong>Quality checks:</strong> Validates data completeness and consistency</li>
                    </ul>
                </div>
            `;
        }
    }

    validateFileSelection() {
        const fileInput = document.getElementById('profileFile');
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
            return true; // No file selected is OK
        }

        const file = fileInput.files[0];
        let isValid = true;
        let message = '';

        // Check file type
        if (!file.name.toLowerCase().endsWith('.xlsx')) {
            isValid = false;
            message = 'File must be an Excel (.xlsx) file';
        }

        // Check file size (100MB limit)
        if (file.size > 100 * 1024 * 1024) {
            isValid = false;
            message = 'File size must be less than 100MB';
        }

        // Update UI
        fileInput.classList.toggle('is-invalid', !isValid);
        fileInput.classList.toggle('is-valid', isValid);

        let feedback = fileInput.parentNode.querySelector('.invalid-feedback');
        if (!feedback && !isValid) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            fileInput.parentNode.appendChild(feedback);
        }

        if (feedback) {
            feedback.textContent = message;
            feedback.style.display = isValid ? 'none' : 'block';
        }

        return isValid;
    }

    validateInputFileOnLoad() {
        // Automatically validate input file when page loads
        const inputFileExists = document.querySelector('[data-exists="true"]');
        if (inputFileExists) {
            setTimeout(() => this.validateInputFile(), 1000);
        }
    }

    async validateInputFile() {
        try {
            this.showValidationProgress();

            const response = await fetch(this.config.apiEndpoints.validateInputFile);
            const data = await response.json();

            this.hideValidationProgress();

            if (data.status === 'success') {
                this.displayValidationResults(data.validation_results);
            } else {
                this.showNotification(`Validation failed: ${data.message}`, 'danger');
            }

        } catch (error) {
            this.hideValidationProgress();
            console.error('Error validating input file:', error);
            this.showNotification(`Validation error: ${error.message}`, 'danger');
        }
    }

    showValidationProgress() {
        const statusDiv = document.getElementById('processingStatus');
        if (statusDiv) {
            statusDiv.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>
                    <span>Validating input file...</span>
                </div>
            `;
            statusDiv.className = 'alert alert-info';
        }
    }

    hideValidationProgress() {
        const statusDiv = document.getElementById('processingStatus');
        if (statusDiv) {
            statusDiv.innerHTML = '<i class="fas fa-hourglass-start me-2"></i>Ready for input...';
            statusDiv.className = 'alert alert-secondary';
        }
    }

    displayValidationResults(results) {
        const statusDiv = document.getElementById('processingStatus');
        if (!statusDiv) return;

        let overallStatus = 'success';
        let issues = [];

        // Check each validation result
        Object.entries(results).forEach(([key, result]) => {
            if (result.status === 'error') {
                overallStatus = 'error';
                issues.push(`${key}: ${result.message}`);
            }
        });

        if (overallStatus === 'success') {
            statusDiv.innerHTML = `
                <div class="validation-success">
                    <i class="fas fa-check-circle text-success me-2"></i>
                    <strong>Input file validated successfully</strong>
                    <div class="small mt-1">
                        Historical data: ${results.historical_data?.rows || 0} hours, 
                        Annual targets: ${results.annual_targets?.years?.length || 0} years,
                        Monthly peaks: ${results.monthly_peaks?.years_with_peaks?.length || 0} years
                    </div>
                </div>
            `;
            statusDiv.className = 'alert alert-success';
        } else {
            statusDiv.innerHTML = `
                <div class="validation-errors">
                    <i class="fas fa-exclamation-triangle text-warning me-2"></i>
                    <strong>Validation issues found:</strong>
                    <ul class="small mb-0 mt-1">
                        ${issues.map(issue => `<li>${issue}</li>`).join('')}
                    </ul>
                </div>
            `;
            statusDiv.className = 'alert alert-warning';
        }

        this.validationResults = results;
    }

    async generateEnhancedLoadProfiles() {
        // Enhanced validation before generation
        if (!this.validateAllInputs()) {
            return;
        }

        const formData = this.prepareEnhancedFormData();
        this.showEnhancedGenerationProgress();

        try {
            const response = await fetch(this.config.apiEndpoints.generateProfiles, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.handleEnhancedGenerationResponse(data);
        } catch (error) {
            this.handleGenerationError(error);
        } finally {
            this.hideGenerationProgress();
        }
    }

    validateAllInputs() {
        let isValid = true;
        const errors = [];

        // Check method selection
        const method = document.querySelector('input[name="method"]:checked')?.value;
        if (!method) {
            errors.push('Please select a generation method');
            isValid = false;
        }

        // Check base year for base_year method
        if (method === 'base_year') {
            const baseYear = document.getElementById('baseYear')?.value;
            if (!baseYear) {
                errors.push('Please select a base year');
                isValid = false;
            }
        }

        // Validate year range
        if (!this.validateYearRange()) {
            isValid = false;
        }

        // Validate load factor inputs
        if (!this.validateLoadFactorImprovement()) {
            isValid = false;
        }

        // Validate custom load factor rows
        const customRows = document.querySelectorAll('.custom-load-factor-row');
        customRows.forEach(row => {
            if (!this.validateCustomLoadFactorRow(row)) {
                isValid = false;
            }
        });

        // Check if input file validation passed
        if (this.validationResults) {
            const hasErrors = Object.values(this.validationResults).some(result => result.status === 'error');
            if (hasErrors) {
                errors.push('Input file validation failed - please fix file issues first');
                isValid = false;
            }
        }

        if (!isValid) {
            let errorMessage = 'Please fix the following issues:\n' + errors.join('\n');
            this.showNotification(errorMessage, 'warning');
        }

        return isValid;
    }

    prepareEnhancedFormData() {
        const form = document.getElementById('profileOptions');
        const formData = new FormData(form);

        // Add enhanced settings
        formData.set('enhanced_mode', 'true');
        formData.set('use_constraints', document.getElementById('useConstraints').checked.toString());

        const useImprovedLF = document.getElementById('useImprovedLoadFactors').checked;
        formData.set('use_improved_load_factors', useImprovedLF.toString());

        if (useImprovedLF) {
            formData.set('use_excel_load_factors', document.getElementById('useExcelLoadFactors').checked.toString());
            formData.set('use_monthly_excel_load_factors', document.getElementById('useMonthlyExcelLoadFactors').checked.toString());

            // Collect and validate custom load factors
            const customLFs = this.collectAndValidateCustomLoadFactors();
            formData.set('custom_load_factors', JSON.stringify(customLFs));
        }

        // Handle forecast scenario
        const forecastScenario = formData.get('forecast_scenario');
        if (forecastScenario === "null" || forecastScenario === "undefined" || forecastScenario === "") {
            formData.delete('forecast_scenario');
        }

        // Add validation parameters
        formData.set('yearly_tolerance_pct', this.config.validation.yearlyTolerancePct.toString());
        formData.set('monthly_tolerance_pct', this.config.validation.monthlyTolerancePct.toString());
        formData.set('load_factor_tolerance_pct', this.config.validation.loadFactorTolerancePct.toString());

        return formData;
    }

    collectAndValidateCustomLoadFactors() {
        const customLFs = {};
        const rows = document.querySelectorAll('#customLoadFactorsContainer .custom-load-factor-row');

        rows.forEach(row => {
            const yearInput = row.querySelector('.custom-year');
            const factorInput = row.querySelector('.custom-factor');

            if (yearInput && factorInput) {
                const year = yearInput.value;
                const factor = factorInput.value;

                if (year && factor) {
                    const yearInt = parseInt(year);
                    const factorFloat = parseFloat(factor);

                    // Additional validation
                    if (!isNaN(yearInt) && !isNaN(factorFloat) &&
                        factorFloat >= 10 && factorFloat <= 95) {
                        customLFs[yearInt] = factorFloat;
                    }
                }
            }
        });

        return customLFs;
    }

    showEnhancedGenerationProgress() {
        const modal = document.getElementById('processingModal');
        if (!modal) return;

        const bsModal = bootstrap.Modal.getOrCreateInstance(modal);
        bsModal.show();

        // Enhanced progress indicators
        this.resetEnhancedProgressIndicators();
        this.startEnhancedProgressAnimation();
    }

    resetEnhancedProgressIndicators() {
        const statusEl = document.getElementById('processingStatus');
        const progressEl = document.getElementById('processingProgress');
        const messageEl = document.getElementById('processingMessage');

        if (statusEl) statusEl.innerHTML = '<i class="fas fa-cogs fa-spin me-2"></i>Generating Enhanced Load Profiles...';
        if (progressEl) {
            progressEl.style.width = '0%';
            progressEl.setAttribute('aria-valuenow', '0');
            progressEl.textContent = '0%';
        }
        if (messageEl) messageEl.textContent = 'Initializing enhanced generation system...';
    }

    startEnhancedProgressAnimation() {
        const steps = [
            'Loading and validating input data...',
            'Extracting load patterns with advanced algorithms...',
            'Generating initial profile with STL decomposition...',
            'Applying hierarchical constraints...',
            'Enforcing yearly totals with high precision...',
            'Applying monthly peak constraints...',
            'Optimizing load factors while preserving energy...',
            'Performing comprehensive validation...',
            'Formatting output and finalizing...',
            'Enhanced profile generation complete!'
        ];

        let currentStep = 0;
        let currentProgress = 0;

        this.generationProgressInterval = setInterval(() => {
            currentProgress += Math.floor(Math.random() * 8) + 2;
            currentProgress = Math.min(currentProgress, 95);

            const progressEl = document.getElementById('processingProgress');
            const messageEl = document.getElementById('processingMessage');

            if (progressEl) {
                progressEl.style.width = `${currentProgress}%`;
                progressEl.setAttribute('aria-valuenow', currentProgress);
                progressEl.textContent = `${currentProgress}%`;
            }

            // Update step message
            const stepIndex = Math.floor((currentProgress / 95) * steps.length);
            if (stepIndex !== currentStep && stepIndex < steps.length && messageEl) {
                currentStep = stepIndex;
                messageEl.textContent = steps[stepIndex];
            }

            if (currentProgress >= 95) {
                clearInterval(this.generationProgressInterval);
            }
        }, 500);
    }

    handleEnhancedGenerationResponse(data) {
        this.completeProgress();

        if (data.status === 'success') {
            this.showEnhancedSuccessModal(data);
            this.refreshGeneratedProfilesList(data.profiles);

            // Show enhanced success notification
            const message = data.enhanced ?
                'Enhanced load profiles generated with validated constraints!' :
                'Load profiles generated successfully!';
            this.showNotification(message, 'success');
        } else {
            this.showNotification(data.message || 'Error generating enhanced profiles', 'danger');
        }
    }

    showEnhancedSuccessModal(data) {
        const messageEl = document.getElementById('successMessage');
        const detailEl = document.getElementById('profileDetailMessage');

        if (messageEl) {
            messageEl.textContent = data.enhanced ?
                'Enhanced load profiles generated with strict constraint validation!' :
                data.message;
        }

        if (detailEl) {
            const details = data.enhanced ?
                `Enhanced features applied: Hierarchical constraints, energy conservation, 
                 load factor optimization, and comprehensive validation with ${this.config.validation.yearlyTolerancePct}% yearly tolerance.` :
                (data.details || '');
            detailEl.textContent = details;
        }

        const modal = document.getElementById('successModal');
        if (modal) {
            const bsModal = bootstrap.Modal.getOrCreateInstance(modal);
            bsModal.show();
        }
    }

    // Enhanced visualization methods
    updateVisualizationDataTable(profileData) {
        const tableElement = document.getElementById('profileDataTable');

        if (!tableElement) {
            console.error('Profile data table element not found');
            return;
        }

        // Enhanced data validation and cleaning
        const cleanedData = this.performEnhancedDataValidation(profileData);

        if (cleanedData.length === 0) {
            this.showTableError('No valid data found after enhanced validation');
            return;
        }

        // Destroy existing DataTable
        if ($.fn.DataTable.isDataTable(tableElement)) {
            try {
                $(tableElement).DataTable().clear().destroy();
            } catch (e) {
                console.warn('Error destroying existing DataTable:', e);
            }
        }

        const tbody = tableElement.querySelector('tbody');
        if (!tbody) {
            console.error('Table tbody not found');
            return;
        }

        // Calculate enhanced statistics
        const stats = this.calculateEnhancedStatistics(cleanedData);

        // Generate enhanced table rows
        const rowsHtml = this.generateEnhancedTableRows(cleanedData, stats);
        tbody.innerHTML = rowsHtml;

        // Initialize enhanced DataTable
        this.initializeEnhancedDataTable(tableElement, cleanedData.length);
    }

    performEnhancedDataValidation(rawData) {
        if (!rawData || !Array.isArray(rawData)) {
            console.error('Invalid profile data: not an array');
            return [];
        }

        const cleanedData = [];
        const validationStats = {
            totalRows: rawData.length,
            validRows: 0,
            invalidTimestamps: 0,
            invalidDemands: 0,
            negativeValues: 0,
            extremeValues: 0
        };

        rawData.forEach((row, index) => {
            try {
                if (!row || typeof row !== 'object') {
                    return;
                }

                // Enhanced timestamp validation
                if (!row.timestamp) {
                    validationStats.invalidTimestamps++;
                    return;
                }

                const timestamp = new Date(row.timestamp);
                if (isNaN(timestamp.getTime())) {
                    validationStats.invalidTimestamps++;
                    return;
                }

                // Enhanced demand validation
                if (row.demand === undefined || row.demand === null) {
                    validationStats.invalidDemands++;
                    return;
                }

                const demandValue = parseFloat(row.demand);
                if (isNaN(demandValue)) {
                    validationStats.invalidDemands++;
                    return;
                }

                // Check for negative values
                if (demandValue < 0) {
                    validationStats.negativeValues++;
                    return;
                }

                // Check for extreme values (enhanced detection)
                if (demandValue > 1000000) { // > 1 million MW
                    validationStats.extremeValues++;
                    // Still include but flag for review
                }

                cleanedData.push({
                    timestamp: row.timestamp,
                    demand: demandValue,
                    originalIndex: index
                });

                validationStats.validRows++;

            } catch (e) {
                console.warn(`Enhanced validation error at row ${index}:`, e);
            }
        });

        // Log enhanced validation statistics
        console.log('Enhanced Data Validation Results:', validationStats);

        if (validationStats.validRows / validationStats.totalRows < 0.9) {
            console.warn(`Low data quality: only ${(validationStats.validRows / validationStats.totalRows * 100).toFixed(1)}% of rows are valid`);
        }

        return cleanedData;
    }

    calculateEnhancedStatistics(data) {
        const demands = data.map(d => d.demand);

        return {
            count: data.length,
            min: Math.min(...demands),
            max: Math.max(...demands),
            mean: demands.reduce((sum, val) => sum + val, 0) / demands.length,
            median: this.calculateMedian(demands),
            std: this.calculateStandardDeviation(demands),
            q25: this.calculatePercentile(demands, 25),
            q75: this.calculatePercentile(demands, 75)
        };
    }

    calculateMedian(values) {
        const sorted = [...values].sort((a, b) => a - b);
        const mid = Math.floor(sorted.length / 2);
        return sorted.length % 2 === 0 ?
            (sorted[mid - 1] + sorted[mid]) / 2 :
            sorted[mid];
    }

    calculateStandardDeviation(values) {
        const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
        const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
        return Math.sqrt(variance);
    }

    calculatePercentile(values, percentile) {
        const sorted = [...values].sort((a, b) => a - b);
        const index = (percentile / 100) * (sorted.length - 1);
        const lower = Math.floor(index);
        const upper = Math.ceil(index);
        const weight = index % 1;

        return sorted[lower] * (1 - weight) + sorted[upper] * weight;
    }

    generateEnhancedTableRows(data, stats) {
        const displayData = data.slice(0, 1000); // Limit for performance
        let rowsHtml = '';

        displayData.forEach((row, index) => {
            try {
                const timestamp = new Date(row.timestamp);
                const demand = row.demand;

                // Enhanced formatting
                const formattedTimestamp = timestamp.toLocaleString('en-US', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false
                });

                // Enhanced categorization
                const percentPeak = ((demand / stats.max) * 100).toFixed(1);
                const category = this.categorizeEnhancedDemand(demand, stats);
                const formattedDemand = demand.toFixed(3);

                // Enhanced styling based on statistics
                const rowClass = this.getEnhancedRowClass(demand, stats);

                rowsHtml += `
                    <tr class="${rowClass}">
                        <td>${formattedTimestamp}</td>
                        <td class="text-end">${formattedDemand}</td>
                        <td class="text-end">${percentPeak}%</td>
                        <td><span class="badge ${this.getCategoryBadgeClass(category)}">${category}</span></td>
                    </tr>
                `;
            } catch (e) {
                console.warn(`Error formatting enhanced row ${index}:`, e);
            }
        });

        // Add enhanced summary row if data was truncated
        if (data.length > displayData.length) {
            rowsHtml += `
                <tr class="table-info">
                    <td colspan="4" class="text-center small">
                        <i class="fas fa-info-circle me-1"></i>
                        Showing first ${displayData.length} of ${data.length} rows. 
                        Enhanced validation passed ${data.length} hours.
                        Export full data using the export buttons above.
                    </td>
                </tr>
            `;
        }

        return rowsHtml;
    }

    categorizeEnhancedDemand(demand, stats) {
        const percentOfMax = (demand / stats.max) * 100;

        if (percentOfMax >= 95) return 'Peak';
        if (percentOfMax >= 85) return 'Very High';
        if (percentOfMax >= 70) return 'High';
        if (percentOfMax >= 50) return 'Medium-High';
        if (percentOfMax >= 30) return 'Medium';
        if (percentOfMax >= 15) return 'Low-Medium';
        return 'Low';
    }

    getEnhancedRowClass(demand, stats) {
        const percentOfMax = (demand / stats.max) * 100;

        if (percentOfMax >= 95) return 'table-danger';
        if (percentOfMax >= 85) return 'table-warning';
        if (percentOfMax <= 10) return 'table-light';
        return '';
    }

    getCategoryBadgeClass(category) {
        const classes = {
            'Peak': 'bg-danger',
            'Very High': 'bg-warning text-dark',
            'High': 'bg-info',
            'Medium-High': 'bg-primary',
            'Medium': 'bg-secondary',
            'Low-Medium': 'bg-light text-dark',
            'Low': 'bg-dark'
        };
        return classes[category] || 'bg-secondary';
    }

    initializeEnhancedDataTable(tableElement, dataLength) {
        try {
            $(tableElement).DataTable({
                pageLength: 25,
                lengthMenu: [10, 25, 50, 100],
                responsive: true,
                destroy: true,
                searching: true,
                ordering: true,
                info: true,
                autoWidth: false,
                language: {
                    emptyTable: "No enhanced data available",
                    zeroRecords: "No matching records found",
                    info: "Showing _START_ to _END_ of _TOTAL_ validated entries",
                    infoFiltered: "(filtered from _MAX_ total validated entries)"
                },
                columnDefs: [
                    {
                        targets: [1], // Demand column
                        type: 'num',
                        render: function (data, type, row) {
                            if (type === 'display') {
                                return parseFloat(data).toFixed(3);
                            }
                            return data;
                        }
                    },
                    {
                        targets: [2], // Percentage column
                        type: 'num',
                        render: function (data, type, row) {
                            if (type === 'display') {
                                return data;
                            }
                            return parseFloat(data.replace('%', ''));
                        }
                    }
                ],
                order: [[0, 'asc']], // Sort by timestamp ascending
                drawCallback: function () {
                    // Add enhanced tooltips
                    $('[data-bs-toggle="tooltip"]').tooltip();
                }
            });

            console.log(`Enhanced DataTable initialized successfully with ${dataLength} validated rows`);

        } catch (error) {
            console.error('Error initializing enhanced DataTable:', error);
            this.showTableError('Table sorting and filtering unavailable due to initialization error.');
        }
    }

    showTableError(message) {
        const tbody = document.querySelector('#profileDataTable tbody');
        if (tbody) {
            tbody.innerHTML = `
                <tr class="table-danger">
                    <td colspan="4" class="text-center">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        ${message}
                    </td>
                </tr>
            `;
        }
    }

    // Enhanced notification system
    showNotification(message, type = 'info', duration = 5000) {
        const containerId = 'enhancedAlertPlaceholder';
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
                maxWidth: '450px'
            });
            document.body.appendChild(container);
        }

        const alertId = `enhanced-alert-${Date.now()}`;
        const iconMap = {
            'success': 'fa-check-circle',
            'danger': 'fa-exclamation-triangle',
            'warning': 'fa-exclamation-circle',
            'info': 'fa-info-circle'
        };

        const alertHtml = `
            <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show shadow-lg border-0" role="alert" style="min-width: 320px;">
                <div class="d-flex align-items-start">
                    <i class="fas ${iconMap[type] || 'fa-info-circle'} me-2 mt-1"></i>
                    <div class="flex-grow-1">
                        <div class="fw-bold small">Enhanced Load Profile System</div>
                        <div>${message}</div>
                    </div>
                </div>
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

    // Override existing methods to maintain compatibility
    bindVisualizationEvents() {
        // Enhanced visualization event binding
        const profileSelect = document.getElementById('profileSelect');
        if (profileSelect) {
            profileSelect.addEventListener('change', () => this.loadProfileDataForVisualization());
        }

        const yearSelect = document.getElementById('yearSelect');
        if (yearSelect) {
            yearSelect.addEventListener('change', () => this.handleYearSelectionChange());
        }

        const vizTypeSelect = document.getElementById('visualizationType');
        if (vizTypeSelect) {
            vizTypeSelect.addEventListener('change', () => this.updateVisualizationPlot());
        }

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
        // Enhanced modal event handling
    }

    initializeUI() {
        this.initializeBootstrapComponents();
        this.setupInitialState();
        this.loadInitialData();
        this.addEnhancedUIElements();
    }

    addEnhancedUIElements() {
        // Add enhanced UI elements
        const statusDiv = document.getElementById('processingStatus');
        if (statusDiv) {
            // Add validation button if it doesn't exist
            if (!document.getElementById('validateInputBtn')) {
                const validateBtn = document.createElement('button');
                validateBtn.id = 'validateInputBtn';
                validateBtn.className = 'btn btn-sm btn-outline-primary ms-2';
                validateBtn.innerHTML = '<i class="fas fa-check-circle me-1"></i>Validate Input';
                validateBtn.title = 'Validate input file structure and data quality';
                statusDiv.parentNode.appendChild(validateBtn);
            }
        }
    }

    initializeBootstrapComponents() {
        // Enhanced Bootstrap component initialization
        const triggerTabList = document.querySelectorAll('#loadProfileTabs button[data-bs-toggle="tab"]');
        triggerTabList.forEach(triggerEl => new bootstrap.Tab(triggerEl));

        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }

    setupInitialState() {
        const currentMethod = document.querySelector('input[name="method"]:checked');
        if (currentMethod) {
            this.toggleMethodOptions(currentMethod.value);
        }

        const constraintsCheckbox = document.getElementById('useConstraints');
        if (constraintsCheckbox) {
            this.toggleConstraintOptions(constraintsCheckbox.checked);
        }
    }

    loadInitialData() {
        const forecastScenarioSelect = document.getElementById('forecastScenario');
        if (forecastScenarioSelect && forecastScenarioSelect.value) {
            this.handleScenarioChange(forecastScenarioSelect.value);
        }

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

    // Maintain compatibility with existing methods
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

    clearBaseYearPatternsDisplay() {
        const container = document.getElementById('baseYearPatternsContainer');
        if (container) {
            container.innerHTML = '';
        }
    }

    // Placeholder methods for maintaining compatibility - implement as needed
    handleBaseYearChange(baseYear) {
        if (document.getElementById('baseYearMethod')?.checked && baseYear) {
            this.fetchBaseYearPatterns(baseYear);
        } else {
            this.clearBaseYearPatternsDisplay();
        }
    }

    handleScenarioChange(scenarioName) {
        this.fetchAndDisplayScenarioInfo(scenarioName);
    }

    async fetchBaseYearPatterns(baseYear) {
        // Implementation similar to original but with enhanced error handling
        // ... (implement based on original fetchBaseYearPatterns)
    }

    async fetchAndDisplayScenarioInfo(scenarioName) {
        // Implementation similar to original but with enhanced error handling
        // ... (implement based on original fetchAndDisplayScenarioInfo)
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

    // Additional methods for maintaining compatibility
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

    handleGenerationError(error) {
        console.error('Error generating enhanced load profiles:', error);
        this.showNotification('Error: ' + error.message, 'danger');

        const statusEl = document.getElementById('processingStatus');
        if (statusEl) {
            statusEl.innerHTML = `<i class="fas fa-times-circle text-danger me-2"></i>Enhanced generation failed: ${error.message}`;
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
                const listItem = this.createEnhancedProfileListItem(profile);
                listContainer.appendChild(listItem);
            });

            listContainer.style.display = 'block';
            noProfilesMsg.style.display = 'none';
        } else {
            listContainer.style.display = 'none';
            noProfilesMsg.style.display = 'block';
        }
    }

    createEnhancedProfileListItem(profile) {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center flex-wrap';

        li.innerHTML = `
            <div class="me-auto">
                <h6 class="mb-0 text-primary d-flex align-items-center">
                    <i class="fas fa-chart-line me-2"></i>
                    ${profile.name}
                    <span class="badge bg-success ms-2 small">Enhanced</span>
                </h6>
                <small class="text-muted d-block">Created: ${profile.created}</small>
                <small class="text-muted d-block">ID: ${profile.id}</small>
            </div>
            <div class="btn-group mt-2 mt-sm-0" role="group">
                <button class="btn btn-sm btn-outline-primary" 
                        onclick="enhancedLoadProfileManager.viewProfileVisualization('${profile.id}')" 
                        title="Visualize Enhanced Profile">
                    <i class="fas fa-chart-bar"></i> 
                    <span class="d-none d-md-inline">Visualize</span>
                </button>
                <button class="btn btn-sm btn-outline-info" 
                        onclick="enhancedLoadProfileManager.showProfileValidation('${profile.id}')" 
                        title="View Validation Results">
                    <i class="fas fa-check-circle"></i> 
                    <span class="d-none d-md-inline">Validate</span>
                </button>
                <button class="btn btn-sm btn-outline-danger" 
                        onclick="enhancedLoadProfileManager.deleteGeneratedProfile('${profile.id}', '${profile.name.replace(/'/g, "\\'")}')" 
                        title="Delete Profile">
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
        profileSelect.innerHTML = '<option value="">- Select an Enhanced Profile -</option>';

        profiles.forEach(profile => {
            const option = new Option(profile.name + ' (Enhanced)', profile.id);
            profileSelect.add(option);
        });

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

    showProfileValidation(profileId) {
        // Show enhanced validation results for a specific profile
        this.showNotification(`Enhanced validation for profile ${profileId} - feature coming soon!`, 'info');
    }

    deleteGeneratedProfile(profileId, profileName) {
        if (!confirm(`Are you sure you want to delete enhanced profile "${profileName}" (ID: ${profileId})? This cannot be undone.`)) {
            return;
        }

        this.showNotification(`Deleting enhanced profile "${profileName}". In a real app, this would call a backend API.`, "warning");
        this.removeProfileFromUI(profileId);
    }

    removeProfileFromUI(profileId) {
        const listItem = Array.from(document.querySelectorAll('#generatedProfilesList li'))
            .find(li => li.innerHTML.includes(profileId));
        if (listItem) listItem.remove();

        const profileSelect = document.getElementById('profileSelect');
        const optionToRemove = profileSelect?.querySelector(`option[value="${profileId}"]`);
        if (optionToRemove) optionToRemove.remove();

        if (document.querySelectorAll('#generatedProfilesList li').length === 0) {
            document.getElementById('noProfilesMessage').style.display = 'block';
        }

        if (profileSelect?.value === profileId) {
            profileSelect.value = "";
            this.loadProfileDataForVisualization();
        }
    }

    // Placeholder implementations for visualization methods
    async loadProfileDataForVisualization() {
        // Implementation similar to original but with enhanced error handling
        const profileId = document.getElementById('profileSelect')?.value;
        if (!profileId) {
            this.resetVisualizationUI();
            return;
        }
        // ... implement based on original
    }

    resetVisualizationUI() {
        // Implementation similar to original
        // ... implement based on original
    }

    handleYearSelectionChange() {
        // Implementation similar to original
        // ... implement based on original
    }

    updateVisualizationPlot() {
        // Implementation similar to original
        // ... implement based on original
    }

    downloadVisualizationImage() {
        // Implementation similar to original
        // ... implement based on original
    }

    generatePdfReport() {
        this.showNotification("Enhanced PDF report generation is available in the full system.", "info");
    }

    exportVisualizationData(format) {
        // Implementation similar to original but with enhanced features
        // ... implement based on original
    }

    switchToVisualizationIfProfileExists() {
        const vizTabButton = document.getElementById('visualize-tab');
        if (vizTabButton) {
            new bootstrap.Tab(vizTabButton).show();
        }
    }


    // =============================================================================
    // FUTURE YEAR PATTERNS DISPLAY
    // =============================================================================

    async showFutureYearsDemandModal(baseYear) {
        /**
         * Show modal with future year patterns based on base year
         */
        try {
            // Get current form values for year range
            const startYear = parseInt(document.getElementById('startYear')?.value) || new Date().getFullYear();
            const endYear = parseInt(document.getElementById('endYear')?.value) || startYear + 14;
            const forecastScenario = document.getElementById('forecastScenario')?.value;

            // Validate year range
            if (endYear <= startYear) {
                this.showNotification('End year must be greater than start year', 'warning');
                return;
            }

            if (endYear - startYear > 20) {
                this.showNotification('Year range too large. Maximum 20 years for pattern display.', 'warning');
                return;
            }

            // Show loading modal
            this.showFuturePatternsModal(baseYear, startYear, endYear, true);

            // Fetch future patterns
            await this.fetchAndDisplayFuturePatterns(baseYear, startYear, endYear, forecastScenario);

        } catch (error) {
            console.error('Error showing future years demand modal:', error);
            this.showNotification(`Error loading future patterns: ${error.message}`, 'danger');
        }
    }

    showFuturePatternsModal(baseYear, startYear, endYear, isLoading = false) {
        /**
         * Create and show the future patterns modal
         */
        // Remove existing modal if present
        const existingModal = document.getElementById('futurePatternsModal');
        if (existingModal) {
            existingModal.remove();
        }

        // Create modal HTML
        const modalHtml = `
            <div class="modal fade" id="futurePatternsModal" tabindex="-1" 
                 aria-labelledby="futurePatternsModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-xl modal-dialog-scrollable">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="futurePatternsModalLabel">
                                <i class="fas fa-chart-line me-2"></i>
                                Future Year Monthly Patterns (Base: FY ${baseYear})
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div id="futurePatternsContent">
                                ${isLoading ? this.getFuturePatternsLoadingHTML() : ''}
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">
                                Close
                            </button>
                            <button type="button" class="btn btn-primary" id="exportFuturePatternsBtn" disabled>
                                <i class="fas fa-download me-1"></i>Export to Excel
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('futurePatternsModal'));
        modal.show();

        // Bind export button
        document.getElementById('exportFuturePatternsBtn')?.addEventListener('click', () => {
            this.exportFuturePatterns(baseYear, startYear, endYear);
        });
    }

    getFuturePatternsLoadingHTML() {
        return `
            <div class="text-center py-5">
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <h6>Calculating Future Year Patterns</h6>
                <p class="text-muted">
                    Applying base year patterns to projected annual demands...
                </p>
                <div class="progress mx-auto" style="width: 60%;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                         role="progressbar" style="width: 45%"></div>
                </div>
            </div>
        `;
    }

    async fetchAndDisplayFuturePatterns(baseYear, startYear, endYear, forecastScenario) {
        /**
         * Fetch future patterns data and display in modal
         */
        try {
            // Build API URL
            let apiUrl = `${this.config.apiEndpoints.projectedMetrics}/${baseYear}/${startYear}/${endYear}`;
            if (forecastScenario && forecastScenario !== "null" && forecastScenario !== "undefined") {
                apiUrl += `?forecast_scenario=${encodeURIComponent(forecastScenario)}`;
            }

            const response = await fetch(apiUrl);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.status === 'success') {
                this.displayFuturePatterns(baseYear, startYear, endYear, data, forecastScenario);
                
                // Enable export button
                const exportBtn = document.getElementById('exportFuturePatternsBtn');
                if (exportBtn) {
                    exportBtn.disabled = false;
                    exportBtn.onclick = () => this.exportFuturePatterns(baseYear, startYear, endYear, data);
                }
            } else {
                throw new Error(data.message || 'Failed to fetch future patterns');
            }

        } catch (error) {
            console.error('Error fetching future patterns:', error);
            this.showFuturePatternsError(error.message);
        }
    }

    displayFuturePatterns(baseYear, startYear, endYear, apiData, forecastScenario) {
        /**
         * Display future patterns in the modal content
         */
        const content = document.getElementById('futurePatternsContent');
        if (!content) return;

        const { data: projectedData, baseYearMonths, enhanced } = apiData;
        
        // Create comprehensive display
        let html = `
            <div class="future-patterns-display">
                <!-- Header Information -->
                <div class="alert alert-info">
                    <div class="row">
                        <div class="col-md-8">
                            <h6 class="alert-heading mb-2">
                                <i class="fas fa-info-circle me-1"></i>Future Patterns Overview
                            </h6>
                            <p class="mb-1">
                                <strong>Base Year:</strong> FY ${baseYear} &nbsp;&nbsp;
                                <strong>Projection Period:</strong> FY ${startYear} - ${endYear} &nbsp;&nbsp;
                                <strong>Years:</strong> ${projectedData.length}
                            </p>
                            ${forecastScenario ? `<p class="mb-0"><strong>Scenario:</strong> ${forecastScenario}</p>` : ''}
                            ${enhanced ? '<span class="badge bg-success">Enhanced Generation</span>' : ''}
                        </div>
                        <div class="col-md-4 text-end">
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-primary" onclick="enhancedLoadProfileManager.showYearlyComparison()">
                                    <i class="fas fa-chart-bar me-1"></i>Yearly View
                                </button>
                                <button class="btn btn-outline-secondary" onclick="enhancedLoadProfileManager.showMonthlyHeatmap()">
                                    <i class="fas fa-table me-1"></i>Heatmap
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Navigation Tabs for Different Views -->
                <ul class="nav nav-tabs mb-3" id="futurePatternsTabsNav" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="yearly-summary-tab" data-bs-toggle="tab" 
                                data-bs-target="#yearly-summary" type="button" role="tab">
                            <i class="fas fa-chart-line me-1"></i>Yearly Summary
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="monthly-heatmap-tab" data-bs-toggle="tab" 
                                data-bs-target="#monthly-heatmap" type="button" role="tab">
                            <i class="fas fa-th me-1"></i>Monthly Heatmap
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="trend-analysis-tab" data-bs-toggle="tab" 
                                data-bs-target="#trend-analysis" type="button" role="tab">
                            <i class="fas fa-trending-up me-1"></i>Trend Analysis
                        </button>
                    </li>
                </ul>

                <!-- Tab Content -->
                <div class="tab-content" id="futurePatternsTabsContent">
                    ${this.generateYearlySummaryTab(projectedData, baseYearMonths)}
                    ${this.generateMonthlyHeatmapTab(projectedData, baseYearMonths)}
                    ${this.generateTrendAnalysisTab(projectedData, baseYearMonths)}
                </div>
            </div>
        `;

        content.innerHTML = html;

        // Initialize Bootstrap tabs
        const tabList = content.querySelectorAll('[data-bs-toggle="tab"]');
        tabList.forEach(tab => new bootstrap.Tab(tab));

        // Store data for export
        this.currentFuturePatternsData = {
            baseYear,
            startYear,
            endYear,
            projectedData,
            baseYearMonths,
            forecastScenario
        };
    }

    generateYearlySummaryTab(projectedData, months) {
        /**
         * Generate yearly summary tab content
         */
        let html = `
            <div class="tab-pane fade show active" id="yearly-summary" role="tabpanel">
                <div class="row mb-3">
                    <div class="col-md-12">
                        <h6>Annual Demand and Load Factor Progression</h6>
                        <div class="table-responsive">
                            <table class="table table-sm table-striped table-hover">
                                <thead class="table-dark">
                                    <tr>
                                        <th>Financial Year</th>
                                        <th>Annual Total (GWh)</th>
                                        <th>Peak Month</th>
                                        <th>Peak Demand (MW)</th>
                                        <th>Load Factor (%)</th>
                                        <th>Growth Rate (%)</th>
                                    </tr>
                                </thead>
                                <tbody>
        `;

        let previousTotal = null;
        projectedData.forEach((yearData, index) => {
            const { year, annualTotal_GWh, monthlyData, yearlyLoadFactor_Percent } = yearData;
            
            // Find peak month
            const peakMonth = monthlyData.reduce((max, month) => 
                month.maxDemand_MW > max.maxDemand_MW ? month : max
            );
            
            // Calculate growth rate
            const growthRate = previousTotal ? 
                ((annualTotal_GWh - previousTotal) / previousTotal * 100).toFixed(1) : 
                '--';
            
            const rowClass = index === 0 ? 'table-info' : '';
            
            html += `
                <tr class="${rowClass}">
                    <td><strong>FY ${year}</strong></td>
                    <td>${annualTotal_GWh.toLocaleString()}</td>
                    <td>${peakMonth.month}</td>
                    <td>${peakMonth.maxDemand_MW.toFixed(1)}</td>
                    <td>${yearlyLoadFactor_Percent.toFixed(1)}%</td>
                    <td>${growthRate !== '--' ? `+${growthRate}%` : growthRate}</td>
                </tr>
            `;
            
            previousTotal = annualTotal_GWh;
        });

        html += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Quick Statistics Cards -->
                <div class="row">
                    ${this.generateQuickStatsCards(projectedData)}
                </div>
            </div>
        `;

        return html;
    }

    generateQuickStatsCards(projectedData) {
        /**
         * Generate quick statistics cards
         */
        if (projectedData.length === 0) return '';

        const firstYear = projectedData[0];
        const lastYear = projectedData[projectedData.length - 1];
        
        const totalGrowth = ((lastYear.annualTotal_GWh - firstYear.annualTotal_GWh) / firstYear.annualTotal_GWh * 100).toFixed(1);
        const avgGrowthRate = (totalGrowth / projectedData.length).toFixed(2);
        
        const allPeaks = projectedData.flatMap(y => y.monthlyData.map(m => m.maxDemand_MW));
        const overallPeak = Math.max(...allPeaks).toFixed(1);
        
        const avgLoadFactor = (projectedData.reduce((sum, y) => sum + y.yearlyLoadFactor_Percent, 0) / projectedData.length).toFixed(1);

        return `
            <div class="col-md-3">
                <div class="card bg-primary text-white">
                    <div class="card-body text-center">
                        <h5 class="card-title">${totalGrowth}%</h5>
                        <p class="card-text small">Total Growth</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-success text-white">
                    <div class="card-body text-center">
                        <h5 class="card-title">${avgGrowthRate}%</h5>
                        <p class="card-text small">Avg. Annual Growth</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-info text-white">
                    <div class="card-body text-center">
                        <h5 class="card-title">${overallPeak} MW</h5>
                        <p class="card-text small">Overall Peak</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-warning text-dark">
                    <div class="card-body text-center">
                        <h5 class="card-title">${avgLoadFactor}%</h5>
                        <p class="card-text small">Avg. Load Factor</p>
                    </div>
                </div>
            </div>
        `;
    }

    generateMonthlyHeatmapTab(projectedData, months) {
        /**
         * Generate monthly heatmap tab content
         */
        let html = `
            <div class="tab-pane fade" id="monthly-heatmap" role="tabpanel">
                <div class="mb-3">
                    <h6>Monthly Demand Patterns Across Years</h6>
                    <p class="text-muted">
                        Interactive heatmap showing monthly demand patterns. Darker colors indicate higher values.
                    </p>
                </div>
                
                <!-- Metric Selection -->
                <div class="mb-3">
                    <div class="btn-group btn-group-sm" role="group" aria-label="Metric selection">
                        <input type="radio" class="btn-check" name="heatmapMetric" id="metric-total" value="totalDemand_GWh" checked>
                        <label class="btn btn-outline-primary" for="metric-total">Total Demand (GWh)</label>
                        
                        <input type="radio" class="btn-check" name="heatmapMetric" id="metric-max" value="maxDemand_MW">
                        <label class="btn btn-outline-primary" for="metric-max">Max Demand (MW)</label>
                        
                        <input type="radio" class="btn-check" name="heatmapMetric" id="metric-avg" value="avgDemand_MW">
                        <label class="btn btn-outline-primary" for="metric-avg">Avg Demand (MW)</label>
                        
                        <input type="radio" class="btn-check" name="heatmapMetric" id="metric-lf" value="loadFactor_Percent">
                        <label class="btn btn-outline-primary" for="metric-lf">Load Factor (%)</label>
                    </div>
                </div>
                
                <!-- Heatmap Container -->
                <div class="table-responsive">
                    <table class="table table-bordered table-sm future-patterns-heatmap" id="futureHeatmapTable">
                        <thead class="table-dark">
                            <tr>
                                <th>Year</th>
                                ${months.map(month => `<th>${month}</th>`).join('')}
                                <th>Annual Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${this.generateHeatmapRows(projectedData, months, 'totalDemand_GWh')}
                        </tbody>
                    </table>
                </div>
                
                <!-- Heatmap Legend -->
                <div class="mt-3">
                    <div class="d-flex align-items-center justify-content-center">
                        <span class="me-2 small">Low</span>
                        <div class="heatmap-legend"></div>
                        <span class="ms-2 small">High</span>
                    </div>
                </div>
            </div>
        `;

        // Add event listeners for metric switching after inserting HTML
        setTimeout(() => {
            const metricRadios = document.querySelectorAll('input[name="heatmapMetric"]');
            metricRadios.forEach(radio => {
                radio.addEventListener('change', (e) => {
                    this.updateHeatmapDisplay(projectedData, months, e.target.value);
                });
            });
        }, 100);

        return html;
    }

    generateHeatmapRows(projectedData, months, metric) {
        /**
         * Generate heatmap table rows for specified metric
         */
        let html = '';
        
        // Calculate value range for color scaling
        const allValues = projectedData.flatMap(yearData => 
            yearData.monthlyData.map(monthData => monthData[metric] || 0)
        );
        const minValue = Math.min(...allValues);
        const maxValue = Math.max(...allValues);
        
        projectedData.forEach(yearData => {
            html += `<tr><td class="fw-bold">FY ${yearData.year}</td>`;
            
            // Monthly values
            yearData.monthlyData.forEach(monthData => {
                const value = monthData[metric] || 0;
                const intensity = maxValue > minValue ? (value - minValue) / (maxValue - minValue) : 0;
                const backgroundColor = this.getHeatmapColor(intensity, metric);
                const textColor = intensity > 0.6 ? 'white' : 'black';
                
                html += `
                    <td style="background-color: ${backgroundColor}; color: ${textColor};" 
                        title="${monthData.month}: ${this.formatHeatmapValue(value, metric)}">
                        ${this.formatHeatmapValue(value, metric)}
                    </td>
                `;
            });
            
            // Annual total
            const annualValue = metric === 'totalDemand_GWh' ? yearData.annualTotal_GWh : 
                             metric === 'loadFactor_Percent' ? yearData.yearlyLoadFactor_Percent :
                             yearData.monthlyData.reduce((sum, m) => sum + (m[metric] || 0), 0);
            
            html += `<td class="fw-bold table-secondary">${this.formatHeatmapValue(annualValue, metric)}</td></tr>`;
        });
        
        return html;
    }

    getHeatmapColor(intensity, metric) {
        /**
         * Get heatmap color based on intensity and metric type
         */
        const colors = {
            'totalDemand_GWh': [65, 131, 215],    // Blue
            'maxDemand_MW': [220, 53, 69],        // Red
            'avgDemand_MW': [25, 135, 84],        // Green
            'loadFactor_Percent': [255, 193, 7]   // Orange
        };
        
        const [r, g, b] = colors[metric] || colors['totalDemand_GWh'];
        const alpha = 0.1 + intensity * 0.8;
        
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    formatHeatmapValue(value, metric) {
        /**
         * Format value for heatmap display
         */
        if (value === null || value === undefined || isNaN(value)) return 'N/A';
        
        if (metric.includes('Percent')) {
            return `${value.toFixed(1)}%`;
        } else if (metric.includes('GWh')) {
            return value.toFixed(1);
        } else if (metric.includes('MW')) {
            return value.toFixed(0);
        }
        
        return value.toFixed(1);
    }

    updateHeatmapDisplay(projectedData, months, selectedMetric) {
        /**
         * Update heatmap display when metric changes
         */
        const tableBody = document.querySelector('#futureHeatmapTable tbody');
        if (tableBody) {
            tableBody.innerHTML = this.generateHeatmapRows(projectedData, months, selectedMetric);
        }
    }

    generateTrendAnalysisTab(projectedData, months) {
        /**
         * Generate trend analysis tab content
         */
        return `
            <div class="tab-pane fade" id="trend-analysis" role="tabpanel">
                <div class="mb-3">
                    <h6>Demand Growth Trends and Analysis</h6>
                    <p class="text-muted">
                        Analysis of growth patterns and seasonal variations across the projection period.
                    </p>
                </div>
                
                <!-- Trend Charts Container -->
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-body">
                                <h6 class="card-title">Annual Growth Trend</h6>
                                <canvas id="annualGrowthChart" width="400" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-body">
                                <h6 class="card-title">Load Factor Evolution</h6>
                                <canvas id="loadFactorChart" width="400" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-3">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-body">
                                <h6 class="card-title">Seasonal Pattern Analysis</h6>
                                <canvas id="seasonalPatternChart" width="800" height="300"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Analysis Summary -->
                <div class="mt-3">
                    ${this.generateTrendAnalysisSummary(projectedData)}
                </div>
            </div>
        `;
    }

    generateTrendAnalysisSummary(projectedData) {
        /**
         * Generate trend analysis summary
         */
        if (projectedData.length < 2) {
            return '<div class="alert alert-info">Insufficient data for trend analysis.</div>';
        }

        // Calculate trends
        const years = projectedData.map(d => d.year);
        const totals = projectedData.map(d => d.annualTotal_GWh);
        const loadFactors = projectedData.map(d => d.yearlyLoadFactor_Percent);
        
        const avgGrowthRate = this.calculateAverageGrowthRate(totals);
        const lfTrend = loadFactors[loadFactors.length - 1] - loadFactors[0];
        
        // Find peak seasonal months
        const monthlyTotals = months.map((month, idx) => {
            const total = projectedData.reduce((sum, year) => sum + year.monthlyData[idx].totalDemand_GWh, 0);
            return { month, total };
        });
        const peakSeasonMonth = monthlyTotals.reduce((max, curr) => curr.total > max.total ? curr : max);
        const lowSeasonMonth = monthlyTotals.reduce((min, curr) => curr.total < min.total ? curr : min);

        return `
            <div class="card bg-light">
                <div class="card-body">
                    <h6 class="card-title">
                        <i class="fas fa-chart-line me-2"></i>Trend Analysis Summary
                    </h6>
                    <div class="row">
                        <div class="col-md-4">
                            <h6 class="text-muted">Growth Pattern</h6>
                            <p class="mb-1">
                                <strong>Average Annual Growth:</strong> ${avgGrowthRate.toFixed(1)}%
                            </p>
                            <p class="mb-1">
                                <strong>Total Period Growth:</strong> ${((totals[totals.length-1] - totals[0]) / totals[0] * 100).toFixed(1)}%
                            </p>
                        </div>
                        <div class="col-md-4">
                            <h6 class="text-muted">Load Factor Trend</h6>
                            <p class="mb-1">
                                <strong>Change:</strong> ${lfTrend > 0 ? '+' : ''}${lfTrend.toFixed(1)}%
                            </p>
                            <p class="mb-1">
                                <strong>Average LF:</strong> ${(loadFactors.reduce((a,b) => a+b, 0) / loadFactors.length).toFixed(1)}%
                            </p>
                        </div>
                        <div class="col-md-4">
                            <h6 class="text-muted">Seasonal Patterns</h6>
                            <p class="mb-1">
                                <strong>Peak Season:</strong> ${peakSeasonMonth.month}
                            </p>
                            <p class="mb-1">
                                <strong>Low Season:</strong> ${lowSeasonMonth.month}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    calculateAverageGrowthRate(values) {
        /**
         * Calculate average growth rate across the series
         */
        if (values.length < 2) return 0;
        
        let totalGrowth = 0;
        let validPeriods = 0;
        
        for (let i = 1; i < values.length; i++) {
            if (values[i-1] > 0) {
                totalGrowth += (values[i] - values[i-1]) / values[i-1];
                validPeriods++;
            }
        }
        
        return validPeriods > 0 ? (totalGrowth / validPeriods) * 100 : 0;
    }

    showFuturePatternsError(errorMessage) {
        /**
         * Show error in future patterns modal
         */
        const content = document.getElementById('futurePatternsContent');
        if (content) {
            content.innerHTML = `
                <div class="alert alert-danger">
                    <h6 class="alert-heading">
                        <i class="fas fa-exclamation-triangle me-2"></i>Error Loading Future Patterns
                    </h6>
                    <p class="mb-0">${errorMessage}</p>
                    <hr>
                    <div class="d-flex justify-content-end">
                        <button class="btn btn-outline-danger btn-sm" onclick="location.reload()">
                            <i class="fas fa-sync me-1"></i>Retry
                        </button>
                    </div>
                </div>
            `;
        }
    }

    exportFuturePatterns(baseYear, startYear, endYear, data) {
        /**
         * Export future patterns data to Excel
         */
        try {
            if (!this.currentFuturePatternsData) {
                this.showNotification('No data available for export', 'warning');
                return;
            }

            const { projectedData, baseYearMonths, forecastScenario } = this.currentFuturePatternsData;
            
            // Create CSV content
            let csvContent = `Future Year Monthly Patterns Export\n`;
            csvContent += `Base Year: FY ${baseYear}\n`;
            csvContent += `Projection Period: FY ${startYear} - ${endYear}\n`;
            csvContent += `Scenario: ${forecastScenario || 'Default'}\n`;
            csvContent += `Export Date: ${new Date().toLocaleString()}\n\n`;
            
            // Headers
            csvContent += `Financial Year,Annual Total (GWh),Load Factor (%),`;
            csvContent += baseYearMonths.map(month => `${month} Total (GWh),${month} Max (MW),${month} LF (%)`).join(',');
            csvContent += `\n`;
            
            // Data rows
            projectedData.forEach(yearData => {
                csvContent += `FY ${yearData.year},${yearData.annualTotal_GWh},${yearData.yearlyLoadFactor_Percent.toFixed(1)},`;
                csvContent += yearData.monthlyData.map(monthData => 
                    `${monthData.totalDemand_GWh},${monthData.maxDemand_MW.toFixed(1)},${monthData.loadFactor_Percent}`
                ).join(',');
                csvContent += `\n`;
            });
            
            // Download file
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', `future_patterns_FY${baseYear}_${startYear}-${endYear}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.showNotification('Future patterns exported successfully', 'success');
            
        } catch (error) {
            console.error('Error exporting future patterns:', error);
            this.showNotification(`Export failed: ${error.message}`, 'danger');
        }
    }

    // =============================================================================
    // ENHANCED BASE YEAR PATTERNS (UPDATE EXISTING METHOD)
    // =============================================================================

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
            <div class="mt-2 d-flex justify-content-between">
                <button class="btn btn-sm btn-outline-primary" type="button" 
                        onclick="enhancedLoadProfileManager.showFutureYearsDemandModal(${baseYear})">
                    <i class="fas fa-chart-line me-1"></i> Project Future Years
                </button>
                <button class="btn btn-sm btn-outline-secondary" type="button" 
                        onclick="enhancedLoadProfileManager.exportBaseYearPatterns(${baseYear})">
                    <i class="fas fa-download me-1"></i> Export Base Patterns
                </button>
            </div>
        `;
        
        return html;
    }

    exportBaseYearPatterns(baseYear) {
        /**
         * Export base year patterns to CSV
         */
        if (!this.currentBaseYearPatternData) {
            this.showNotification('No base year pattern data available for export', 'warning');
            return;
        }

        try {
            const { months, patternData, yearlyLoadFactor, calculatedFromExcel } = this.currentBaseYearPatternData;
            
            let csvContent = `Base Year Monthly Patterns Export\n`;
            csvContent += `Base Year: FY ${baseYear}\n`;
            csvContent += `Overall Load Factor: ${yearlyLoadFactor}%\n`;
            csvContent += `Data Source: ${calculatedFromExcel ? 'Excel' : 'Calculated'}\n`;
            csvContent += `Export Date: ${new Date().toLocaleString()}\n\n`;
            
            // Headers
            csvContent += `Metric,${months.join(',')}\n`;
            
            // Data rows
            for (const [metric, values] of Object.entries(patternData)) {
                csvContent += `${metric},${values.join(',')}\n`;
            }
            
            // Download
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', `base_year_patterns_FY${baseYear}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.showNotification('Base year patterns exported successfully', 'success');
            
        } catch (error) {
            console.error('Error exporting base year patterns:', error);
            this.showNotification(`Export failed: ${error.message}`, 'danger');
        }
    }
}

// Add CSS for heatmap styling
const additionalCSS = `
<style>
.future-patterns-heatmap td {
    text-align: center;
    font-size: 0.85em;
    padding: 0.25rem 0.5rem;
    transition: all 0.2s ease;
}

.future-patterns-heatmap td:hover {
    transform: scale(1.05);
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    z-index: 10;
    position: relative;
}

.heatmap-legend {
    width: 100px;
    height: 20px;
    background: linear-gradient(to right, 
        rgba(65, 131, 215, 0.1), 
        rgba(65, 131, 215, 0.9));
    border: 1px solid #ddd;
    border-radius: 3px;
}

.heatmap-style td {
    transition: all 0.2s ease;
}

.heatmap-style td:hover {
    box-shadow: 0 0 10px rgba(0,0,0,0.3);
    transform: scale(1.02);
    z-index: 10;
    position: relative;
}

.loading-overlay, .no-data-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(255, 255, 255, 0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.chart-container {
    position: relative;
    min-height: 300px;
}
</style>
`;

// Inject CSS if not already present
if (!document.querySelector('#future-patterns-styles')) {
    const styleElement = document.createElement('style');
    styleElement.id = 'future-patterns-styles';
    styleElement.innerHTML = additionalCSS;
    document.head.appendChild(styleElement);
}

// Global instance and initialization
let enhancedLoadProfileManager;

document.addEventListener('DOMContentLoaded', function () {
    enhancedLoadProfileManager = new EnhancedLoadProfileManager();

    // Also maintain backwards compatibility
    window.loadProfileManager = enhancedLoadProfileManager;
});

// Export for global access
window.enhancedLoadProfileManager = enhancedLoadProfileManager;