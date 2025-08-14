import streamlit as st
import pandas as pd
import datetime as dt
from sqlalchemy import create_engine, Column, Integer, Float, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import IntegrityError

st.set_page_config(page_title="Trade Planner & Journal", layout="centered")

# ----- Database (SQLite local) -----
# NOTE: On Streamlit Cloud, files may reset when app sleeps.
# For persistent storage, later switch to a cloud DB (e.g., Supabase/Postgres).
DB_PATH = "sqlite:///trade_app.db"
engine = create_engine(DB_PATH, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Portfolio(Base):
    __tablename__ = "portfolios"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    balance = Column(Float, default=25000.0)
    leverage = Column(Integer, default=100)
    daily_loss_limit = Column(Float, default=1250.0)
    total_loss_limit = Column(Float, default=2500.0)
    risk_per_trade_usd = Column(Float, default=62.5)
    max_daily_risk_usd = Column(Float, default=500.0)
    created_at = Column(DateTime, default=pd.Timestamp.utcnow)
    trades = relationship("Trade", back_populates="portfolio", cascade="all, delete-orphan")

class Symbol(Base):
    __tablename__ = "symbols"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, unique=True, nullable=False)
    pip_size = Column(Float, nullable=False)
    pip_value_per_lot = Column(Float, nullable=False)
    contract_size = Column(Float, nullable=False)
    price = Column(Float, default=0.0)
    created_at = Column(DateTime, default=pd.Timestamp.utcnow)
    trades = relationship("Trade", back_populates="symbol_ref")

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True)
    date = Column(Date, default=dt.date.today)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    symbol_id = Column(Integer, ForeignKey("symbols.id"))
    side = Column(String)
    entry = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    exit = Column(Float, nullable=True)
    lots = Column(Float, default=1.0)
    pip_size = Column(Float)
    pip_value_per_lot = Column(Float)
    sl_pips = Column(Float)
    tp_pips = Column(Float)
    result_pips = Column(Float, nullable=True)
    pl_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, default=pd.Timestamp.utcnow)
    portfolio = relationship("Portfolio", back_populates="trades")
    symbol_ref = relationship("Symbol", back_populates="trades")

Base.metadata.create_all(engine)

def init_defaults():
    sess = SessionLocal()
    if not sess.query(Symbol).filter_by(symbol="XAUUSD").first():
        sess.add(Symbol(symbol="XAUUSD", pip_size=0.01, pip_value_per_lot=0.1, contract_size=100, price=2400))
    if not sess.query(Symbol).filter_by(symbol="BTCUSD").first():
        sess.add(Symbol(symbol="BTCUSD", pip_size=1.0, pip_value_per_lot=1.0, contract_size=1, price=60000))
    if not sess.query(Portfolio).filter_by(name="WeMaster 510zero 25k").first():
        sess.add(Portfolio(name="WeMaster 510zero 25k", balance=25000, leverage=100,
                           daily_loss_limit=1250, total_loss_limit=2500,
                           risk_per_trade_usd=62.5, max_daily_risk_usd=500))
    sess.commit(); sess.close()
init_defaults()

def get_df(rows):
    return pd.DataFrame(rows, columns=rows[0].keys() if rows else [])

def calc_lot(risk_usd, sl_pips, pip_value):
    if sl_pips and pip_value:
        return risk_usd / (sl_pips * pip_value)
    return 0.0

def est_margin(contract_size, price, lots, leverage):
    if not leverage: return 0.0
    return (contract_size * price * lots) / leverage

def calc_pips(entry, price, pip_size, side):
    if entry is None or price is None or not pip_size: return None
    move = (price - entry) / pip_size
    return move if side == "Buy" else -move

