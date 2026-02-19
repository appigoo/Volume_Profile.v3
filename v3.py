import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide", page_title="Advanced Volume Profile VA")

st.title("⚖️ 市场价值区域分析 (Value Area 70%)")

with st.sidebar:
    st.header("配置")
    symbol = st.text_input("股票代码", value="NVDA")
    period = st.selectbox("时期", ["3mo", "6mo", "1y", "2y"], index=1)
    bins_count = st.slider("价格区间细分", 50, 200, 100)
    va_percent = st.slider("价值区域占比 (%)", 50, 90, 70) / 100.0

@st.cache_data
def load_stock_data(ticker, p):
    df = yf.download(ticker, period=p)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

try:
    df = load_stock_data(symbol, period)
    
    # 1. 计算成交量分布
    price_min, price_max = df['Low'].min(), df['High'].max()
    bins = np.linspace(price_min, price_max, bins_count)
    df['bin_mid'] = pd.cut(df['Close'], bins=bins, labels=bins[:-1] + np.diff(bins)/2)
    
    vp = df.groupby('bin_mid', observed=True)['Volume'].sum().reset_index()
    vp['bin_mid'] = vp['bin_mid'].astype(float)
    
    # 2. 计算 POC
    poc_idx = vp['Volume'].idxmax()
    poc_price = vp.loc[poc_idx, 'bin_mid']
    
    # 3. 计算 Value Area (VA)
    total_volume = vp['Volume'].sum()
    target_volume = total_volume * va_percent
    
    current_vol = vp.loc[poc_idx, 'Volume']
    up_idx = poc_idx
    down_idx = poc_idx
    
    # 迭代扩展直到达到目标成交量
    while current_vol < target_volume:
        vol_up = vp.loc[up_idx + 1, 'Volume'] if up_idx + 1 < len(vp) else 0
        vol_down = vp.loc[down_idx - 1, 'Volume'] if down_idx - 1 >= 0 else 0
        
        if vol_up == 0 and vol_down == 0: break
            
        if vol_up >= vol_down:
            current_vol += vol_up
            up_idx += 1
        else:
            current_vol += vol_down
            down_idx -= 1
            
    vah = vp.loc[up_idx, 'bin_mid']
    val = vp.loc[down_idx, 'bin_mid']

    # --- 绘图 ---
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, column_widths=[0.7, 0.3], horizontal_spacing=0.03)

    # K线
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K线"), row=1, col=1)

    # 绘制 VA 区域带
    fig.add_hrect(y0=val, y1=vah, fillcolor="rgba(255, 255, 255, 0.05)", line_width=0, row=1, col=1)
    
    # 绘制 POC/VAH/VAL 线
    for price, color, name in [(poc_price, "Gold", "POC"), (vah, "Cyan", "VAH"), (val, "Magenta", "VAL")]:
        fig.add_shape(type="line", x0=df.index[0], x1=df.index[-1], y0=price, y1=price, 
                      line=dict(color=color, width=1.5, dash="dash"), row=1, col=1)

    # 筹码分布图颜色区分
    vp['color'] = 'rgba(100, 149, 237, 0.2)'  # 默认淡色
    vp.loc[down_idx:up_idx, 'color'] = 'rgba(100, 149, 237, 0.7)' # 价值区域深色
    vp.iloc[poc_idx:poc_idx+1, 2] = 'Gold' # POC 金色

    fig.add_trace(go.Bar(x=vp['Volume'], y=vp['bin_mid'], orientation='h', marker_color=vp['color'], name="成交量分布"), row=1, col=2)

    fig.update_layout(template="plotly_dark", height=800, showlegend=False, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # 数据面板
    cols = st.columns(4)
    cols[0].metric("VAH (上限)", f"${vah:.2f}")
    cols[1].metric("POC (核心)", f"${poc_price:.2f}")
    cols[2].metric("VAL (下限)", f"${val:.2f}")
    cols[3].metric("当前状态", "区间内" if val <= df['Close'].iloc[-1] <= vah else "区间外")

except Exception as e:
    st.error(f"分析出错: {e}")
