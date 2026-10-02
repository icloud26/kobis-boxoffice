import streamlit as st
import pandas as pd
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# -------------------------------------------------
# 기본 설정
# -------------------------------------------------
st.set_page_config(
    page_title="일별 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스")
st.caption("영화진흥위원회 KOBIS 일별 박스오피스")


# -------------------------------------------------
# 한국 시간을 기준으로 날짜 계산
#
# 오늘 데이터는 아직 집계 전일 수 있으므로
# 사용자가 선택할 수 있는 가장 늦은 날짜는 '어제'입니다.
# -------------------------------------------------
korea_time = datetime.now(ZoneInfo("Asia/Seoul"))
yesterday = korea_time.date() - timedelta(days=1)


# -------------------------------------------------
# 달력에서 조회 날짜 선택
#
# 기본값은 어제로 설정합니다.
# max_value를 어제로 설정하여
# 오늘이나 미래 날짜는 선택할 수 없게 합니다.
# -------------------------------------------------
selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday
)

# KOBIS API가 요구하는 yyyymmdd 형태로 변환
target_date = selected_date.strftime("%Y%m%d")

# 화면에 보여 줄 날짜
display_date = selected_date.strftime("%Y년 %m월 %d일")


# -------------------------------------------------
# KOBIS API에서 박스오피스 데이터 가져오기
#
# 선택한 날짜가 같으면 API를 계속 호출하지 않고
# 약 1시간 동안 저장된 데이터를 사용합니다.
# -------------------------------------------------
@st.cache_data(ttl=3600)
def get_boxoffice(target_date):

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    # 인증키는 Streamlit 비밀 금고에서 가져옵니다.
    api_key = st.secrets["KOBIS_KEY"]

    params = {
        "key": api_key,
        "targetDt": target_date
    }

    response = requests.get(
        url,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    return response.json()


# -------------------------------------------------
# API 호출 및 오류 처리
# -------------------------------------------------
try:

    # 비밀 금고에 인증키가 있는지 확인
    if "KOBIS_KEY" not in st.secrets:

        st.error("KOBIS 인증키를 찾을 수 없습니다.")

        st.info(
            "Streamlit Cloud의 비밀 금고(Secrets)에 "
            "KOBIS_KEY가 올바르게 등록되어 있는지 확인해 주세요."
        )

        st.stop()


    data = get_boxoffice(target_date)


    # -------------------------------------------------
    # KOBIS는 인증키가 잘못된 경우에도
    # 상태코드 200과 faultInfo를 보낼 수 있습니다.
    # -------------------------------------------------
    if "faultInfo" in data:

        st.error("KOBIS API에서 오류를 반환했습니다.")

        fault = data["faultInfo"]
        message = fault.get("message", "오류 내용이 없습니다.")

        st.warning(f"오류 내용: {message}")

        st.info(
            "KOBIS 인증키와 Streamlit 비밀 금고의 "
            "KOBIS_KEY 설정을 확인해 주세요."
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


    # -------------------------------------------------
    # 영화 목록이 없는 경우
    # -------------------------------------------------
    if not movies:

        st.warning("그날은 아직 집계 전입니다.")

        st.info(
            "다른 날짜를 선택해 주세요."
        )

        st.stop()


    # -------------------------------------------------
    # 필요한 데이터만 가져오기
    # rankInten도 추가합니다.
    # -------------------------------------------------
    df = pd.DataFrame(movies)

    df = df[
        [
            "rank",
            "rankInten",
            "movieNm",
            "openDt",
            "audiCnt",
            "audiAcc",
            "scrnCnt"
        ]
    ].copy()


    # -------------------------------------------------
    # KOBIS의 숫자 데이터는 문자열입니다.
    # 계산과 정렬을 위해 숫자로 변환합니다.
    # -------------------------------------------------
    numeric_columns = [
        "rank",
        "rankInten",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0).astype(int)


    # 순위 순서로 정렬
    df = df.sort_values("rank")


    # -------------------------------------------------
    # 순위 변동 표시 만들기
    #
    # 양수 → 순위 상승 : 🔺
    # 음수 → 순위 하락 : 🔽
    # 0    → 변동 없음 : -
    # -------------------------------------------------
    def rank_change(value):

        if value > 0:
            return f"🔺 {value}"

        elif value < 0:
            return f"🔽 {abs(value)}"

        else:
            return "-"


    df["순위변동"] = df["rankInten"].apply(rank_change)


    # -------------------------------------------------
    # 누적 관객 100만 명을 넘은 영화에는
    # 영화명 옆에 트로피를 붙입니다.
    # -------------------------------------------------
    def add_trophy(row):

        if row["audiAcc"] > 1_000_000:
            return f'{row["movieNm"]} 🏆'

        return row["movieNm"]


    df["표시영화명"] = df.apply(
        add_trophy,
        axis=1
    )


    # -------------------------------------------------
    # 선택한 날짜 표시
    # -------------------------------------------------
    st.subheader(f"📅 {display_date} 박스오피스")


    # -------------------------------------------------
    # 1위 영화 지표 카드
    # -------------------------------------------------
    first_movie = df.iloc[0]

    st.markdown("### 🏆 박스오피스 1위")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "영화",
            first_movie["표시영화명"]
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

    table_df = df[
        [
            "rank",
            "순위변동",
            "표시영화명",
            "openDt",
            "audiCnt",
            "audiAcc",
            "scrnCnt"
        ]
    ].copy()

    table_df = table_df.rename(
        columns={
            "rank": "순위",
            "표시영화명": "영화명",
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
    # 관객 수 상위 5편 막대그래프
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
# 인터넷 연결이나 KOBIS 서버 요청 오류
# -------------------------------------------------
except requests.exceptions.RequestException:

    st.error("KOBIS 서버에서 데이터를 가져오지 못했습니다.")

    st.info(
        "인터넷 연결 상태를 확인하고 잠시 후 다시 시도해 주세요. "
        "KOBIS 서버가 일시적으로 응답하지 않는 경우도 있습니다."
    )


# -------------------------------------------------
# 그 밖의 예상하지 못한 오류
# -------------------------------------------------
except Exception as e:

    st.error("박스오피스 데이터를 처리하는 중 문제가 발생했습니다.")

    st.info(
        "Streamlit 비밀 금고에 KOBIS_KEY가 정확하게 등록되어 있는지 "
        "확인해 주세요."
    )

    st.caption(f"오류 내용: {e}")
