import streamlit as st
import pandas as pd
import pydeck as pdk
import uuid
from vehicles import get_years, get_makes, get_models, get_trims, get_vehicle_mpg
from routing import geocode, get_route, process_route_steps, search_addresses
from prices import get_fred_baseline_price
from physics import calculate_segment_fuel

st.set_page_config(page_title="Real Gas Cost Calculator", layout="wide")

st.title("🚗 Real Gas Cost Calculator")
st.write("A physics-based road-trip gas cost calculator utilizing real road data and EPA vehicle ratings.")

# --- STATE INIT ---
if "fwd_wps" not in st.session_state: st.session_state.fwd_wps = []
if "ret_wps" not in st.session_state: st.session_state.ret_wps = []
if "prev_round_trip" not in st.session_state: st.session_state.prev_round_trip = False

def add_fwd(): st.session_state.fwd_wps.append(str(uuid.uuid4()))
def rem_fwd(wp_id): st.session_state.fwd_wps.remove(wp_id)
def add_ret(): st.session_state.ret_wps.append(str(uuid.uuid4()))
def rem_ret(wp_id): st.session_state.ret_wps.remove(wp_id)

# --- MAIN PAGE INPUTS ---
st.header("1. Trip Details")
st.markdown("**Select your origin & destination address, be sure to hit 'Verify Addresses' before continuing to Vehicle Selection**")

origin_str = st.text_input("**Origin Address**", "San Francisco, CA")

for idx, wp_id in enumerate(st.session_state.fwd_wps):
    c1, c2 = st.columns([11, 1])
    c1.text_input(f"Stop {idx+1} Address", key=f"fwd_val_{wp_id}")
    c2.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
    c2.button("➖", key=f"rm_fwd_{wp_id}", on_click=rem_fwd, args=(wp_id,), help="Remove this stop")
    
st.button("➕ Add Stop", on_click=add_fwd)

dest_str = st.text_input("**Destination Address**", "Los Angeles, CA")

round_trip = st.checkbox("Round Trip", value=False, key="round_trip")

if round_trip and not st.session_state.prev_round_trip:
    # Just checked! Auto-populate return stops in reverse order
    st.session_state.ret_wps = []
    for fwd_id in reversed(st.session_state.fwd_wps):
        new_id = str(uuid.uuid4())
        st.session_state.ret_wps.append(new_id)
        # Pre-fill the input widget state so the text matches
        st.session_state[f"ret_val_{new_id}"] = st.session_state.get(f"fwd_val_{fwd_id}", "")

st.session_state.prev_round_trip = round_trip

if round_trip:
    st.markdown("#### Return Route Stops")
    for idx, wp_id in enumerate(st.session_state.ret_wps):
        c1, c2 = st.columns([11, 1])
        c1.text_input(f"Return Stop {idx+1} Address", key=f"ret_val_{wp_id}")
        c2.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        c2.button("➖", key=f"rm_ret_{wp_id}", on_click=rem_ret, args=(wp_id,), help="Remove this return stop")
    st.button("➕ Add Return Stop", on_click=add_ret)

search_btn = st.button("Verify Addresses")

import streamlit.components.v1 as components
components.html(
    """
    <script>
    const doc = window.parent.document;
    const buttons = Array.from(doc.querySelectorAll('button'));
    const verifyBtn = buttons.find(b => b.innerText.includes('Verify Addresses'));
    if (verifyBtn) {
        verifyBtn.style.backgroundColor = 'red';
        verifyBtn.style.color = 'black';
        verifyBtn.style.fontWeight = 'bold';
        verifyBtn.style.borderColor = 'darkred';
    }
    </script>
    """,
    height=0,
    width=0
)

# --- SEARCH & GEOCODE ---
if search_btn:
    st.session_state.origin_results = search_addresses(origin_str)
    st.session_state.dest_results = search_addresses(dest_str)
    
    fwd_queries = [st.session_state.get(f"fwd_val_{w}", "").strip() for w in st.session_state.fwd_wps if st.session_state.get(f"fwd_val_{w}", "").strip()]
    st.session_state.fwd_results = [search_addresses(q) for q in fwd_queries]
    
    ret_queries = [st.session_state.get(f"ret_val_{w}", "").strip() for w in st.session_state.ret_wps if st.session_state.get(f"ret_val_{w}", "").strip()]
    st.session_state.ret_results = [search_addresses(q) for q in ret_queries]

