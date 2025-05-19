import json
import os

DATA_FILE = "data/balance.json"

def load_data():
    """Load data from the JSON file."""
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as file:
        return json.load(file)

def save_data(data):
    """Save data to the JSON file."""
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)