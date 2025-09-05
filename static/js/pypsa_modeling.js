// static/js/pypsa_modeling.js
document.addEventListener('DOMContentLoaded', function () {
    const pypsaRunForm = document.getElementById('pypsaRunForm');
    const runPypsaBtn = document.getElementById('runPypsaBtn');
    const cancelPypsaBtn = document.getElementById('cancelPypsaBtn');
    const statusContainer = document.getElementById('pypsaStatusContainer');
    const scenarioNameRunningSpan = document.getElementById('pypsaScenarioNameRunning');
    const progressBar = document.getElementById('pypsaProgressBar');
    const jobStatusSpan = document.getElementById('pypsaJobStatus');
    const currentStepSpan = document.getElementById('pypsaCurrentStep');
    const logOutputDiv = document.getElementById('pypsaLogOutput');
    const existingScenariosListDiv = document.getElementById('existingScenariosList');
    const noScenariosMessageDiv = document.getElementById('noScenariosMessage');
    const loadExcelSettingsBtn = document.getElementById('loadExcelSettingsBtn');

    const highsSolverTypeSelect = document.getElementById('highsSolverType');
    const simplexStrategyContainer = document.getElementById('simplexStrategyContainer');
    const pdlpGapTolContainer = document.getElementById('pdlpGapTolContainer');


    let currentJobId = null;
    let statusPollingInterval = null;
    let lastLogLength = 0; // To fetch only new logs


    // In pypsa_modeling.js
    function toggleSolverSpecificOptions() {
        if (!highsSolverTypeSelect) return;
        const selectedSolver = highsSolverTypeSelect.value;
        const pdlpInput = document.getElementById('pdlpGapTol'); // Get the input element

        if (simplexStrategyContainer) {
            const isSimplex = selectedSolver === 'simplex';
            simplexStrategyContainer.style.display = isSimplex ? 'block' : 'none';
            simplexStrategyContainer.setAttribute('aria-hidden', String(!isSimplex)); // String true/false
            // No need for tabindex on container usually, focus is on input
        }
        if (pdlpGapTolContainer) {
            const isPdlp = selectedSolver === 'pdlp';
            pdlpGapTolContainer.style.display = isPdlp ? 'block' : 'none';
            pdlpGapTolContainer.setAttribute('aria-hidden', String(!isPdlp));
            if (pdlpInput) {
                pdlpInput.setAttribute('tabindex', isPdlp ? '0' : '-1'); // '0' for natural order, '-1' to remove
            }
        }
    }
    if (highsSolverTypeSelect) {
        highsSolverTypeSelect.addEventListener('change', toggleSolverSpecificOptions);
        toggleSolverSpecificOptions(); // Initial call
    }


    // --- Load Initial Settings from Excel ---
    function loadExcelSettings() {
        if (!runPypsaBtn || runPypsaBtn.disabled) { // Check if run button is disabled (e.g., no input file)
            console.warn("PyPSA input file might be missing, skipping Excel settings load.");
            return;
        }
        showLoading(true);
        fetch('/pypsa/api/get_pypsa_settings_from_excel')
            .then(response => response.json())
            .then(data => {
                showLoading(false);
                if (data.status === 'success' && data.settings) {
                    populateSettingsForm(data.settings);
                    showGlobalAlert('Default settings loaded from Excel.', 'success', 3000);
                } else {
                    showGlobalAlert(data.message || 'Could not load settings from Excel. Using UI defaults.', 'warning');
                    // Set UI defaults if Excel load fails
                    setDefaultUISettings();
                }
            })
            .catch(error => {
                showLoading(false);
                showGlobalAlert('Error fetching settings from Excel: ' + error, 'danger');
                console.error('Error fetching Excel settings:', error);
                setDefaultUISettings();
            });
    }

    function setDefaultUISettings() {
        // Define your default UI settings here if Excel load fails
        document.getElementById('runPypsaModelOn').value = 'All Snapshots';
        document.getElementById('weightings').value = 1;
        document.getElementById('baseYear').value = 2025;
        document.getElementById('multiYearInvestment').value = 'No';
        document.getElementById('generatorCluster').checked = false; // Default based on your preference
        document.getElementById('committableUnits').checked = false; // Default
        document.getElementById('logToConsoleSolver').checked = true;
        document.getElementById('solverThreads').value = 0;
        document.getElementById('highsSolverType').value = 'simplex';
        document.getElementById('solverParallel').checked = true;
        document.getElementById('solverPresolve').checked = true;
        document.getElementById('simplexStrategy').value = '0';
        document.getElementById('pdlpGapTol').value = '1e-4';
        toggleSolverSpecificOptions(); // Ensure correct options are shown
    }


    function populateSettingsForm(settings) {
        // Populate form fields, ensuring elements exist
        const fields = {
            'runPypsaModelOn': settings['Run Pypsa Model on'],
            'weightings': settings['Weightings'],
            'baseYear': settings['Base_Year'],
            'multiYearInvestment': settings['Multi Year Investment'],
            'generatorCluster': settings['Generator Cluster'] === true || settings['Generator Cluster'] === 'Yes', // Handle boolean or string "Yes"
            'committableUnits': settings['Committable'] === true || settings['Committable'] === 'Yes',
            // Add other settings from your Excel that map to UI elements
        };

        for (const id in fields) {
            const element = document.getElementById(id);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = fields[id];
                } else {
                    element.value = fields[id];
                }
            }
        }
        // For solver options, these are typically not in the Excel settings sheet in the same way
        // So, we might prefer to keep UI defaults or let the user configure them.
        // If you do want to load them from Excel, ensure they are in your `settings_main_excel_table`
        // with specific keys like 'Solver Threads', 'Highs Algorithm' etc.
        // For now, I'll assume solver options are primarily UI-driven after initial defaults.
        toggleSolverSpecificOptions(); // Update visibility of solver-specific fields
    }

    if (loadExcelSettingsBtn) {
        loadExcelSettingsBtn.addEventListener('click', loadExcelSettings);
        if (runPypsaBtn && !runPypsaBtn.disabled) loadExcelSettings();
        else setDefaultUISettings(); // Set defaults if input file is missing
    } else {
        setDefaultUISettings(); // Set defaults if button doesn't exist (e.g. testing)
    }


    // --- Run PyPSA Model ---
    if (pypsaRunForm) {
        pypsaRunForm.addEventListener('submit', function (e) {
            e.preventDefault();
            console.log("PyPSA Run Form Submitted!"); // <<<< ADD THIS LOG
            const scenarioNameInput = document.getElementById('scenarioName');
            const scenarioName = scenarioNameInput.value.trim();
            if (!scenarioName) {
                showGlobalAlert('Scenario name is required.', 'warning');
                scenarioNameInput.classList.add('is-invalid');
                scenarioNameInput.focus();
                return;
            }
            scenarioNameInput.classList.remove('is-invalid');

            const settingsOverrides = {
                'Run Pypsa Model on': document.getElementById('runPypsaModelOn').value,
                'Weightings': parseInt(document.getElementById('weightings').value) || 1,
                'Base_Year': parseInt(document.getElementById('baseYear').value) || 2025,
                'Multi Year Investment': document.getElementById('multiYearInvestment').value,
                'Generator Cluster': document.getElementById('generatorCluster').checked,
                'Committable': document.getElementById('committableUnits').checked,
                'log_to_console_solver': document.getElementById('logToConsoleSolver').checked,
                'solver_threads': parseInt(document.getElementById('solverThreads').value),
                'highs_solver_type': document.getElementById('highsSolverType').value,
                'solver_parallel': document.getElementById('solverParallel').checked,
                'solver_presolve': document.getElementById('solverPresolve').checked,
                'simplex_strategy': document.getElementById('highsSolverType').value === 'simplex' ? parseInt(document.getElementById('simplexStrategy').value) : undefined,
                'pdlp_gap_tol': document.getElementById('highsSolverType').value === 'pdlp' ? parseFloat(document.getElementById('pdlpGapTol').value) : undefined,
            };

            showLoading(true);
            runPypsaBtn.disabled = true;
            runPypsaBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Initiating...';
            logOutputDiv.innerHTML = ''; // Clear previous logs
            lastLogLength = 0;

            fetch('pypsa/api/run_pypsa_model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scenarioName: scenarioName, settings: settingsOverrides })
            })
                .then(response => response.json())
                .then(data => {
                    showLoading(false);
                    if (data.status === 'started') {
                        currentJobId = data.jobId;
                        statusContainer.style.display = 'block';
                        if (scenarioNameRunningSpan) scenarioNameRunningSpan.textContent = scenarioName;
                        updateStatusUI({ progress: 0, status: 'Queued', current_step: 'Waiting in queue...', log: ["Model run queued."] });
                        cancelPypsaBtn.style.display = 'inline-block';
                        cancelPypsaBtn.disabled = false;
                        runPypsaBtn.innerHTML = '<i class="fas fa-hourglass-half me-2"></i>Model Running...';
                        startStatusPolling();
                    } else {
                        showGlobalAlert(data.message || 'Failed to start model run.', 'danger');
                        runPypsaBtn.disabled = false;
                        runPypsaBtn.innerHTML = '<i class="fas fa-play me-2"></i>Run PyPSA Model';
                    }
                })
                .catch(error => {
                    showLoading(false);
                    runPypsaBtn.disabled = false;
                    runPypsaBtn.innerHTML = '<i class="fas fa-play me-2"></i>Run PyPSA Model';
                    showGlobalAlert('Error starting model run: ' + error, 'danger');
                });
        });
    }

    // --- Model Status Polling ---
    function startStatusPolling() {
        if (statusPollingInterval) clearInterval(statusPollingInterval);
        statusPollingInterval = setInterval(fetchPypsaStatus, 2500); // Poll every 2.5 seconds
    }

    function fetchPypsaStatus() {
        if (!currentJobId) return;

        fetch(`/pypsa/api/pypsa_model_status/${currentJobId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'error' && data.message === 'Job not found') {
                    // Job might have been cleared from server (e.g. on restart)
                    clearInterval(statusPollingInterval);
                    statusPollingInterval = null;
                    showGlobalAlert('Lost connection to model run status. Please check manually.', 'warning');
                    resetRunUI();
                    return;
                }
                updateStatusUI(data);
                if (['Completed', 'Failed', 'Cancelled'].includes(data.status)) {
                    clearInterval(statusPollingInterval);
                    statusPollingInterval = null;
                    resetRunUI();
                    if (data.status === 'Completed') {
                        showGlobalAlert(`Scenario '${data.scenario_name}' completed! Results are available.`, 'success');
                        loadExistingScenarios();
                    } else if (data.status === 'Failed') {
                        showGlobalAlert(`Scenario '${data.scenario_name}' failed: ${data.error || 'Unknown error'}`, 'danger', 10000);
                    } else if (data.status === 'Cancelled') {
                        showGlobalAlert(`Scenario '${data.scenario_name}' was cancelled.`, 'warning');
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching status:', error);
                // Consider stopping polling after several errors
            });
    }

    function resetRunUI() {
        runPypsaBtn.disabled = false;
        const inputFileExists = runPypsaBtn.hasAttribute('disabled') ? false : !runPypsaBtn.getAttribute('disabled');
        runPypsaBtn.disabled = !inputFileExists; // Re-disable if input file is still not there
        runPypsaBtn.innerHTML = '<i class="fas fa-play me-2"></i>Run PyPSA Model';
        cancelPypsaBtn.style.display = 'none';
    }

    function updateStatusUI(data) {
        if (progressBar) {
            progressBar.style.width = `${data.progress || 0}%`;
            progressBar.textContent = `${data.progress || 0}%`;
        }
        if (jobStatusSpan) {
            jobStatusSpan.textContent = data.status || 'N/A';
            jobStatusSpan.className = `fw-bold status-${(data.status || 'unknown').toLowerCase().replace(/\s+/g, '_')}`;
        }
        if (currentStepSpan) currentStepSpan.textContent = data.current_step || 'N/A';

        if (logOutputDiv && data.log && Array.isArray(data.log)) {
            const newLogEntries = data.log.slice(lastLogLength);
            newLogEntries.forEach(logEntry => {
                const p = document.createElement('p');
                const entryText = typeof logEntry === 'string' ? logEntry : JSON.stringify(logEntry);

                if (entryText.toLowerCase().includes('error')) p.className = 'log-error';
                else if (entryText.toLowerCase().includes('warning')) p.className = 'log-warning';
                else if (entryText.toLowerCase().startsWith('---')) p.className = 'log-debug'; // For year headers
                else p.className = 'log-info';

                p.textContent = entryText.trim();
                logOutputDiv.appendChild(p);
            });
            lastLogLength = data.log.length;
            logOutputDiv.scrollTop = logOutputDiv.scrollHeight;
        }
    }

    // --- Cancel PyPSA Model Run ---
    if (cancelPypsaBtn) {
        cancelPypsaBtn.addEventListener('click', function () {
            if (!currentJobId) return;

            showLoading(true);
            cancelPypsaBtn.disabled = true;
            cancelPypsaBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Cancelling...';

            // Assuming backend has a similar cancel endpoint for PyPSA jobs
            fetch(`/pypsa/api/cancel_forecast/${currentJobId}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    showLoading(false);
                    cancelPypsaBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Run'; // Reset text
                    // Do not re-enable here, let status polling handle it
                    if (data.status === 'cancelled' || data.message.includes('cancelled')) {
                        showGlobalAlert('Model run cancellation requested.', 'info');
                        // Status will reflect cancellation soon via polling
                    } else {
                        showGlobalAlert(data.message || 'Failed to request cancellation.', 'danger');
                        cancelPypsaBtn.disabled = false; // Re-enable a_nd try again if failed
                    }
                })
                .catch(error => {
                    showLoading(false);
                    cancelPypsaBtn.disabled = false;
                    cancelPypsaBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Run';
                    showGlobalAlert('Error cancelling model run: ' + error, 'danger');
                });
        });
    }

    // --- Load Existing Scenarios ---
    function loadExistingScenarios() {
        if (!existingScenariosListDiv) return;
        existingScenariosListDiv.innerHTML = `
            <div class="list-group-item text-center">
                <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
                <span class="ms-2 text-muted">Fetching scenarios...</span>
            </div>`;
        if (noScenariosMessageDiv) noScenariosMessageDiv.style.display = 'none';

        fetch('/pypsa/api/pypsa_scenarios')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success' && data.scenarios.length > 0) {
                    let html = '';
                    data.scenarios.forEach(scenario => {
                        let statusBadgeClass = 'bg-secondary';
                        if (scenario.status === 'Completed') statusBadgeClass = 'bg-success';
                        else if (scenario.status === 'Running' || scenario.status === 'Queued' || scenario.status.includes('Processing')) statusBadgeClass = 'bg-info text-dark';
                        else if (scenario.status === 'Failed') statusBadgeClass = 'bg-danger';
                        else if (scenario.status === 'Cancelled') statusBadgeClass = 'bg-warning text-dark';

                        html += `
                            <div class="list-group-item list-group-item-action flex-column align-items-start mb-2 border rounded">
                                <div class="d-flex w-100 justify-content-between">
                                    <h6 class="mb-1 scenario-name">${scenario.name}</h6>
                                    <span class="badge ${statusBadgeClass} py-1 px-2">${scenario.status}</span>
                                </div>
                                <p class="mb-1 text-muted small"><i class="fas fa-calendar-alt me-1"></i> ${new Date(scenario.last_modified).toLocaleString()}</p>
                                <div class="scenario-actions mt-2 text-end">
                                    <button class="btn btn-sm btn-outline-primary download-results-btn" data-scenario="${scenario.name}" title="Download Results">
                                        <i class="fas fa-download"></i> Download
                                    </button>
                                </div>
                            </div>`;
                    });
                    existingScenariosListDiv.innerHTML = html;

                    document.querySelectorAll('.download-results-btn').forEach(btn => {
                        btn.addEventListener('click', function () {
                            const scenarioName = this.dataset.scenario;
                            showDownloadOptionsModal(scenarioName);
                        });
                    });

                } else {
                    existingScenariosListDiv.innerHTML = '';
                    if (noScenariosMessageDiv) noScenariosMessageDiv.style.display = 'block';
                }
            })
            .catch(error => {
                existingScenariosListDiv.innerHTML = '<div class="alert alert-danger">Error loading scenarios.</div>';
                console.error('Error loading scenarios:', error);
            });
    }

    function showDownloadOptionsModal(scenarioName) {
        let modalEl = document.getElementById('downloadOptionsModal');
        const downloadModal = modalEl ? new bootstrap.Modal(modalEl) : null;
        if (!downloadModal) return;

        document.getElementById('downloadScenarioName').textContent = scenarioName;
        const fileListDiv = document.getElementById('fileListForDownload');
        fileListDiv.innerHTML = '<div class="d-flex align-items-center justify-content-center p-3"><div class="spinner-border spinner-border-sm text-primary me-2"></div>Loading file list...</div>';
        downloadModal.show();

        let jobFiles = null;
        // Prioritize job from current session
        for (const jobId in pypsa_jobs) {
            if (pypsa_jobs[jobId].scenario_name === scenarioName && pypsa_jobs[jobId].status === 'Completed') {
                jobFiles = pypsa_jobs[jobId].result_files;
                break;
            }
        }

        // If not in current jobs (e.g., from previous session), fetch file list from a new API endpoint
        if (!jobFiles) {
            // Placeholder: you'd need an API like /api/list_scenario_files/<scenario_name>
            // For now, this part will show "no files" if not in active pypsa_jobs.
            // To make this robust, backend needs to list files from the scenario's directory.
            console.warn(`Files for scenario '${scenarioName}' not in active job list. Need API to list disk files.`);
            fileListDiv.innerHTML = '<p class="text-muted p-3">Could not retrieve file list. Scenario data might be from a previous session.</p>';
            return;
        }

        if (jobFiles && jobFiles.length > 0) {
            fileListDiv.innerHTML = ''; // Clear loading

            const ncFiles = jobFiles.filter(f => f.endsWith('.nc'));
            const logFiles = jobFiles.filter(f => f.endsWith('.log'));
            const csvGroups = {};
            jobFiles.filter(f => f.endsWith('.csv') && !f.startsWith('~$')).forEach(f => {
                const parts = f.split(/[/\\]/);
                const groupName = parts.length > 1 && parts[0].startsWith('results_') ? parts[0] :
                    (parts.length > 1 && parts[0].startsWith('multiyear_')) ? "Multi-Year Aggregated" : "Root CSVs";
                if (!csvGroups[groupName]) csvGroups[groupName] = [];
                csvGroups[groupName].push(f);
            });

            const createFileLink = (file) => {
                const displayFileName = file.split(/[/\\]/).pop();
                const fileLink = document.createElement('a');
                // Ensure full path is sent if it's nested
                const filePathForApi = file;
                fileLink.href = `/pypsa/api/download_pypsa_result/${encodeURIComponent(scenarioName)}/${encodeURIComponent(filePathForApi)}`;

                let iconClass = 'fa-file-alt';
                if (displayFileName.endsWith('.nc')) iconClass = 'fa-database';
                else if (displayFileName.endsWith('.csv')) iconClass = 'fa-file-csv';
                else if (displayFileName.endsWith('.log')) iconClass = 'fa-file-code';

                fileLink.className = 'list-group-item list-group-item-action d-flex align-items-center';
                fileLink.innerHTML = `<i class="fas ${iconClass} me-2 text-secondary"></i> ${displayFileName}`;
                fileLink.setAttribute('download', displayFileName); // Suggest original name
                return fileLink;
            };

            if (ncFiles.length > 0) {
                ncFiles.forEach(file => fileListDiv.appendChild(createFileLink(file)));
            }

            Object.keys(csvGroups).sort().forEach(groupName => {
                const groupHeader = document.createElement('div');
                groupHeader.className = 'list-group-item list-group-item-light mt-2 fw-bold small text-uppercase';
                groupHeader.textContent = groupName.replace('results_', 'Year ').replace('multiyear_aggregated_results', 'Multi-Year Aggregated');
                fileListDiv.appendChild(groupHeader);
                csvGroups[groupName].sort().forEach(file => {
                    fileListDiv.appendChild(createFileLink(file));
                });
            });

            if (logFiles.length > 0) {
                const groupHeader = document.createElement('div');
                groupHeader.className = 'list-group-item list-group-item-light mt-2 fw-bold small text-uppercase';
                groupHeader.textContent = "Log Files";
                fileListDiv.appendChild(groupHeader);
                logFiles.forEach(file => fileListDiv.appendChild(createFileLink(file)));
            }

        } else {
            fileListDiv.innerHTML = '<p class="text-muted p-3">No downloadable result files found for this scenario.</p>';
        }
    }

    // --- Initial Load of scenarios ---
    if (runPypsaBtn && !runPypsaBtn.disabled) { // Only load if input file likely exists
        loadExistingScenarios();
    } else {
        if (noScenariosMessageDiv) noScenariosMessageDiv.style.display = 'block';
        if (existingScenariosListDiv) existingScenariosListDiv.innerHTML = '';
    }
});