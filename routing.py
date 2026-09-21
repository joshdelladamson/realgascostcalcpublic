import requests
import streamlit as st
import pandas as pd
import math
from typing import Dict, List, Tuple, Any, Optional
import time

def search_addresses(query: str) -> List[Dict[str, Any]]:
    """Search for addresses using Photon API."""
    if not query:
        return []
        
    url = "https://photon.komoot.io/api/"
    params = {"q": query, "limit": 5}
    headers = {"User-Agent": "RealGasCostCalc/1.0 (Python requests)"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            if geom.get("type") == "Point":
                lon, lat = geom["coordinates"]
                name = props.get("name", "")
                city = props.get("city", props.get("town", props.get("village", "")))
                state = props.get("state", "")
                country = props.get("country", "")
                
                # Build a display label
                parts = [p for p in [name, city, state, country] if p]
                label = ", ".join(parts)
                
                # State mapping for US
                us_states = {
                    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
                    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
                    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
                    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
                    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
                    "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
                    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
                    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
                    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
                    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"
                }
                
                state_abbr = "US"
                if state:
                    if state in us_states:
                        state_abbr = us_states[state]
                    elif len(state) == 2:
                        state_abbr = state.upper()
                
                results.append({
                    "label": label,
                    "lat": float(lat),
                    "lon": float(lon),
                    "state_abbr": state_abbr
                })
        return results
    except Exception as e:
        st.error(f"Failed to search address: {e}")
        return []

def geocode(address: str) -> Optional[Tuple[float, float, str, str]]:
    """Fallback geocode that just picks the first result from search."""
    results = search_addresses(address)
    if results:
        res = results[0]
        return res["lat"], res["lon"], res["state_abbr"], res["label"]
    return None

@st.cache_data(ttl=3600)
def get_route(origin: Tuple[float, float], dest: Tuple[float, float]) -> Optional[List[Dict[str, Any]]]:
    """Fetch routes from OSRM including alternatives."""
    url = f"http://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
    params = {
        "steps": "true",
        "geometries": "geojson",
        "overview": "full",
        "annotations": "true",
        "alternatives": "2"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("code") == "Ok" and len(data["routes"]) > 0:
            return data["routes"]
    except Exception as e:
        st.error(f"Failed to fetch route from OSRM: {e}")
        
    return None

def get_elevations(locations: List[Tuple[float, float]]) -> List[float]:
    """Fetch elevations from OpenTopoData for a list of (lat, lon)."""
    if not locations:
        return []
        
    # OpenTopoData allows up to 100 locations per request
    elevations = []
    chunk_size = 100
    
    for i in range(0, len(locations), chunk_size):
        chunk = locations[i:i + chunk_size]
        loc_str = "|".join([f"{lat},{lon}" for lat, lon in chunk])
        url = f"https://api.opentopodata.org/v1/srtm90m?locations={loc_str}"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                elevations.extend([res.get("elevation") or 0.0 for res in results])
            else:
                # Fallback to 0 if API fails
                elevations.extend([0.0] * len(chunk))
        except Exception:
            elevations.extend([0.0] * len(chunk))
            
        time.sleep(0.1) # Be nice to the API
        
    return elevations

@st.cache_data(ttl=3600)
def process_route_steps(route_data: Dict[str, Any]) -> pd.DataFrame:
    """Process OSRM steps into a DataFrame with distances, speeds, and elevations."""
    legs = route_data.get("legs", [])
    if not legs:
        return pd.DataFrame()
        
    steps = legs[0].get("steps", [])
    
    processed_steps = []
    points_to_elevate = []
    
    for step in steps:
        dist_m = step.get("distance", 0)
        dur_s = step.get("duration", 0)
        
        # Convert to miles and hours
        dist_mi = dist_m * 0.000621371
        dur_h = dur_s / 3600.0
        
        avg_speed_mph = (dist_mi / dur_h) if dur_h > 0 else 0
        
        # Get coordinates for elevation
        # Geometry is GeoJSON LineString
        geom = step.get("geometry", {}).get("coordinates", [])
        if geom and len(geom) >= 2:
            start_lon, start_lat = geom[0]
            end_lon, end_lat = geom[-1]
            points_to_elevate.append((start_lat, start_lon))
            points_to_elevate.append((end_lat, end_lon))
        else:
            points_to_elevate.append((0, 0))
            points_to_elevate.append((0, 0))
            
        processed_steps.append({
            "name": step.get("name", "Unnamed Road"),
            "distance_mi": dist_mi,
            "duration_h": dur_h,
            "avg_speed_mph": avg_speed_mph,
            "geometry": geom
        })
        
    # Fetch elevations
    if points_to_elevate:
        elevations_m = get_elevations(points_to_elevate)
        # Convert to feet
        elevations_ft = [e * 3.28084 if e else 0 for e in elevations_m]
        
        for i, step in enumerate(processed_steps):
            step["start_elev_ft"] = elevations_ft[i*2]
            step["end_elev_ft"] = elevations_ft[i*2 + 1]
            step["elev_change_ft"] = step["end_elev_ft"] - step["start_elev_ft"]
            
            # Grade = rise / run
            run_ft = step["distance_mi"] * 5280
            step["grade_pct"] = (step["elev_change_ft"] / run_ft * 100) if run_ft > 0 else 0
            
    df = pd.DataFrame(processed_steps)
    
    # We will no longer fabricate speed_limit_mph
    return df

