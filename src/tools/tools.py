import pandas as pd
import os

from langchain.tools import tool

@tool
def get_column_names(filepath: str) -> str:
    """Gets the column names of a CSV file. If the file is not found, suggests similar files.

    Args:
        filepath: location of the csv
    """
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        return str(list(df.columns))
    
    # Search for similar files
    filename = os.path.basename(filepath)
    similar = []
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".csv") and filename.lower() in f.lower() or f.lower() in filename.lower():
                similar.append(os.path.join(root, f))
    
    if similar:
        return f"File '{filepath}' not found. Did you mean: {', '.join(similar)}?"
    return f"File '{filepath}' not found and no similar files found."