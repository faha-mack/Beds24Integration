```bash
# Clone the repository
git clone <repository-url>
cd <repository-directory>

# Set up a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use 'venv\Scripts\activate'

# Install required Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Run the FastAPI application
python main.py