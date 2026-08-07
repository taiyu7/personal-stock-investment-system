from __future__ import annotations

import streamlit as st


def render_trade_concept_page() -> None:
    st.subheader("交易觀念")
    st.markdown("- 有量才有價，量先價行")
    st.markdown("**Why：** 有量才有市場關注度，股票才會動，參與人數才多，比較不會被個別主力影響。")
    st.markdown("### 量價位關係")
    st.markdown("""<table class="trade-concept-table"><thead><tr><th>量／價</th><th>高檔／創新高</th><th>低檔</th></tr></thead><tbody><tr><td>大量紅 K</td><td>強勢確認，但要觀察是否爆量過熱。</td><td>可能是低檔轉強或主力進場訊號。</td></tr><tr><td>大量黑 K</td><td>偏向出貨或獲利了結。</td><td>可能是恐慌殺盤或最後一跌，需等止跌確認。</td></tr><tr><td>量放大紅 K</td><td>多方續攻，趨勢延續機率高。</td><td>買盤開始進場，需搭配突破與均線確認。</td></tr><tr><td>量縮小黑 K</td><td>漲多後休息，未破支撐前先視為整理。</td><td>賣壓減弱但買盤不足，等待方向。</td></tr></tbody></table>""", unsafe_allow_html=True)
    st.markdown("**大量：** 大於五日均量兩倍以上；高價股可視流動性調整。")
