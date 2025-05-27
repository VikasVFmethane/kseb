
document.addEventListener('DOMContentLoaded', function () {
    const sidebarToggleBtn = document.getElementById('sidebarToggle');
    const body = document.body;
    const sidebar = document.getElementById('appSidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const toggleIcon = sidebarToggleBtn ? sidebarToggleBtn.querySelector('i') : null;

    const PREFERS_REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const SIDEBAR_STATE_KEY = 'sidebarCollapsedState';

    // --- Active Process Management ---
    window.ActiveProcessManager = {
        tasks: {}, // { taskId: { id: taskId, name: 'Task Name', cancelCallback: () => {}, status: 'running', element: null } }

        add: function(taskId, taskName, cancelCallback) {
            if (this.tasks[taskId]) {
                console.warn(`Task with ID ${taskId} already exists.`);
                this.updateNotification(taskId, taskName, 'running', true); // Update existing
                return;
            }
            console.log(`[ProcessManager] Adding task: ${taskId} - ${taskName}`);
            this.tasks[taskId] = { 
                id: taskId, 
                name: taskName, 
                cancelCallback: cancelCallback, 
                status: 'running' 
            };
            this.addNotificationToModal(taskId, taskName, true);
        },

        remove: function(taskId) {
            console.log(`[ProcessManager] Removing task: ${taskId}`);
            delete this.tasks[taskId];
            this.removeNotificationFromModal(taskId);
        },

        updateStatus: function(taskId, status, message) {
            if (this.tasks[taskId]) {
                console.log(`[ProcessManager] Updating task status: ${taskId} - ${status}`);
                this.tasks[taskId].status = status;
                this.updateNotification(taskId, this.tasks[taskId].name, status, status === 'running', message);
                 if (status === 'completed' || status === 'failed' || status === 'cancelled') {
                    // Optionally auto-remove from modal after a delay or keep it for history
                    setTimeout(() => this.removeNotificationFromModal(taskId), 15000);
                }
            }
        },

        getTask: function(taskId) {
            return this.tasks[taskId];
        },

        isTaskPrefixRunning: function(prefix) {
            for (const taskId in this.tasks) {
                if (this.tasks[taskId].name.startsWith(prefix) && this.tasks[taskId].status === 'running') {
                    return this.tasks[taskId];
                }
            }
            return false;
        },

        cancelTask: function(taskId) {
            const task = this.getTask(taskId);
            if (task && task.status === 'running' && typeof task.cancelCallback === 'function') {
                console.log(`[ProcessManager] Cancelling task: ${taskId}`);
                task.cancelCallback(); // Backend will eventually update status via polling
            } else {
                console.warn(`[ProcessManager] Task ${taskId} not found or not cancellable.`);
                showGlobalAlert(`Could not cancel task: ${task ? task.name : taskId}. It may have already completed or is not cancellable.`, 'warning');
            }
        },

        // --- Notification Modal Management ---
        addNotificationToModal: function(taskId, taskName, isCancellable) {
            const notificationsList = document.getElementById('notificationsListContainer');
            const noNotificationsText = document.getElementById('noNotificationsText');
            if (!notificationsList) return;

            if (noNotificationsText) noNotificationsText.style.display = 'none';

            let notificationItem = document.getElementById(`notification-${taskId}`);
            if (notificationItem) { // Update existing
                 notificationItem.querySelector('.notification-title').textContent = taskName;
                 const statusSpan = notificationItem.querySelector('.notification-status-badge');
                 if (statusSpan) {
                    statusSpan.className = 'badge bg-info notification-status-badge';
                    statusSpan.textContent = 'Running';
                 }
                 const messageArea = notificationItem.querySelector('.notification-message');
                 if(messageArea) messageArea.textContent = 'Task re-initialized or updated.';

                 const cancelButton = notificationItem.querySelector('.cancel-task-btn');
                 if (isCancellable && !cancelButton) {
                    const newCancelButton = this.createCancelButton(taskId);
                    notificationItem.querySelector('.notification-actions')?.appendChild(newCancelButton);
                 } else if (!isCancellable && cancelButton) {
                    cancelButton.remove();
                 }
                return;
            }

            notificationItem = document.createElement('div');
            notificationItem.id = `notification-${taskId}`;
            notificationItem.className = 'notification-item border-start border-4 border-info p-3 mb-2 bg-light-subtle rounded shadow-sm';
            
            notificationItem.innerHTML = `
                <div class="d-flex align-items-center mb-1">
                    <i class="fas fa-spinner fa-spin notification-icon me-2 text-info"></i>
                    <div class="notification-content flex-grow-1">
                        <h6 class="notification-title mb-0">${taskName}</h6>
                        <small class="notification-time text-muted">${new Date().toLocaleTimeString()}</small>
                    </div>
                    <span class="badge bg-info notification-status-badge">Running</span>
                </div>
                <div class="notification-message text-muted small mt-1 mb-2" id="notification-message-${taskId}">
                    Process initiated...
                </div>
                <div class="notification-actions text-end">
                    ${isCancellable ? `<button class="btn btn-sm btn-outline-danger cancel-task-btn" data-task-id="${taskId}"><i class="fas fa-times-circle me-1"></i>Cancel</button>` : ''}
                </div>
            `;
            
            notificationsList.prepend(notificationItem);
            const cancelButton = notificationItem.querySelector('.cancel-task-btn');
            if (cancelButton) {
                cancelButton.addEventListener('click', () => {
                    this.cancelTask(taskId);
                });
            }
            this.updateNotificationBadge();
        },
        
        createCancelButton: function(taskId) {
            const button = document.createElement('button');
            button.className = 'btn btn-sm btn-outline-danger cancel-task-btn';
            button.dataset.taskId = taskId;
            button.innerHTML = '<i class="fas fa-times-circle me-1"></i>Cancel';
            button.addEventListener('click', () => this.cancelTask(taskId));
            return button;
        },

        updateNotification: function(taskId, taskName, status, isCancellable, message = '') {
            const notificationItem = document.getElementById(`notification-${taskId}`);
            if (!notificationItem) {
                 // If notification doesn't exist, create it (e.g. for tasks started before page load, discovered via polling)
                if (status === 'running' || status === 'queued' || status.toLowerCase().includes('processing')) {
                   this.addNotificationToModal(taskId, taskName, isCancellable);
                   const newItem = document.getElementById(`notification-${taskId}`);
                   if (newItem) { // Now update the newly created one
                      this.updateNotificationContent(newItem, taskName, status, isCancellable, message);
                   }
                }
                return;
            }
            this.updateNotificationContent(notificationItem, taskName, status, isCancellable, message);
        },
        
        updateNotificationContent: function(notificationItem, taskName, status, isCancellable, message) {
            const iconEl = notificationItem.querySelector('.notification-icon');
            const statusBadgeEl = notificationItem.querySelector('.notification-status-badge');
            const titleEl = notificationItem.querySelector('.notification-title');
            const messageEl = notificationItem.querySelector('.notification-message');
            const actionsEl = notificationItem.querySelector('.notification-actions');
            const timeEl = notificationItem.querySelector('.notification-time');

            if(titleEl) titleEl.textContent = taskName;
            if(timeEl) timeEl.textContent = new Date().toLocaleTimeString();
            if(messageEl) messageEl.textContent = message || `${status}...`;

            let iconClass = 'fas fa-spinner fa-spin text-info';
            let badgeClass = 'badge bg-info';
            let borderClass = 'border-info';

            switch (status.toLowerCase()) {
                case 'completed':
                    iconClass = 'fas fa-check-circle text-success';
                    badgeClass = 'badge bg-success';
                    borderClass = 'border-success';
                    isCancellable = false;
                    break;
                case 'failed':
                    iconClass = 'fas fa-times-circle text-danger';
                    badgeClass = 'badge bg-danger';
                    borderClass = 'border-danger';
                    isCancellable = false;
                    break;
                case 'cancelled':
                    iconClass = 'fas fa-ban text-warning';
                    badgeClass = 'badge bg-warning text-dark';
                    borderClass = 'border-warning';
                    isCancellable = false;
                    break;
                case 'queued':
                     iconClass = 'fas fa-clock text-secondary';
                     badgeClass = 'badge bg-secondary';
                     borderClass = 'border-secondary';
                    break;
                default: // running, processing_inputs etc.
                    iconClass = 'fas fa-spinner fa-spin text-info';
                    badgeClass = 'badge bg-info';
                    borderClass = 'border-info';
                    break;
            }
            
            if (iconEl) iconEl.className = `${iconClass} notification-icon me-2`;
            if (statusBadgeEl) {
                statusBadgeEl.className = `${badgeClass} notification-status-badge`;
                statusBadgeEl.textContent = status;
            }
            notificationItem.className = `notification-item border-start border-4 ${borderClass} p-3 mb-2 bg-light-subtle rounded shadow-sm`;

            if (actionsEl) {
                const existingCancelBtn = actionsEl.querySelector('.cancel-task-btn');
                if (isCancellable) {
                    if (!existingCancelBtn) {
                        actionsEl.appendChild(this.createCancelButton(notificationItem.id.replace('notification-', '')));
                    } else {
                         existingCancelBtn.style.display = '';
                    }
                } else {
                    if (existingCancelBtn) {
                        existingCancelBtn.style.display = 'none'; // Hide instead of remove to keep listeners if needed
                    }
                }
            }
             this.updateNotificationBadge();
        },

        removeNotificationFromModal: function(taskId) {
            const notificationItem = document.getElementById(`notification-${taskId}`);
            if (notificationItem) {
                notificationItem.remove();
            }
            const notificationsList = document.getElementById('notificationsListContainer');
            const noNotificationsText = document.getElementById('noNotificationsText');
            if (notificationsList && noNotificationsText && notificationsList.children.length === 0) {
                noNotificationsText.style.display = 'block';
            }
            this.updateNotificationBadge();
        },
        updateNotificationBadge: function() {
            const notificationsList = document.getElementById('notificationsListContainer');
            if (!notificationsList) return;
            const count = notificationsList.querySelectorAll('.notification-item').length;
            const badge = document.getElementById('notificationCountBadge');
            if (badge) {
                badge.textContent = count;
                badge.style.display = count > 0 ? 'flex' : 'none';
            }
        }
    };
    
    // Initialize notification badge count
     window.ActiveProcessManager.updateNotificationBadge();

     // Mark all as read button
    const markAllReadBtn = document.getElementById('markAllNotificationsReadBtn');
    if(markAllReadBtn) {
        markAllReadBtn.addEventListener('click', () => {
            const notificationsList = document.getElementById('notificationsListContainer');
            if(notificationsList) {
                notificationsList.innerHTML = ''; // Clear all
                 window.ActiveProcessManager.updateNotificationBadge();
                 const noNotificationsText = document.getElementById('noNotificationsText');
                 if(noNotificationsText) noNotificationsText.style.display = 'block';
                 showGlobalAlert('All notifications cleared.', 'success', 2000);
            }
            // Also clear from ActiveProcessManager if tasks are truly done
            for (const taskId in window.ActiveProcessManager.tasks) {
                const task = window.ActiveProcessManager.tasks[taskId];
                if (task.status !== 'running' && task.status !== 'queued' && !task.status.toLowerCase().includes('processing')) {
                    delete window.ActiveProcessManager.tasks[taskId];
                }
            }
        });
    }


    // Sidebar toggle logic
    function setSidebarState(collapsed) {
        if (collapsed) {
            body.classList.add('sidebar-collapsed');
            if (toggleIcon) toggleIcon.classList.replace('fa-chevron-left', 'fa-chevron-right');
            if (sidebarToggleBtn) {
                sidebarToggleBtn.setAttribute('aria-expanded', 'false');
                sidebarToggleBtn.setAttribute('aria-label', 'Expand Sidebar');
            }
            localStorage.setItem(SIDEBAR_STATE_KEY, 'true');
        } else {
            body.classList.remove('sidebar-collapsed');
            if (toggleIcon) toggleIcon.classList.replace('fa-chevron-right', 'fa-chevron-left');
            if (sidebarToggleBtn) {
                sidebarToggleBtn.setAttribute('aria-expanded', 'true');
                sidebarToggleBtn.setAttribute('aria-label', 'Collapse Sidebar');
            }
            localStorage.setItem(SIDEBAR_STATE_KEY, 'false');
        }
        updateTooltips();
        // Dispatch a custom event for other scripts to listen to sidebar state changes
        window.dispatchEvent(new CustomEvent('sidebarStateChanged', { detail: { collapsed } }));
    }

    function toggleSidebar() {
        setSidebarState(!body.classList.contains('sidebar-collapsed'));
    }

    function updateTooltips() {
        const isCollapsed = body.classList.contains('sidebar-collapsed');
        const navLinks = sidebar ? sidebar.querySelectorAll('.sidebar-nav a[data-bs-toggle="tooltip"]') : [];

        navLinks.forEach(link => {
            const tooltipInstance = bootstrap.Tooltip.getInstance(link);
            if (isCollapsed) {
                if (!tooltipInstance) {
                     new bootstrap.Tooltip(link, {
                        placement: 'right',
                        trigger: 'hover focus', 
                        title: link.querySelector('.nav-text') ? link.querySelector('.nav-text').textContent.trim() : link.title
                    });
                } else {
                    tooltipInstance.enable();
                }
            } else {
                if (tooltipInstance) {
                    tooltipInstance.dispose(); // Dispose tooltip when not collapsed to prevent issues
                }
            }
        });
    }

    const savedState = localStorage.getItem(SIDEBAR_STATE_KEY);
    const initialCollapsedState = window.innerWidth > 768 ? (savedState === 'true') : true;
    setSidebarState(initialCollapsedState);

    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener('click', toggleSidebar);
    }
    
    // Mobile overlay logic
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function () {
            if (body.classList.contains('sidebar-expanded-mobile')) {
                body.classList.remove('sidebar-expanded-mobile');
                body.style.overflow = '';
                sidebarOverlay.setAttribute('aria-hidden', 'true');
                if (window.innerWidth <= 768 && !body.classList.contains('sidebar-collapsed')) {
                    setSidebarState(true);
                }
            }
        });
    }

    let resizeTimer;
    window.addEventListener('resize', function () {
        if (PREFERS_REDUCED_MOTION) return;
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            const isMobile = window.innerWidth <= 768;
            if (body.classList.contains('sidebar-expanded-mobile') && !isMobile) {
                body.classList.remove('sidebar-expanded-mobile');
                body.style.overflow = '';
                if (sidebarOverlay) sidebarOverlay.setAttribute('aria-hidden', 'true');
            }
            updateTooltips();
        }, 250);
    });

    updateTooltips(); // Initial call
});

