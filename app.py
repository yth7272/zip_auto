# ==========================================
# [메인 앱] 우편번호 자동 입력 Web App
# ==========================================
# Streamlit 기반 - Google Sheets 연동

import streamlit as st
import pandas as pd
import time

from sheets_handler import (
    connect_sheet,
    get_worksheet_names,
    read_sheet_preview,
    read_all_data,
    find_empty_zipcode_rows,
    write_results,
)
from zipcode_helper import recommend_zipcode

# ── 페이지 설정 ──
st.set_page_config(
    page_title="우편번호 자동 입력",
    page_icon="📮",
    layout="wide",
)

st.title("📮 우편번호 자동 입력")
st.caption("Google Sheets의 주소를 분석하여 우편번호를 자동으로 채워줍니다.")

# ── Session State 초기화 ──
if "sheet_connected" not in st.session_state:
    st.session_state.sheet_connected = False
if "worksheet" not in st.session_state:
    st.session_state.worksheet = None
if "preview_data" not in st.session_state:
    st.session_state.preview_data = None
if "headers" not in st.session_state:
    st.session_state.headers = []
if "addr_col" not in st.session_state:
    st.session_state.addr_col = None
if "zip_col" not in st.session_state:
    st.session_state.zip_col = None
if "acc_col" not in st.session_state:
    st.session_state.acc_col = None
if "processing_done" not in st.session_state:
    st.session_state.processing_done = False
if "results" not in st.session_state:
    st.session_state.results = []


# ══════════════════════════════════════════
# STEP 1: 시트 연결
# ══════════════════════════════════════════
st.header("① 시트 연결", divider="gray")

col_url, col_btn = st.columns([4, 1])
with col_url:
    sheet_url = st.text_input(
        "Google Sheets URL",
        placeholder="https://docs.google.com/spreadsheets/d/...",
        label_visibility="collapsed",
    )

# 워크시트 선택
worksheet_name = None
if sheet_url and not st.session_state.sheet_connected:
    try:
        ws_names = get_worksheet_names(sheet_url)
        if len(ws_names) > 1:
            worksheet_name = st.selectbox("워크시트 선택", ws_names)
        else:
            worksheet_name = ws_names[0]
    except Exception as e:
        st.error(f"시트에 접근할 수 없습니다. 서비스 계정 이메일에 시트를 공유했는지 확인하세요.\n\n`{e}`")

with col_btn:
    st.write("")  # 수직 정렬용
    connect_clicked = st.button("🔗 연결", use_container_width=True, type="primary")

if connect_clicked and sheet_url:
    with st.spinner("시트에 연결 중..."):
        try:
            ws, _ = connect_sheet(sheet_url, worksheet_name)
            preview = read_sheet_preview(ws, max_rows=15)

            st.session_state.worksheet = ws
            st.session_state.preview_data = preview
            st.session_state.headers = preview[0] if preview else []
            st.session_state.sheet_connected = True
            st.session_state.addr_col = None
            st.session_state.zip_col = None
            st.session_state.acc_col = None
            st.session_state.processing_done = False
            st.session_state.results = []
            st.rerun()
        except Exception as e:
            st.error(f"연결 실패: {e}")


