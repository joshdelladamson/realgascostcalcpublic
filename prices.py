import requests
import streamlit as st
from typing import Optional



@st.cache_data(ttl=86400)
def fetch_fred_price(grade: str = "Regular") -> float:
    """Fetch the latest US Gas Price from FRED as a free baseline based on grade."""
    
    grade_map = {
        "Regular": "GASREGW",
        "Midgrade (Blend)": "GASMIDW",
        "Premium": "GASPRMW",
        "Diesel": "GASDESW"
    }
    
    series_id = grade_map.get(grade, "GASREGW")
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = response.text.strip().split('\n')
        # Iterate backwards to find the last valid float price
        for line in reversed(lines):
            parts = line.split(',')
            if len(parts) == 2:
                try:
                    return float(parts[1])
                except ValueError:
                    continue
    except Exception:
        pass
    return 3.50  # Fallback baseline

