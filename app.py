import streamlit as st
import pandas as pd
import pydeck as pdk
from vehicles import get_years, get_makes, get_models, get_trims, get_vehicle_mpg
from routing import geocode, get_route, process_route_steps, search_addresses
from prices import get_fred_baseline_price
from physics import calculate_segment_fuel

st.set_page_config(page_title="Real Gas Cost Calculator", layout="wide")

st.title("🚗 Real Gas Cost Calculator")
st.write("A physics-based road-trip gas cost calculator utilizing real road data and EPA vehicle ratings.")

# --- MAIN PAGE INPUTS ---
st.header("1. Trip Details")

if "num_stops" not in st.session_state:
    st.session_state.num_stops = 0

col_add, col_rem, _ = st.columns([1, 1, 4])
if col_add.button("➕ Add Stop"):
    st.session_state.num_stops += 1
if col_rem.button("➖ Remove Stop"):
    if st.session_state.num_stops > 0:
        st.session_state.num_stops -= 1

origin_str = st.text_input("Origin Address", "San Francisco, CA")

waypoints_strs = []
for i in range(st.session_state.num_stops):
    waypoints_strs.append(st.text_input(f"Stop {i+1} Address", key=f"stop_in_{i}"))
    
dest_str = st.text_input("Destination Address", "Los Angeles, CA")
st.checkbox("Round Trip", value=False, key="round_trip")
search_btn = st.button("Search Addresses")

if search_btn:
    st.session_state.origin_results = search_addresses(origin_str)
    st.session_state.dest_results = search_addresses(dest_str)
    
    # Process waypoints
    valid_waypoints = [w.strip() for w in waypoints_strs if w.strip()]
    st.session_state.waypoints_results = [search_addresses(w) for w in valid_waypoints]

# Collect all confirmed coordinates
route_coords = []

# Origin
if "origin_results" in st.session_state:
    if st.session_state.origin_results:
        origin_labels = [opt["label"] for opt in st.session_state.origin_results]
        sel_origin = st.selectbox("Select exact Origin", origin_labels)
        if sel_origin:
            sel_dict = next((opt for opt in st.session_state.origin_results if opt["label"] == sel_origin), None)
            if sel_dict:
                route_coords.append((sel_dict["lat"], sel_dict["lon"]))
    else:
        st.warning("Could not find an address match for the Origin.")

# Waypoints
if "waypoints_results" in st.session_state and st.session_state.waypoints_results:
    for i, w_results in enumerate(st.session_state.waypoints_results):
        if w_results:
            labels = [opt["label"] for opt in w_results]
            sel = st.selectbox(f"Select exact Stop {i+1}", labels, key=f"wp_{i}")
            if sel:
                sel_dict = next((opt for opt in w_results if opt["label"] == sel), None)
                if sel_dict:
                    route_coords.append((sel_dict["lat"], sel_dict["lon"]))
        else:
            st.warning(f"Could not find an address match for Stop {i+1}. Please try a different search.")

# Destination
if "dest_results" in st.session_state:
    if st.session_state.dest_results:
        dest_labels = [opt["label"] for opt in st.session_state.dest_results]
        sel_dest = st.selectbox("Select exact Destination", dest_labels)
        if sel_dest:
            sel_dict = next((opt for opt in st.session_state.dest_results if opt["label"] == sel_dest), None)
            if sel_dict:
                route_coords.append((sel_dict["lat"], sel_dict["lon"]))
    else:
        st.warning("Could not find an address match for the Destination.")

st.header("2. Vehicle Selection")
col1, col2, col3, col4 = st.columns(4)

years = get_years()
year = col1.selectbox("Year", years, index=None, placeholder="Select Year") if years else None

make = None
if year:
    makes = get_makes(year)
    make = col2.selectbox("Make", makes, index=None, placeholder="Select Make") if makes else None

model = None
if make:
    models = get_models(year, make)
    model = col3.selectbox("Model", models, index=None, placeholder="Select Model") if models else None

trim_id = None
if model:
    trims = get_trims(year, make, model)
    if trims:
        trim_options = {t["text"]: t["value"] for t in trims}
        trim_text = col4.selectbox("Trim", list(trim_options.keys()), index=None, placeholder="Select Trim")
        if trim_text:
            trim_id = trim_options[trim_text]

