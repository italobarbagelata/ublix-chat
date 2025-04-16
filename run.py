import os
import sys
import subprocess

def main():
    # Ensure we're in the right directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Create and activate virtual environment if it doesn't exist
    if not os.path.exists('antenv'):
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, '-m', 'venv', 'antenv'])
    
    # Install dependencies
    print("Installing dependencies...")
    if os.name == 'nt':  # Windows
        pip_path = os.path.join('antenv', 'Scripts', 'pip')
    else:  # Linux/Mac
        pip_path = os.path.join('antenv', 'bin', 'pip')
    
    subprocess.check_call([pip_path, 'install', '--upgrade', 'pip'])
    subprocess.check_call([pip_path, 'install', '-r', 'requirements.txt'])
    
    # Start the application
    print("Starting application...")
    if os.name == 'nt':  # Windows
        python_path = os.path.join('antenv', 'Scripts', 'python')
    else:  # Linux/Mac
        python_path = os.path.join('antenv', 'bin', 'python')
    
    subprocess.check_call([python_path, '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'])

if __name__ == "__main__":
    main() 