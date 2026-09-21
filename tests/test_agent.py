import pytest
import pandas as pd
import os

def test_get_column_names_returns_correct_columns(tmp_path):
    # create a temp CSV
    df = pd.DataFrame({"name": [], "age": [], "city": []})
    csv_path = tmp_path / "test.csv"
    df.to_csv(csv_path, index=False)
    
    # import and call the tool directly
    from src.tools.tools import get_column_names
    result = get_column_names.invoke({"filepath": str(csv_path)})
    
    assert "name" in result
    assert "age" in result
    assert "city" in result