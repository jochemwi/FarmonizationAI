import pandas as pd
from langchain.tools import tool

@tool
def get_column_names(filepath: str) -> list[str]:
	"""gets the column names

	Args:
		filepath: location of the csv
	
	
	"""
	df = pd.read_csv(filepath)
	return list(df.columns)

  