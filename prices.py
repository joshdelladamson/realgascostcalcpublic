import requests
import streamlit as st
from typing import Optional



@st.cache_data(ttl=86400)
def get_fred_baseline_price() -> float:
    """Fetch the latest US Regular All Formulations Gas Price from FRED as a free baseline."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GASREGW"
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

