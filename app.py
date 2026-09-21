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

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Trip Details")

with st.sidebar.form("trip_form"):
    origin_str = st.text_input("Origin Address", "San Francisco, CA")
    dest_str = st.text_input("Destination Address", "Los Angeles, CA")
    search_btn = st.form_submit_button("Search Addresses")

if search_btn:
    st.session_state.origin_results = search_addresses(origin_str)
    st.session_state.dest_results = search_addresses(dest_str)

origin = None
if "origin_results" in st.session_state and st.session_state.origin_results:
    origin_labels = [opt["label"] for opt in st.session_state.origin_results]
    sel_origin = st.sidebar.selectbox("Select exact Origin", origin_labels)
    if sel_origin:
        sel_dict = next((opt for opt in st.session_state.origin_results if opt["label"] == sel_origin), None)
        if sel_dict:
            origin = (sel_dict["lat"], sel_dict["lon"], sel_dict["state_abbr"], sel_dict["label"])

dest = None
if "dest_results" in st.session_state and st.session_state.dest_results:
    dest_labels = [opt["label"] for opt in st.session_state.dest_results]
    sel_dest = st.sidebar.selectbox("Select exact Destination", dest_labels)
    if sel_dest:
        sel_dict = next((opt for opt in st.session_state.dest_results if opt["label"] == sel_dest), None)
        if sel_dict:
            dest = (sel_dict["lat"], sel_dict["lon"], sel_dict["state_abbr"], sel_dict["label"])

round_trip = st.sidebar.checkbox("Round Trip", value=False)

st.sidebar.header("2. Vehicle Selection")
years = get_years()
year = st.sidebar.selectbox("Year", years, index=None, placeholder="Select Year") if years else None

make = None
if year:
    makes = get_makes(year)
    make = st.sidebar.selectbox("Make", makes, index=None, placeholder="Select Make") if makes else None

model = None
if make:
    models = get_models(year, make)
    model = st.sidebar.selectbox("Model", models, index=None, placeholder="Select Model") if models else None

trim_id = None
if model:
    trims = get_trims(year, make, model)
    if trims:
        trim_options = {t["text"]: t["value"] for t in trims}
        trim_text = st.sidebar.selectbox("Trim", list(trim_options.keys()), index=None, placeholder="Select Trim")
        if trim_text:
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
baseline_price = get_fred_baseline_price()
st.sidebar.caption(f"📈 US National Average (FRED): **${baseline_price:.2f}/gal**")

manual_price = st.sidebar.number_input("Manual Override Gas Price ($/gal)", min_value=0.1, value=baseline_price, step=0.1, help="Defaults to FRED average, but you can override it.")

# --- ACTION BUTTON ---
if st.sidebar.button("Calculate Cost", type="primary"):
    st.session_state.calculate = True

if st.session_state.get("calculate", False):
    # 1. Geocode
    if not origin or not dest:
        st.error("Please search and select an origin and destination address.")
        st.stop()
        
    # 2. Price lookup
    active_price = manual_price
    st.sidebar.info(f"Using gas price: ${active_price:.2f}/gal")
        
    # 3. Routing
    with st.spinner("Finding routes..."):
        routes = get_route((origin[0], origin[1]), (dest[0], dest[1]))
        
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
    if round_trip:
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
