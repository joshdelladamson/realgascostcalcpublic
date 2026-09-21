import streamlit as st
import pandas as pd
import pydeck as pdk
from vehicles import get_years, get_makes, get_models, get_trims, get_vehicle_mpg
from routing import geocode, search_addresses, get_route, process_route_steps
from prices import get_live_gas_price
from physics import calculate_segment_fuel

st.set_page_config(page_title="RealGasCostCalc", layout="wide")

st.title("🚗 RealGasCostCalc")
st.write("A physics-based road-trip gas cost calculator utilizing real road data and EPA vehicle ratings.")

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Trip Details")
origin_str = st.sidebar.text_input("Search Origin", "San Francisco, CA")
origin_results = search_addresses(origin_str) if origin_str else []
origin_options = {res["label"]: res for res in origin_results}
origin_selected_label = st.sidebar.selectbox("Select Origin", list(origin_options.keys())) if origin_options else None

dest_str = st.sidebar.text_input("Search Destination", "Los Angeles, CA")
dest_results = search_addresses(dest_str) if dest_str else []
dest_options = {res["label"]: res for res in dest_results}
dest_selected_label = st.sidebar.selectbox("Select Destination", list(dest_options.keys())) if dest_options else None

round_trip = st.sidebar.checkbox("Round Trip", value=False)

st.sidebar.header("2. Vehicle Selection")
years = get_years()
year = st.sidebar.selectbox("Year", years) if years else None

make = None
if year:
    makes = get_makes(year)
    make = st.sidebar.selectbox("Make", makes) if makes else None

model = None
if make:
    models = get_models(year, make)
    model = st.sidebar.selectbox("Model", models) if models else None

trim_id = None
if model:
    trims = get_trims(year, make, model)
    if trims:
        trim_options = {t["text"]: t["value"] for t in trims}
        trim_text = st.sidebar.selectbox("Trim", list(trim_options.keys()))
        trim_id = trim_options[trim_text]

vehicle_mpg = None
if trim_id:
    vehicle_mpg = get_vehicle_mpg(trim_id)
    if vehicle_mpg:
        st.sidebar.success(f"EPA Rating: {vehicle_mpg['city']} City / {vehicle_mpg['highway']} Hwy MPG")
    else:
        st.sidebar.warning("Could not fetch EPA rating.")

manual_city_mpg = st.sidebar.number_input("Override City MPG", value=float(vehicle_mpg['city']) if vehicle_mpg else 25.0)
manual_hwy_mpg = st.sidebar.number_input("Override Highway MPG", value=float(vehicle_mpg['highway']) if vehicle_mpg else 35.0)

st.sidebar.header("3. Gas Price")
eia_key = st.sidebar.text_input("EIA API Key (Optional)", type="password", help="Get one for free at eia.gov. Defaults to manual price if empty.")
manual_price = st.sidebar.number_input("Manual Gas Price ($/gal)", min_value=0.1, value=3.50, step=0.1)

# --- ACTION BUTTON ---
if st.sidebar.button("Calculate Cost", type="primary"):
    with st.spinner("Analyzing route and fetching data..."):
        # 1. Geocode
        origin = None
        if origin_selected_label:
            res = origin_options[origin_selected_label]
            origin = (res["lat"], res["lon"], res["state_abbr"])
            
        dest = None
        if dest_selected_label:
            res = dest_options[dest_selected_label]
            dest = (res["lat"], res["lon"], res["state_abbr"])
        
        if not origin or not dest:
            st.error("Could not determine origin or destination. Please make sure both are selected.")
            st.stop()
            
        # 2. Price lookup
        live_price = get_live_gas_price(eia_key, origin[2]) if eia_key else None
        active_price = manual_price
        
        if live_price:
            st.info(f"Using live EIA gas price for {origin[2]} or US Avg: ${live_price:.2f}/gal")
            active_price = live_price
        else:
            if eia_key:
                st.warning("EIA lookup failed, falling back to manual price.")
            st.info(f"Using manual gas price: ${active_price:.2f}/gal")
            
        # 3. Routing
        route_data = get_route((origin[0], origin[1]), (dest[0], dest[1]))
        if not route_data:
            st.error("Failed to fetch route from OSRM.")
            st.stop()
            
        # 4. Process steps
        with st.spinner("Calculating elevations and segment speeds..."):
            df_steps = process_route_steps(route_data)
            
        if df_steps.empty:
            st.error("No route steps found.")
            st.stop()
            
        # 5. Physics Model
        total_gallons = 0.0
        total_distance = 0.0
        
        gallons_list = []
        eff_mpg_list = []
        
        for _, row in df_steps.iterrows():
            gals, eff = calculate_segment_fuel(
                distance_mi=row["distance_mi"],
                speed_mph=row["avg_speed_mph"],
                speed_limit_mph=0.0, # Removed speed limit heuristic
                grade_pct=row.get("grade_pct", 0),
                city_mpg=manual_city_mpg,
                highway_mpg=manual_hwy_mpg
            )
            gallons_list.append(gals)
            eff_mpg_list.append(eff)
            
            total_gallons += gals
            total_distance += row["distance_mi"]
            
        df_steps["gallons_used"] = gallons_list
        df_steps["effective_mpg"] = eff_mpg_list
        df_steps["cost"] = df_steps["gallons_used"] * active_price
        
        # Round trip logic
        multiplier = 2 if round_trip else 1
        total_gallons *= multiplier
        total_distance *= multiplier
        total_cost = total_gallons * active_price
        
        # --- RESULTS UI ---
        st.header("Trip Results")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Cost", f"${total_cost:.2f}")
        col2.metric("Total Fuel", f"{total_gallons:.2f} gal")
        col3.metric("Total Distance", f"{total_distance:.1f} mi")
        col4.metric("Avg Effective MPG", f"{(total_distance/total_gallons):.1f}" if total_gallons > 0 else "N/A")
        
        # Map
        st.subheader("Route Map")
        path = []
        for _, row in df_steps.iterrows():
            geom = row.get("geometry", [])
            for pt in geom:
                path.append([pt[0], pt[1]])
                
        if path:
            layer = pdk.Layer(
                'PathLayer',
                data=[{"path": path}],
                get_path="path",
                get_color=[255, 0, 0, 200],
                width_scale=20,
                width_min_pixels=5,
                get_width=5
            )
            view_state = pdk.ViewState(
                longitude=origin[1],
                latitude=origin[0],
                zoom=5,
                pitch=0
            )
            r = pdk.Deck(layers=[layer], initial_view_state=view_state, map_style="road")
            st.pydeck_chart(r)
            
        # Table
        st.subheader("Segment Breakdown")
        display_df = df_steps[["name", "distance_mi", "avg_speed_mph", "grade_pct", "effective_mpg", "cost"]].copy()
        
        # Formatting for readability
        display_df["distance_mi"] = display_df["distance_mi"].map("{:.2f}".format)
        display_df["avg_speed_mph"] = display_df["avg_speed_mph"].map("{:.1f}".format)
        display_df["grade_pct"] = display_df["grade_pct"].map("{:.1f}%".format)
        display_df["effective_mpg"] = display_df["effective_mpg"].map("{:.1f}".format)
        display_df["cost"] = display_df["cost"].map("${:.2f}".format)
        
        st.dataframe(display_df, use_container_width=True)