# ══════════════════════════════════════════
# STEP 2: 시트 미리보기 + Column 선택
# ══════════════════════════════════════════
if st.session_state.sheet_connected and st.session_state.preview_data:
    st.header("② Column 지정", divider="gray")

    preview = st.session_state.preview_data
    headers = st.session_state.headers

    # 중복 헤더 처리: 같은 이름이 있으면 _2, _3 등 접미사 추가
    def deduplicate_headers(cols):
        seen = {}
        result = []
        for col in cols:
            if col in seen:
                seen[col] += 1
                result.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 1
                result.append(col)
        return result

    display_headers = deduplicate_headers(headers)

    # 미리보기 테이블 표시
    if len(preview) > 1:
        df_preview = pd.DataFrame(preview[1:], columns=display_headers)
        st.dataframe(df_preview, use_container_width=True, height=300)
    else:
        st.warning("시트에 데이터가 없습니다.")

    # Column 선택 UI
    st.markdown("**아래에서 각 역할의 Column을 선택하세요:**")

    col1, col2, col3 = st.columns(3)

    with col1:
        addr_col = st.selectbox(
            "📍 주소 Column",
            options=headers,
            index=None,
            placeholder="주소가 있는 Column 선택",
            key="addr_col_select",
        )

    with col2:
        zip_col = st.selectbox(
            "📮 우편번호 Column",
            options=headers,
            index=None,
            placeholder="우편번호를 쓸 Column 선택",
            key="zip_col_select",
        )

    with col3:
        acc_col = st.selectbox(
            "📊 정확도 Column",
            options=headers,
            index=None,
            placeholder="정확도를 쓸 Column 선택",
            key="acc_col_select",
        )

    # 선택 상태 저장
    st.session_state.addr_col = addr_col
    st.session_state.zip_col = zip_col
    st.session_state.acc_col = acc_col

    # 선택 상태 표시
    if addr_col and zip_col:
        cols_info = f"주소: **{addr_col}** → 우편번호: **{zip_col}**"
        if acc_col:
            cols_info += f" / 정확도: **{acc_col}**"
        st.success(f"✅ {cols_info}")


# ══════════════════════════════════════════
# STEP 3: 실행
# ══════════════════════════════════════════
if (
    st.session_state.sheet_connected
    and st.session_state.addr_col
    and st.session_state.zip_col
):
    st.header("③ 실행", divider="gray")

    # 대상 행 미리 확인
    ws = st.session_state.worksheet
    headers = st.session_state.headers

    addr_idx = headers.index(st.session_state.addr_col)
    zip_idx = headers.index(st.session_state.zip_col)
    acc_idx = headers.index(st.session_state.acc_col) if st.session_state.acc_col else -1

    all_data = read_all_data(ws)
    rows_to_process = find_empty_zipcode_rows(all_data, addr_idx, zip_idx)

    st.info(f"📋 전체 {len(all_data) - 1}행 중 **{len(rows_to_process)}행**의 우편번호가 비어있습니다.")

    if not rows_to_process:
        st.success("모든 행에 우편번호가 이미 있습니다! 🎉")
        if st.button("🔄 재스캔", key="rescan_empty"):
            st.session_state.processing_done = False
            st.session_state.results = []
            st.rerun()
    else:
        # 미리보기: 처리 대상 주소 목록
        with st.expander(f"처리 대상 주소 {len(rows_to_process)}건 보기"):
            for r in rows_to_process[:20]:
                st.text(f"  행 {r['row_num']}: {r['address']}")
            if len(rows_to_process) > 20:
                st.text(f"  ... 외 {len(rows_to_process) - 20}건")

        # 실행 버튼
        col_run, col_rescan, col_option = st.columns([2, 1, 3])
        with col_option:
            use_gemini = st.checkbox("Gemini AI 보정 사용 (정규식 실패 시)", value=True)

        with col_run:
            run_clicked = st.button(
                f"🚀 우편번호 {len(rows_to_process)}건 자동 입력",
                type="primary",
                use_container_width=True,
            )

        with col_rescan:
            if st.button("🔄 재스캔", key="rescan_run"):
                st.session_state.processing_done = False
                st.session_state.results = []
                st.rerun()

        # ── 처리 실행 ──
        if run_clicked:
            st.session_state.processing_done = False
            st.session_state.results = []

            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.container()

            results = []
            total = len(rows_to_process)

            for i, row_info in enumerate(rows_to_process):
                row_num = row_info["row_num"]
                address = row_info["address"]

                status_text.text(f"처리 중... ({i + 1}/{total}) - {address[:40]}")
                progress_bar.progress((i + 1) / total)

                # 우편번호 추천
                rec = recommend_zipcode(address, use_gemini_fallback=use_gemini)

                result_entry = {
                    "row_num": row_num,
                    "address": address,
                    "zipcode": rec["zipcode"],
                    "road_addr": rec["road_addr"],
                    "accuracy": rec["accuracy"],
                    "source": rec["source"],
                }
                results.append(result_entry)

                # API rate limit 방지
                time.sleep(0.3)

            # ── 결과 표시 ──
            status_text.text("결과 확인 중...")
            progress_bar.progress(1.0)

            st.session_state.results = results
            st.session_state.processing_done = True
            st.rerun()