vehicle_mpg = None
if trim_id:
    vehicle_mpg = get_vehicle_mpg(trim_id)
    if vehicle_mpg:
        st.success(f"EPA Rating: {vehicle_mpg['city']} City / {vehicle_mpg['highway']} Hwy MPG")
    else:
        st.warning("Could not fetch EPA rating.")

col_mpg1, col_mpg2 = st.columns(2)
manual_city_mpg = col_mpg1.number_input("Override City MPG", value=float(vehicle_mpg['city']) if vehicle_mpg else 25.0)
manual_hwy_mpg = col_mpg2.number_input("Override Highway MPG", value=float(vehicle_mpg['highway']) if vehicle_mpg else 35.0)

st.header("3. Gas Price")
baseline_price = get_fred_baseline_price()
st.caption(f"📈 US National Average (FRED): **${baseline_price:.2f}/gal**")

manual_price = st.number_input("Manual Override Gas Price ($/gal)", min_value=0.1, value=baseline_price, step=0.1, help="Defaults to FRED average, but you can override it.")

# --- ACTION BUTTON ---
st.header("4. Calculate")
if st.button("Calculate Cost", type="primary"):
    st.session_state.calculate = True

if st.session_state.get("calculate", False):
    if len(route_coords) < 2:
        st.error("Please search and select at least an origin and destination address.")
        st.stop()
        
    active_price = manual_price
    st.info(f"Using gas price: ${active_price:.2f}/gal")
        
    # 3. Routing
    with st.spinner("Finding routes..."):
        routes = get_route(route_coords)
        
    if not routes:
        st.error("Failed to fetch route from OSRM.")
        st.stop()
        
    # Optional Route Selection
    if len(routes) > 1:
        route_options = []
        for i, r in enumerate(routes):
            dist = r["distance"] * 0.000621371
            dur = r["duration"] / 60
            label = f"Route {i+1} (Fastest)" if i == 0 else f"Route {i+1} (Alternate)"
            route_options.append(f"{label}: {dist:.1f} mi, {dur:.0f} mins")
            
        selected_route_label = st.radio("🛣️ **Select Route to Compare**", route_options, horizontal=True)
        selected_idx = route_options.index(selected_route_label)
        route_data = routes[selected_idx]
    else:
        route_data = routes[0]
        st.info("No alternate routes available.")
        
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
            speed_limit_mph=row.get("speed_limit_mph", 0),
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
    multiplier = 2 if st.session_state.get('round_trip', False) else 1
    total_gallons *= multiplier
    total_distance *= multiplier
    total_cost = total_gallons * active_price
    
    # --- RESULTS UI ---
    st.header("Trip Results")
    st.divider()
    
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
            longitude=route_coords[0][1],
            latitude=route_coords[0][0],
            zoom=5,
            pitch=0
        )
        r = pdk.Deck(layers=[layer], initial_view_state=view_state, map_style="road")
        st.pydeck_chart(r)
        
    # Table
    if multiplier == 2:
        st.subheader("One-Way Segment Breakdown (Multiplied by 2 for Totals above)")
    else:
        st.subheader("Segment Breakdown")
        
    df_steps["cumulative_cost"] = df_steps["cost"].cumsum()
    display_df = df_steps[["name", "distance_mi", "avg_speed_mph", "grade_pct", "effective_mpg", "cost", "cumulative_cost"]].copy()
    display_df.rename(columns={"cost": "Segment Cost", "cumulative_cost": "Running Total"}, inplace=True)
    
    # Formatting for readability
    display_df["distance_mi"] = display_df["distance_mi"].map("{:.2f}".format)
    display_df["avg_speed_mph"] = display_df["avg_speed_mph"].map("{:.1f}".format)
    display_df["grade_pct"] = display_df["grade_pct"].map("{:.1f}%".format)
    display_df["effective_mpg"] = display_df["effective_mpg"].map("{:.1f}".format)
    display_df["Segment Cost"] = display_df["Segment Cost"].map("${:.2f}".format)
    display_df["Running Total"] = display_df["Running Total"].map("${:.2f}".format)
    
    st.dataframe(display_df, use_container_width=True)
