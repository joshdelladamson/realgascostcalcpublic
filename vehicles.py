import requests
import streamlit as st
from typing import List, Dict, Any, Optional

BASE_URL = "https://www.fueleconomy.gov/ws/rest/vehicle"
HEADERS = {"Accept": "application/json"}

@st.cache_data(ttl=86400)
def get_years() -> List[str]:
    """Fetch available vehicle years (1998+)."""
    try:
        response = requests.get(f"{BASE_URL}/menu/year", headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        menu_items = data.get("menuItem", [])
        if isinstance(menu_items, dict):
            menu_items = [menu_items]
        
        years = [item["value"] for item in menu_items if int(item["value"]) >= 1998]
        return sorted(years, reverse=True)
    except Exception as e:
        st.error(f"Failed to fetch years from fueleconomy.gov: {e}")
        return []

@st.cache_data(ttl=86400)
def get_makes(year: str) -> List[str]:
    """Fetch available makes for a given year."""
    try:
        response = requests.get(f"{BASE_URL}/menu/make?year={year}", headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        menu_items = data.get("menuItem", [])
        if isinstance(menu_items, dict):
            menu_items = [menu_items]
        return [item["value"] for item in menu_items]
    except Exception as e:
        st.error(f"Failed to fetch makes: {e}")
        return []

@st.cache_data(ttl=86400)
def get_models(year: str, make: str) -> List[str]:
    """Fetch available models for a given year and make."""
    try:
        response = requests.get(f"{BASE_URL}/menu/model?year={year}&make={make}", headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        menu_items = data.get("menuItem", [])
        if isinstance(menu_items, dict):
            menu_items = [menu_items]
        return [item["value"] for item in menu_items]
    except Exception as e:
        st.error(f"Failed to fetch models: {e}")
        return []

@st.cache_data(ttl=86400)
def get_trims(year: str, make: str, model: str) -> List[Dict[str, str]]:
    """Fetch available trims for a given year, make, model. Returns list of dicts with 'text' and 'value' (id)."""
    try:
        response = requests.get(f"{BASE_URL}/menu/options?year={year}&make={make}&model={model}", headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        menu_items = data.get("menuItem", [])
        if isinstance(menu_items, dict):
            menu_items = [menu_items]
        return [{"text": item["text"], "value": item["value"]} for item in menu_items]
    except Exception as e:
        st.error(f"Failed to fetch trims: {e}")
        return []

@st.cache_data(ttl=86400)
def get_vehicle_mpg(vehicle_id: str) -> Optional[Dict[str, float]]:
    """Fetch city and highway MPG for a specific vehicle ID."""
    try:
        response = requests.get(f"{BASE_URL}/{vehicle_id}", headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        city_mpg = float(data.get("city08", 0))
        highway_mpg = float(data.get("highway08", 0))
        combined_mpg = float(data.get("comb08", 0))
        
        if city_mpg == 0 or highway_mpg == 0:
            return None
            
        return {
            "city": city_mpg,
            "highway": highway_mpg,
            "combined": combined_mpg
        }
    except Exception as e:
        st.error(f"Failed to fetch vehicle details: {e}")
        return None