# --- CONFIRM ADDRESSES ---
route_coords = []
origin_dict = None

# Origin
if "origin_results" in st.session_state:
    if st.session_state.origin_results:
        origin_labels = [opt["label"] for opt in st.session_state.origin_results]
        sel_origin = st.selectbox("**Select exact Origin**", origin_labels)
        if sel_origin:
            origin_dict = next((opt for opt in st.session_state.origin_results if opt["label"] == sel_origin), None)
            if origin_dict:
                route_coords.append((origin_dict["lat"], origin_dict["lon"]))
    else:
        st.warning("Could not find an address match for the Origin.")

# Fwd Stops
if "fwd_results" in st.session_state and st.session_state.fwd_results:
    for i, w_results in enumerate(st.session_state.fwd_results):
        if w_results:
            labels = [opt["label"] for opt in w_results]
            sel = st.selectbox(f"Select exact Stop {i+1}", labels, key=f"wp_fwd_{i}")
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
        sel_dest = st.selectbox("**Select exact Destination**", dest_labels)
        if sel_dest:
            sel_dict = next((opt for opt in st.session_state.dest_results if opt["label"] == sel_dest), None)
            if sel_dict:
                route_coords.append((sel_dict["lat"], sel_dict["lon"]))
    else:
        st.warning("Could not find an address match for the Destination.")

# Ret Stops
if round_trip:
    if "ret_results" in st.session_state and st.session_state.ret_results:
        for i, w_results in enumerate(st.session_state.ret_results):
            if w_results:
                labels = [opt["label"] for opt in w_results]
                sel = st.selectbox(f"Select exact Return Stop {i+1}", labels, key=f"wp_ret_{i}")
                if sel:
                    sel_dict = next((opt for opt in w_results if opt["label"] == sel), None)
                    if sel_dict:
                        route_coords.append((sel_dict["lat"], sel_dict["lon"]))
            else:
                st.warning(f"Could not find an address match for Return Stop {i+1}. Please try a different search.")
    
    if origin_dict:
        route_coords.append((origin_dict["lat"], origin_dict["lon"]))

st.header("2. Vehicle Selection")
col1, col2, col3, col4 = st.columns(4)

years = get_years()
year = col1.selectbox("**Year**", years, index=None, placeholder="Select Year") if years else None

make = None
if year:
    makes = get_makes(year)
    make = col2.selectbox("**Make**", makes, index=None, placeholder="Select Make") if makes else None

model = None
if make:
    models = get_models(year, make)
    model = col3.selectbox("**Model**", models, index=None, placeholder="Select Model") if models else None

trim_id = None
if model:
    trims = get_trims(year, make, model)
    if trims:
        trim_options = {t["text"]: t["value"] for t in trims}
        trim_text = col4.selectbox("**Trim**", list(trim_options.keys()), index=None, placeholder="Select Trim")
        if trim_text:
            trim_id = trim_options[trim_text]

vehicle_mpg = None
if trim_id:
    vehicle_mpg = get_vehicle_mpg(trim_id)
    if vehicle_mpg:
        st.success(f"EPA Rating: {vehicle_mpg['city']} City / {vehicle_mpg['highway']} Hwy MPG")
    else:
        st.warning("Could not fetch EPA rating.")

if "show_city_override" not in st.session_state: st.session_state.show_city_override = False
if "show_hwy_override" not in st.session_state: st.session_state.show_hwy_override = False
if "show_gas_override" not in st.session_state: st.session_state.show_gas_override = False

def toggle_gas(): st.session_state.show_gas_override = not st.session_state.show_gas_override

def toggle_city(): st.session_state.show_city_override = not st.session_state.show_city_override
def toggle_hwy(): st.session_state.show_hwy_override = not st.session_state.show_hwy_override

col_mpg1, col_mpg2 = st.columns(2)
manual_city_mpg = None
with col_mpg1:
    if not st.session_state.show_city_override:
        st.button("➕ Override City MPG", on_click=toggle_city)
    else:
        sc1, sc2 = st.columns([5, 1])
        manual_city_mpg = sc1.number_input("Override City MPG", value=float(vehicle_mpg['city']) if vehicle_mpg else 25.0)
        sc2.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        sc2.button("➖", key="rm_city", on_click=toggle_city, help="Remove City Override")

