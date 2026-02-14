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
CORE_COLS = ["Product Name"] + EXPENSE_COLS

if not os.path.exists("backups"):
    os.makedirs("backups")

SALES_ORDER = ["Date", "Customer", "Product", "Qty", "Price Tier", "Cost", "Boxed Cost", "Profit", "Discount", "Total", "Status", "Payment"]

# --- DYNAMIC CSS (STRICT COMPACT SIDEBAR) ---
st.markdown(f"""
    <style>
    html, body, [class*="ViewContainer"] {{ font-size: 12px !important; }}
    .block-container {{ padding: 1rem !important; }}
    [data-testid="stSidebar"] {{ min-width: 160px !important; max-width: 160px !important; }}
    h1 {{ display: block !important; font-size: 1.3rem !important; font-weight: 700 !important; margin-top: 0.5rem !important; color: #FFFFFF !important; }}
    .stButton > button {{ 
        width: 100% !important; 
        padding: 2px 8px !important; 
        text-align: left !important;
        font-size: 11px !important;
        border-radius: 4px !important;
        min-height: 24px !important;
        line-height: 1.2 !important;
        margin-bottom: -10px !important;
    }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.2rem !important; padding-top: 1rem !important; }}
    hr {{ border: none !important; height: 1px !important; background-color: #333 !important; display: block !important; margin: 5px 0 !important; }}
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
        try:
            if os.path.getsize(file) > 0:
                df = pd.read_csv(file)
                if not df.empty and "Date" in df.columns:
                    df["Date"] = pd.to_datetime(df["Date"], errors='coerce').dt.date
                    df["Date"] = df["Date"].fillna(date.today())
                return df
        except Exception:
            pass
    return pd.DataFrame(defaults)

def save_data(df, file):
    df.to_csv(file, index=False)

def log_action(action_desc):
    user = st.session_state.get('user', 'System')
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    new_log = pd.DataFrame({"Timestamp": [now], "User": [user], "Detailed Action": [action_desc]})
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        try:
            log_df = pd.concat([new_log, pd.read_csv(LOG_FILE)], ignore_index=True)
        except:
            log_df = new_log
    else:
        log_df = new_log
    log_df.to_csv(LOG_FILE, index=False)

# --- USER DB INIT ---
primary_admin = {"Username": ["Musika"], "Password": [make_hashes("Iameternal11!")], "Role": ["Admin"]}
users_df = load_data(USERS_FILE, primary_admin)

# --- SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user' not in st.session_state: st.session_state.user = None
if 'role' not in st.session_state: st.session_state.role = None
if 'current_page' not in st.session_state: st.session_state.current_page = "Dashboard"

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    st.markdown("<h1>🔐 Login</h1>", unsafe_allow_html=True)
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
price_tiers_list = [c for c in db_df.columns if c not in CORE_COLS]

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown(f"👤 **{st.session_state.user}**")
    if st.button("📊 Dashboard"): st.session_state.current_page = "Dashboard"
    if st.button("📂 Database"): st.session_state.current_page = "Database"
    if st.button("📦 Inventory"): st.session_state.current_page = "Inventory"
    if st.button("💰 Sales"): st.session_state.current_page = "Sales"
    if st.button("💸 Expenses"): st.session_state.current_page = "Expenditures"
    if st.button("📜 Logs"): st.session_state.current_page = "Log"
    if st.session_state.role == "Admin":
        if st.button("🛡️ Admin"): st.session_state.current_page = "Admin"
    st.write("---")
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.rerun()

page = st.session_state.current_page

# --- ADMIN PAGE ---
if page == "Admin" and st.session_state.role == "Admin":
    st.markdown("<h1>🛡️ User Management</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        ac1, ac2, ac3, ac4 = st.columns([2, 2, 1, 1])
        new_u = ac1.text_input("New User", key="adm_u")
        new_p = ac2.text_input("New Pwd", type="password", key="adm_p")
        new_r = ac3.selectbox("Role", ["Staff", "Admin"])
        if ac4.button("Add"):
            if new_u and new_p:
                new_row = pd.DataFrame({"Username": [new_u], "Password": [make_hashes(new_p)], "Role": [new_r]})
                users_df = pd.concat([users_df, new_row], ignore_index=True)
                save_data(users_df, USERS_FILE); log_action(f"Admin added user {new_u}"); st.rerun()
    st.data_editor(users_df, use_container_width=True, hide_index=True, column_config={"Password": None})

# --- DASHBOARD ---
elif page == "Dashboard":
    st.markdown("<h1>📊 Dashboard</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        f1, f2 = st.columns(2)
        all_dates = pd.to_datetime(st.session_state.sales["Date"])
        y = sorted(all_dates.dt.year.unique().tolist(), reverse=True) if not all_dates.empty else [date.today().year]
        s_y = f1.selectbox("Year", y)
        s_m = f2.selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=date.today().month-1)
    
    midx = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].index(s_m)+1
    fs = st.session_state.sales.copy(); fs["Date"] = pd.to_datetime(fs["Date"])
    fs = fs[(fs["Date"].dt.year == s_y) & (fs["Date"].dt.month == midx)]
    
    cash = (st.session_state.cash_in['Amount'].sum() + st.session_state.sales['Profit'].sum()) - st.session_state.expenditures['Cost'].sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Cash", f"₱{cash:,.2f}"); m2.metric("Profit", f"₱{fs['Profit'].sum():,.2f}")
    m3.metric("Net Period", f"₱{(fs['Profit'].sum() - st.session_state.expenditures['Cost'].sum()):,.2f}"); m4.metric("Unpaid Balance", f"₱{fs[fs['Payment'] == 'Unpaid']['Total'].sum():,.2f}")
    
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.write("### 🚨 Stock Alerts")
        summary = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
        alerts = summary[summary["Quantity"] < 5].sort_values("Quantity")
        if not alerts.empty: st.dataframe(alerts, use_container_width=True, hide_index=True)
        else: st.success("Stock Healthy ✅")
    with c2:
        st.write("### 🏆 Top Sellers")
        if not fs.empty: st.table(fs.groupby("Product")["Qty"].sum().sort_values(ascending=False).head(5).reset_index())
    
    st.write("---")
    st.write("### 📈 Cash Trend")
    p, d, e = st.session_state.sales[['Date', 'Profit']].rename(columns={'Profit': 'A'}), st.session_state.cash_in[['Date', 'Amount']].rename(columns={'Amount': 'A'}), st.session_state.expenditures[['Date', 'Cost']].rename(columns={'Cost': 'A'})
    e['A'] = -e['A']; t_df = pd.concat([p, d, e])
    if not t_df.empty:
        t_df['Date'] = pd.to_datetime(t_df['Date']); t_df = t_df.sort_values('Date').groupby('Date').sum().reset_index(); t_df['Cum'] = t_df['A'].cumsum()
        st.plotly_chart(px.line(t_df, x='Date', y='Cum', template="plotly_dark", markers=True), use_container_width=True)

# --- DATABASE ---
elif page == "Database":
    st.markdown("<h1>📂 Database</h1>", unsafe_allow_html=True)
    col_add, col_del = st.columns(2)
    with col_add:
        st.write("### ➕ Add Price Tier")
        t1, t2 = st.columns([3, 1])
        nt = t1.text_input("New Tier Name")
        if t2.button("Add"):
            if nt and nt not in db_df.columns:
                db_df[nt] = 0.0; save_data(db_df, DB_FILE); log_action(f"📂 Added Tier {nt}"); st.rerun()
    with col_del:
        st.write("### 🗑️ Remove Price Tier")
        d1, d2 = st.columns([3, 1])
        tier_to_del = d1.selectbox("Select Tier", [""] + price_tiers_list)
        if d2.button("Delete"):
            if tier_to_del:
                db_df = db_df.drop(columns=[tier_to_del])
                save_data(db_df, DB_FILE); log_action(f"📂 Deleted Tier {tier_to_del}"); st.rerun()
    st.write("---")
    ed = st.data_editor(db_df, use_container_width=True, hide_index=True, num_rows="dynamic")
    if not ed.equals(db_df): save_data(ed, DB_FILE); log_action("DB Table Updated"); st.rerun()

# --- INVENTORY ---
elif page == "Inventory":
    st.markdown("<h1>📦 Inventory</h1>", unsafe_allow_html=True)
    l, r = st.columns([1, 2])
    with l:
        st.write("### 📊 Quick Tally")
        # FIXED SORTING: Least quantity at the top by default
        sdf = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
        sdf = sdf.sort_values(by="Quantity", ascending=True)
        sdf["Alert"] = sdf["Quantity"].apply(lambda q: "❌ Out" if q <= 0 else "⚠️ Low" if q < 5 else "✅ Good")
        st.dataframe(sdf, use_container_width=True, hide_index=True)
    with r:
        st.write("### ⚙️ Add Stock Entry")
        f = st.columns([2, 1, 1, 0.5])
        np, nq, ns = f[0].selectbox("Item", sorted(product_list)), f[1].number_input("Qty", min_value=1), f[2].selectbox("Status", ["In Stock", "Bought"])
        if f[3].button("➕"):
            nr = pd.DataFrame({"Product Name": [np], "Quantity": [nq], "Status": [ns], "Date": [date.today()]})
            st.session_state.stock = pd.concat([st.session_state.stock, nr], ignore_index=True); save_data(st.session_state.stock, STOCK_FILE); st.rerun()
        ed_s = st.data_editor(st.session_state.stock.copy().iloc[::-1], use_container_width=True, hide_index=True, num_rows="dynamic")
        if not ed_s.equals(st.session_state.stock.iloc[::-1]): save_data(ed_s.iloc[::-1], STOCK_FILE); st.rerun()

# --- SALES ---
elif page == "Sales":
    st.markdown("<h1>💰 Sales Tracker</h1>", unsafe_allow_html=True)
    sdf = st.session_state.sales.copy(); sdf["Date"] = pd.to_datetime(sdf["Date"]).dt.date
    conf = {"Product": st.column_config.SelectboxColumn(options=sorted(product_list)), "Price Tier": st.column_config.SelectboxColumn(options=price_tiers_list), "Status": st.column_config.SelectboxColumn(options=["Sold", "Reserved"]), "Payment": st.column_config.SelectboxColumn(options=["Paid", "Unpaid"])}
    ed = st.data_editor(sdf[SALES_ORDER], use_container_width=True, hide_index=True, num_rows="dynamic", column_config=conf, key="sales_ed")
    state = st.session_state["sales_ed"]
    if state["edited_rows"] or state["added_rows"] or state["deleted_rows"]:
        ndf = ed.copy()
        for idx in ndf.index:
            row = ndf.loc[idx]; m = db_df[db_df["Product Name"] == row["Product"]]
            if not m.empty:
                t = str(row["Price Tier"]); uc, bc = float(m["Cost per Unit"].values[0]), float(m["Boxed Cost"].values[0])
                pt = float(m[t].values[0]) if t in m.columns else 0.0
                qty, disc = float(row["Qty"]), float(row["Discount"])
                ndf.at[idx, "Cost"], ndf.at[idx, "Boxed Cost"] = uc, bc
                tot = (pt - disc) * qty; ndf.at[idx, "Total"], ndf.at[idx, "Profit"] = tot, tot - (bc * qty)
                old = st.session_state.sales.iloc[idx] if idx < len(st.session_state.sales) else None
                if row["Status"] == "Sold" and (old is None or old["Status"] != "Sold"):
                    s, need = st.session_state.stock, int(qty)
                    mask = (s["Product Name"] == row["Product"]) & (s["Status"] == "In Stock") & (s["Quantity"] > 0)
                    for ti in s[mask].index:
                        if need <= 0: break
                        tk = min(need, s.at[ti, "Quantity"]); s.at[ti, "Quantity"] -= tk; need -= tk
                    save_data(s, STOCK_FILE); log_action(f"🟢 [SOLD] {int(qty)} of {row['Product']}")
        save_data(ndf, SALES_FILE); st.rerun()

# --- EXPENSES ---
elif page == "Expenditures":
    st.markdown("<h1>💸 Expenditures</h1>", unsafe_allow_html=True)
    m1, m2 = st.columns(2); e_t, d_t = st.session_state.expenditures['Cost'].sum(), st.session_state.cash_in['Amount'].sum()
    m1.metric("Expenses", f"₱{e_t:,.2f}"); m2.metric("Deposits", f"₱{d_t:,.2f}")
    r = st.columns([2, 1, 0.4])
    it, ct = r[0].text_input("Item"), r[1].number_input("Cost", min_value=0.0)
    if r[2].button("➕"):
        new = pd.DataFrame({"Date": [date.today()], "Item": [it], "Cost": [ct]})
        st.session_state.expenditures = pd.concat([st.session_state.expenditures, new], ignore_index=True)
        save_data(st.session_state.expenditures, EXPENSE_FILE); log_action(f"💸 Expense: {it}"); st.rerun()

# --- LOG ---
elif page == "Log":
    st.markdown("<h1>📜 Logs</h1>", unsafe_allow_html=True)
    if st.button("🛡️ Backup"):
        b = f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"; os.makedirs(b, exist_ok=True)
        for f in [DB_FILE, STOCK_FILE, SALES_FILE, EXPENSE_FILE, CASH_FILE, LOG_FILE, USERS_FILE]: 
            if os.path.exists(f): shutil.copy(f, b)
        st.success("Backup Saved")
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0: 
        st.dataframe(pd.read_csv(LOG_FILE), use_container_width=True, hide_index=True)
