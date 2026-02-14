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
    import plotly.graph_objects as go
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

# --- DYNAMIC CSS ---
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

def log_action(action_detail):
    u_name, u_role = st.session_state.get('user', 'Unknown'), st.session_state.get('role', 'System')
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    new_log = pd.DataFrame({"Timestamp": [now], "Identity": [f"{u_name} ({u_role})"], "Action Detail": [action_detail]})
    log_df = pd.concat([new_log, load_data(LOG_FILE, {"Timestamp":[], "Identity":[], "Action Detail":[]})], ignore_index=True)
    save_data(log_df, LOG_FILE)

def request_deletion(df_row, source_page):
    approvals = load_data(APPROVAL_FILE, {"Request Date": [], "User": [], "Page": [], "Details": [], "RawData": []})
    row_str = " | ".join([f"{k}:{v}" for k, v in df_row.to_dict().items()])
    new_req = pd.DataFrame({
        "Request Date": [datetime.now().strftime("%Y-%m-%d %I:%M %p")],
        "User": [st.session_state.user],
        "Page": [source_page],
        "Details": [row_str],
        "RawData": [df_row.to_json()]
    })
    save_data(pd.concat([approvals, new_req], ignore_index=True), APPROVAL_FILE)
    log_action(f"Requested deletion of row from {source_page}: {row_str}")

# --- INITIALIZATION ---
users_df = load_data(USERS_FILE, {"Username": ["Musika"], "Password": [make_hashes("Iameternal11!")], "Role": ["Admin"], "Status": ["Approved"]})
db_df = load_data(DB_FILE, {"Product Name": ["Item 1"], "Cost per Unit": [0.0], "Boxed Cost": [0.0]})
st.session_state.inventory = db_df
st.session_state.stock = load_data(STOCK_FILE, {"Product Name": ["Item 1"], "Quantity": [0], "Status": ["In Stock"], "Date": [date.today()]})
if 'sales' not in st.session_state:
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
                st.success("Request sent to Musika.")
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
        if st.button("🛡️ Admin Page"): st.session_state.current_page = "Admin"
    st.write("---")
    if st.button("🚪 Logout"): 
        cookie_manager.delete("inv_pro_user"); log_action("Logged out."); st.session_state.logged_in = False; st.rerun()

page = st.session_state.current_page

