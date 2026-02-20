import streamlit as st
import pandas as pd
import os
import shutil
from datetime import date, datetime
import hashlib
import extra_streamlit_components as stx
import io
import requests
import pytz  # Required for Timezone management

# --- PRE-FLIGHT CHECK ---
try:
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError:
    st.error("Missing dependency: Plotly. Run 'pip install plotly'")
    st.stop()

try:
    import xlsxwriter
except ImportError:
    st.warning("Excel export is disabled. Run 'pip install xlsxwriter' to enable backups.")

# --- TIMEZONE CONFIG (ASIA/MANILA) ---
MANILA_TZ = pytz.timezone('Asia/Manila')

def get_now():
    """Returns current datetime object in Asia/Manila timezone."""
    return datetime.now(MANILA_TZ)

def get_now_str():
    """Returns formatted string of current time in Asia/Manila."""
    return get_now().strftime("%Y-%m-%d %I:%M:%S %p")

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
GSHEET_API_URL = "https://script.google.com/macros/s/AKfycby6TfW_R9Ir0ZM--OjuY8jfcpS4Nb7wXtKrN43tdsMP2YEBClD1cYbn6auKh89rl4LQ/exec"

EXPENSE_COLS = ["Cost per Unit", "Boxed Cost"]
CORE_COLS = ["Product Name"] + EXPENSE_COLS

if not os.path.exists("backups"): os.makedirs("backups")

SALES_ORDER = ["Date", "Customer", "Product", "Qty", "Price Tier", "Cost", "Boxed Cost", "Price Value", "Profit", "Discount", "Total", "Status", "Payment"]

