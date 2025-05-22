import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import base64
import io
from io import BytesIO
def generate_correlation_plot(df, target_column='Electricity'):
    """
    Generate a correlation heatmap for the DataFrame.
    
    Args:
        df: DataFrame to analyze
        target_column: Target column for correlation (default: 'Electricity')
        
    Returns:
        Base64 encoded PNG image of the correlation plot
    """
    try:
        # Select numeric columns only
        numeric_df = df.select_dtypes(include=['number'])
        
        # Calculate correlation matrix
        corr_matrix = numeric_df.corr()
        
        # Create plot
        plt.figure(figsize=(10, 8))
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1, fmt='.2f')
        plt.title(f'Correlation Matrix for {target_column}')
        plt.tight_layout()
        
        # Save plot to a bytes buffer
        buf = BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        
        # Encode the image to base64
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        return f'data:image/png;base64,{img_str}'
    except Exception as e:
        print(f"Error generating correlation plot: {e}")
        return None

def generate_area_chart(df, x_column='Year'):
    """
    Generate an area chart for the DataFrame.
    
    Args:
        df: DataFrame to visualize
        x_column: Column to use for x-axis (default: 'Year')
        
    Returns:
        Base64 encoded PNG image of the area chart
    """
    try:
        # Create plot
        plt.figure(figsize=(12, 6))
        
        # Plot all columns except the x-axis column and 'Total' as stacked areas
        columns_to_plot = [col for col in df.columns if col != x_column and col != 'Total']
        df.plot(x=x_column, y=columns_to_plot, kind='area', stacked=True, alpha=0.7, ax=plt.gca())
        
        # Plot 'Total' as a line if it exists
        if 'Total' in df.columns:
            df.plot(x=x_column, y='Total', kind='line', color='black', linewidth=2, ax=plt.gca())
        
        plt.title(f'Electricity Consumption by Sector')
        plt.xlabel(x_column)
        plt.ylabel('Electricity (units)')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend(title='Sectors')
        plt.tight_layout()
        
        # Save plot to a bytes buffer
        buf = BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        
        # Encode the image to base64
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        return f'data:image/png;base64,{img_str}'
    except Exception as e:
        print(f"Error generating area chart: {e}")
        return None