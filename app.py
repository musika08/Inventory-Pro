import streamlit as st
import pandas as pd
import os
import shutil
from datetime import date, datetime
import hashlib

# --- PRE-FLIGHT CHECK ---
try:
    import plotly.express as px
except ImportError:
    st.error("Missing dependency: Plotly. Run 'pip install plotly'")
    st.stop()

# --- CONFIG & COMPACT CSS ---
st.set_page_config(page_title="Inventory Pro", layout="wide")

DB_FILE = "inventory_data.csv"
STOCK_FILE = "stock_data.csv"
SALES_FILE = "sales_data.csv"
EXPENSE_FILE = "expenditures.csv"
CASH_FILE = "cash_in.csv"
LOG_FILE = "activity_log.csv"
USERS_FILE = "users_db.csv"
EXPENSE_COLS = ["Cost per Unit", "Boxed Cost"]

if not os.path.exists("backups"):
    os.makedirs("backups")

SALES_ORDER = ["Date", "Customer", "Product", "Qty", "Price Tier", "Cost", "Boxed Cost", "Profit", "Discount", "Total", "Status", "Payment"]

# --- DYNAMIC CSS (ULTRA COMPACT) ---
st.markdown(f"""
    <style>
    html, body, [class*="ViewContainer"] {{ font-size: 11px !important; }}
    .block-container {{ padding: 1rem !important; }}
    
    /* Sidebar Width & Spacing */
    [data-testid="stSidebar"] {{ min-width: 160px !important; max-width: 160px !important; }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.1rem !important; padding: 0.5rem !important; }}
    
    /* Ultra Compact Buttons */
    .stButton > button {{ 
        width: 100% !important; 
        padding: 2px 8px !important; 
        min-height: 24px !important;
        line-height: 1.2 !important;
        text-align: left !important; 
        font-size: 10px !important; 
        border-radius: 3px !important;
        margin: 0px !important;
    }}
    
    h1 {{ display: block !important; font-size: 1.2rem !important; font-weight: 700 !important; margin-top: 0.5rem !important; color: #FFFFFF !important; }}
    hr {{ border: none !important; height: 1px !important; background-color: #333 !important; display: block !important; margin: 4px 0 !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- SECURITY UTILS ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# --- DATA HELPERS ---
def load_data(file, defaults):
    if os.path.exists(file):
        df = pd.read_csv(file)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.date
            df["Date"] = df["Date"].fillna(date.today())
        return df
    return pd.DataFrame(defaults)

def save_data(df, file):
    df.to_csv(file, index=False)

def log_action(action_desc):
    user = st.session_state.get('user', 'System')
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    new_log = pd.DataFrame({"Timestamp": [now], "User": [user], "Detailed Action": [action_desc]})
    if os.path.exists(LOG_FILE):
        log_df = pd.concat([new_log, pd.read_csv(LOG_FILE)], ignore_index=True)
    else:
        log_df = new_log
    log_df.to_csv(LOG_FILE, index=False)

# --- USER DB INIT ---
primary_admin = {"Username": ["Musika"], "Password": [make_hashes("Iameternal11!")], "Role": ["Admin"]}
users_db = load_data(USERS_FILE, primary_admin)

# --- SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user' not in st.session_state: st.session_state.user = None
if 'role' not in st.session_state: st.session_state.role = None
if 'current_page' not in st.session_state: st.session_state.current_page = "Dashboard"

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    st.markdown("<h1>🔐 Inventory Pro Login</h1>", unsafe_allow_html=True)
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        res = users_db[users_db['Username'] == u]
        if not res.empty and check_hashes(p, res.iloc[0]['Password']):
            st.session_state.logged_in = True
            st.session_state.user = u
            st.session_state.role = res.iloc[0]['Role']
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

# --- DATA LOAD ---
db_df = load_data(DB_FILE, {"Product Name": ["Item 1"], "Cost per Unit": [0.0], "Boxed Cost": [0.0]})
st.session_state.inventory = db_df
st.session_state.stock = load_data(STOCK_FILE, {"Product Name": ["Item 1"], "Quantity": [0], "Status": ["In Stock"], "Date": [date.today()]})
st.session_state.sales = load_data(SALES_FILE, {c: [] for c in SALES_ORDER})
st.session_state.expenditures = load_data(EXPENSE_FILE, {"Date": [], "Item": [], "Cost": []})
st.session_state.cash_in = load_data(CASH_FILE, {"Date": [], "Source": [], "Amount": []})

product_list = db_df["Product Name"].dropna().unique().tolist()
price_tiers_list = [c for c in db_df.columns if c not in ["Product Name"] + EXPENSE_COLS]

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown(f"**{st.session_state.user}** ({st.session_state.role})")
    if st.button("📊 Dashboard"): st.session_state.current_page = "Dashboard"
    if st.button("📂 Database"): st.session_state.current_page = "Database"
    if st.button("📦 Inventory"): st.session_state.current_page = "Inventory"
    if st.button("💰 Sales"): st.session_state.current_page = "Sales"
    if st.button("💸 Expenditures"): st.session_state.current_page = "Expenditures"
    if st.button("📜 Activity Log"): st.session_state.current_page = "Log"
    if st.session_state.role == "Admin":
        if st.button("🛡️ Admin Page"): st.session_state.current_page = "Admin"
    st.write("---")
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.rerun()

page = st.session_state.current_page

# --- ADMIN PAGE ---
if page == "Admin" and st.session_state.role == "Admin":
    st.markdown("<h1>🛡️ Admin Management</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        st.write("### ➕ Add Staff")
        ac1, ac2, ac3 = st.columns([2, 2, 1])
        nu, np = ac1.text_input("Username"), ac2.text_input("Password", type="password")
        if ac3.button("Add"):
            if nu and nu not in users_db['Username'].values:
                nr = pd.DataFrame({"Username": [nu], "Password": [make_hashes(np)], "Role": ["Staff"]})
                users_db = pd.concat([users_db, nr], ignore_index=True); save_data(users_db, USERS_FILE)
                log_action(f"Admin: Added user {nu}"); st.rerun()
    st.write("### 👥 Active Users")
    st.data_editor(users_db, use_container_width=True, hide_index=True)

# --- DASHBOARD ---
elif page == "Dashboard":
    st.markdown("<h1>📊 Dashboard</h1>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    # Basic math for summary metrics
    total_sales = st.session_state.sales['Total'].sum()
    total_profit = st.session_state.sales['Profit'].sum()
    total_expenses = st.session_state.expenditures['Cost'].sum()
    m1.metric("Cash Balance", f"₱{total_sales - total_expenses:,.2f}")
    m2.metric("Total Profit", f"₱{total_profit:,.2f}")
    
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.write("### 🚨 Stock Alerts")
        summary = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
        st.dataframe(summary[summary["Quantity"] < 5], use_container_width=True, hide_index=True)
    with c2:
        st.write("### 🏆 Top Products")
        if not st.session_state.sales.empty:
            st.table(st.session_state.sales.groupby("Product")["Qty"].sum().sort_values(ascending=False).head(5).reset_index())

# --- SALES TRACKER ---
elif page == "Sales":
    st.markdown("<h1>💰 Sales Tracker</h1>", unsafe_allow_html=True)
    sales_df = st.session_state.sales.copy(); sales_df["Date"] = pd.to_datetime(sales_df["Date"]).dt.date
    conf = {
        "Product": st.column_config.SelectboxColumn("Product", options=sorted(product_list), required=True),
        "Price Tier": st.column_config.SelectboxColumn("Price Tier", options=price_tiers_list, required=True),
        "Status": st.column_config.SelectboxColumn("Status", options=["Sold", "Reserved"], default="Sold", required=True),
    }
    ed = st.data_editor(sales_df[SALES_ORDER], use_container_width=True, hide_index=True, num_rows="dynamic", column_config=conf, key="sales_ed")
    if not ed.equals(sales_df[SALES_ORDER]):
        # Calculation logic and deduction logic here
        save_data(ed, SALES_FILE); log_action("Sales Updated"); st.rerun()

# --- DATABASE ---
elif page == "Database":
    st.markdown("<h1>📂 Database</h1>", unsafe_allow_html=True)
    ed_db = st.data_editor(db_df, use_container_width=True, hide_index=True, num_rows="dynamic")
    if not ed_db.equals(db_df):
        save_data(ed_db, DB_FILE); log_action("Database modified"); st.rerun()

# --- INVENTORY ---
elif page == "Inventory":
    st.markdown("<h1>📦 Inventory</h1>", unsafe_allow_html=True)
    ed_inv = st.data_editor(st.session_state.stock, use_container_width=True, hide_index=True, num_rows="dynamic")
    if not ed_inv.equals(st.session_state.stock):
        save_data(ed_inv, STOCK_FILE); log_action("Inventory adjusted"); st.rerun()

# --- EXPENDITURES ---
elif page == "Expenditures":
    st.markdown("<h1>💸 Expenditures</h1>", unsafe_allow_html=True)
    st.data_editor(st.session_state.expenditures, use_container_width=True, hide_index=True, num_rows="dynamic")

# --- LOG ---
elif page == "Log":
    st.markdown("<h1>📜 Log</h1>", unsafe_allow_html=True)
    st.dataframe(load_data(LOG_FILE, {}), use_container_width=True, hide_index=True)
