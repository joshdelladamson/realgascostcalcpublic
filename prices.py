import requests
import streamlit as st
from typing import Optional

@st.cache_data(ttl=86400)
def get_live_gas_price(api_key: str, state_abbr: str = "US") -> Optional[float]:
    """
    Fetch the latest weekly retail gasoline price from EIA API.
    Defaults to US average if state is not mapped.
    """
    if not api_key:
        return None
    
    # State mapping to EIA series IDs for Regular All Formulations Retail Gasoline Prices
    state_series = {
        "CA": "EMM_EPMR_PTE_SCA_DPG",
        "TX": "EMM_EPMR_PTE_STX_DPG",
        "NY": "EMM_EPMR_PTE_SNY_DPG",
        "CO": "EMM_EPMR_PTE_SCO_DPG",
        "FL": "EMM_EPMR_PTE_SFL_DPG",
        "MA": "EMM_EPMR_PTE_SMA_DPG",
        "MN": "EMM_EPMR_PTE_SMN_DPG",
        "OH": "EMM_EPMR_PTE_SOH_DPG",
        "WA": "EMM_EPMR_PTE_SWA_DPG",
    }
    
    series_id = state_series.get(state_abbr, "EMM_EPMR_PTE_NUS_DPG")
    
    url = (
        f"https://api.eia.gov/v2/petroleum/pri/gnd/data/"
        f"?api_key={api_key}"
        f"&frequency=weekly"
        f"&data[0]=value"
        f"&facets[series][]={series_id}"
        f"&sort[0][column]=period"
        f"&sort[0][direction]=desc"
        f"&offset=0"
        f"&length=1"
    )
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "response" in data and "data" in data["response"] and len(data["response"]["data"]) > 0:
            return float(data["response"]["data"][0]["value"])
            
    except Exception as e:
        st.warning(f"Failed to fetch live gas price from EIA API: {e}")
        
    return None

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

