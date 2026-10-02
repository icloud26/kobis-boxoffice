import streamlit as st
import pandas as pd
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# -------------------------------------------------
# 기본 설정
# -------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회 KOBIS 일별 박스오피스")


# -------------------------------------------------
# 한국 시간을 기준으로 '어제' 날짜 계산
# Streamlit Cloud 서버의 시간과 관계없이
# Asia/Seoul 시간대를 사용합니다.
# -------------------------------------------------
korea_time = datetime.now(ZoneInfo("Asia/Seoul"))
yesterday = korea_time.date() - timedelta(days=1)

# KOBIS API가 요구하는 yyyymmdd 형태로 변환
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여 줄 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# -------------------------------------------------
# KOBIS API에서 박스오피스 데이터 가져오기
#
# 같은 날짜의 데이터를 계속 요청하지 않도록
# 약 1시간 동안 결과를 기억합니다.
# ttl=3600 → 3600초 = 1시간
# -------------------------------------------------
@st.cache_data(ttl=3600)
def get_boxoffice(target_date):

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    # 인증키는 코드에 직접 쓰지 않고
    # Streamlit의 비밀 금고에서 가져옵니다.
    api_key = st.secrets["KOBIS_KEY"]

    params = {
        "key": api_key,
        "targetDt": target_date
    }

    # 서버가 너무 오래 응답하지 않을 경우를 대비해
    # 최대 10초까지만 기다립니다.
    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    # HTTP 요청 자체가 실패했다면 오류를 발생시킵니다.
    response.raise_for_status()

    data = response.json()

    return data


# -------------------------------------------------
# API 호출 및 오류 처리
# -------------------------------------------------
try:

    # 비밀 금고에 인증키가 있는지 먼저 확인
    if "KOBIS_KEY" not in st.secrets:
        st.error("KOBIS 인증키를 찾을 수 없습니다.")
        st.info(
            "Streamlit Cloud의 비밀 금고(Secrets)에 "
            "KOBIS_KEY가 올바르게 등록되어 있는지 확인해 주세요."
        )
        st.stop()

    data = get_boxoffice(target_date)


    # -------------------------------------------------
    # KOBIS는 인증키 등이 잘못되어도
    # 상태코드 200과 함께 faultInfo를 보낼 수 있습니다.
    # -------------------------------------------------
    if "faultInfo" in data:

        st.error("KOBIS API에서 오류를 반환했습니다.")

        fault = data["faultInfo"]

        message = fault.get("message", "오류 내용이 없습니다.")

        st.warning(f"오류 내용: {message}")

        st.info(
            "KOBIS 인증키가 정확한지, "
            "Streamlit 비밀 금고의 KOBIS_KEY 설정이 올바른지 "
            "확인해 주세요."
        )

        st.stop()


    # -------------------------------------------------
    # 영화 목록 가져오기
    # -------------------------------------------------
    boxoffice_result = data.get("boxOfficeResult", {})

    movies = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )


    # 영화 목록이 비어 있는 경우
    if not movies:

        st.warning("해당 날짜의 박스오피스 데이터가 없습니다.")

        st.info(
            "조회 날짜가 올바른지 확인하거나, "
            "KOBIS에서 해당 날짜의 집계가 완료되었는지 "
            "확인해 주세요."
        )

        st.stop()


    # -------------------------------------------------
    # 필요한 항목만 데이터프레임으로 만들기
    # -------------------------------------------------
    df = pd.DataFrame(movies)

    df = df[
        [
            "rank",
            "movieNm",
            "openDt",
            "audiCnt",
            "audiAcc",
            "scrnCnt"
        ]
    ].copy()


    # -------------------------------------------------
    # KOBIS의 숫자 데이터는 문자열로 들어옵니다.
    # 계산, 정렬, 그래프를 위해 숫자로 변환합니다.
    # -------------------------------------------------
    numeric_columns = [
        "rank",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0).astype(int)


    # 순위 순서대로 정렬
    df = df.sort_values("rank")


    # -------------------------------------------------
    # 제목과 조회 날짜 표시
    # -------------------------------------------------
    st.subheader(f"📅 {display_date} 박스오피스")


    # -------------------------------------------------
    # 1위 영화 정보
    # -------------------------------------------------
    first_movie = df.iloc[0]

    st.markdown("### 🏆 박스오피스 1위")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "영화",
            first_movie["movieNm"]
        )

    with col2:
        st.metric(
            "관객 수",
            f'{first_movie["audiCnt"]:,}명'
        )

    with col3:
        st.metric(
            "누적 관객",
            f'{first_movie["audiAcc"]:,}명'
        )


    # -------------------------------------------------
    # 전체 박스오피스 표
    # -------------------------------------------------
    st.markdown("### 📋 일별 박스오피스 순위")

    # 화면에서 보기 좋은 한글 이름으로 변경
    table_df = df.rename(
        columns={
            "rank": "순위",
            "movieNm": "영화명",
            "openDt": "개봉일",
            "audiCnt": "관객수",
            "audiAcc": "누적관객",
            "scrnCnt": "스크린수"
        }
    )

    st.dataframe(
        table_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "관객수": st.column_config.NumberColumn(
                "관객수",
                format="%d명"
            ),
            "누적관객": st.column_config.NumberColumn(
                "누적관객",
                format="%d명"
            ),
            "스크린수": st.column_config.NumberColumn(
                "스크린수",
                format="%d개"
            )
        }
    )


    # -------------------------------------------------
    # 관객 수가 많은 영화 5편
    #
    # 순위가 아니라 실제 관객 수를 기준으로
    # 다시 정렬합니다.
    # -------------------------------------------------
    st.markdown("### 📊 관객 수 상위 5편")

    top5 = (
        df.sort_values(
            "audiCnt",
            ascending=False
        )
        .head(5)
        [["movieNm", "audiCnt"]]
        .set_index("movieNm")
    )

    st.bar_chart(
        top5,
        y="audiCnt",
        x_label="영화",
        y_label="관객 수"
    )


# -------------------------------------------------
# 인터넷 연결 문제, 서버 오류 등의 처리
# -------------------------------------------------
except requests.exceptions.RequestException:

    st.error("KOBIS 서버에서 데이터를 가져오지 못했습니다.")

    st.info(
        "인터넷 연결 상태를 확인하고 잠시 후 다시 시도해 주세요. "
        "KOBIS 서버가 일시적으로 응답하지 않는 경우도 있습니다."
    )


# -------------------------------------------------
# 그 밖의 예상하지 못한 오류 처리
# -------------------------------------------------
except Exception as e:

    st.error("박스오피스 데이터를 처리하는 중 문제가 발생했습니다.")

    st.info(
        "Streamlit 비밀 금고에 KOBIS_KEY가 정확하게 등록되어 있는지 "
        "확인해 주세요."
    )

    # 초보 단계에서는 문제 확인을 위해 오류 내용도 표시
    st.caption(f"오류 내용: {e}")