def compute_trade_fields(t, srow):
    t.pip_size = srow.pip_size
    t.pip_value_per_lot = srow.pip_value_per_lot
    t.sl_pips = abs((t.entry - t.sl) / srow.pip_size) if t.entry and t.sl else None
    t.tp_pips = abs((t.tp - t.entry) / srow.pip_size) if t.entry and t.tp else None
    if t.exit:
        t.result_pips = calc_pips(t.entry, t.exit, srow.pip_size, t.side)
        t.pl_usd = (t.result_pips or 0) * srow.pip_value_per_lot * (t.lots or 1.0)

st.title("📈 Trade Planner & Journal (Multi‑Portfolio)")

tab1, tab2, tab3, tab4 = st.tabs(["📐 Planner", "🧾 Trade Log", "📊 Dashboard", "⚙️ Settings"])

# -------- Planner --------
with tab1:
    sess = SessionLocal()
    plist = sess.query(Portfolio).order_by(Portfolio.id.desc()).all()
    slist = sess.query(Symbol).order_by(Symbol.symbol.asc()).all()
    p_choice = st.selectbox("เลือกพอร์ต", plist, format_func=lambda p: p.name if p else "-")
    s_choice = st.selectbox("สัญลักษณ์", slist, format_func=lambda s: s.symbol if s else "-")

    risk_usd = st.number_input("Risk ต่อไม้ ($)", value=float(p_choice.risk_per_trade_usd) if p_choice else 62.5, min_value=1.0, step=0.5)
    sl_pips = st.number_input("Stop Loss (pips)", value=625.0, min_value=1.0, step=1.0)
    pip_value = st.number_input("Pip Value/1 lot ($/pip)", value=float(s_choice.pip_value_per_lot) if s_choice else 0.1, min_value=0.0001, step=0.01, format="%.4f")
    lots = calc_lot(risk_usd, sl_pips, pip_value)
    st.metric("🎯 Lot Size", f"{lots:.3f} lots")
    margin = est_margin(s_choice.contract_size, s_choice.price, lots, p_choice.leverage if p_choice else 100)
    st.caption(f"ประมาณการ Margin: ~ ${margin:,.2f} (Contract×Price×Lots÷Leverage)")
    st.info("สูตร: Lot = Risk$ / (SLpips × PipValue); Margin ≈ Contract×Price×Lots÷Leverage")
    sess.close()

# -------- Trade Log --------
with tab2:
    sess = SessionLocal()
    plist = sess.query(Portfolio).order_by(Portfolio.id.desc()).all()
    slist = sess.query(Symbol).order_by(Symbol.symbol.asc()).all()
    p_choice = st.selectbox("เลือกพอร์ต", plist, index=0, format_func=lambda p: p.name if p else "-", key="p2")
    s_choice = st.selectbox("สัญลักษณ์", slist, index=0, format_func=lambda s: s.symbol if s else "-", key="s2")

    with st.form("trade_form", clear_on_submit=True):
        date = st.date_input("วันที่", value=dt.date.today())
        side = st.selectbox("ทิศทาง", ["Buy", "Sell"])
        lots_in = st.number_input("Lots", value=1.0, min_value=0.01, step=0.01)
        entry = st.number_input("Entry", value=0.0, step=0.01, format="%.2f")
        sl = st.number_input("SL", value=0.0, step=0.01, format="%.2f")
        tp = st.number_input("TP", value=0.0, step=0.01, format="%.2f")
        exitp = st.number_input("Exit (ใส่เมื่อปิดออเดอร์)", value=0.0, step=0.01, format="%.2f")
        submitted = st.form_submit_button("บันทึกเทรด")
        if submitted:
            t = Trade(date=date, portfolio_id=p_choice.id, symbol_id=s_choice.id, side=side,
                      lots=lots_in, entry=entry or None, sl=sl or None, tp=tp or None, exit=exitp or None)
            compute_trade_fields(t, s_choice)
            sess.add(t)
            sess.commit()
            st.success("บันทึกเทรดแล้ว ✅")

    q = sess.query(Trade.id, Trade.date, Trade.side, Trade.lots, Trade.entry, Trade.sl, Trade.tp, Trade.exit,
                   Trade.sl_pips, Trade.tp_pips, Trade.result_pips, Trade.pl_usd).filter(Trade.portfolio_id==p_choice.id).order_by(Trade.id.desc())
    df = get_df(q)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        dfd = df.groupby("date", as_index=False)["pl_usd"].sum().rename(columns={"pl_usd":"daily_pl"})
        st.bar_chart(dfd.set_index("date"))
    sess.close()

