/**
 * Energy Demand Forecasting Platform - Main JavaScript
 * Handles all interactive functionality across the platform
 */

document.addEventListener('DOMContentLoaded', function () {
    // ========== Project Mode Selection ==========
    const createNewMode = document.getElementById('createNewMode');
    const selectExistingMode = document.getElementById('selectExistingMode');
    const createNewFields = document.getElementById('createNewFields');
    const selectExistingFields = document.getElementById('selectExistingFields');

    // Toggle between create new and select existing modes
    if (createNewMode && selectExistingMode && createNewFields && selectExistingFields) {
        createNewMode.addEventListener('change', function () {
            if (this.checked) {
                createNewFields.style.display = 'block';
                selectExistingFields.style.display = 'none';
            }
        });

        selectExistingMode.addEventListener('change', function () {
            if (this.checked) {
                createNewFields.style.display = 'none';
                selectExistingFields.style.display = 'block';
            }
        });
    }

    // ========== Create New Project Functionality ==========
    const projectForm = document.getElementById('projectForm');
    const projectName = document.getElementById('projectName');
    const projectLocation = document.getElementById('projectLocation');
    const browseBtn = document.getElementById('browseBtn');
    const createProjectBtn = document.getElementById('createProjectBtn');

    // Setup directory/folder selection for new project
    if (browseBtn && projectLocation) {
        browseBtn.addEventListener('click', function () {
            selectFolder(projectLocation, false, validateNewProjectForm);
        });

        // Add a method to enable direct manual entry
        projectLocation.addEventListener('click', function () {
            // If input is already editable, do nothing
            if (!this.hasAttribute('readonly')) return;

            // Remove readonly to allow manual editing
            this.removeAttribute('readonly');
            this.focus();

            // Add a small helper text if it doesn't exist
            if (!document.getElementById('locationHelp')) {
                const helpText = document.createElement('small');
                helpText.className = 'form-text text-muted mt-1';
                helpText.id = 'locationHelp';
                helpText.textContent = 'You can type the folder path directly or use the browse button';
                this.parentNode.appendChild(helpText);
            }

            // Update the browse button text
            if (browseBtn) {
                browseBtn.innerHTML = '<i class="fas fa-folder-open"></i> Browse';
            }
        });

        // Validate form when project location changes
        projectLocation.addEventListener('input', validateNewProjectForm);
    }

    // Validate new project form
    function validateNewProjectForm() {
        if (!projectForm || !createProjectBtn) return;

        if (projectName && projectLocation) {
            // Enable submit button if both fields have values
            const isValid = projectName.value.trim() !== '' && projectLocation.value.trim() !== '';

            createProjectBtn.disabled = !isValid;

            // Add visual feedback
            if (projectName.value.trim() !== '') {
                projectName.classList.add('is-valid');
                projectName.classList.remove('is-invalid');
            } else {
                projectName.classList.remove('is-valid');
                if (projectName.value !== '') {
                    projectName.classList.add('is-invalid');
                }
            }

            if (projectLocation.value.trim() !== '') {
                projectLocation.classList.add('is-valid');
                projectLocation.classList.remove('is-invalid');
            } else {
                projectLocation.classList.remove('is-valid');
                if (projectLocation.value !== '') {
                    projectLocation.classList.add('is-invalid');
                }
            }
        }
    }

    // Initialize validation on project name input
    if (projectName) {
        projectName.addEventListener('input', validateNewProjectForm);
    }

    // ========== Select Existing Project Functionality ==========
    const existingProjectPath = document.getElementById('existingProjectPath');
    const browseExistingBtn = document.getElementById('browseExistingBtn');
    const loadProjectBtn = document.getElementById('loadProjectBtn');
    const validationStatus = document.getElementById('projectValidationStatus');

    // Setup directory selection for existing project
    if (browseExistingBtn && existingProjectPath) {
        browseExistingBtn.addEventListener('click', function () {
            selectFolder(existingProjectPath, true, validateExistingProject);
        });

        // Add input handler for manual entry
        existingProjectPath.addEventListener('input', function () {
            validateExistingProject();
        });
    }

    // Load existing project handler
    if (loadProjectBtn) {
        loadProjectBtn.addEventListener('click', function () {
            if (!existingProjectPath || !existingProjectPath.value.trim()) return;

            // Load the existing project
            loadExistingProject(existingProjectPath.value.trim());
        });
    }

    // ========== Form Submission for New Project ==========
    if (projectForm) {
        projectForm.addEventListener('submit', function (e) {
            e.preventDefault();

            // If in "select existing" mode, don't process form submission
            if (selectExistingMode && selectExistingMode.checked) {
                return;
            }

            // Final validation before submission
            if (!projectName || !projectName.value.trim()) {
                showAlert('Please enter a project name', 'danger');
                projectName.classList.add('is-invalid');
                projectName.focus();
                return;
            }

            if (!projectLocation || !projectLocation.value.trim()) {
                showAlert('Please select a project location', 'danger');
                projectLocation.classList.add('is-invalid');
                projectLocation.focus();
                return;
            }

            // Show loading state
            const submitBtn = createProjectBtn;
            const originalBtnText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Creating...';

            // Submit form data using fetch API
            fetch('/create_project', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    'projectName': projectName.value.trim(),
                    'projectLocation': projectLocation.value.trim()
                })
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Reset button state
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText;

                    if (data.status === 'success') {
                        showAlert(data.message, 'success');
                        showProjectSuccessModal(data.project_path);
                        projectForm.reset();

                        // Reset validation classes
                        projectName.classList.remove('is-valid', 'is-invalid');
                        projectLocation.classList.remove('is-valid', 'is-invalid');
                    } else {
                        showAlert(data.message || 'An error occurred', 'danger');
                    }
                })
                .catch(error => {
                    // Reset button state
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText;

                    showAlert('An error occurred: ' + error.message, 'danger');
                    console.error('Error creating project:', error);
                });
        });
    }

    // ========== Folder Selection Function ==========
    function selectFolder(inputElement, validateStructure, callback) {
        if (!inputElement) return;

        // Create a temporary file input element for directory selection
        const fileInput = document.createElement('input');
        fileInput.type = 'file';

        // Try to set directory selection attributes with better browser support
        try {
            // Chrome, Edge, Opera
            fileInput.setAttribute('webkitdirectory', '');
            // Firefox (partially supported)
            fileInput.setAttribute('directory', '');
            fileInput.setAttribute('mozdirectory', '');
            // Allow multiple file selection (needed for directory selection)
            fileInput.multiple = true;
        } catch (e) {
            console.error('Directory selection not supported by this browser', e);
        }

        fileInput.style.display = 'none';
        document.body.appendChild(fileInput);

        // Handle the file selection
        fileInput.addEventListener('change', function () {
            console.log('File selection changed', fileInput.files);

            if (fileInput.files && fileInput.files.length > 0) {
                try {
                    // Get proper folder path
                    let folderPath = getFolderPathFromSelection(fileInput.files);
                    console.log('Extracted folder path:', folderPath);

                    // Update input field with the folder path
                    inputElement.value = folderPath;

                    // Run callback function for validation if provided
                    if (typeof callback === 'function') {
                        callback();
                    }
                } catch (e) {
                    console.error('Error extracting folder path', e);
                    // Fallback to manual entry
                    promptForManualEntry(inputElement, validateStructure, callback);
                }
            } else {
                console.log('No files selected');
            }

            // Clean up the temporary input
            document.body.removeChild(fileInput);
        });

        // Handle potential cancellation
        fileInput.addEventListener('cancel', function () {
            console.log('File selection cancelled');
            document.body.removeChild(fileInput);
        });

        // Trigger the file selection dialog
        fileInput.click();
    }

    // Extract folder path from selected files with improved algorithm
    function getFolderPathFromSelection(files) {
        if (!files || files.length === 0) {
            throw new Error('No files selected');
        }

        console.log('Getting folder path from', files.length, 'files');

        // Try using webkitRelativePath first (most reliable when supported)
        if (files[0].webkitRelativePath) {
            const pathParts = files[0].webkitRelativePath.split('/');

            // If we have a full path with multiple parts
            if (pathParts.length > 1) {
                // Return just the first part (the folder name)
                return pathParts[0];
            }
        }

        // Try to get parent folder from file path (for browsers that support full paths)
        if (files[0].path) {
            const pathParts = files[0].path.split(/[/\\]/); // Split on both / and \
            return pathParts.slice(0, -1).join('/'); // Join all but the last part
        }

        // If we have multiple files, we can try to infer the common parent directory
        if (files.length > 1 && files[0].name && files[1].name) {
            return "Selected folder with " + files.length + " files";
        }

        // Last resort: just use the filename as indication
        return "Folder containing " + files[0].name;
    }

    // Improved manual entry prompt with validation
    function promptForManualEntry(inputElement, validateStructure, callback) {
        if (!inputElement) return;

        // Create a more helpful modal for manual folder path entry
        const modalHTML = `
            <div class="modal fade" id="folderEntryModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Enter Folder Path</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-warning">
                                <i class="fas fa-exclamation-triangle me-2"></i>
                                Automatic folder selection is not fully supported by your browser. Please enter the folder path manually.
                            </div>
                            <div class="mb-3">
                                <label for="manualFolderPath" class="form-label">Folder Path:</label>
                                <input type="text" id="manualFolderPath" class="form-control" 
                                       placeholder="e.g., C:\\Projects\\Energy Forecasting">
                            </div>
                            ${validateStructure ?
                `<div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>
                                    <strong>Note:</strong> Make sure the folder contains the required project structure with "inputs" and "results" subfolders.
                                </div>` :
                `<div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>
                                    <strong>Note:</strong> A new folder with this name will be created at this location.
                                </div>`
            }
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="confirmFolderBtn">Confirm</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add the modal to the DOM
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Get modal elements
        const folderEntryModal = document.getElementById('folderEntryModal');
        const manualFolderPath = document.getElementById('manualFolderPath');
        const confirmFolderBtn = document.getElementById('confirmFolderBtn');

        // Initialize and show the modal
        const folderModal = new bootstrap.Modal(folderEntryModal);
        folderModal.show();

        // Focus the input field
        manualFolderPath.focus();

        // Enable enter key submission
        manualFolderPath.addEventListener('keyup', function (e) {
            if (e.key === 'Enter') {
                confirmFolderBtn.click();
            }
        });

        // Handle manual entry confirmation
        confirmFolderBtn.addEventListener('click', function () {
            const manualPath = manualFolderPath.value.trim();
            if (manualPath) {
                inputElement.value = manualPath;
                folderModal.hide();

                // Run callback function for validation if provided
                if (typeof callback === 'function') {
                    callback();
                }
            } else {
                // Highlight empty input
                manualFolderPath.classList.add('is-invalid');
            }
        });

        // Clean up after the modal is hidden
        folderEntryModal.addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    }

    // Validate existing project through actual server request
    function validateExistingProject() {
        if (!existingProjectPath || !loadProjectBtn || !validationStatus) return;

        const folderPath = existingProjectPath.value.trim();

        if (!folderPath) {
            loadProjectBtn.disabled = true;
            validationStatus.innerHTML = '';
            existingProjectPath.classList.remove('is-valid', 'is-invalid');
            return;
        }

        // Show validating status
        validationStatus.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin me-2"></i>Validating project structure...</div>';

        // Make a real server-side call to validate the folder structure
        fetch('/validate_project', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                'projectPath': folderPath
            })
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    // Valid project structure
                    existingProjectPath.classList.add('is-valid');
                    existingProjectPath.classList.remove('is-invalid');
                    loadProjectBtn.disabled = false;
                    validationStatus.innerHTML = `<div class="alert alert-success">
                    <i class="fas fa-check-circle me-2"></i>${data.message}
                </div>`;
                } else if (data.status === 'warning') {
                    // Incomplete but fixable project structure
                    existingProjectPath.classList.add('is-valid');
                    existingProjectPath.classList.remove('is-invalid');
                    loadProjectBtn.disabled = false;
                    validationStatus.innerHTML = `<div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i>${data.message}
                    ${data.can_fix ? '<p class="mt-2 mb-0"><small>These issues will be fixed automatically when loading the project.</small></p>' : ''}
                </div>`;
                } else {
                    // Invalid project structure
                    existingProjectPath.classList.add('is-invalid');
                    existingProjectPath.classList.remove('is-valid');
                    loadProjectBtn.disabled = true;
                    validationStatus.innerHTML = `<div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>${data.message}
                </div>`;
                }
            })
            .catch(error => {
                console.error('Error validating project:', error);
                existingProjectPath.classList.add('is-invalid');
                existingProjectPath.classList.remove('is-valid');
                loadProjectBtn.disabled = true;
                validationStatus.innerHTML = `<div class="alert alert-danger">
                <i class="fas fa-exclamation-circle me-2"></i>Error validating project: ${error.message}
            </div>`;
            });
        // Add this at the end of the function where validation is successful
        if (data.status === 'success' || (data.status === 'warning' && data.can_fix)) {
            // Get project name from path
            const pathParts = folderPath.split(/[/\\]/);
            const projectName = pathParts[pathParts.length - 1];

            // Add to recent projects
            addToRecentProjects(projectName, folderPath);
        }

    }
    // Add to recent projects list
    function addToRecentProjects(name, path) {
        // Get existing list
        let recentProjects = JSON.parse(localStorage.getItem('recentProjects') || '[]');

        // Check if project already exists
        const existingIndex = recentProjects.findIndex(p => p.path === path);
        if (existingIndex >= 0) {
            // Remove existing entry
            recentProjects.splice(existingIndex, 1);
        }

        // Add to beginning of list
        recentProjects.unshift({
            name: name,
            path: path,
            lastOpened: new Date().toISOString()
        });

        // Keep only the 5 most recent
        recentProjects = recentProjects.slice(0, 5);

        // Save back to localStorage
        localStorage.setItem('recentProjects', JSON.stringify(recentProjects));

        // Reload list
        loadRecentProjects();
    }

    // Call when mode changes
    selectExistingMode.addEventListener('change', function () {
        if (this.checked) {
            loadRecentProjects();
            createNewFields.style.display = 'none';
            selectExistingFields.style.display = 'block';
        }
    });
    // Load existing project with actual server request
    function loadExistingProject(projectPath) {
        if (!projectPath) return;

        // Show loading state
        const originalBtnText = loadProjectBtn.innerHTML;
        loadProjectBtn.disabled = true;
        loadProjectBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';

        // Make actual server request to load the project
        fetch('/load_project', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                'projectPath': projectPath
            })
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Reset button state
                loadProjectBtn.disabled = false;
                loadProjectBtn.innerHTML = originalBtnText;

                if (data.status === 'success') {
                    showAlert(data.message, 'success');
                    showProjectLoadedModal(data.project_path);
                } else {
                    showAlert(data.message || 'An error occurred', 'danger');
                }
            })
            .catch(error => {
                // Reset button state
                loadProjectBtn.disabled = false;
                loadProjectBtn.innerHTML = originalBtnText;

                showAlert('An error occurred: ' + error.message, 'danger');
                console.error('Error loading project:', error);
            });
    }

    // ========== Project Success Modal ==========
    function showProjectSuccessModal(projectPath) {
        // Create modal HTML
        const modalHTML = `
        <div class="modal fade" id="projectSuccessModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Project Created Successfully</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="success-icon text-center">
                            <i class="fas fa-check-circle text-success" style="font-size: 48px;"></i>
                        </div>
                        <p class="mt-3">Your project folder structure has been created successfully at:</p>
                        <p class="text-primary fw-semibold">${projectPath}</p>
                        
                        <h6 class="mt-4 mb-3">Project Structure:</h6>
                        <ul class="folder-structure">
                            <li><i class="fas fa-folder"></i> <strong>Project Root</strong>
                                <ul>
                                    <li><i class="fas fa-folder"></i> inputs
                                        <ul>
                                            <li><i class="fas fa-file-excel"></i> data_input_template.xlsx</li>
                                            <li><i class="fas fa-file-excel"></i> load_curve_template.xlsx</li>
                                            <li><i class="fas fa-file-excel"></i> pypsa_input_template.xlsx</li>
                                        </ul>
                                    </li>
                                    <li><i class="fas fa-folder"></i> results
                                        <ul>
                                            <li><i class="fas fa-folder"></i> demand_projection</li>
                                            <li><i class="fas fa-folder"></i> load_profiles</li>
                                            <li><i class="fas fa-folder"></i> Pypsa_results</li>
                                        </ul>
                                    </li>
                                </ul>
                            </li>
                        </ul>
                        
                        <div class="alert alert-info mt-3">
                            <i class="fas fa-info-circle me-2"></i>
                            Template files have been copied to the inputs folder to help you get started.
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <a href="#" class="btn btn-primary" id="startProjectButton">Start Working on Project</a>
                    </div>
                </div>
            </div>
        </div>
        `;

        // Add modal to the DOM
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Initialize and show the modal
        const modal = new bootstrap.Modal(document.getElementById('projectSuccessModal'));
        modal.show();

        // Handle "Start Working on Project" button
        document.getElementById('startProjectButton').addEventListener('click', function (e) {
            e.preventDefault();

            // In a real application, this would open the project dashboard
            // For this example, we'll just show a message
            showAlert('Opening project dashboard...', 'info');
            modal.hide();

            // Redirect to project dashboard (in a real app)
            // window.location.href = '/project/dashboard?path=' + encodeURIComponent(projectPath);
        });

        // Remove modal from DOM after it's hidden
        document.getElementById('projectSuccessModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    }

    // ========== Project Loaded Modal ==========
    function showProjectLoadedModal(projectPath) {
        // Create modal HTML
        const modalHTML = `
        <div class="modal fade" id="projectLoadedModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Project Loaded Successfully</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="success-icon text-center">
                            <i class="fas fa-check-circle text-success" style="font-size: 48px;"></i>
                        </div>
                        <p class="mt-3">The existing project has been loaded successfully:</p>
                        <p class="text-primary fw-semibold">${projectPath}</p>
                        
                        <div class="alert alert-info mt-3">
                            <i class="fas fa-info-circle me-2"></i>
                            The project structure has been verified, and all required folders are present.
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <a href="#" class="btn btn-primary" id="openDashboardButton">Go to Project Dashboard</a>
                    </div>
                </div>
            </div>
        </div>
        `;

        // Add modal to the DOM
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Initialize and show the modal
        const modal = new bootstrap.Modal(document.getElementById('projectLoadedModal'));
        modal.show();

        // Handle "Go to Project Dashboard" button
        document.getElementById('openDashboardButton').addEventListener('click', function (e) {
            e.preventDefault();

            // In a real application, this would open the project dashboard
            // For this example, we'll just show a message
            showAlert('Opening project dashboard...', 'info');
            modal.hide();

            // Redirect to project dashboard (in a real app)
            // window.location.href = '/project/dashboard?path=' + encodeURIComponent(projectPath);
        });

        // Remove modal from DOM after it's hidden
        document.getElementById('projectLoadedModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    }

    // ========== Alert Message Function ==========
    function showAlert(message, type) {
        // Create alert element
        const alertElement = document.createElement('div');
        alertElement.className = `alert alert-${type} alert-dismissible fade show`;
        alertElement.role = 'alert';

        alertElement.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        // Insert the alert at the top of the content area
        const contentArea = document.querySelector('.content-area');
        if (contentArea) {
            // Insert after any existing flash messages
            const flashMessages = contentArea.querySelector('.alert');
            if (flashMessages) {
                flashMessages.parentNode.insertBefore(alertElement, flashMessages.nextSibling);
            } else {
                contentArea.insertBefore(alertElement, contentArea.firstChild);
            }

            // Auto-dismiss after 5 seconds
            setTimeout(() => {
                alertElement.classList.remove('show');
                setTimeout(() => {
                    if (alertElement.parentNode) {
                        alertElement.parentNode.removeChild(alertElement);
                    }
                }, 300);
            }, 5000);
        }
    }

    // ========== Initialize forms on load ==========
    // Run initial validations
    if (createNewMode && createNewMode.checked) {
        validateNewProjectForm();
    } else if (selectExistingMode && selectExistingMode.checked) {
        validateExistingProject();
    }

    // ========== Feature Cards Functionality ==========
    const featureCards = document.querySelectorAll('.feature-card');

    featureCards.forEach(card => {
        const featureLink = card.querySelector('.feature-link');
        const helpBtn = card.querySelector('.help-btn');

        // Make the entire card clickable except for the help button
        card.addEventListener('click', function (e) {
            // Don't trigger if the help button was clicked
            if (e.target.closest('.help-btn')) {
                return;
            }

            // Don't trigger if the link itself was clicked (to avoid double navigation)
            if (e.target.closest('.feature-link')) {
                return;
            }

            // Navigate to the feature page
            if (featureLink) {
                window.location.href = featureLink.getAttribute('href');
            }
        });

        // Add hover effect synchronization
        card.addEventListener('mouseenter', function () {
            card.classList.add('hover');
            if (featureLink) {
                featureLink.classList.add('hover-effect');
            }
        });

        card.addEventListener('mouseleave', function () {
            card.classList.remove('hover');
            if (featureLink) {
                featureLink.classList.remove('hover-effect');
            }
        });
    });

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    if (window.bootstrap && window.bootstrap.Tooltip) {
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
});
function loadRecentProjects() {
    const recentProjectsContainer = document.getElementById('recentProjectsContainer');
    const noRecentProjectsMessage = document.getElementById('noRecentProjectsMessage');

    // Get recent projects from localStorage
    const recentProjects = JSON.parse(localStorage.getItem('recentProjects') || '[]');

    if (recentProjects.length > 0) {
        // Hide "no projects" message
        noRecentProjectsMessage.style.display = 'none';

        // Create project cards
        let projectCardsHTML = '';

        recentProjects.forEach(project => {
            const projectDate = new Date(project.lastOpened);
            const formattedDate = projectDate.toLocaleDateString() + ' ' +
                projectDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            projectCardsHTML += `
                <div class="recent-project-card mb-2">
                    <div class="card">
                        <div class="card-body py-2 px-3">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <h6 class="mb-0">${project.name}</h6>
                                    <small class="text-muted">${project.path}</small>
                                </div>
                                <div>
                                    <span class="text-muted me-3 small">Last opened: ${formattedDate}</span>
                                    <button class="btn btn-sm btn-primary load-recent-project-btn" 
                                            data-path="${project.path}">
                                        <i class="fas fa-folder-open me-1"></i>Load
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        recentProjectsContainer.innerHTML = projectCardsHTML;

        // Add event listeners to load buttons
        document.querySelectorAll('.load-recent-project-btn').forEach(button => {
            button.addEventListener('click', function () {
                const projectPath = this.dataset.path;
                existingProjectPath.value = projectPath;
                validateExistingProject();
            });
        });
    } else {
        // Show "no projects" message
        noRecentProjectsMessage.style.display = 'block';
    }
}
// Add to home.js - Feature card usage tracking
function trackFeatureUsage(featureId) {
    // Get existing feature usage from localStorage
    let featureUsage = JSON.parse(localStorage.getItem('featureUsage') || '{}');
    
    // Update usage timestamp for this feature
    featureUsage[featureId] = new Date().toISOString();
    
    // Save back to localStorage
    localStorage.setItem('featureUsage', JSON.stringify(featureUsage));
}

// Add click handlers to feature links
document.querySelectorAll('.feature-link').forEach(link => {
    link.addEventListener('click', function() {
        const featureCard = this.closest('.feature-card');
        if (featureCard) {
            trackFeatureUsage(featureCard.dataset.feature);
        }
    });
});

// Add to Jinja2 template - Create is_used function