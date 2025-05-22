# flask geminii/setup.py
import sys
import os
from cx_Freeze import setup, Executable

# --- Attempt to fix RecursionError by increasing the limit ---
# Keep this from the previous step, as it might still be needed.
try:
    sys.setrecursionlimit(3000)
    print(f"Set recursion limit to {sys.getrecursionlimit()}")
except Exception as e:
    print(f"Warning: Could not set recursion limit: {e}")

# --- Basic Setup ---
project_root_dir = os.path.abspath(os.path.dirname(__file__))
base = None
if sys.platform == "win32":
    base = "Win32GUI"

# --- Dependencies ---
# ** Added 'pyarrow' and 'seaborn' explicitly **
packages = [










    "Flask", "pandas", "numpy", "matplotlib","plotly", # From requirements.txt
    "scipy", "statsmodels", "sklearn", "openpyxl", # Inferred
    "jinja2", "werkzeug", "dotenv",   "reportlab",          # Flask/Config
    "datetime", "os", "logging", "traceback", "json","prophet", # Standard
    "xgboost",'pypsa'
    # --- Added based on runtime error ---
    "pyarrow",      # Explicitly include pyarrow to help cx_Freeze find all parts
    "seaborn",      # Explicitly include seaborn as it was in the traceback trigger path

    # --- PyPSA related (Commented out unless needed & verified) ---
    # "pypsa", "pyomo", "networkx", "tables", "xarray",
]

# --- Modules to explicitly include ---
# Helps cx_Freeze find modules, especially in subdirectories or complex packages
includes = [
    "models.demand_forecast",
    "models.demand_curve_report",
    "models.demand_forecast_monthly",
    "energy_convertors",
    "forecasting",
    "load_profile_manager",
    "config",

    # --- Ensure pandas._libs are included (Can sometimes help with pandas/numpy issues) ---
    "pandas._libs.tslibs",

    # --- PyPSA related (Commented out unless needed) ---
    # "pypsa_results",
    # "models.pypsa_model",
]

# --- Packages to exclude ---
excludes = ["tkinter"]

# --- Files and Folders to Include ---
include_files = [
    ("static", "static"),
    ("templates", "templates"),

]

# --- Build Options ---
build_exe_options = {
    "packages": packages,
    "includes": includes,
    "excludes": excludes,
    "include_files": include_files,
    "optimize": 2,
}

# --- Define the Executable ---
executables = [
    Executable(
        script="app.py",
        base=base,
        target_name="EnergyModeler.exe",
        icon=None,
    )
]

# --- Setup Configuration ---
setup(
    name="EnergyModelerWebApp",
    version="1.0",
    description="Energy Modeler Flask App",
    options={"build_exe": build_exe_options},
    executables=executables,
)

print("\n--- Setup Script Finished ---")