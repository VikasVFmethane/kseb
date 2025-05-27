// static/js/recent-projects.js

document.addEventListener('DOMContentLoaded', function() {
    // Load recent projects on page load if container exists
    const recentProjectsContainer = document.getElementById('existingProjectsDashboard');
    if (recentProjectsContainer) {
        // Make the container visible - it might be hidden by default
        recentProjectsContainer.style.display = 'block';
        loadRecentProjects();
    }

    // Set up the delete project modal handlers
    setupDeleteProjectHandlers();
});

function loadRecentProjects() {
    // Show loading state
    const projectCardsContainer = document.getElementById('projectCardsContainer');
    if (!projectCardsContainer) return;
    
    console.log("Loading recent projects...");
    
    projectCardsContainer.innerHTML = `
        <div class="col placeholder-glow">
            <div class="card h-100 project-card-placeholder">
                <div class="card-body">
                    <h5 class="card-title placeholder w-75"></h5>
                    <p class="card-text placeholder w-100"></p>
                    <p class="card-text placeholder w-50"></p>
                    <a href="#" tabindex="-1" class="btn btn-primary disabled placeholder col-6"></a>
                </div>
            </div>
        </div>
    `;
    
    // Hide "no projects" message while loading
    const noProjectsMessage = document.getElementById('noProjectsMessage');
    if (noProjectsMessage) {
        noProjectsMessage.style.display = 'none';
    }
    
    // Fetch recent projects
    fetch('/project/api/recent_projects')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Received recent projects data:", data);
            
            if (!data.recent_projects || data.recent_projects.length === 0) {
                // Show "no projects" message
                if (noProjectsMessage) {
                    noProjectsMessage.style.display = 'block';
                }
                projectCardsContainer.innerHTML = '';
                return;
            }
            
            // Create HTML for project cards
            let html = '';
            data.recent_projects.forEach(project => {
                // Format date
                let formattedDate = 'N/A';
                try {
                    const lastOpenedDate = new Date(project.last_opened);
                    formattedDate = lastOpenedDate.toLocaleString();
                } catch (error) {
                    console.warn("Error formatting date:", error);
                }
                
                html += `
                    <div class="col">
                        <div class="card h-100 project-card">
                            <div class="card-body">
                                <h5 class="card-title">${project.name}</h5>
                                <p class="card-text text-muted small">
                                    <i class="fas fa-folder me-1"></i> ${project.path}
                                </p>
                                <p class="card-text small">
                                    <i class="fas fa-clock me-1"></i> Last opened: ${formattedDate}
                                </p>
                            </div>
                            <div class="card-footer d-flex justify-content-between">
                                <button class="btn btn-primary btn-sm load-project-btn" data-path="${project.path}">
                                    <i class="fas fa-folder-open me-1"></i> Open
                                </button>
                                <button class="btn btn-outline-danger btn-sm delete-project-btn" 
                                        data-path="${project.path}" 
                                        data-name="${project.name}">
                                    <i class="fas fa-trash-alt"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            projectCardsContainer.innerHTML = html;
            
            // Add click handlers for load buttons
            document.querySelectorAll('.load-project-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const projectPath = this.getAttribute('data-path');
                    loadProjectByPath(projectPath);
                });
            });
            
            // Add click handlers for delete buttons
            document.querySelectorAll('.delete-project-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const projectPath = this.getAttribute('data-path');
                    const projectName = this.getAttribute('data-name');
                    showDeleteConfirmation(projectName, projectPath);
                });
            });
            
            // Show the container
            const dashboard = document.getElementById('existingProjectsDashboard');
            if (dashboard) {
                dashboard.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error loading recent projects:', error);
            if (projectCardsContainer) {
                projectCardsContainer.innerHTML = `
                    <div class="col-12">
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-circle me-2"></i>
                            Error loading recent projects: ${error.message}
                        </div>
                    </div>
                `;
            }
        });
}

function loadProjectByPath(projectPath) {
    // Show loading overlay
    if (typeof showLoading === 'function') {
        showLoading(true);
    } else {
        console.log("Loading project...");
    }
    
    // Load project via API
    fetch('/project/load', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            'projectPath': projectPath
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Show success message using native alert if showGlobalAlert isn't available
            try {
                if (typeof showGlobalAlert === 'function') {
                    showGlobalAlert(`Project "${data.project_name}" loaded successfully`, 'success');
                } else {
                    alert(`Project "${data.project_name}" loaded successfully`);
                }
            } catch (error) {
                console.warn("Error showing alert:", error);
                alert(`Project "${data.project_name}" loaded successfully`);
            }
            
            // Redirect to dashboard after short delay
            setTimeout(() => {
                window.location.href = '/demand/projection';
            }, 1000);
        } else {
            // Show error message
            try {
                if (typeof showGlobalAlert === 'function') {
                    showGlobalAlert(data.message || 'Failed to load project', 'danger');
                } else {
                    alert(data.message || 'Failed to load project');
                }
            } catch (error) {
                console.warn("Error showing alert:", error);
                alert(data.message || 'Failed to load project');
            }
            
            if (typeof showLoading === 'function') {
                showLoading(false);
            }
        }
    })
    .catch(error => {
        console.error('Error loading project:', error);
        
        // Show error message
        try {
            if (typeof showGlobalAlert === 'function') {
                showGlobalAlert(`Error loading project: ${error.message}`, 'danger');
            } else {
                alert(`Error loading project: ${error.message}`);
            }
        } catch (error) {
            console.warn("Error showing alert:", error);
            alert(`Error loading project`);
        }
        
        if (typeof showLoading === 'function') {
            showLoading(false);
        }
    });
}

function setupDeleteProjectHandlers() {
    // Set up the confirm delete button handler
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function() {
            const projectPath = this.getAttribute('data-path');
            deleteProject(projectPath);
        });
    }
}

function showDeleteConfirmation(projectName, projectPath) {
    const modal = document.getElementById('deleteProjectModal');
    if (!modal) return;
    
    // Update the modal content
    const projectNameElement = document.getElementById('projectToDelete');
    if (projectNameElement) {
        projectNameElement.textContent = projectName;
    }
    
    // Set the project path on the confirm button
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    if (confirmBtn) {
        confirmBtn.setAttribute('data-path', projectPath);
    }
    
    // Show the modal
    const modalInstance = new bootstrap.Modal(modal);
    modalInstance.show();
}

function deleteProject(projectPath) {
    // Call the API to delete the project from recent projects
    fetch('/project/api/delete_recent_project', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            'projectPath': projectPath
        })
    })
    .then(response => response.json())
    .then(data => {
        // Hide the modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('deleteProjectModal'));
        if (modal) modal.hide();
        
        if (data.status === 'success') {
            // Show success message
            try {
                if (typeof showGlobalAlert === 'function') {
                    showGlobalAlert('Project removed from recent projects', 'success');
                } else {
                    alert('Project removed from recent projects');
                }
            } catch (error) {
                console.warn("Error showing alert:", error);
                alert('Project removed from recent projects');
            }
            
            // Reload the projects list
            loadRecentProjects();
        } else {
            // Show error message
            try {
                if (typeof showGlobalAlert === 'function') {
                    showGlobalAlert(data.message || 'Failed to remove project', 'danger');
                } else {
                    alert(data.message || 'Failed to remove project');
                }
            } catch (error) {
                console.warn("Error showing alert:", error);
                alert(data.message || 'Failed to remove project');
            }
        }
    })
    .catch(error => {
        console.error('Error deleting project:', error);
        
        // Hide the modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('deleteProjectModal'));
        if (modal) modal.hide();
        
        // Show error message
        try {
            if (typeof showGlobalAlert === 'function') {
                showGlobalAlert(`Error removing project: ${error.message}`, 'danger');
            } else {
                alert(`Error removing project: ${error.message}`);
            }
        } catch (error) {
            console.warn("Error showing alert:", error);
            alert('Error removing project');
        }
    });
}