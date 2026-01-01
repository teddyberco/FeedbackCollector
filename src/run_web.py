from app import app
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    # Ensure we're in the correct directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Create templates directory if it doesn't exist
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print(f"Created templates directory at: {templates_dir}")
    
    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"Created data directory at: {data_dir}")
        
    print("\nStarting web interface for Feedback Collector")
    print("===========================================")
    print("1. Access the interface at: http://localhost:5000")
    print("2. View and manage keywords")
    print("3. Run feedback collection")
    print("4. View collection results")
    print("===========================================\n")
    
    # Set the template folder explicitly
    app.template_folder = os.path.abspath(templates_dir)
    print(f"Template folder set to: {app.template_folder}")
    
    # Run the Flask application
    app.run(debug=True, port=5000)