# ══════════════════════════════════════════
# STEP 4: 결과 확인 + 시트 기록
# ══════════════════════════════════════════
if st.session_state.processing_done and st.session_state.results:
    st.header("④ 결과 확인", divider="gray")

    results = st.session_state.results

    # 통계
    success_count = sum(1 for r in results if r["zipcode"])
    fail_count = len(results) - success_count
    avg_accuracy = (
        sum(r["accuracy"] for r in results if r["zipcode"]) / success_count
        if success_count > 0
        else 0
    )

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("전체", f"{len(results)}건")
    col_s2.metric("성공", f"{success_count}건")
    col_s3.metric("실패", f"{fail_count}건")
    col_s4.metric("평균 정확도", f"{avg_accuracy:.0f}%")

    # 결과 테이블
    df_results = pd.DataFrame(
        [
            {
                "행": r["row_num"],
                "원본 주소": r["address"],
                "우편번호": r["zipcode"] or "❌ 조회 실패",
                "매칭 주소": r["road_addr"],
                "정확도": f"{r['accuracy']}%" if r["zipcode"] else "-",
                "방식": r["source"],
            }
            for r in results
        ]
    )

    st.dataframe(
        df_results,
        use_container_width=True,
        height=400,
        column_config={
            "정확도": st.column_config.TextColumn(width="small"),
            "방식": st.column_config.TextColumn(width="small"),
        },
    )

    # 시트에 기록 버튼
    st.divider()

    # 성공한 결과만 필터
    writable_results = [r for r in results if r["zipcode"]]

    if writable_results:
        write_clicked = st.button(
            f"✏️ 시트에 {len(writable_results)}건 기록하기",
            type="primary",
            use_container_width=False,
        )

        if write_clicked:
            ws = st.session_state.worksheet
            headers = st.session_state.headers
            zip_idx = headers.index(st.session_state.zip_col)
            acc_idx = (
                headers.index(st.session_state.acc_col)
                if st.session_state.acc_col
                else -1
            )

            with st.spinner("시트에 기록 중..."):
                try:
                    write_data = [
                        {
                            "row_num": r["row_num"],
                            "zipcode": r["zipcode"],
                            "accuracy": r["accuracy"],
                        }
                        for r in writable_results
                    ]
                    write_results(ws, write_data, zip_idx, acc_idx)
                    st.success(f"✅ {len(writable_results)}건이 시트에 기록되었습니다!")
                    st.balloons()
                    if st.button("🔄 재스캔", key="rescan_done"):
                        st.session_state.processing_done = False
                        st.session_state.results = []
                        st.rerun()
                except Exception as e:
                    st.error(f"기록 실패: {e}")
    else:
        st.warning("기록할 결과가 없습니다.")


# ══════════════════════════════════════════
# 사이드바: 설정 안내
# ══════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ 설정")

    st.markdown("""
    ### 사전 준비
    1. **서비스 계정** JSON 파일을 `service_account.json`으로 저장
    2. Google Sheets에 서비스 계정 이메일을 **편집자**로 공유
    3. `.streamlit/secrets.toml`에 API 키 설정:
    
    ```toml
    GEMINI_API_KEY = "..."
    JUSO_API_KEY = "..."
    ```
    """)

    st.divider()

    st.markdown("""
    ### 처리 흐름
    1. 🔗 시트 연결
    2. 📍 Column 지정 (주소 / 우편번호 / 정확도)
    3. 🚀 자동 조회 실행
    4. ✏️ 결과 확인 후 시트에 기록
    
    ### 정확도 기준
    - **90%+** : API 직접 매칭 성공
    - **70~85%** : Gemini 보정 후 매칭
    - **50% 이하** : 불확실한 매칭
    """)
