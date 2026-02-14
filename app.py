import streamlit as st
import pandas as pd
import os
import shutil
from datetime import date, datetime
import hashlib
import ast

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
APPROVAL_FILE = "pending_approvals.csv"
EXPENSE_COLS = ["Cost per Unit", "Boxed Cost"]
CORE_COLS = ["Product Name"] + EXPENSE_COLS

if not os.path.exists("backups"): os.makedirs("backups")

SALES_ORDER = ["Date", "Customer", "Product", "Qty", "Price Tier", "Cost", "Boxed Cost", "Profit", "Discount", "Total", "Status", "Payment"]

# --- DYNAMIC CSS (STRICT COMPACT SIDEBAR) ---
st.markdown(f"""
    <style>
    html, body, [class*="ViewContainer"] {{ font-size: 12px !important; }}
    .block-container {{ padding: 1rem !important; }}
    [data-testid="stSidebar"] {{ min-width: 160px !important; max-width: 160px !important; }}
    h1 {{ display: block !important; font-size: 1.3rem !important; font-weight: 700 !important; margin-top: 0.5rem !important; color: #FFFFFF !important; }}
    .stButton > button {{ width: 100% !important; padding: 2px 8px !important; text-align: left !important; font-size: 11px !important; border-radius: 4px !important; min-height: 24px !important; margin-bottom: -10px !important; }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.2rem !important; padding-top: 1rem !important; }}
    hr {{ border: none !important; height: 1px !important; background-color: #333 !important; display: block !important; margin: 5px 0 !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- SECURITY & DATA HELPERS ---
def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

def load_data(file, defaults):
    if os.path.exists(file) and os.path.getsize(file) > 0:
        try:
            df = pd.read_csv(file)
            if not df.empty and "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.date
                df["Date"] = df["Date"].fillna(date.today())
            return df
        except: pass
    return pd.DataFrame(defaults)

def save_data(df, file): df.to_csv(file, index=False)

def log_action(action_desc):
    user = st.session_state.get('user', 'System')
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    new_log = pd.DataFrame({"Timestamp": [now], "User": [user], "Detailed Action": [action_desc]})
    log_df = pd.concat([new_log, load_data(LOG_FILE, {})], ignore_index=True)
    save_data(log_df, LOG_FILE)

def request_deletion(page_name, row_data):
    pending = load_data(APPROVAL_FILE, {"Timestamp": [], "User": [], "Page": [], "Data": []})
    new_req = pd.DataFrame({
        "Timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M")],
        "User": [st.session_state.user],
        "Page": [page_name],
        "Data": [str(row_data)]
    })
    save_data(pd.concat([pending, new_req], ignore_index=True), APPROVAL_FILE)
    st.warning(f"Deletion from {page_name} blocked and sent to Admin for approval.")

# --- INITIALIZATION ---
users_df = load_data(USERS_FILE, {"Username": ["Musika"], "Password": [make_hashes("Iameternal11!")], "Role": ["Admin"], "Status": ["Approved"]})
db_df = load_data(DB_FILE, {"Product Name": ["Item 1"], "Cost per Unit": [0.0], "Boxed Cost": [0.0]})
st.session_state.inventory = db_df
st.session_state.stock = load_data(STOCK_FILE, {"Product Name": ["Item 1"], "Quantity": [0], "Status": ["In Stock"], "Date": [date.today()]})
st.session_state.sales = load_data(SALES_FILE, {c: [] for c in SALES_ORDER})
st.session_state.expenditures = load_data(EXPENSE_FILE, {"Date": [], "Item": [], "Cost": []})
st.session_state.cash_in = load_data(CASH_FILE, {"Date": [], "Source": [], "Amount": []})

product_list = db_df["Product Name"].dropna().unique().tolist()
price_tiers_list = [c for c in db_df.columns if c not in CORE_COLS]

# --- LOGIN / SIGNUP ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_page' not in st.session_state: st.session_state.current_page = "Dashboard"

if not st.session_state.logged_in:
    st.markdown("<h1>🔐 Inventory Pro</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Create Account"])
    with t1:
        u, p = st.text_input("Username"), st.text_input("Password", type="password")
        if st.button("Login"):
            res = users_df[users_df['Username'] == u]
            if not res.empty and check_hashes(p, res.iloc[0]['Password']):
                if res.iloc[0]['Status'] == "Approved":
                    st.session_state.logged_in, st.session_state.user, st.session_state.role = True, u, res.iloc[0]['Role']
                    st.rerun()
                else: st.error("Account pending Admin approval.")
            else: st.error("Invalid credentials.")
    with t2:
        nu, np = st.text_input("New Username"), st.text_input("New Password", type="password")
        if st.button("Submit Request"):
            if nu in users_df['Username'].values: st.error("Username taken.")
            else:
                new_u = pd.DataFrame({"Username": [nu], "Password": [make_hashes(np)], "Role": ["Staff"], "Status": ["Pending"]})
                save_data(pd.concat([users_df, new_u], ignore_index=True), USERS_FILE)
                st.success("Request sent to Admin.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"👤 **{st.session_state.user}**")
    for p in ["Dashboard", "Database", "Inventory", "Sales", "Expenditures", "Log"]:
        if st.button(p): st.session_state.current_page = p
    if st.session_state.role == "Admin": 
        if st.button("🛡️ Admin"): st.session_state.current_page = "Admin"
    st.write("---")
    if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

# --- PAGES ---
page = st.session_state.current_page

if page == "Admin" and st.session_state.role == "Admin":
    st.markdown("<h1>🛡️ Admin Approvals</h1>", unsafe_allow_html=True)
    st.write("### 👥 Pending User Accounts")
    pend_users = users_df[users_df['Status'] == "Pending"]
    if not pend_users.empty:
        for idx, row in pend_users.iterrows():
            c1, c2 = st.columns([3, 1])
            c1.write(f"User: **{row['Username']}**")
            if c2.button(f"Approve {row['Username']}"):
                users_df.at[idx, 'Status'] = "Approved"
                save_data(users_df, USERS_FILE); log_action(f"Approved user {row['Username']}"); st.rerun()
    else: st.info("No pending users.")

    st.write("### 🗑️ Pending Deletion Requests")
    pend_del = load_data(APPROVAL_FILE, {})
    if not pend_del.empty:
        st.dataframe(pend_del, use_container_width=True)
        if st.button("Clear All Requests"): save_data(pd.DataFrame(), APPROVAL_FILE); st.rerun()
    else: st.info("No pending deletions.")

elif page == "Dashboard":
    st.markdown("<h1>📊 Dashboard</h1>", unsafe_allow_html=True)
    cash = (st.session_state.cash_in['Amount'].sum() + st.session_state.sales['Profit'].sum()) - st.session_state.expenditures['Cost'].sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Cash", f"₱{cash:,.2f}"); m2.metric("Profit", f"₱{st.session_state.sales['Profit'].sum():,.2f}")
    st.write("### 🚨 Stock Alerts")
    summary = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index().sort_values("Quantity")
    st.dataframe(summary[summary["Quantity"] < 5], use_container_width=True, hide_index=True)

elif page == "Database":
    st.markdown("<h1>📂 Database</h1>", unsafe_allow_html=True)
    # Restore Price Tier Removal Tool
    c_add, c_del = st.columns(2)
    with c_add:
        st.write("### ➕ Add Tier")
        t1, t2 = st.columns([3, 1])
        nt = t1.text_input("New Name")
        if t2.button("Add"):
            db_df[nt] = 0.0; save_data(db_df, DB_FILE); st.rerun()
    with c_del:
        st.write("### 🗑️ Remove Tier")
        d1, d2 = st.columns([3, 1])
        td = d1.selectbox("Select to Delete", [""] + price_tiers_list)
        if d2.button("Delete"):
            if td:
                db_df = db_df.drop(columns=[td]); save_data(db_df, DB_FILE); st.rerun()
    
    ed = st.data_editor(db_df, use_container_width=True, hide_index=True, num_rows="dynamic")
    if len(ed) < len(db_df): request_deletion("Database", "Row deletion blocked"); st.rerun()
    elif not ed.equals(db_df): save_data(ed, DB_FILE); st.rerun()

elif page == "Inventory":
    st.markdown("<h1>📦 Inventory</h1>", unsafe_allow_html=True)
    # Tally back on the left side
    cl, cr = st.columns([1, 2])
    with cl:
        st.write("### 📊 Tally")
        sdf = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index().sort_values("Quantity")
        st.dataframe(sdf, use_container_width=True, hide_index=True)
    with cr:
        st.write("### ➕ Stock Entry")
        ed_s = st.data_editor(st.session_state.stock.copy().iloc[::-1], use_container_width=True, num_rows="dynamic")
        if len(ed_s) < len(st.session_state.stock): request_deletion("Inventory", "Row deletion blocked"); st.rerun()
        elif not ed_s.equals(st.session_state.stock.iloc[::-1]): save_data(ed_s.iloc[::-1], STOCK_FILE); st.rerun()

elif page == "Sales":
    st.markdown("<h1>💰 Sales Tracker</h1>", unsafe_allow_html=True)
    ed = st.data_editor(st.session_state.sales[SALES_ORDER], use_container_width=True, num_rows="dynamic")
    if len(ed) < len(st.session_state.sales): request_deletion("Sales", "Row deletion blocked"); st.rerun()
    elif not ed.equals(st.session_state.sales[SALES_ORDER]):
        save_data(ed, SALES_FILE); st.rerun()

elif page == "Expenditures":
    st.markdown("<h1>💸 Expenditures & Deposits</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.write("### ➖ Log Expense")
        it, ct = st.text_input("Item"), st.number_input("Cost", min_value=0.0)
        if st.button("Add Expense"):
            new = pd.DataFrame({"Date": [date.today()], "Item": [it], "Cost": [ct]})
            save_data(pd.concat([st.session_state.expenditures, new], ignore_index=True), EXPENSE_FILE); st.rerun()
    with c2:
        # Restore Deposits
        st.write("### ➕ Log Deposit")
        src, amt = st.text_input("Source"), st.number_input("Amount", min_value=0.0)
        if st.button("Add Deposit"):
            new = pd.DataFrame({"Date": [date.today()], "Source": [src], "Amount": [amt]})
            save_data(pd.concat([st.session_state.cash_in, new], ignore_index=True), CASH_FILE); st.rerun()

elif page == "Log":
    st.markdown("<h1>📜 Logs</h1>", unsafe_allow_html=True)
    st.dataframe(load_data(LOG_FILE, {}), use_container_width=True)