if page == "Dashboard":
    st.markdown("<h1>📊 Dashboard</h1>", unsafe_allow_html=True)
    with st.container(border=True):
        f1, f2 = st.columns(2)
        dash_sales = st.session_state.sales.copy()
        dash_sales["Date"] = pd.to_datetime(dash_sales["Date"], errors='coerce')
        y_list = sorted(dash_sales["Date"].dt.year.dropna().unique().tolist(), reverse=True)
        if not y_list: y_list = [date.today().year]
        s_y = f1.selectbox("Year", y_list)
        s_m = f2.selectbox("Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], index=date.today().month-1)
    
    m_idx = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].index(s_m)+1
    
    # Filtered Monthly Data
    fs_monthly = dash_sales[(dash_sales["Date"].dt.year == s_y) & (dash_sales["Date"].dt.month == m_idx)]
    paid_monthly = fs_monthly[fs_monthly['Payment'] == 'Paid']
    
    # Monthly Expenditures
    exp_df = st.session_state.expenditures.copy()
    exp_df["Date"] = pd.to_datetime(exp_df["Date"], errors='coerce')
    monthly_exp_val = exp_df[(exp_df["Date"].dt.year == s_y) & (exp_df["Date"].dt.month == m_idx)]['Cost'].sum()
    
    # Advanced Calculations
    rev = paid_monthly['Total'].sum()
    prof = paid_monthly['Profit'].sum()
    margin = (prof / rev * 100) if rev > 0 else 0
    exp_ratio = (monthly_exp_val / rev * 100) if rev > 0 else 0

    # Metric Row
    m1, m2, m3, m4 = st.columns(4)
    total_paid_profit = dash_sales[dash_sales['Payment'] == 'Paid']['Profit'].sum()
    net_cash = (st.session_state.cash_in['Amount'].sum() + total_paid_profit) - st.session_state.expenditures['Cost'].sum()
    
    m1.metric("Total Net Money", f"₱{net_cash:,.2f}")
    m2.metric("Monthly Paid Profit", f"₱{prof:,.2f}")
    m3.metric("Profit Margin %", f"{margin:.1f}%")
    m4.metric("Expense Ratio", f"{exp_ratio:.1f}%")

    # --- GRAPHS SECTION ---
    st.write("---")
    g1, g2 = st.columns(2)

    with g1:
        st.write("### ⚖️ Profit vs. Expenses")
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=[s_m], y=[prof], name='Paid Profit', marker_color='#2ecc71'))
        fig_comp.add_trace(go.Bar(x=[s_m], y=[monthly_exp_val], name='Expenses', marker_color='#e74c3c'))
        fig_comp.update_layout(barmode='group', template="plotly_dark", height=300, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_comp, use_container_width=True)

    with g2:
        st.write("### 📈 Margin by Product")
        if not paid_monthly.empty:
            prod_stats = paid_monthly.groupby("Product").agg({"Total":"sum", "Profit":"sum"}).reset_index()
            prod_stats["Margin %"] = (prod_stats["Profit"] / prod_stats["Total"] * 100)
            fig_margin = px.bar(prod_stats.sort_values("Margin %"), x="Margin %", y="Product", orientation='h', 
                                template="plotly_dark", color="Margin %", color_continuous_scale="Viridis")
            fig_margin.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_margin, use_container_width=True)
        else:
            st.info("No paid sales data for this month to show margins.")

    

    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.write("### 🚨 Stock Alerts")
        sdf = st.session_state.stock[st.session_state.stock["Status"] == "In Stock"].groupby("Product Name")["Quantity"].sum().reset_index()
        alerts = sdf[sdf["Quantity"] < 5].sort_values("Quantity")
        st.dataframe(alerts, use_container_width=True, hide_index=True)
    with c2:
        st.write("### 🏆 Top Sellers (Paid)")
        if not paid_monthly.empty: 
            st.table(paid_monthly.groupby("Product")["Qty"].sum().sort_values(ascending=False).head(5))