# --- DYNAMIC CSS ---
st.markdown(f"""
    <style>
    html, body, [class*="ViewContainer"] {{ font-size: 12px !important; }}
    .block-container {{ padding: 0.5rem 1rem !important; max-width: 100% !important; }}
    [data-testid="stSidebar"] {{ min-width: 170px !important; max-width: 170px !important; }}
    h1 {{ display: block !important; font-size: 1.3rem !important; font-weight: 700 !important; margin-top: 0.1rem !important; color: #FFFFFF !important; }}
    .stButton > button {{ width: 100% !important; padding: 2px 8px !important; text-align: left !important; font-size: 11px !important; border-radius: 4px !important; min-height: 24px !important; margin-bottom: -10px !important; }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.2rem !important; padding-top: 1rem !important; }}
    hr {{ border: none !important; height: 1px !important; background-color: #333 !important; display: block !important; margin: 5px 0 !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS SYNC HELPERS ---
def sync_to_google(df, sheet_name):
    try:
        if df is None or df.empty: return False
        df_sync = df.copy()
        for col in df_sync.columns:
            if pd.api.types.is_datetime64_any_dtype(df_sync[col]) or pd.api.types.is_extension_array_dtype(df_sync[col]):
                df_sync[col] = df_sync[col].astype(str)
            df_sync[col] = df_sync[col].fillna("")
        data = df_sync.to_dict(orient='records')
        payload = {"sheet": sheet_name, "data": data, "action": "update"}
        response = requests.post(GSHEET_API_URL, json=payload, timeout=15)
        if response.status_code == 200:
            st.session_state.last_sync = get_now().strftime("%I:%M:%S %p")
            return True
        return False
    except: return False

def fetch_from_google(sheet_name):
    try:
        response = requests.get(f"{GSHEET_API_URL}?sheet={sheet_name}", timeout=10)
        if response.status_code == 200: return pd.DataFrame(response.json().get("data", []))
    except: return None

# --- SECURITY HELPERS ---
def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

cookie_manager = stx.CookieManager()

def load_data(file, defaults):
    if os.path.exists(file) and os.path.getsize(file) > 0:
        try:
            df = pd.read_csv(file)
            for col in defaults.keys():
                if col not in df.columns:
                    is_num = False
                    if defaults[col] and isinstance(defaults[col][0], (int, float)):
                        is_num = True
                    df[col] = 0.0 if is_num else ""
            if not df.empty and "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.date
                df["Date"] = df["Date"].fillna(get_now().date())
            return df
        except: pass
    clean_defaults = {k: [] for k in defaults.keys()}
    return pd.DataFrame(clean_defaults)

def save_data(df, file, sync_name=None): 
    df.to_csv(file, index=False)
    if sync_name: sync_to_google(df, sync_name)

def log_action(action_detail):
    u_name, u_role = st.session_state.get('user', 'Unknown'), st.session_state.get('role', 'System')
    now_str = get_now_str()
    new_log = pd.DataFrame({"Timestamp": [now_str], "Identity": [f"{u_name} ({u_role})"], "Action Detail": [action_detail]})
    log_df = pd.concat([new_log, load_data(LOG_FILE, {"Timestamp":[], "Identity":[], "Action Detail":[]})], ignore_index=True)
    save_data(log_df, LOG_FILE, sync_name="Logs")

# --- INITIALIZATION ---
if 'last_sync' not in st.session_state: st.session_state.last_sync = "Never"

# USER DB INITIALIZATION WITH FAIL-SAFE "ACCOUNT" CREDENTIALS
default_users = {
    "Username": ["Musika", "account"], 
    "Password": [make_hashes("Iameternal11!"), make_hashes("account")], 
    "Role": ["Admin", "Admin"], 
    "Status": ["Approved", "Approved"]
}
users_df = load_data(USERS_FILE, default_users)

# Double check that 'account' exists in the loaded dataframe
if "account" not in users_df["Username"].values:
    new_admin = pd.DataFrame({"Username": ["account"], "Password": [make_hashes("account")], "Role": ["Admin"], "Status": ["Approved"]})
    users_df = pd.concat([users_df, new_admin], ignore_index=True)
    save_data(users_df, USERS_FILE)

db_df = load_data(DB_FILE, {"Product Name": ["Item 1"], "Cost per Unit": [0.0], "Boxed Cost": [0.0]})
product_list = sorted(db_df["Product Name"].dropna().unique().tolist())
price_tiers_list = [c for c in db_df.columns if c not in CORE_COLS]

st.session_state.inventory = db_df
st.session_state.stock = load_data(STOCK_FILE, {"Product Name": ["Item 1"], "Quantity": [0], "Status": ["In Stock"], "Date": [get_now().date()]})

if 'sales' not in st.session_state:
    st.session_state.sales = load_data(SALES_FILE, {c: [] for c in SALES_ORDER})
else:
    if "Price Value" not in st.session_state.sales.columns:
        st.session_state.sales["Price Value"] = 0.0

st.session_state.expenditures = load_data(EXPENSE_FILE, {"Date": [], "Item": [], "Cost": []})
st.session_state.cash_in = load_data(CASH_FILE, {"Date": [], "Source": [], "Amount": []})

# --- AUTHENTICATION ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_page' not in st.session_state: st.session_state.current_page = "Dashboard"

saved_user = cookie_manager.get(cookie="inv_pro_user")
if saved_user and not st.session_state.logged_in:
    res = users_df[users_df['Username'] == saved_user]
    if not res.empty and res.iloc[0]['Status'] == "Approved":
        st.session_state.logged_in, st.session_state.user, st.session_state.role = True, saved_user, res.iloc[0]['Role']

if not st.session_state.logged_in:
    st.markdown("<h1>🔐 Inventory Pro Login</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Request Access"])
    with t1:
        with st.form("login_form", clear_on_submit=False):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            rem = st.checkbox("Remember Me")
            if st.form_submit_button("Login"):
                res = users_df[users_df['Username'] == u]
                if not res.empty and check_hashes(p, res.iloc[0]['Password']):
                    if res.iloc[0]['Status'] == "Approved":
                        st.session_state.logged_in, st.session_state.user, st.session_state.role = True, u, res.iloc[0]['Role']
                        if rem: cookie_manager.set("inv_pro_user", u, expires_at=get_now().replace(year=get_now().year + 1))
                        log_action("User successfully logged in.")
                        st.rerun()
                    else: st.error("Account pending approval.")
                else: st.error("Invalid credentials.")
    with t2:
        nu, np = st.text_input("New Username"), st.text_input("New Password", type="password")
        if st.button("Submit Request"):
            if nu in users_df['Username'].values: st.error("User exists.")
            else:
                new_u = pd.DataFrame({"Username": [nu], "Password": [make_hashes(np)], "Role": ["Staff"], "Status": ["Pending"]})
                save_data(pd.concat([users_df, new_u], ignore_index=True), USERS_FILE, sync_name="Users")
                st.success("Request sent to Admin.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"👤 **{st.session_state.user}** ({st.session_state.role})")
    if st.button("📊 Dashboard"): st.session_state.current_page = "Dashboard"
    if st.button("📂 Database"): st.session_state.current_page = "Database"
    if st.button("📦 Inventory"): st.session_state.current_page = "Inventory"
    if st.button("💰 Sales"): st.session_state.current_page = "Sales"
    if st.button("💸 Expenditures"): st.session_state.current_page = "Expenditures"
    if st.button("📜 Activity Log"): st.session_state.current_page = "Log"
    if st.session_state.role == "Admin": 
        p_users = len(users_df[users_df['Status'] == "Pending"])
        admin_btn_label = f"🛡️ Admin Page (🚨 {p_users})" if p_users > 0 else "🛡️ Admin Page"
        if st.button(admin_btn_label): st.session_state.current_page = "Admin"
    st.write("---")
    st.write(f"☁️ Cloud Sync: **{st.session_state.last_sync}**")
    if st.button("🚪 Logout"): 
        cookie_manager.delete("inv_pro_user"); log_action("User logged out."); st.session_state.logged_in = False; st.rerun()

page = st.session_state.current_page

if page == "Dashboard":
    st.markdown("<h1>📊 Dashboard</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        f1, f2, f3 = st.columns([1, 1, 1])
        dash_sales = st.session_state.sales.copy()
        dash_sales["Date"] = pd.to_datetime(dash_sales["Date"], errors='coerce')
        y_list = sorted(dash_sales["Date"].dt.year.dropna().unique().tolist(), reverse=True)
        if not y_list: y_list = [get_now().year]
        s_y = f1.selectbox("Year", y_list)
        s_m = f2.selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=get_now().month-1)
        s_v_tier = f3.selectbox("Valuation Tier", price_tiers_list if price_tiers_list else ["None"])
    
    m_idx = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].index(s_m)+1
    fs_monthly = dash_sales[(dash_sales["Date"].dt.year == s_y) & (dash_sales["Date"].dt.month == m_idx)]
    paid_monthly = fs_monthly[(fs_monthly['Payment'] == 'Paid') & (fs_monthly['Profit'] > 0)]
    
    exp_df = st.session_state.expenditures.copy()
    exp_df["Date"] = pd.to_datetime(exp_df["Date"], errors='coerce')
    monthly_exp_val = exp_df[(exp_df["Date"].dt.year == s_y) & (exp_df["Date"].dt.month == m_idx)]['Cost'].sum()
    
    rev, prof = paid_monthly['Total'].sum(), paid_monthly['Profit'].sum()
    margin = (prof / rev * 100) if rev > 0 else 0
    exp_ratio = (monthly_exp_val / rev * 100) if rev > 0 else 0

    current_stock = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
    val_df = current_stock.merge(db_df, on="Product Name", how="left")
    total_valuation_cost = (val_df["Quantity"] * val_df["Cost per Unit"].fillna(0)).sum()
    potential_sales_val = (val_df["Quantity"] * val_df[s_v_tier].fillna(0)).sum() if s_v_tier in val_df.columns else 0.0

    st.write("### 💎 Financial Overview")
    m1, m2, m3, m4 = st.columns(4)
    total_paid_rev = dash_sales[dash_sales['Payment'] == 'Paid']['Total'].sum()
    net_cash = (st.session_state.cash_in['Amount'].sum() + total_paid_rev) - st.session_state.expenditures['Cost'].sum()
    m1.metric("Total Net Money (Cash)", f"₱{net_cash:,.2f}"); m2.metric("Monthly Paid Profit", f"₱{prof:,.2f}")
    m3.metric("Profit Margin %", f"{margin:.1f}%"); m4.metric("Expense Ratio", f"{exp_ratio:.1f}%")

    st.write("### 📦 Stock Valuation")
    v1, v2 = st.columns(2)
    v1.metric("Total Stock Value (Cost)", f"₱{total_valuation_cost:,.2f}")
    v2.metric(f"Potential Sales Value ({s_v_tier})", f"₱{potential_sales_val:,.2f}")

    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.write("### 🚨 Stock Alerts")
        alerts = current_stock[current_stock["Quantity"] < 5].sort_values("Quantity")
        st.dataframe(alerts, use_container_width=True, hide_index=True)
    with c2:
        if not paid_monthly.empty: 
            st.write("### 🏆 Top Sellers (Paid)")
            st.table(paid_monthly.groupby("Product")["Qty"].sum().sort_values(ascending=False).head(5))

elif page == "Database":
    st.markdown("<h1>📂 Database</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        nt = st.text_input("Tier Name")
        if st.button("Add Tier"): 
            db_df[nt] = 0.0; save_data(db_df, DB_FILE, sync_name="Database"); st.rerun()
    with c2:
        td = st.selectbox("Select Tier to Remove", [""] + price_tiers_list)
        if st.button("Delete Tier") and td: 
            db_df = db_df.drop(columns=[td]); save_data(db_df, DB_FILE, sync_name="Database"); st.rerun()
    ed_db = st.data_editor(db_df, use_container_width=True, hide_index=True, num_rows="dynamic", height=600)
    if not ed_db.equals(db_df): save_data(ed_db, DB_FILE, sync_name="Database"); st.rerun()

elif page == "Inventory":
    st.markdown("<h1>📦 Inventory</h1>", unsafe_allow_html=True)
    cl, cr = st.columns([1, 2.5])
    with cl:
        sdf = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index().sort_values("Quantity")
        sdf["Stat"] = sdf["Quantity"].apply(lambda q: "❌" if q <= 0 else "⚠️" if q < 5 else "✅")
        st.dataframe(sdf, use_container_width=True, hide_index=True, height=600)
    with cr:
        f = st.columns([1.2, 1, 1, 1, 0.5])
        c_date, np, nq, ns = f[0].date_input("Date"), f[1].selectbox("Product", product_list), f[2].number_input("Qty", min_value=1), f[3].selectbox("Status", ["In Stock", "Bought"])
        if f[4].button("➕"):
            nr = pd.DataFrame({"Product Name": [np], "Quantity": [nq], "Status": [ns], "Date": [c_date]})
            st.session_state.stock = pd.concat([st.session_state.stock, nr], ignore_index=True)
            save_data(st.session_state.stock, STOCK_FILE, sync_name="Inventory"); st.rerun()
        ed_s = st.data_editor(st.session_state.stock.copy().iloc[::-1], use_container_width=True, hide_index=True, num_rows="dynamic", height=500)
        if not ed_s.equals(st.session_state.stock.iloc[::-1]): save_data(ed_s.iloc[::-1], STOCK_FILE, sync_name="Inventory"); st.rerun()

elif page == "Sales":
    st.markdown("<h1>💰 Sales Tracker</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        sf = st.columns([1, 1.2, 1.5, 0.8, 1, 0.5])
        s_date, s_cust, s_prod, s_qty, s_tier = sf[0].date_input("Date"), sf[1].text_input("Customer"), sf[2].selectbox("Product", [""]+product_list), sf[3].number_input("Qty", min_value=1), sf[4].selectbox("Tier", [""]+price_tiers_list)
        if sf[5].button("➕"):
            if s_prod and s_tier:
                match = db_df[db_df["Product Name"] == s_prod]
                u_c, b_c, u_p = float(match["Cost per Unit"].values[0]), float(match["Boxed Cost"].values[0]), float(match[s_tier].values[0])
                calc_tot = u_p * s_qty
                new_row = pd.DataFrame([{"Date": s_date, "Customer": s_cust, "Product": s_prod, "Qty": s_qty, "Price Tier": s_tier, "Price Value": u_p, "Cost": u_c, "Boxed Cost": b_c, "Profit": calc_tot - (b_c * s_qty), "Discount": 0.0, "Total": calc_tot, "Status": "Pending", "Payment": "Unpaid"}])
                st.session_state.sales = pd.concat([st.session_state.sales, new_row], ignore_index=True)
                save_data(st.session_state.sales, SALES_FILE, sync_name="Sales"); st.rerun()

    conf = {
        "Date": st.column_config.DateColumn("Date", required=True),
        "Product": st.column_config.SelectboxColumn("Product", options=product_list),
        "Price Tier": st.column_config.SelectboxColumn("Price Tier", options=price_tiers_list),
        "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Sold", "Cancelled"]),
        "Payment": st.column_config.SelectboxColumn("Payment", options=["Unpaid", "Paid"]),
        "Cost": st.column_config.NumberColumn(disabled=True, format="₱%.2f"),
        "Total": st.column_config.NumberColumn(disabled=True, format="₱%.2f")
    }
    view = st.session_state.sales[SALES_ORDER].copy().iloc[::-1]
    for c in ["Qty", "Discount", "Price Value", "Cost", "Boxed Cost", "Profit", "Total"]:
        if c in view.columns: view[c] = pd.to_numeric(view[c], errors='coerce').fillna(0.0)

    ed_sales = st.data_editor(view, use_container_width=True, hide_index=True, num_rows="dynamic", column_config=conf, height=600)
    
    if not ed_sales.equals(view):
        ndf = ed_sales.copy()
        for idx in ndf.index:
            row = ndf.loc[idx]
            old_row = view.loc[idx] if idx in view.index else None
            prod, tier = row["Product"], row["Price Tier"]
            if prod and tier:
                match = db_df[db_df["Product Name"] == prod]
                if not match.empty:
                    u_c, b_c, u_p = float(match["Cost per Unit"].values[0]), float(match["Boxed Cost"].values[0]), float(match[tier].values[0])
                    qty, disc = float(row["Qty"]), float(row["Discount"])
                    tot, prf = (u_p - disc) * qty, ((u_p - disc) * qty) - (b_c * qty)
                    ndf.at[idx, "Price Value"], ndf.at[idx, "Cost"], ndf.at[idx, "Boxed Cost"], ndf.at[idx, "Total"], ndf.at[idx, "Profit"] = u_p, u_c, b_c, tot, prf
            if old_row is not None and row["Status"] == "Sold" and old_row["Status"] != "Sold":
                s_df = st.session_state.stock.copy()
                mask = (s_df["Product Name"] == prod) & (s_df["Status"] == "In Stock") & (s_df["Quantity"] > 0)
                available, needed = s_df[mask].index, int(row["Qty"])
                for s_idx in available:
                    if needed <= 0: break
                    take = min(needed, s_df.at[s_idx, "Quantity"])
                    s_df.at[s_idx, "Quantity"] -= take; needed -= take
                st.session_state.stock = s_df; save_data(s_df, STOCK_FILE, sync_name="Inventory")
        save_data(ndf.iloc[::-1], SALES_FILE, sync_name="Sales"); st.rerun()

elif page == "Expenditures":
    st.markdown("<h1>💸 Expenditures</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        ex_d, it, ct = st.date_input("Ex Date"), st.text_input("Ex Item"), st.number_input("Ex Cost", min_value=0.0)
        if st.button("Add Expense"):
            new = pd.DataFrame({"Date": [ex_d], "Item": [it], "Cost": [ct]})
            st.session_state.expenditures = pd.concat([st.session_state.expenditures, new]); save_data(st.session_state.expenditures, EXPENSE_FILE, sync_name="Expenses"); st.rerun()
    with c2:
        in_d, src, amt = st.date_input("Dep Date"), st.text_input("Dep Source"), st.number_input("Dep Amount", min_value=0.0)
        if st.button("Add Deposit"):
            new = pd.DataFrame({"Date": [in_d], "Source": [src], "Amount": [amt]})
            st.session_state.cash_in = pd.concat([st.session_state.cash_in, new]); save_data(st.session_state.cash_in, CASH_FILE, sync_name="CashIn"); st.rerun()
    l, r = st.columns(2)
    with l:
        ed_ex = st.data_editor(st.session_state.expenditures.copy().iloc[::-1], use_container_width=True, hide_index=True, num_rows="dynamic", height=500)
        if not ed_ex.equals(st.session_state.expenditures.iloc[::-1]): save_data(ed_ex.iloc[::-1], EXPENSE_FILE, sync_name="Expenses"); st.rerun()
    with r:
        ed_in = st.data_editor(st.session_state.cash_in.copy().iloc[::-1], use_container_width=True, hide_index=True, num_rows="dynamic", height=500)
        if not ed_in.equals(st.session_state.cash_in.iloc[::-1]): save_data(ed_in.iloc[::-1], CASH_FILE, sync_name="CashIn"); st.rerun()

elif page == "Admin" and st.session_state.role == "Admin":
    st.markdown("<h1>🛡️ Admin Control</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Requests", "Cloud Sync Hub"])
    with t1:
        pend = users_df[users_df['Status'] == "Pending"]
        for idx, row in pend.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"User: **{row['Username']}**")
                if c2.button(f"Approve", key=f"app_{idx}"):
                    users_df.at[idx, 'Status'] = "Approved"; save_data(users_df, USERS_FILE, sync_name="Users"); st.rerun()
                if c3.button(f"Reject", key=f"rej_{idx}"):
                    save_data(users_df.drop(idx), USERS_FILE, sync_name="Users"); st.rerun()
    with t2:
        if st.button("🚀 Push All Data to Google Sheets"):
            sync_to_google(st.session_state.inventory, "Database"); sync_to_google(st.session_state.stock, "Inventory")
            sync_to_google(st.session_state.sales, "Sales"); sync_to_google(st.session_state.expenditures, "Expenses")
            sync_to_google(st.session_state.cash_in, "CashIn"); sync_to_google(users_df, "Users")
            st.success("Cloud Backup Complete!")

elif page == "Log":
    st.markdown("<h1>📜 Activity Log</h1>", unsafe_allow_html=True)
    log_data = load_data(LOG_FILE, {})
    if not log_data.empty:
        log_data['User'] = log_data['Identity'].str.split(' (', regex=False).str[0]
        user_list = ["All Users"] + sorted(log_data['User'].unique().tolist())
        selected_user = st.selectbox("Filter Logs by Staff Member", user_list)
        display_data = log_data[log_data['User'] == selected_user].drop(columns=['User']) if selected_user != "All Users" else log_data.drop(columns=['User'])
    else:
        display_data = log_data
    st.dataframe(display_data, use_container_width=True, hide_index=True, height=700)
    if st.session_state.role == "Admin" and st.button("⚠️ Clear Activity Log"):
        save_data(pd.DataFrame(columns=["Timestamp", "Identity", "Action Detail"]), LOG_FILE, sync_name="Logs"); st.rerun()
