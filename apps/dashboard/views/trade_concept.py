from __future__ import annotations

import streamlit as st


def render_stock_concept_page() -> None:
    st.subheader("進銘的股價概念")
    st.markdown("- 有量才有價，量先價行")
    st.markdown("**Why：** 有量才有市場關注度，股票才會動，參與人數才多，比較不會被個別主力影響")
    st.markdown("### 量價位關係")
    st.markdown(
        """
        <table class="trade-concept-table">
            <thead><tr><th>量 / 價</th><th>高檔 / 創新高</th><th>低檔</th></tr></thead>
            <tbody>
                <tr><td>大量紅 K</td><td>強勢確認，但要觀察是否爆量過熱；若隔日續強，容易走主升段。</td><td>可能是低檔轉強或主力進場訊號，需搭配是否站上均線與壓力。</td></tr>
                <tr><td>大量黑 K</td><td>偏向出貨或獲利了結，若跌破大量 K 低點要提高風險意識。</td><td>可能是恐慌殺盤或最後一跌，需等止跌紅 K 或量縮不破低再確認。</td></tr>
                <tr><td>量放大紅 K</td><td>多方續攻，若量價同步且不爆量，趨勢延續機率高。</td><td>買盤開始進場，若突破整理區或站回均線，常是轉強初期。</td></tr>
                <tr><td>量縮小黑 K</td><td>漲多後休息，若未跌破關鍵支撐，通常先視為健康整理。</td><td>賣壓減弱但買盤也不足，容易盤整，需等放量紅 K 才有方向。</td></tr>
            </tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("**大量：** 大於五日均量 2 倍以上，200 元以上股可能可以 1.5 倍")