elif page == "Database":
    st.markdown("<h1>📂 Database</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.write("### ➕ Add Price Tier")
        t1, t2 = st.columns([3, 1])
        nt = t1.text_input("Tier Name")
        if t2.button("Add"):
            db_df[nt] = 0.0; save_data(db_df, DB_FILE); log_action(f"Added Price Tier: '{nt}'"); st.rerun()
    with c2:
        st.write("### 🗑️ Remove Price Tier")
        d1, d2 = st.columns([3, 1])
        td = d1.selectbox("Select Tier", [""] + price_tiers_list)
        if d2.button("Delete"):
            if td: db_df = db_df.drop(columns=[td]); save_data(db_df, DB_FILE); log_action(f"Deleted Price Tier: '{td}'"); st.rerun()
    
    ed = st.data_editor(db_df, use_container_width=True, hide_index=True, num_rows="dynamic")
    if len(ed) < len(db_df):
        removed_mask = ~db_df.index.isin(ed.index)
        removed_row = db_df[removed_mask].iloc[0]
        if st.session_state.role == "Admin":
            save_data(ed, DB_FILE); log_action(f"Admin deleted Product: {removed_row['Product Name']}"); st.rerun()
        else:
            request_deletion(removed_row, "Database")
            st.error("Deletion sent for Admin approval."); st.rerun()
    elif not ed.equals(db_df):
        save_data(ed, DB_FILE); log_action("Modified Database entries."); st.rerun()

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
        if f[4].button("➕", key="inv_add_btn"):
            nr = pd.DataFrame({"Product Name": [np], "Quantity": [nq], "Status": [ns], "Date": [c_date]})
            st.session_state.stock = pd.concat([st.session_state.stock, nr], ignore_index=True); save_data(st.session_state.stock, STOCK_FILE)
            log_action(f"Stocked: {nq} of '{np}'"); st.rerun()
        
        ed_s = st.data_editor(st.session_state.stock.copy().iloc[::-1], use_container_width=True, hide_index=True, num_rows="dynamic")
        if len(ed_s) < len(st.session_state.stock):
            removed_mask = ~st.session_state.stock.iloc[::-1].index.isin(ed_s.index)
            removed_row = st.session_state.stock.iloc[::-1][removed_mask].iloc[0]
            if st.session_state.role == "Admin":
                save_data(ed_s.iloc[::-1], STOCK_FILE); log_action("Admin deleted a stock entry."); st.rerun()
            else:
                request_deletion(removed_row, "Inventory")
                st.error("Deletion requested."); st.rerun()
        elif not ed_s.equals(st.session_state.stock.iloc[::-1]):
            save_data(ed_s.iloc[::-1], STOCK_FILE); log_action("Modified stock logs."); st.rerun()

elif page == "Sales":
    st.markdown("<h1>💰 Sales Tracker</h1>", unsafe_allow_html=True)
    conf = {
        "Date": st.column_config.DateColumn("Date", default=date.today(), required=True),
        "Customer": st.column_config.TextColumn("Customer"),
        "Product": st.column_config.SelectboxColumn("Product", options=product_list),
        "Price Tier": st.column_config.SelectboxColumn("Price Tier", options=price_tiers_list),
        "Status": st.column_config.SelectboxColumn("Status", options=["Pending", "Sold", "Cancelled"]),
        "Payment": st.column_config.SelectboxColumn("Payment", options=["Unpaid", "Paid"]),
        "Cost": st.column_config.NumberColumn("Cost", disabled=True, format="₱%.2f"),
        "Boxed Cost": st.column_config.NumberColumn("Boxed Cost", disabled=True, format="₱%.2f"),
        "Profit": st.column_config.NumberColumn("Profit", disabled=True, format="₱%.2f"),
        "Total": st.column_config.NumberColumn("Total", disabled=True, format="₱%.2f")
    }
    sales_df = st.session_state.sales[SALES_ORDER].copy()
    for col in ["Customer", "Product", "Price Tier", "Status", "Payment"]:
        sales_df[col] = sales_df[col].astype(str).replace(['nan', 'None', ''], '')
    for col in ["Qty", "Discount", "Cost", "Boxed Cost", "Profit", "Total"]:
        sales_df[col] = pd.to_numeric(sales_df[col], errors='coerce').fillna(0.0)
    
    ed = st.data_editor(sales_df, use_container_width=True, hide_index=True, num_rows="dynamic", column_config=conf, key="sales_v13")
    if not ed.equals(sales_df):
        ndf = ed.copy()
        needs_rerun = False
        if len(ed) < len(st.session_state.sales):
            removed_mask = ~sales_df.index.isin(ed.index)
            removed_row = sales_df[removed_mask].iloc[0]
            if st.session_state.role == "Admin":
                save_data(ndf, SALES_FILE); st.session_state.sales = ndf; log_action("Admin deleted sales record."); st.rerun()
            else:
                request_deletion(removed_row, "Sales")
                st.error("Admin approval required for deletion."); st.rerun()

        for idx in ndf.index:
            row = ndf.loc[idx]
            old_row = st.session_state.sales.loc[idx] if idx in st.session_state.sales.index else None
            prod, tier = row["Product"], row["Price Tier"]
            if prod and tier:
                match = db_df[db_df["Product Name"] == prod]
                if not match.empty:
                    u_cost, b_cost = float(match["Cost per Unit"].values[0]), float(match["Boxed Cost"].values[0])
                    unit_price = float(match[tier].values[0]) if str(tier) in match.columns else 0.0
                    qty, disc = float(row["Qty"]) if row["Qty"] != 0 else 1.0, float(row["Discount"])
                    calc_total, calc_profit = (unit_price - disc) * qty, ((unit_price - disc) * qty) - (b_cost * qty)
                    if row["Total"] != calc_total or row["Profit"] != calc_profit:
                        ndf.at[idx, "Cost"], ndf.at[idx, "Boxed Cost"], ndf.at[idx, "Total"], ndf.at[idx, "Profit"] = u_cost, b_cost, calc_total, calc_profit
                        needs_rerun = True

            if old_row is None or any(row[c] != old_row[c] for c in ["Product", "Price Tier", "Qty", "Status", "Payment", "Customer"]):
                log_action(f"Sale: {row['Customer']} | {row['Product']} | {row['Status']} | ₱{ndf.at[idx, 'Total']:,.2f}")
                needs_rerun = True

            if old_row is not None and row["Status"] == "Sold" and old_row["Status"] != "Sold":
                s_df = st.session_state.stock.copy()
                needed = int(row["Qty"])
                mask = (s_df["Product Name"] == prod) & (s_df["Status"] == "In Stock") & (s_df["Quantity"] > 0)
                available = s_df[mask].index
                if s_df.loc[available, "Quantity"].sum() >= needed:
                    for s_idx in available:
                        if needed <= 0: break
                        take = min(needed, s_df.at[s_idx, "Quantity"])
                        s_df.at[s_idx, "Quantity"] -= take; needed -= take
                    st.session_state.stock = s_df; save_data(s_df, STOCK_FILE)
                    log_action(f"AUTO-STOCK: -{row['Qty']} {prod}"); needs_rerun = True
                else: st.error(f"Low Stock: {prod}")
        save_data(ndf, SALES_FILE); st.session_state.sales = ndf
        if needs_rerun: st.rerun()

elif page == "Expenditures":
    st.markdown("<h1>💸 Expenditures</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.write("### ➖ Log Expense")
        f_ex = st.columns([1.2, 1.5, 1, 0.4])
        ex_d, it, ct = f_ex[0].date_input("Date", key="exd"), f_ex[1].text_input("Item", key="exit"), f_ex[2].number_input("Cost", min_value=0.0, key="exct")
        if f_ex[3].button("➕", key="ex_add_btn"):
            new = pd.DataFrame({"Date": [ex_d], "Item": [it], "Cost": [ct]})
            st.session_state.expenditures = pd.concat([st.session_state.expenditures, new]); save_data(st.session_state.expenditures, EXPENSE_FILE); log_action(f"Expense: {it}"); st.rerun()
    with c2:
        st.write("### ➕ Log Deposit")
        f_in = st.columns([1.2, 1.5, 1, 0.4])
        in_d, src, amt = f_in[0].date_input("Date", key="ind"), f_in[1].text_input("Source", key="insrc"), f_in[2].number_input("Amt", min_value=0.0, key="inamt")
        if f_in[3].button("➕", key="dep_add_btn"):
            new = pd.DataFrame({"Date": [in_d], "Source": [src], "Amount": [amt]})
            st.session_state.cash_in = pd.concat([st.session_state.cash_in, new]); save_data(st.session_state.cash_in, CASH_FILE); log_action(f"Deposit: {src}"); st.rerun()
    st.write("---")
    l, r = st.columns(2)
    with l:
        st.write("### 📝 Expense History")
        v_ex = st.session_state.expenditures.copy().iloc[::-1]
        ed_ex = st.data_editor(v_ex, use_container_width=True, hide_index=True, num_rows="dynamic")
        if len(ed_ex) < len(v_ex):
            removed_mask = ~v_ex.index.isin(ed_ex.index)
            removed_row = v_ex[removed_mask].iloc[0]
            if st.session_state.role == "Admin":
                save_data(ed_ex.iloc[::-1], EXPENSE_FILE); st.rerun()
            else:
                request_deletion(removed_row, "Expenditures (Expense)")
                st.error("Request sent."); st.rerun()
        elif not ed_ex.equals(v_ex): save_data(ed_ex.iloc[::-1], EXPENSE_FILE); st.rerun()
    with r:
        st.write("### 📝 Deposit History")
        v_in = st.session_state.cash_in.copy().iloc[::-1]
        ed_in = st.data_editor(v_in, use_container_width=True, hide_index=True, num_rows="dynamic")
        if len(ed_in) < len(v_in):
            removed_mask = ~v_in.index.isin(ed_in.index)
            removed_row = v_in[removed_mask].iloc[0]
            if st.session_state.role == "Admin":
                save_data(ed_in.iloc[::-1], CASH_FILE); st.rerun()
            else:
                request_deletion(removed_row, "Expenditures (Deposit)")
                st.error("Request sent."); st.rerun()
        elif not ed_in.equals(v_in): save_data(ed_in.iloc[::-1], CASH_FILE); st.rerun()

elif page == "Admin" and st.session_state.role == "Admin":
    st.markdown("<h1>🛡️ Admin Control Panel</h1>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["User Requests", "User Management (Roles)", "Pending Deletions"])
    
    with t1:
        st.write("### 📩 Access Requests")
        pend = users_df[users_df['Status'] == "Pending"]
        if pend.empty: st.info("No pending requests.")
        for idx, row in pend.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"User: **{row['Username']}**")
                if c2.button(f"Approve", key=f"app_{row['Username']}"):
                    users_df.at[idx, 'Status'] = "Approved"; save_data(users_df, USERS_FILE); log_action(f"Approved {row['Username']}"); st.rerun()
                if c3.button(f"Reject", key=f"rej_{row['Username']}"):
                    users_df = users_df.drop(idx); save_data(users_df, USERS_FILE); log_action(f"Rejected {row['Username']}"); st.rerun()

    with t2:
        st.write("### 👥 Manage User Roles")
        approved_users = users_df[users_df['Status'] == "Approved"]
        for idx, row in approved_users.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([2, 2])
                c1.write(f"User: **{row['Username']}**")
                new_role = c2.selectbox("Assign Role", ["Staff", "Admin"], index=0 if row['Role'] == "Staff" else 1, key=f"role_{row['Username']}")
                if new_role != row['Role']:
                    users_df.at[idx, 'Role'] = new_role
                    save_data(users_df, USERS_FILE)
                    log_action(f"Role Changed: {row['Username']} is now {new_role}")
                    st.rerun()

    with t3:
        st.write("### ⚠️ Deletion Requests")
        del_reqs = load_data(APPROVAL_FILE, {"Request Date": [], "User": [], "Page": [], "Details": [], "RawData": []})
        if del_reqs.empty: st.info("No deletions pending.")
        for idx, row in del_reqs.iterrows():
            with st.container(border=True):
                st.write(f"**From {row['Page']}** | Requested by {row['User']} on {row['Request Date']}")
                st.code(row['Details'])
                c1, c2 = st.columns(2)
                if c1.button("Confirm Deletion", key=f"conf_del_{idx}"):
                    del_reqs = del_reqs.drop(idx); save_data(del_reqs, APPROVAL_FILE)
                    log_action(f"Admin confirmed deletion request from {row['Page']}"); st.rerun()
                if c2.button("Restore / Reject Deletion", key=f"rest_{idx}"):
                    del_reqs = del_reqs.drop(idx); save_data(del_reqs, APPROVAL_FILE)
                    log_action(f"Admin rejected deletion request."); st.rerun()

elif page == "Log":
    st.markdown("<h1>📜 Activity Log</h1>", unsafe_allow_html=True)
    st.dataframe(load_data(LOG_FILE, {}), use_container_width=True, hide_index=True, column_config={"Identity": st.column_config.TextColumn("User", width="small"), "Action Detail": st.column_config.TextColumn("Details", width="large")})
    if st.session_state.role == "Admin" and st.button("🗑️ Clear Logs"):
        save_data(pd.DataFrame(columns=["Timestamp", "Identity", "Action Detail"]), LOG_FILE); log_action("Logs Cleared."); st.rerun()
