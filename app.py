import streamlit as st
import pandas as pd
import os
import shutil
from datetime import date, datetime
import hashlib
import extra_streamlit_components as stx

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
    [data-testid="stSidebar"] {{ min-width: 170px !important; max-width: 170px !important; }}
    h1 {{ display: block !important; font-size: 1.3rem !important; font-weight: 700 !important; margin-top: 0.5rem !important; color: #FFFFFF !important; }}
    .stButton > button {{ width: 100% !important; padding: 2px 8px !important; text-align: left !important; font-size: 11px !important; border-radius: 4px !important; min-height: 24px !important; margin-bottom: -10px !important; }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.2rem !important; padding-top: 1rem !important; }}
    hr {{ border: none !important; height: 1px !important; background-color: #333 !important; display: block !important; margin: 5px 0 !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- SECURITY & COOKIE HELPERS ---
def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

cookie_manager = stx.CookieManager()

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
    u_name, u_role = st.session_state.get('user', 'Unknown'), st.session_state.get('role', 'System')
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    new_log = pd.DataFrame({"Timestamp": [now], "Identity": [f"{u_name} ({u_role})"], "Action Detail": [action_desc]})
    log_df = pd.concat([new_log, load_data(LOG_FILE, {"Timestamp":[], "Identity":[], "Action Detail":[]})], ignore_index=True)
    save_data(log_df, LOG_FILE)

# --- INITIALIZATION ---
users_df = load_data(USERS_FILE, {"Username": ["Musika"], "Password": [make_hashes("Iameternal11!")], "Role": ["Admin"], "Status": ["Approved"]})
db_df = load_data(DB_FILE, {"Product Name": ["Item 1"], "Cost per Unit": [0.0], "Boxed Cost": [0.0]})
st.session_state.inventory = db_df
st.session_state.stock = load_data(STOCK_FILE, {"Product Name": ["Item 1"], "Quantity": [0], "Status": ["In Stock"], "Date": [date.today()]})
st.session_state.sales = load_data(SALES_FILE, {c: [] for c in SALES_ORDER})
st.session_state.expenditures = load_data(EXPENSE_FILE, {"Date": [], "Item": [], "Cost": []})
st.session_state.cash_in = load_data(CASH_FILE, {"Date": [], "Source": [], "Amount": []})

product_list = sorted(db_df["Product Name"].dropna().unique().tolist())
price_tiers_list = [c for c in db_df.columns if c not in CORE_COLS]

# --- AUTHENTICATION ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_page' not in st.session_state: st.session_state.current_page = "Dashboard"

saved_user = cookie_manager.get(cookie="inv_pro_user")
if saved_user and not st.session_state.logged_in:
    res = users_df[users_df['Username'] == saved_user]
    if not res.empty and res.iloc[0]['Status'] == "Approved":
        st.session_state.logged_in, st.session_state.user, st.session_state.role = True, saved_user, res.iloc[0]['Role']

if not st.session_state.logged_in:
    st.markdown("<h1>🔐 Inventory Pro</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Request Access"])
    with t1:
        u, p = st.text_input("Username"), st.text_input("Password", type="password")
        rem = st.checkbox("Remember Me")
        if st.button("Login"):
            res = users_df[users_df['Username'] == u]
            if not res.empty and check_hashes(p, res.iloc[0]['Password']):
                if res.iloc[0]['Status'] == "Approved":
                    st.session_state.logged_in, st.session_state.user, st.session_state.role = True, u, res.iloc[0]['Role']
                    if rem: cookie_manager.set("inv_pro_user", u, expires_at=datetime.now().replace(year=datetime.now().year + 1))
                    log_action("Logged in."); st.rerun()
                else: st.error("Account pending approval.")
            else: st.error("Invalid credentials.")
    with t2:
        nu, np = st.text_input("New Username"), st.text_input("New Password", type="password")
        if st.button("Submit Request"):
            if nu in users_df['Username'].values: st.error("User exists.")
            else:
                new_u = pd.DataFrame({"Username": [nu], "Password": [make_hashes(np)], "Role": ["Staff"], "Status": ["Pending"]})
                save_data(pd.concat([users_df, new_u], ignore_index=True), USERS_FILE)
                st.success("Registration request sent to Musika.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"👤 **{st.session_state.user}**")
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
        cookie_manager.delete("inv_pro_user"); log_action("Logged out."); st.session_state.logged_in = False; st.rerun()

# --- PAGES ---
page = st.session_state.current_page

if page == "Dashboard":
    st.markdown("<h1>📊 Dashboard</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        f1, f2 = st.columns(2)
        all_dates = pd.to_datetime(st.session_state.sales["Date"])
        y_list = sorted(all_dates.dt.year.unique().tolist(), reverse=True) if not all_dates.empty else [date.today().year]
        s_y, s_m = f1.selectbox("Year", y_list), f2.selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=date.today().month-1)
    
    m_idx = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].index(s_m)+1
    fs = st.session_state.sales.copy(); fs["Date"] = pd.to_datetime(fs["Date"])
    if not fs.empty:
        fs = fs[(fs["Date"].dt.year == s_y) & (fs["Date"].dt.month == m_idx)]
    
    cash = (st.session_state.cash_in['Amount'].sum() + st.session_state.sales['Profit'].sum()) - st.session_state.expenditures['Cost'].sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Net Money", f"₱{cash:,.2f}"); m2.metric("Monthly Profit", f"₱{fs['Profit'].sum() if not fs.empty else 0:,.2f}")
    m3.metric("Monthly Revenue", f"₱{fs['Total'].sum() if not fs.empty else 0:,.2f}"); m4.metric("Unpaid Balance", f"₱{fs[fs['Payment'] == 'Unpaid']['Total'].sum() if not fs.empty else 0:,.2f}")
    
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.write("### 🚨 Stock Alerts")
        sdf = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
        alerts = sdf[sdf["Quantity"] < 5].sort_values("Quantity")
        st.dataframe(alerts, use_container_width=True, hide_index=True)
    with c2:
        st.write("### 🏆 Top Sellers")
        if not fs.empty: st.table(fs.groupby("Product")["Qty"].sum().sort_values(ascending=False).head(5))

    st.write("### 📈 Cash Flow Trend")
    p, d, e = st.session_state.sales[['Date', 'Profit']].rename(columns={'Profit': 'A'}), st.session_state.cash_in[['Date', 'Amount']].rename(columns={'Amount': 'A'}), st.session_state.expenditures[['Date', 'Cost']].rename(columns={'Cost': 'A'})
    e['A'] = -e['A']; t_df = pd.concat([p, d, e])
    if not t_df.empty:
        t_df['Date'] = pd.to_datetime(t_df['Date']); t_df = t_df.sort_values('Date').groupby('Date').sum().reset_index(); t_df['Cum'] = t_df['A'].cumsum()
        st.plotly_chart(px.line(t_df, x='Date', y='Cum', template="plotly_dark", markers=True), use_container_width=True)

elif page == "Database":
    st.markdown("<h1>📂 Database</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.write("### ➕ Add Tier")
        t1, t2 = st.columns([3, 1])
        nt = t1.text_input("Tier Name")
        if t2.button("Add"):
            db_df[nt] = 0.0; save_data(db_df, DB_FILE); log_action(f"Added Price Tier: {nt}"); st.rerun()
    with c2:
        st.write("### 🗑️ Remove Tier")
        d1, d2 = st.columns([3, 1])
        td = d1.selectbox("Select Tier", [""] + price_tiers_list)
        if d2.button("Delete"):
            if td: db_df = db_df.drop(columns=[td]); save_data(db_df, DB_FILE); log_action(f"Deleted Price Tier: {td}"); st.rerun()
    
    ed = st.data_editor(db_df, use_container_width=True, hide_index=True, num_rows="dynamic")
    if len(ed) < len(db_df):
        if st.session_state.user == "Musika": save_data(ed, DB_FILE); log_action("Admin deleted a product row."); st.rerun()
        else: st.warning("Staff cannot delete database rows."); st.rerun()
    elif not ed.equals(db_df): save_data(ed, DB_FILE); log_action("Updated Database entries."); st.rerun()

elif page == "Inventory":
    st.markdown("<h1>📦 Inventory Summary</h1>", unsafe_allow_html=True)
    cl, cr = st.columns([1, 2])
    with cl:
        st.write("### 📊 Quick Tally")
        sdf = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index().sort_values("Quantity")
        sdf["Status"] = sdf["Quantity"].apply(lambda q: "❌ Out" if q <= 0 else "⚠️ Low" if q < 5 else "✅ Good")
        st.dataframe(sdf, use_container_width=True, hide_index=True)
    with cr:
        st.write("### ⚙️ Add Stock Entry")
        f = st.columns([1.2, 1, 1, 1, 0.5])
        c_date, np, nq, ns = f[0].date_input("Date"), f[1].selectbox("Product", product_list), f[2].number_input("Qty", min_value=1), f[3].selectbox("Status", ["In Stock", "Bought"])
        if f[4].button("➕"):
            nr = pd.DataFrame({"Product Name": [np], "Quantity": [nq], "Status": [ns], "Date": [c_date]})
            st.session_state.stock = pd.concat([st.session_state.stock, nr], ignore_index=True); save_data(st.session_state.stock, STOCK_FILE); log_action(f"Stocked IN: {nq} of {np}"); st.rerun()
        ed_s = st.data_editor(st.session_state.stock.copy().iloc[::-1], use_container_width=True, num_rows="dynamic")
        if len(ed_s) < len(st.session_state.stock):
            if st.session_state.user == "Musika": save_data(ed_s.iloc[::-1], STOCK_FILE); log_action("Admin deleted stock entry."); st.rerun()
            else: st.warning("Staff delete blocked."); st.rerun()
        elif not ed_s.equals(st.session_state.stock.iloc[::-1]): save_data(ed_s.iloc[::-1], STOCK_FILE); log_action("Modified stock logs."); st.rerun()

elif page == "Sales":
    st.markdown("<h1>💰 Sales Tracker</h1>", unsafe_allow_html=True)
    conf = {"Product": st.column_config.SelectboxColumn(options=product_list), "Price Tier": st.column_config.SelectboxColumn(options=price_tiers_list)}
    
    # RE-IMPLEMENTED FULL AUTO-CALCULATION ENGINE
    cur_sales = st.session_state.sales[SALES_ORDER].copy()
    ed = st.data_editor(cur_sales, use_container_width=True, num_rows="dynamic", column_config=conf, key="sales_ed")
    
    if not ed.equals(cur_sales):
        ndf = ed.copy()
        for idx in ndf.index:
            row = ndf.loc[idx]
            if pd.notnull(row["Product"]) and pd.notnull(row["Price Tier"]):
                match = db_df[db_df["Product Name"] == row["Product"]]
                if not match.empty:
                    tier = str(row["Price Tier"])
                    u_c, b_c = float(match["Cost per Unit"].values[0]), float(match["Boxed Cost"].values[0])
                    p_t = float(match[tier].values[0]) if tier in match.columns else 0.0
                    qty, disc = float(row["Qty"] or 1), float(row["Discount"] or 0)
                    
                    # AUTO-FILL DATA
                    ndf.at[idx, "Cost"] = u_c
                    ndf.at[idx, "Boxed Cost"] = b_c
                    total_val = (p_t - disc) * qty
                    ndf.at[idx, "Total"] = total_val
                    ndf.at[idx, "Profit"] = total_val - (b_c * qty)
                    
                    # Deduct Stock
                    old_row = st.session_state.sales.iloc[idx] if idx < len(st.session_state.sales) else None
                    if row["Status"] == "Sold" and (old_row is None or old_row["Status"] != "Sold"):
                        s_df, needed = st.session_state.stock, int(qty)
                        mask = (s_df["Product Name"] == row["Product"]) & (s_df["Status"] == "In Stock") & (s_df["Quantity"] > 0)
                        for s_idx in s_df[mask].index:
                            if needed <= 0: break
                            take = min(needed, s_df.at[s_idx, "Quantity"])
                            s_df.at[s_idx, "Quantity"] -= take; needed -= take
                        save_data(s_df, STOCK_FILE); log_action(f"🟢 [SOLD] {int(qty)} of {row['Product']}")
        
        if len(ed) < len(st.session_state.sales):
            if st.session_state.user == "Musika": save_data(ndf, SALES_FILE); log_action("Admin deleted sale."); st.rerun()
            else: st.warning("Staff cannot delete sales records."); st.rerun()
        else:
            save_data(ndf, SALES_FILE); log_action("Updated sales entries."); st.rerun()

elif page == "Expenditures":
    st.markdown("<h1>💸 Expenditures & Deposits</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.write("### ➖ Log Expense")
        f_ex = st.columns([1.2, 1.5, 1, 0.4])
        ex_d, it, ct = f_ex[0].date_input("Date", key="ex_cal"), f_ex[1].text_input("Item", key="ex_it"), f_ex[2].number_input("Cost", min_value=0.0, key="ex_ct")
        if f_ex[3].button("➕", key="ex_btn"):
            new = pd.DataFrame({"Date": [ex_d], "Item": [it], "Cost": [ct]})
            st.session_state.expenditures = pd.concat([st.session_state.expenditures, new]); save_data(st.session_state.expenditures, EXPENSE_FILE); log_action(f"Expense: {it}"); st.rerun()
    with c2:
        st.write("### ➕ Log Deposit")
        f_in = st.columns([1.2, 1.5, 1, 0.4])
        in_d, src, amt = f_in[0].date_input("Date", key="in_cal"), f_in[1].text_input("Source", key="in_src"), f_in[2].number_input("Amt", min_value=0.0, key="in_amt")
        if f_in[3].button("➕", key="in_btn"):
            new = pd.DataFrame({"Date": [in_d], "Source": [src], "Amount": [amt]})
            st.session_state.cash_in = pd.concat([st.session_state.cash_in, new]); save_data(st.session_state.cash_in, CASH_FILE); log_action(f"Deposit: {src}"); st.rerun()
    
    st.write("---")
    l, r = st.columns(2)
    with l:
        st.write("### 📝 Expense History")
        v_ex = st.session_state.expenditures.copy().iloc[::-1]
        ed_ex = st.data_editor(v_ex, use_container_width=True, hide_index=True, num_rows="dynamic")
        if not ed_ex.equals(v_ex): save_data(ed_ex.iloc[::-1], EXPENSE_FILE); log_action("Updated Expenses History."); st.rerun()
    with r:
        st.write("### 📝 Deposit History")
        v_in = st.session_state.cash_in.copy().iloc[::-1]
        ed_in = st.data_editor(v_in, use_container_width=True, hide_index=True, num_rows="dynamic")
        if not ed_in.equals(v_in): save_data(ed_in.iloc[::-1], CASH_FILE); log_action("Updated Deposits History."); st.rerun()

elif page == "Admin" and st.session_state.role == "Admin":
    st.markdown("<h1>🛡️ Admin Approvals</h1>", unsafe_allow_html=True)
    pend_users = users_df[users_df['Status'] == "Pending"]
    for idx, row in pend_users.iterrows():
        c1, c2 = st.columns([3, 1]); c1.write(f"Account Request: **{row['Username']}**")
        if c2.button(f"Approve {row['Username']}"):
            users_df.at[idx, 'Status'] = "Approved"; save_data(users_df, USERS_FILE); log_action(f"Approved {row['Username']}"); st.rerun()

elif page == "Log":
    st.markdown("<h1>📜 Activity Log</h1>", unsafe_allow_html=True)
    st.dataframe(load_data(LOG_FILE, {}), use_container_width=True, hide_index=True)
    if st.session_state.role == "Admin" and st.button("🗑️ Clear Logs"):
        save_data(pd.DataFrame(columns=["Timestamp", "Identity", "Action Detail"]), LOG_FILE); log_action("Wiped logs."); st.rerun()