manual_hwy_mpg = None
with col_mpg2:
    if not st.session_state.show_hwy_override:
        st.button("➕ Override Highway MPG", on_click=toggle_hwy)
    else:
        sc1, sc2 = st.columns([5, 1])
        manual_hwy_mpg = sc1.number_input("Override Highway MPG", value=float(vehicle_mpg['highway']) if vehicle_mpg else 35.0)
        sc2.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        sc2.button("➖", key="rm_hwy", on_click=toggle_hwy, help="Remove Highway Override")

st.header("3. Gas Price")
fuel_grade = st.radio("Select Fuel Grade", ["Regular", "Midgrade (Blend)", "Premium", "Diesel"], horizontal=True)

baseline_price = get_fred_baseline_price(fuel_grade)
st.caption(f"📈 US National Average ({fuel_grade}): **${baseline_price:.2f}/gal**")

manual_price = None
if not st.session_state.show_gas_override:
    st.button("➕ Override Gas Price", on_click=toggle_gas)
else:
    sc1, sc2 = st.columns([5, 1])
    manual_price = sc1.number_input("Override Gas Price ($/gal)", min_value=0.1, value=baseline_price, step=0.1)
    sc2.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
    sc2.button("➖", key="rm_gas", on_click=toggle_gas, help="Remove Gas Price Override")

# --- ACTION BUTTON ---
st.header("4. Calculate")
if st.button("Calculate Cost", type="primary"):
    st.session_state.calculate = True

if st.session_state.get("calculate", False):
    if len(route_coords) < 2:
        st.error("Please search and select at least an origin and destination address.")
        st.stop()
        
    active_city_mpg = manual_city_mpg if manual_city_mpg is not None else (float(vehicle_mpg['city']) if vehicle_mpg else None)
    active_hwy_mpg = manual_hwy_mpg if manual_hwy_mpg is not None else (float(vehicle_mpg['highway']) if vehicle_mpg else None)
    
    if active_city_mpg is None or active_hwy_mpg is None:
        st.error("Please finish selecting your vehicle's trim, or click ➕ Override to manually provide your City and Highway MPG.")
        st.stop()
        
    active_price = manual_price if manual_price is not None else baseline_price
    st.info(f"Using gas price: ${active_price:.2f}/gal")
        
    with st.spinner("Finding routes..."):
        routes = get_route(route_coords)
        
    if not routes:
        st.error("Failed to fetch route from OSRM.")
        st.stop()
        
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
        
    with st.spinner("Calculating elevations and segment speeds..."):
        df_steps = process_route_steps(route_data)
            
    if df_steps.empty:
        st.error("No route steps found.")
        st.stop()
        
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
            city_mpg=active_city_mpg,
            highway_mpg=active_hwy_mpg
        )
        gallons_list.append(gals)
        eff_mpg_list.append(eff)
        
        total_gallons += gals
        total_distance += row["distance_mi"]
        
    df_steps["gallons_used"] = gallons_list
    df_steps["effective_mpg"] = eff_mpg_list
    df_steps["cost"] = df_steps["gallons_used"] * active_price
    
    total_cost = total_gallons * active_price
    
    # --- RESULTS UI ---
    st.header("Trip Results")
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cost", f"${total_cost:.2f}")
    col2.metric("Total Fuel", f"{total_gallons:.2f} gal")
    col3.metric("Total Distance", f"{total_distance:.1f} mi")
    col4.metric("Avg Effective MPG", f"{(total_distance/total_gallons):.1f}" if total_gallons > 0 else "N/A")
    
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
        
    st.subheader("Segment Breakdown")
        
    df_steps["cumulative_cost"] = df_steps["cost"].cumsum()
    display_df = df_steps[["name", "distance_mi", "avg_speed_mph", "grade_pct", "effective_mpg", "cost", "cumulative_cost"]].copy()
    display_df.rename(columns={"cost": "Segment Cost", "cumulative_cost": "Running Total"}, inplace=True)
    
    display_df["distance_mi"] = display_df["distance_mi"].map("{:.2f}".format)
    display_df["avg_speed_mph"] = display_df["avg_speed_mph"].map("{:.1f}".format)
    display_df["grade_pct"] = display_df["grade_pct"].map("{:.1f}%".format)
    display_df["effective_mpg"] = display_df["effective_mpg"].map("{:.1f}".format)
    display_df["Segment Cost"] = display_df["Segment Cost"].map("${:.2f}".format)
    display_df["Running Total"] = display_df["Running Total"].map("${:.2f}".format)
    
    st.dataframe(display_df, use_container_width=True)