// Enhanced Global Alert Function (Toast-like)
function showGlobalAlert(message, type = 'info', duration = 5000) {
    console.log(`[GlobalAlert] ${type}: ${message}`);
    try {
        const alertPlaceholderId = 'globalAlertPlaceholder'; // Ensure this div exists in sidebar_layout.html
        let alertPlaceholder = document.getElementById(alertPlaceholderId);

        if (!alertPlaceholder) {
            console.warn('Global alert placeholder not found. Creating one.');
            alertPlaceholder = document.createElement('div');
            alertPlaceholder.id = alertPlaceholderId;
            // Basic styling for the placeholder container itself
            Object.assign(alertPlaceholder.style, {
                position: 'fixed',
                top: '80px', /* Adjust if top bar height changes */
                right: '20px',
                zIndex: '1060', /* Ensure it's above most content */
                width: 'auto', /* Fit content */
                maxWidth: '400px' /* Max width for alerts */
            });
            document.body.appendChild(alertPlaceholder);
        }

        const alertId = `global-alert-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const iconClass = type === 'success' ? 'fa-check-circle' :
                          type === 'danger' ? 'fa-exclamation-triangle' :
                          type === 'warning' ? 'fa-exclamation-circle' : 'fa-info-circle';

        const alertElement = document.createElement('div');
        alertElement.id = alertId;
        // Use Bootstrap's alert classes for styling and dismissal
        alertElement.className = `alert alert-${type} alert-dismissible fade show shadow-sm`; 
        alertElement.setAttribute('role', 'alert');
        alertElement.style.marginBottom = '0.75rem'; // Spacing between alerts
        alertElement.style.display = 'flex'; // For icon alignment
        alertElement.style.alignItems = 'flex-start'; // Align icon with first line

        alertElement.innerHTML = `
            <i class="fas ${iconClass} fa-lg alert-icon me-2" style="padding-top: 0.25rem;"></i>
            <div class="alert-content flex-grow-1">${message}</div>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertPlaceholder.appendChild(alertElement);

        if (duration > 0) {
            setTimeout(() => {
                const bsAlert = bootstrap.Alert.getInstance(alertElement);
                if (bsAlert) {
                    bsAlert.close(); // This handles fade out and removal
                } else if (alertElement.parentNode) {
                    // Fallback if Bootstrap instance not found (e.g., element removed prematurely)
                    alertElement.classList.remove('show');
                     // Wait for fade out transition before removing from DOM
                    alertElement.addEventListener('transitionend', () => {
                        if(alertElement.parentNode) alertElement.remove();
                    }, { once: true });
                    // Failsafe removal
                    setTimeout(() => { if(alertElement.parentNode) alertElement.remove(); }, 200);
                }
            }, duration);
        }
    } catch (error) {
        console.error("Error in showGlobalAlert:", error, "Original Message:", message);
        // Fallback to window.alert if the sophisticated system fails
        window.alert(`${type.toUpperCase()}: ${message}`);
    }
}

// Global Loading Overlay Control (ensure #loadingOverlay exists in HTML)
const loadingOverlay = document.getElementById('loadingOverlay');
function showLoading(show = true) {
    console.log(`[Loading] Setting overlay to: ${show}`);
    if (loadingOverlay) {
        loadingOverlay.style.display = show ? 'flex' : 'none';
        loadingOverlay.setAttribute('aria-hidden', String(!show));
    }
}
