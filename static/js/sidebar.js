document.addEventListener('DOMContentLoaded', function () {
    const sidebarToggleBtn = document.getElementById('sidebarToggle');
    const body = document.body;
    const sidebar = document.getElementById('appSidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const toggleIcon = sidebarToggleBtn ? sidebarToggleBtn.querySelector('i') : null;

    const PREFERS_REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const SIDEBAR_STATE_KEY = 'sidebarCollapsedState';
    // Global alert function
    // In sidebar.js OR a common utility JS file
    function showGlobalAlert(message, type = 'info', duration = 5000) {
        try {
            const alertPlaceholderId = 'globalAlertPlaceholder';
            let alertPlaceholder = document.getElementById(alertPlaceholderId);

            if (!alertPlaceholder) {
                alertPlaceholder = document.createElement('div');
                alertPlaceholder.id = alertPlaceholderId;
                alertPlaceholder.style.position = 'fixed';
                alertPlaceholder.style.top = '80px';
                alertPlaceholder.style.right = '20px';
                alertPlaceholder.style.zIndex = '1060'; // Higher than most modals
                alertPlaceholder.style.maxWidth = '400px';
                document.body.appendChild(alertPlaceholder);
            }

            const alertId = `global-alert-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            const iconClass = type === 'success' ? 'fa-check-circle text-success' :
                type === 'danger' ? 'fa-exclamation-triangle text-danger' :
                    type === 'warning' ? 'fa-exclamation-circle text-warning' :
                        'fa-info-circle text-info';

            const alertElement = document.createElement('div');
            alertElement.id = alertId;
            alertElement.className = `alert alert-${type} alert-dismissible fade`; // Start without 'show'
            alertElement.setAttribute('role', 'alert');
            alertElement.style.marginBottom = '0.5rem';

            alertElement.innerHTML = `
            <i class="fas ${iconClass} fa-lg alert-icon me-2" style="padding-top:0.25rem;"></i>
            <div class="alert-content flex-grow-1">${message}</div>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

            alertPlaceholder.insertAdjacentElement('beforeend', alertElement); // Use insertAdjacentElement

            // Force a reflow before adding 'show' class for the transition to work
            void alertElement.offsetWidth;
            alertElement.classList.add('show');

            if (duration) {
                setTimeout(() => {
                    // Attempt to close using Bootstrap's API first
                    const bsAlertInstance = bootstrap.Alert.getInstance(alertElement);
                    if (bsAlertInstance) {
                        bsAlertInstance.close(); // This handles the fade and removal
                    } else if (alertElement && alertElement.classList.contains('show')) {
                        // Fallback if instance not found or already being dismissed
                        alertElement.classList.remove('show');
                        alertElement.addEventListener('transitionend', () => {
                            if (alertElement.parentNode) alertElement.remove();
                        }, { once: true });
                        // Failsafe removal
                        setTimeout(() => { if (alertElement && alertElement.parentNode) alertElement.remove(); }, 200);
                    } else if (alertElement && alertElement.parentNode) {
                        // If 'show' is already gone but element persists
                        alertElement.remove();
                    }
                }, duration);
            }
        } catch (error) {
            console.error("Error in showGlobalAlert:", error, "Message:", message, "Type:", type);
            window.alert(`${type.toUpperCase()}: ${message}`); // Fallback
        }
    }

    function setSidebarState(collapsed) {
        if (collapsed) {
            body.classList.add('sidebar-collapsed');
            if (toggleIcon) toggleIcon.classList.replace('fa-chevron-left', 'fa-chevron-right');
            if (sidebarToggleBtn) sidebarToggleBtn.setAttribute('aria-expanded', 'false');
            if (sidebarToggleBtn) sidebarToggleBtn.setAttribute('aria-label', 'Expand Sidebar');
            localStorage.setItem(SIDEBAR_STATE_KEY, 'true');
        } else {
            body.classList.remove('sidebar-collapsed');
            if (toggleIcon) toggleIcon.classList.replace('fa-chevron-right', 'fa-chevron-left');
            if (sidebarToggleBtn) sidebarToggleBtn.setAttribute('aria-expanded', 'true');
            if (sidebarToggleBtn) sidebarToggleBtn.setAttribute('aria-label', 'Collapse Sidebar');
            localStorage.setItem(SIDEBAR_STATE_KEY, 'false');
        }
        // Re-initialize or update tooltips if their trigger condition changes
        updateTooltips();
    }

    function toggleSidebar() {
        setSidebarState(!body.classList.contains('sidebar-collapsed'));
    }

    function updateTooltips() {
        const isCollapsed = body.classList.contains('sidebar-collapsed');
        const navLinks = sidebar ? sidebar.querySelectorAll('.sidebar-nav a') : [];

        navLinks.forEach(link => {
            const tooltipInstance = bootstrap.Tooltip.getInstance(link);
            if (isCollapsed) {
                if (!tooltipInstance) {
                    new bootstrap.Tooltip(link, {
                        placement: 'right',
                        trigger: 'hover focus', // Show on hover and focus
                        title: link.querySelector('.nav-text') ? link.querySelector('.nav-text').textContent : link.title
                    });
                } else {
                    tooltipInstance.enable();
                }
            } else {
                if (tooltipInstance) {
                    tooltipInstance.disable();
                }
            }
        });
    }

    // Load saved sidebar state
    const savedState = localStorage.getItem(SIDEBAR_STATE_KEY);
    // Default to collapsed on larger screens, can be changed
    const initialCollapsedState = window.innerWidth > 768 ? (savedState === 'true') : true;
    setSidebarState(initialCollapsedState);


    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener('click', function () {
            toggleSidebar();

            // Mobile specific overlay and body scroll management
            if (window.innerWidth <= 768) {
                body.classList.toggle('sidebar-expanded-mobile'); // Use a more specific class
                if (body.classList.contains('sidebar-expanded-mobile')) {
                    body.style.overflow = 'hidden';
                    if (sidebarOverlay) sidebarOverlay.setAttribute('aria-hidden', 'false');
                } else {
                    body.style.overflow = '';
                    if (sidebarOverlay) sidebarOverlay.setAttribute('aria-hidden', 'true');
                }
            }
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function () {
            if (body.classList.contains('sidebar-expanded-mobile')) {
                body.classList.remove('sidebar-expanded-mobile');
                body.style.overflow = '';
                sidebarOverlay.setAttribute('aria-hidden', 'true');
                // Also ensure the main sidebar state reflects collapse on mobile close
                if (window.innerWidth <= 768 && !body.classList.contains('sidebar-collapsed')) {
                    setSidebarState(true);
                }
            }
        });
    }

    // Adjust sidebar state on window resize
    let resizeTimer;
    window.addEventListener('resize', function () {
        if (PREFERS_REDUCED_MOTION) return; // Skip resize adjustments if prefers reduced motion
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            const isMobile = window.innerWidth <= 768;

            if (body.classList.contains('sidebar-expanded-mobile') && !isMobile) {
                // If resized to desktop while mobile sidebar was open
                body.classList.remove('sidebar-expanded-mobile');
                body.style.overflow = '';
                if (sidebarOverlay) sidebarOverlay.setAttribute('aria-hidden', 'true');
            } else if (isMobile && !body.classList.contains('sidebar-collapsed') && !body.classList.contains('sidebar-expanded-mobile')) {
                // If resized to mobile and desktop sidebar was open, collapse it.
                // setSidebarState(true);
            }
            updateTooltips(); // Update tooltips on resize
        }, 250);
    });

    // Initial tooltip setup
    updateTooltips();
});