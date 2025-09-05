from flask import Blueprint, render_template, url_for, flash, redirect, current_app

core_bp = Blueprint('core', __name__, template_folder='../templates', static_folder='../static')

# Helper function to be moved
def get_recent_activities():
    # Using current_app.logger as 'logger' might not be defined here directly
    current_app.logger.debug("Fetching recent activities") 
    activities = [
        {
            'icon': 'fas fa-chart-line',
            'title': 'Created forecast for "Energy Scenario 2025"',
            'time': '2 hours ago',
            'link': url_for('demand.demand_visualization_route') # This will eventually be demand_bp.demand.demand_visualization_route
        },
        {
            'icon': 'fas fa-upload',
            'title': 'Uploaded data for "Regional Analysis"',
            'time': 'Yesterday',
            'link': '#'
        },
        {
            'icon': 'fas fa-cogs',
            'title': 'Ran PyPSA model for "Renewable Integration"',
            'time': '3 days ago',
            'link': url_for('pypsa.pypsa_results_route') # This will eventually be pypsa_bp.pypsa.pypsa_results_route
        }
    ]
    return activities

@core_bp.route('/')
def home():
    current_app.logger.info("Accessing home route via core_bp")
    try:
        recent_activities = get_recent_activities()
        current_app.logger.debug(f"Retrieved {len(recent_activities)} recent activities for core_bp.home")
        
        return render_template('home.html', 
                              recent_activities=recent_activities,
                              current_project=current_app.config.get('CURRENT_PROJECT'))
    except Exception as e:
        current_app.logger.exception(f"Error rendering home template via core_bp: {e}")
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('core.home')) # Adjusted to core.home

@core_bp.route('/user_guide')
def user_guide():
    current_app.logger.info("Accessing user_guide route via core_bp")
    return render_template('user_guide.html')

@core_bp.route('/tutorials')
def tutorials():
    current_app.logger.info("Accessing tutorials route via core_bp")
    flash('Tutorials page is coming soon!', 'info')
    # Assuming home is now part of this blueprint, redirect to 'core.home'
    return redirect(url_for('core.home'))
