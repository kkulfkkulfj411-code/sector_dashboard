# -*- coding: utf-8 -*-
"""
東証セクター資金流動・ローテーション監視ダッシュボード (RRG軸 対TOPIX明記版)
"""

import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

# ページ設定（スマホ閲覧に最適化）
st.set_page_config(
    page_title="セクター資金流動ダッシュボード",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

BENCHMARK_TOPIX_CODE = "1306"
BENCHMARK_GROWTH_CODE = "2516"

TOPIX17_ETFS = [
    ("1617", "食品(17業種)", "#38B000"),
    ("1618", "エネルギー資源(17業種)", "#E76F51"),
    ("1619", "建設・資材(17業種)", "#F4A261"),
    ("1620", "素材・化学(17業種)", "#2A9D8F"),
    ("1621", "医薬品(17業種)", "#52B788"),
    ("1622", "自動車・輸送機(17業種)", "#3A86FF"),
    ("1623", "鉄鋼・非鉄(17業種)", "#457B9D"),
    ("1624", "機械(17業種)", "#1D3557"),
    ("1625", "電機・精密(17業種)", "#E63946"),
    ("1626", "情報通信・サービス他(17業種)", "#8338EC"),
    ("1627", "電力・ガス(17業種)", "#FB8500"),
    ("1628", "運輸・物流(17業種)", "#6D597A"),
    ("1629", "商社・卸売(17業種)", "#0077B6"),
    ("1630", "小売(17業種)", "#80B918"),
    ("1631", "銀行(17業種)", "#D97706"),
    ("1632", "金融(除く銀行)(17業種)", "#CA6702"),
    ("1633", "不動産(17業種)", "#BB3E03"),
]

MACRO6_GROUPS = {
    "①電機・精密・情報通信": [("1625", "電機・精密"), ("1626", "情報通信・サービス")],
    "②機械・自動車・輸送機": [("1624", "機械"), ("1622", "自動車・輸送機")],
    "③銀行・金融・不動産": [("1631", "銀行"), ("1632", "金融(除銀)"), ("1633", "不動産")],
    "④商社・資源・鉄鋼・化学": [("1629", "商社・卸売"), ("1618", "エネルギー資源"), ("1623", "鉄鋼・非鉄"), ("1620", "素材・化学")],
    "⑤建設・電力・運輸インフラ": [("1619", "建設・資材"), ("1627", "電力・ガス"), ("1628", "運輸・物流")],
    "⑥小売・食品・医薬ディフェンシブ": [("1630", "小売"), ("1617", "食品"), ("1621", "医薬品")],
}

@st.cache_data(ttl=3600)
def fetch_data():
    codes = [BENCHMARK_TOPIX_CODE, BENCHMARK_GROWTH_CODE] + [c for c, _, _ in TOPIX17_ETFS]
    yf_tickers = [f"{c}.T" for c in codes]
    end_dt = datetime.date.today() + datetime.timedelta(days=1)
    start_dt = end_dt - datetime.timedelta(days=160)
    
    raw = yf.download(yf_tickers, start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"), auto_adjust=True, progress=False, threads=True)
    if raw.empty:
        raise RuntimeError("株価データの取得に失敗しました。")
    
    closes = raw["Close"].copy()
    volumes = raw["Volume"].copy()
    closes.columns = [str(col).replace(".T", "") for col in closes.columns]
    volumes.columns = [str(col).replace(".T", "") for col in volumes.columns]
    closes = closes.dropna(how="all").ffill()
    volumes = volumes.loc[closes.index].fillna(0)
    return closes, volumes

# サイドバー設定
st.sidebar.title("🎛️ 表示設定")
mode = st.sidebar.selectbox(
    "集計モード選択",
    ["topix_macro6", "topix17_etf"],
    index=0,
    format_func=lambda x: "★東証全体・6大マクロ業種 (スマホ閲覧に最適)" if x=="topix_macro6" else "東証17業種ETF個別 (詳細)"
)
window_days = st.sidebar.slider("表示期間 (営業日)", 20, 100, 60, 10)
trail_len = st.sidebar.slider("RRG軌跡日数", 3, 15, 5, 1)

st.title("📊 東証セクター資金流動・ローテーション分析")
st.markdown("市場全体の資金がどのセクターへ流入・流出しているかをリアルタイムに可視化（対TOPIX基準）。")

with st.spinner("最新データを取得・計算中..."):
    closes, volumes = fetch_data()
    daily_ret = closes.pct_change() * 100.0
    
    for col in daily_ret.columns:
        if daily_ret[col].abs().max() > 15.0:
            daily_ret.loc[daily_ret[col].abs() > 15.0, col] = 0.0

    trading_val = closes * volumes
    tv_ma20 = trading_val.rolling(20, min_periods=5).mean()
    rvol_df = (trading_val / tv_ma20.replace(0, np.nan)).clip(upper=10.0)

    if mode == "topix_macro6":
        sec_members = {gname: [item for item in glist] for gname, glist in MACRO6_GROUPS.items()}
        colors = {gname: plt_col for gname, plt_col in zip(MACRO6_GROUPS.keys(), ["#E63946", "#1D3557", "#D97706", "#3A86FF", "#E76F51", "#38B000"])}
    else:
        sec_members = {name: [(code, name)] for code, name, _ in TOPIX17_ETFS}
        colors = {name: col for _, name, col in TOPIX17_ETFS}

    sector_list = list(sec_members.keys())
    sec_daily_med = pd.DataFrame(index=closes.index)
    sec_rvol_med = pd.DataFrame(index=closes.index)

    for sec in sector_list:
        valid_codes = [c for c, _ in sec_members[sec] if c in daily_ret.columns]
        if valid_codes:
            sec_daily_med[sec] = daily_ret[valid_codes].median(axis=1)
            sec_rvol_med[sec] = rvol_df[valid_codes].median(axis=1)
        else:
            sec_daily_med[sec] = 0.0
            sec_rvol_med[sec] = 1.0

    actual_win = min(window_days, len(sec_daily_med))
    plot_ret = sec_daily_med.iloc[-actual_win:].fillna(0.0)
    cum_ret = plot_ret.cumsum()
    cum_ret = cum_ret.sub(cum_ret.iloc[0])

    topix_daily = daily_ret[BENCHMARK_TOPIX_CODE].fillna(0.0) if BENCHMARK_TOPIX_CODE in daily_ret.columns else sec_daily_med.mean(axis=1)
    topix_plot = topix_daily.iloc[-actual_win:].cumsum()
    topix_plot = topix_plot - topix_plot.iloc[0]

    full_cum = sec_daily_med.fillna(0.0).cumsum()
    full_topix = topix_daily.cumsum()
    rel_cum = full_cum.sub(full_topix, axis=0)

    r5_rel = rel_cum.diff(5)
    r20_rel = rel_cum.diff(20)
    std_r20 = max(float(r20_rel.iloc[-actual_win:].std().mean()), 0.8)
    std_mom = max(float((r5_rel * 2.5 - r20_rel).iloc[-actual_win:].std().mean()), 0.8)

    rs_x, rs_y = {}, {}
    for sec in sector_list:
        x_series = 100.0 + (r20_rel[sec].iloc[-trail_len:] / std_r20) * 4.0
        y_series = 100.0 + ((r5_rel[sec].iloc[-trail_len:] * 2.5 - r20_rel[sec].iloc[-trail_len:]) / std_mom) * 4.0
        rs_x[sec] = x_series.fillna(100.0).round(2).tolist()
        rs_y[sec] = y_series.fillna(100.0).round(2).tolist()

    ret_5d = {sec: round(float(full_cum[sec].iloc[-1] - full_cum[sec].iloc[-min(6, len(full_cum))]), 2) for sec in sector_list}
    ret_20d = {sec: round(float(full_cum[sec].iloc[-1] - full_cum[sec].iloc[-min(21, len(full_cum))]), 2) for sec in sector_list}
    ret_60d = {sec: round(float(cum_ret[sec].iloc[-1]), 2) for sec in sector_list}
    latest_rvol = {sec: round(float(sec_rvol_med[sec].iloc[-3:].mean()), 2) for sec in sector_list}

# --- ① RRGグラフ（軸タイトルに対TOPIX比較を明記） ---
st.subheader("① 資金ローテーション軌跡 (RRG)")

with st.expander("📖 RRGグラフの見方（4エリアの意味）", expanded=False):
    st.markdown("""
    - 🟢 **右上【主導 (Leading)】**：TOPIXより強く、短期の資金流入も加速している本命セクター（順張り・強気）。
    - 🔵 **左上【改善 (Improving)】**：中期的にはまだTOPIXに劣るが、直近で初動の資金が流入し始めているセクター（底値圏・初動）。
    - 🟡 **右下【失速 (Weakening)】**：中期的にはTOPIXより強いが、直近の資金流入が減速し利確売り等に押されている状態。
    - 🔴 **左下【遅行 (Lagging)】**：TOPIXより弱く、資金が流出している状態（避けるべきセクター）。
    """)

fig_rrg = go.Figure()

fig_rrg.add_shape(type="rect", x0=100, x1=125, y0=100, y1=125, fillcolor="#E8F5E9", opacity=0.35, line_width=0)
fig_rrg.add_shape(type="rect", x0=100, x1=125, y0=75, y1=100, fillcolor="#FFF8E1", opacity=0.4, line_width=0)
fig_rrg.add_shape(type="rect", x0=75, x1=100, y0=75, y1=100, fillcolor="#FFEBEE", opacity=0.35, line_width=0)
fig_rrg.add_shape(type="rect", x0=75, x1=100, y0=100, y1=125, fillcolor="#E3F2FD", opacity=0.35, line_width=0)

fig_rrg.add_hline(y=100, line_dash="dash", line_color="gray")
fig_rrg.add_vline(x=100, line_dash="dash", line_color="gray")

for sec in sector_list:
    xs, ys = rs_x[sec], rs_y[sec]
    c = colors.get(sec, "#333")
    vr = latest_rvol[sec]
    short_label = sec[:2] if mode == "topix_macro6" else sec
    
    fig_rrg.add_trace(go.Scatter(
        x=xs, y=ys, mode="lines+markers", name=sec,
        line=dict(color=c, width=2.5), marker=dict(size=6, color=c),
        hovertemplate=f"<b>{sec}</b><br>対TOPIXトレンド(X): %{{x}}<br>短期モメンタム(Y): %{{y}}<extra></extra>"
    ))
    fig_rrg.add_trace(go.Scatter(
        x=[xs[-1]], y=[ys[-1]], mode="markers+text",
        text=[f"{short_label} ({vr}x)"], textposition="top center",
        marker=dict(size=max(vr * 14, 12), color=c, line=dict(color="white", width=2)),
        showlegend=False, hovertemplate=f"<b>{sec} (最新)</b><br>代金倍率: {vr}倍<br>5日騰落: {ret_5d[sec]}%<extra></extra>"
    ))

fig_rrg.update_layout(
    xaxis_title="中期相対トレンド (対TOPIX RS-Ratio: 100=TOPIXと同等)",
    yaxis_title="短期資金モメンタム (対TOPIX RS-Momentum)",
    height=500, 
    margin=dict(t=20, l=10, r=10, b=20),
    legend=dict(orientation="h", y=-0.28, font=dict(size=11)),
    annotations=[
        dict(x=0.98, y=0.98, xref="paper", yref="paper", text="<b>【主導 Leading】</b>", showarrow=False, xanchor="right", yanchor="top", font=dict(size=11, color="#1B5E20"), bgcolor="rgba(232, 245, 233, 0.85)", borderpad=3),
        dict(x=0.02, y=0.98, xref="paper", yref="paper", text="<b>【改善 Improving】</b>", showarrow=False, xanchor="left", yanchor="top", font=dict(size=11, color="#0D47A1"), bgcolor="rgba(227, 242, 253, 0.85)", borderpad=3),
        dict(x=0.98, y=0.02, xref="paper", yref="paper", text="<b>【失速 Weakening】</b>", showarrow=False, xanchor="right", yanchor="bottom", font=dict(size=11, color="#E65100"), bgcolor="rgba(255, 248, 225, 0.85)", borderpad=3),
        dict(x=0.02, y=0.02, xref="paper", yref="paper", text="<b>【遅行 Lagging】</b>", showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=11, color="#B71C1C"), bgcolor="rgba(255, 235, 235, 0.85)", borderpad=3),
    ]
)
st.plotly_chart(fig_rrg, use_container_width=True)

# --- ② 期間累積リターン推移グラフ ---
st.subheader("② 期間累積リターン推移 (対TOPIX)")
fig_cum = go.Figure()
dates = pd.to_datetime(cum_ret.index)

for sec in sector_list:
    fig_cum.add_trace(go.Scatter(
        x=dates, y=cum_ret[sec], mode="lines", name=sec,
        line=dict(color=colors.get(sec, "#555"), width=2.2)
    ))

fig_cum.add_trace(go.Scatter(
    x=dates, y=topix_plot, mode="lines", name="★TOPIX基準",
    line=dict(color="#111111", width=2.5, dash="dot")
))

fig_cum.add_hline(y=0, line_dash="solid", line_color="#444444", line_width=1.5)

fig_cum.update_layout(
    xaxis=dict(
        type="date",
        tickformat="%m/%d",
        nticks=6,
        tickangle=0,
        showgrid=True,
        gridcolor="#E5E7EB",
        gridwidth=1
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="#E5E7EB",
        gridwidth=1
    ),
    yaxis_title="累積騰落率 (%)", 
    height=420,
    margin=dict(t=10, l=10, r=10, b=20), 
    legend=dict(orientation="h", y=-0.38, font=dict(size=9.5))
)
st.plotly_chart(fig_cum, use_container_width=True)

# --- ③ 情報充実型・スマホ最適化カード型ランキング ---
st.subheader("📋 セクター別 モメンタム＆代金ランキング")
st.markdown("<small>※プラスは赤、マイナスは紺。代金倍率1.2倍超や騰落率±3%超は太字</small>", unsafe_allow_html=True)

sorted_sectors = sorted(sector_list, key=lambda s: ret_5d[s], reverse=True)

for sec in sorted_sectors:
    r5 = ret_5d[sec]
    r20 = ret_20d[sec]
    r60 = ret_60d[sec]
    rv = latest_rvol[sec]
    
    def get_style(val, threshold):
        color = "#D62828" if val >= 0 else "#1D3557"
        weight = "bold" if abs(val) >= threshold else "normal"
        return f"color: {color}; font-weight: {weight};"

    r5_style = get_style(r5, 3.0)
    r20_style = get_style(r20, 5.0)
    r60_style = get_style(r60, 10.0)
    rv_style = f"font-weight: {'bold' if rv >= 1.2 else 'normal'}; color: {'#D97706' if rv >= 1.2 else '#222'};"
    
    sec_color = colors.get(sec, "#333")

    card_html = f"""
    <div style="background-color: #ffffff; padding: 10px 14px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid {sec_color}; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
        <div style="font-weight: bold; font-size: 14.5px; margin-bottom: 6px; color: #111; display: flex; justify-content: space-between;">
            <span>{sec}</span>
            <span style="font-size: 12.5px; font-weight: normal;">代金倍率: <b style="{rv_style}">{rv:.2f}倍</b></span>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 12.5px; background: #F8F9FA; padding: 5px 8px; border-radius: 4px;">
            <span>短期5日: <b style="{r5_style}">{r5:+.2f}%</b></span>
            <span>中期20日: <span style="{r20_style}">{r20:+.2f}%</span></span>
            <span>長期{window_days}日: <span style="{r60_style}">{r60:+.2f}%</span></span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)