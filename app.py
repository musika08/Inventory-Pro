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

# --- DYNAMIC CSS ---
st.markdown(f"""
    <style>
    html, body, [class*="ViewContainer"] {{ font-size: 12px !important; }}
    .block-container {{ padding: 1rem !important; }}
    [data-testid="stSidebar"] {{ min-width: 180px !important; max-width: 180px !important; }}
    .stButton > button {{ width: 100% !important; padding: 4px 10px !important; text-align: left !important; font-size: 11px !important; border-radius: 4px !important; }}
    h1 {{ display: block !important; font-size: 1.4rem !important; font-weight: 700 !important; margin-top: 1rem !important; color: #FFFFFF !important; }}
    hr {{ border: none !important; height: 1px !important; background-color: #333 !important; display: block !important; margin: 8px 0 !important; }}
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
# Hardcoded primary admin Musika
primary_admin = {"Username": ["Musika"], "Password": [make_hashes("Iameternal11!")], "Role": ["Admin"]}
users_df = load_data(USERS_FILE, primary_admin)

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
        res = users_df[users_df['Username'] == u]
        if not res.empty and check_hashes(p, res.iloc[0]['Password']):
            st.session_state.logged_in = True
            st.session_state.user = u
            st.session_state.role = res.iloc[0]['Role']
            st.rerun()
        else:
            st.error("Invalid Username or Password")
    st.stop()

# --- DATA INITIALIZATION ---
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
    st.markdown(f"👤 **{st.session_state.user}** ({st.session_state.role})")
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

# --- PAGE: ADMIN ---
if page == "Admin" and st.session_state.role == "Admin":
    st.markdown("<h1>🛡️ Admin & User Management</h1>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.write("### ➕ Add New User")
        ac1, ac2, ac3, ac4 = st.columns([2, 2, 1, 1])
        new_u = ac1.text_input("Username", key="new_u")
        new_p = ac2.text_input("Password", type="password", key="new_p")
        new_r = ac3.selectbox("Role", ["Staff", "Admin"], key="new_r")
        if ac4.button("Add User"):
            if new_u in users_df['Username'].values:
                st.error("User already exists!")
            else:
                new_user_row = pd.DataFrame({"Username": [new_u], "Password": [make_hashes(new_p)], "Role": [new_r]})
                users_df = pd.concat([users_df, new_user_row], ignore_index=True)
                save_data(users_df, USERS_FILE)
                log_action(f"Admin: Added new user '{new_u}' as {new_r}")
                st.success(f"User {new_u} added!")
                st.rerun()

    st.write("### 👥 Manage Users")
    edited_users = st.data_editor(users_df, use_container_width=True, hide_index=True, column_config={
        "Password": st.column_config.TextColumn("Password (Hashed)", disabled=True),
        "Role": st.column_config.SelectboxColumn("Role", options=["Admin", "Staff"], required=True)
    })
    if not edited_users.equals(users_df):
        save_data(edited_users, USERS_FILE)
        log_action("Admin: Modified User Database")
        st.rerun()

# --- PAGE: DASHBOARD ---
elif page == "Dashboard":
    st.markdown("<h1>📊 Dashboard</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        f_row = st.columns(2)
        all_dates = pd.to_datetime(st.session_state.sales["Date"])
        y = sorted(all_dates.dt.year.unique().tolist(), reverse=True) if not all_dates.empty else [date.today().year]
        s_y, s_m = f_row[0].selectbox("Year", y), f_row[1].selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=date.today().month-1)
    
    month_idx = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].index(s_m)+1
    f_sales = st.session_state.sales.copy(); f_sales["Date"] = pd.to_datetime(f_sales["Date"])
    f_sales = f_sales[(f_sales["Date"].dt.year == s_y) & (f_sales["Date"].dt.month == month_idx)]
    
    cash = (st.session_state.cash_in['Amount'].sum() + st.session_state.sales['Profit'].sum()) - st.session_state.expenditures['Cost'].sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Money", f"₱{cash:,.2f}"); m2.metric("Monthly Profit", f"₱{f_sales['Profit'].sum():,.2f}")
    m3.metric("Net Period Profit", f"₱{(f_sales['Profit'].sum() - st.session_state.expenditures['Cost'].sum()):,.2f}"); m4.metric("Unpaid Balance", f"₱{f_sales[f_sales['Payment'] == 'Unpaid']['Total'].sum():,.2f}")
    
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.write("### 🚨 Current Stock Alerts")
        summary = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
        alerts = summary[summary["Quantity"] < 5].sort_values("Quantity")
        if not alerts.empty: st.dataframe(alerts, use_container_width=True, hide_index=True)
        else: st.success("All stock healthy! ✅")
    with c2:
        st.write("### 🏆 Top Selling Products")
        if not f_sales.empty: st.table(f_sales.groupby("Product")["Qty"].sum().sort_values(ascending=False).head(5).reset_index())
    
    st.write("---")
    st.write("### 📈 Net Cash Flow Trend")
    p, d, e = st.session_state.sales[['Date', 'Profit']].rename(columns={'Profit': 'Amt'}), st.session_state.cash_in[['Date', 'Amount']].rename(columns={'Amount': 'Amt'}), st.session_state.expenditures[['Date', 'Cost']].rename(columns={'Cost': 'Amt'})
    e['Amt'] = -e['Amt']; t_df = pd.concat([p, d, e])
    if not t_df.empty:
        t_df['Date'] = pd.to_datetime(t_df['Date']); t_df = t_df.sort_values('Date').groupby('Date').sum().reset_index(); t_df['CumCash'] = t_df['Amt'].cumsum()
        st.plotly_chart(px.line(t_df, x='Date', y='CumCash', template="plotly_dark", markers=True), use_container_width=True)

# --- PAGE: DATABASE ---
elif page == "Database":
    st.markdown("<h1>📂 Database</h1>", unsafe_allow_html=True)
    t_c1, t_c2 = st.columns([4, 1])
    n_t = t_c1.text_input("New Tier Name")
    if t_c2.button("➕"):
        if n_t and n_t not in db_df.columns:
            db_df[n_t] = 0.0; save_data(db_df, DB_FILE); log_action(f"📂 Added Tier '{n_t}'"); st.rerun()
    ed = st.data_editor(db_df, use_container_width=True, hide_index=True, num_rows="dynamic")
    if not ed.equals(db_df):
        save_data(ed, DB_FILE); log_action("📂 Database modified"); st.rerun()

# --- PAGE: INVENTORY ---
elif page == "Inventory":
    st.markdown("<h1>📦 Inventory Summary</h1>", unsafe_allow_html=True)
    c_l, c_r = st.columns([1, 2])
    with c_l:
        st.write("### 📊 Quick Tally")
        sum_df = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
        sum_df["Alert"] = sum_df["Quantity"].apply(lambda q: "❌ Out" if q <= 0 else "⚠️ Low" if q < 5 else "✅ Good")
        st.dataframe(sum_df, use_container_width=True, hide_index=True)
    with c_r:
        st.write("### ⚙️ Add Stock Entry")
        f_row = st.columns([1.5, 0.7, 1, 0.4])
        n_p, n_q, n_s = f_row[0].selectbox("Product", product_list), f_row[1].number_input("Qty", min_value=1), f_row[2].selectbox("Status", ["In Stock", "Bought"])
        if f_row[3].button("➕"):
            n_row = pd.DataFrame({"Product Name": [n_p], "Quantity": [n_q], "Status": [n_s], "Date": [date.today()]})
            st.session_state.stock = pd.concat([st.session_state.stock, n_row], ignore_index=True)
            save_data(st.session_state.stock, STOCK_FILE); log_action(f"➕ Stocked {n_q} of '{n_p}'"); st.rerun()
        s_v = st.session_state.stock.copy().iloc[::-1]
        ed_s = st.data_editor(s_v, use_container_width=True, hide_index=True, num_rows="dynamic", key="ed_stock")
        if not ed_s.equals(s_v):
            save_data(ed_s.iloc[::-1], STOCK_FILE); log_action("📦 Stock adjusted"); st.rerun()

# --- PAGE: SALES ---
elif page == "Sales":
    st.markdown("<h1>💰 Sales Tracker</h1>", unsafe_allow_html=True)
    sales_df = st.session_state.sales.copy(); sales_df["Date"] = pd.to_datetime(sales_df["Date"]).dt.date
    sales_config = {
        "Product": st.column_config.SelectboxColumn("Product", options=sorted(product_list), required=True),
        "Price Tier": st.column_config.SelectboxColumn("Price Tier", options=price_tiers_list, required=True),
        "Status": st.column_config.SelectboxColumn("Status", options=["Sold", "Reserved"], default="Sold", required=True),
        "Payment": st.column_config.SelectboxColumn("Payment", options=["Paid", "Unpaid"], default="Unpaid", required=True),
    }
    edited_sales = st.data_editor(sales_df[SALES_ORDER], use_container_width=True, hide_index=True, num_rows="dynamic", column_config=sales_config, key="sales_editor")
    state = st.session_state["sales_editor"]
    if state["edited_rows"] or state["added_rows"] or state["deleted_rows"]:
        new_df = edited_sales.copy()
        for idx in new_df.index:
            row = new_df.loc[idx]
            match = db_df[db_df["Product Name"] == row["Product"]]
            if not match.empty:
                tier = str(row["Price Tier"])
                u_c, b_c = float(match["Cost per Unit"].values[0]), float(match["Boxed Cost"].values[0])
                p_t = float(match[tier].values[0]) if tier in match.columns else 0.0
                qty, disc = float(row["Qty"]), float(row["Discount"])
                new_df.at[idx, "Cost"], new_df.at[idx, "Boxed Cost"] = u_c, b_c
                total = (p_t - disc) * qty
                new_df.at[idx, "Total"], new_df.at[idx, "Profit"] = total, total - (b_c * qty)
                # Deduct Stock Logic
                old_row = st.session_state.sales.iloc[idx] if idx < len(st.session_state.sales) else None
                if row["Status"] == "Sold" and (old_row is None or old_row["Status"] != "Sold"):
                    s_df, needed = st.session_state.stock, int(qty)
                    mask = (s_df["Product Name"] == row["Product"]) & (s_df["Status"] == "In Stock") & (s_df["Quantity"] > 0)
                    for t_idx in s_df[mask].index:
                        if needed <= 0: break
                        take = min(needed, s_df.at[t_idx, "Quantity"])
                        s_df.at[t_idx, "Quantity"] -= take; needed -= take
                    save_data(s_df, STOCK_FILE); log_action(f"🟢 [SOLD] {int(qty)} of '{row['Product']}'")
        save_data(new_df, SALES_FILE); st.rerun()

# --- PAGE: EXPENDITURES ---
elif page == "Expenditures":
    st.markdown("<h1>💸 Expenditures</h1>", unsafe_allow_html=True)
    m1, m2 = st.columns(2)
    e_t, d_t = st.session_state.expenditures['Cost'].sum(), st.session_state.cash_in['Amount'].sum()
    m1.metric("Expenses", f"₱{e_t:,.2f}"); m2.metric("Deposits", f"₱{d_t:,.2f}")
    
    # Add logic here for expense/deposit inputs
    ex_row = st.columns([2, 1, 0.4])
    item, cost = ex_row[0].text_input("Expense"), ex_row[1].number_input("Cost", min_value=0.0)
    if ex_row[2].button("➕"):
        new_ex = pd.DataFrame({"Date": [date.today()], "Item": [item], "Cost": [cost]})
        st.session_state.expenditures = pd.concat([st.session_state.expenditures, new_ex], ignore_index=True)
        save_data(st.session_state.expenditures, EXPENSE_FILE); log_action(f"💸 Expense: {item}"); st.rerun()

# --- PAGE: LOG ---
elif page == "Log":
    st.markdown("<h1>📜 Activity Log</h1>", unsafe_allow_html=True)
    if st.button("🛡️ Create Backup"):
        b_dir = f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"; os.makedirs(b_dir, exist_ok=True)
        for f in [DB_FILE, STOCK_FILE, SALES_FILE, EXPENSE_FILE, CASH_FILE, LOG_FILE, USERS_FILE]: 
            if os.path.exists(f): shutil.copy(f, b_dir)
        st.success("Backup Saved")
    if os.path.exists(LOG_FILE): st.dataframe(pd.read_csv(LOG_FILE), use_container_width=True, hide_index=True)