# -------- Dashboard --------
with tab3:
    sess = SessionLocal()
    plist = sess.query(Portfolio).order_by(Portfolio.id.desc()).all()
    p_choice = st.selectbox("เลือกพอร์ต", plist, index=0, format_func=lambda p: p.name if p else "-", key="p3")
    q = sess.query(Trade.date, Trade.pl_usd).filter(Trade.portfolio_id==p_choice.id)
    df = get_df(q)
    if df.empty:
        st.info("ยังไม่มีข้อมูลเทรด")
    else:
        total_pl = df["pl_usd"].sum(skipna=True)
        best = df["pl_usd"].max(skipna=True)
        worst = df["pl_usd"].min(skipna=True)
        c1,c2,c3 = st.columns(3)
        c1.metric("กำไรรวม (USD)", f"{total_pl:,.2f}")
        c2.metric("ไม้ดีที่สุด", f"{best:,.2f}")
        c3.metric("ไม้แย่ที่สุด", f"{worst:,.2f}")
        dfd = df.groupby("date", as_index=False)["pl_usd"].sum().rename(columns={"pl_usd":"daily_pl"})
        st.line_chart(dfd.set_index("date"))
    sess.close()

# -------- Settings --------
with tab4:
    sess = SessionLocal()
    st.subheader("พอร์ต")
    name = st.text_input("ชื่อพอร์ตใหม่")
    c1,c2,c3 = st.columns(3)
    balance = c1.number_input("Balance", value=25000.0, step=100.0)
    leverage = c2.number_input("Leverage", value=100, step=1)
    risk_trade = c3.number_input("Risk ต่อไม้ ($)", value=62.5, step=0.5)
    c4,c5,c6 = st.columns(3)
    max_daily = c4.number_input("Max Daily Risk ($)", value=500.0, step=10.0)
    dloss = c5.number_input("Daily Loss Limit ($)", value=1250.0, step=10.0)
    tloss = c6.number_input("Total Loss Limit ($)", value=2500.0, step=10.0)
    if st.button("บันทึกพอร์ต"):
        if name.strip():
            try:
                sess.add(Portfolio(name=name.strip(), balance=balance, leverage=int(leverage),
                                   risk_per_trade_usd=risk_trade, max_daily_risk_usd=max_daily,
                                   daily_loss_limit=dloss, total_loss_limit=tloss))
                sess.commit(); st.success("บันทึกพอร์ตแล้ว ✅")
            except IntegrityError:
                sess.rollback(); st.error("มีชื่อพอร์ตนี้อยู่แล้ว")

    st.markdown("---")
    st.subheader("สัญลักษณ์")
    syms = sess.query(Symbol).all()
    for s in syms:
        with st.expander(f"{s.symbol} | pip={s.pip_size} | pipVal={s.pip_value_per_lot} | contract={s.contract_size}"):
            new_price = st.number_input(f"{s.symbol} Spot/Mark Price", value=float(s.price), step=1.0, key=f"price_{s.id}")
            if st.button(f"อัปเดตราคา {s.symbol}", key=f"btn_{s.id}"):
                s.price = new_price; sess.commit(); st.success("อัปเดตราคาแล้ว ✅")

    st.markdown("---")
    st.caption("หมายเหตุ: สำหรับการเก็บข้อมูลถาวร แนะนำต่อฐานข้อมูลคลาวด์ (เช่น Supabase/Postgres) ในเวอร์ชันถัดไป.")
    sess.close()
