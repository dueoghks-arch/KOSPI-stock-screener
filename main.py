from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
import time
import FinanceDataReader as fdr
import numpy as np
import pandas as pd
import yfinance as yf


def get_filtered_krx_tickers(kosdaq_percentile=50):
    print("⏳ [KRX] Fetching and filtering tickers...")
    try:
        df_kospi = fdr.StockListing("KOSPI")
        df_kosdaq = fdr.StockListing("KOSDAQ")

        df_kospi.columns = [col.upper() for col in df_kospi.columns]
        df_kosdaq.columns = [col.upper() for col in df_kosdaq.columns]

        df_kosdaq = df_kosdaq.copy()
        df_kosdaq["MARCAP"] = pd.to_numeric(
            df_kosdaq["MARCAP"], errors="coerce"
        )
        df_kosdaq = df_kosdaq.dropna(subset=["MARCAP"])

        cutoff_value = df_kosdaq["MARCAP"].quantile(
            1 - (kosdaq_percentile / 100)
        )
        df_kosdaq_filtered = df_kosdaq[
            df_kosdaq["MARCAP"] >= cutoff_value
        ].copy()

        df_kospi["CODE"] = df_kospi["CODE"].astype(str).str.strip().str.zfill(6)
        df_kosdaq_filtered["CODE"] = (
            df_kosdaq_filtered["CODE"].astype(str).str.strip().str.zfill(6)
        )

        kospi_tickers = [f"{code}.KS" for code in df_kospi["CODE"]]
        kosdaq_tickers = [f"{code}.KQ" for code in df_kosdaq_filtered["CODE"]]

        tickers = kospi_tickers + kosdaq_tickers
        total_listing = pd.concat([df_kospi, df_kosdaq_filtered], axis=0)

        cutoff_in_eok = round(cutoff_value / 1e8, 1)
        print("✅ [KRX] 필터링 완료.")
        print(f"    > KOSPI: {len(kospi_tickers)}개 (전체)")
        print(
            f"    > KOSDAQ: {len(kosdaq_tickers)}개 (시총 상위 {kosdaq_percentile}%, 기준점: 약 {cutoff_in_eok:,}억 원 이상)"
        )
        print(f"    > 총 대상 종목: {len(tickers)}개")

        return tickers, total_listing

    except Exception as e:
        print(f"⚠️ [KRX] Failed: {e}. Using fallback assets.")
        fallback_tickers = [
            "005930.KS",
            "000660.KS",
            "005380.KS",
            "035420.KS",
            "035720.KS",
        ]
        fallback_df = pd.DataFrame({
            "CODE": ["005930", "000660", "005380", "035420", "035720"],
            "NAME": ["삼성전자", "SK하이닉스", "현대차", "NAVER", "카카오"],
            "MARCAP": [
                400000000000000,
                100000000000000,
                50000000000000,
                30000000000000,
                20000000000000,
            ],
        })
        return fallback_tickers, fallback_df


def send_email(content, is_html=False):
    user = os.environ.get("EMAIL_USER")
    pw = os.environ.get("EMAIL_PASS")

    if not user or not pw:
        print(
            "\n⚠️ [ENV] Secrets missing. Outputting directly to console:\n"
        )
        print(content)
        return

    msg = MIMEText(content, "html" if is_html else "plain")
    msg["Subject"] = (
        f"📈 [국장 스캐너] 트리플 AND(이평선 돌파 + 52주 신고가) 포착 리포트 ({datetime.now().strftime('%Y-%m-%d')})"
    )
    msg["From"] = user
    msg["To"] = user

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(user, pw)
        server.sendmail(user, user, msg.as_string())
        server.quit()
        print("📧 [EMAIL] Report dispatched successfully!")
    except Exception as e:
        print(f"❌ [EMAIL] Dispatch failed: {e}")


def screen_krx_stocks():
    tickers, krx_listing = get_filtered_krx_tickers(kosdaq_percentile=50)
    results = []
    print(
        f"📊 [SCAN] Analyzing {len(tickers)} assets under Triple AND Logic..."
    )

    chunk_size = 80
    all_close_data = pd.DataFrame()

    print(
        "⏳ [DATA] Downloading 5-year weekly chart history via yfinance..."
    )
    for i in range(0, len(tickers), chunk_size):
        chunk_tickers = tickers[i : i + chunk_size]
        try:
            # MultiIndex 문제 예방을 위해 Price 추출 방식을 안전하게 처리
            chunk_data = yf.download(
                chunk_tickers,
                period="5y",
                interval="1wk",
                progress=False,
                timeout=40,
            )
            if not chunk_data.empty:
                if "Close" in chunk_data:
                    chunk_close = chunk_data["Close"]
                else:
                    chunk_close = chunk_data

                if all_close_data.empty:
                    all_close_data = chunk_close
                else:
                    all_close_data = pd.concat(
                        [all_close_data, chunk_close], axis=1
                    )

            print(
                f"   > ⏳ Progress: {min(i + chunk_size, len(tickers))} / {len(tickers)} completed..."
            )
            time.sleep(1.0)
        except Exception as e:
            print(f"⚠️ Chunk download error: {e}")
            continue

    if all_close_data.empty:
        print("❌ [DATA] Terminated: No valid data aggregated.")
        return

    if all_close_data.index.tz is not None:
        all_close_data.index = all_close_data.index.tz_localize(None)

    name_dict = {}
    marcap_dict = {}
    if not krx_listing.empty:
        name_dict = pd.Series(
            krx_listing["NAME"].values, index=krx_listing["CODE"].values
        ).to_dict()
        marcap_dict = pd.Series(
            krx_listing["MARCAP"].values, index=krx_listing["CODE"].values
        ).to_dict()

    if isinstance(all_close_data, pd.Series):
        all_close_data = all_close_data.to_frame()

    for ticker in all_close_data.columns:
        try:
            series_close = all_close_data[ticker].dropna()
            if len(series_close) < 200:
                continue

            ma5 = series_close.rolling(window=5).mean()
            ma30 = series_close.rolling(window=30).mean()
            ma200 = series_close.rolling(window=200).mean()

            curr_price = series_close.iloc[-1]
            curr_ma5 = ma5.iloc[-1]
            curr_ma30 = ma30.iloc[-1]
            curr_ma200 = ma200.iloc[-1]

            # [수정 1] 이전 52주간의 최고가 계산 (현재 주차 제외)
            high_52w_prev = series_close.iloc[-53:-1].max()

            # ---------------------------------------------------------
            # 조건 1. 최근 8주 내 5주선이 30주/200주 상향돌파 OR 10% 이내 근접
            # ---------------------------------------------------------
            cross_5_30 = (ma5 > ma30) & (ma5.shift(1) <= ma30.shift(1))
            cross_5_200 = (ma5 > ma200) & (ma5.shift(1) <= ma200.shift(1))

            prox_5_30 = (abs(ma5 - ma30) / series_close) <= 0.10
            prox_5_200 = (abs(ma5 - ma200) / series_close) <= 0.10

            cond1_30 = cross_5_30 | prox_5_30
            cond1_200 = cross_5_200 | prox_5_200

            cond1 = (
                cond1_30.iloc[-8:].any() or cond1_200.iloc[-8:].any()
            )

            # ---------------------------------------------------------
            # 조건 2. 최근 26주 내 30주선이 200주선 상향돌파 OR 현재 정배열 상태
            # ---------------------------------------------------------
            cross_30_200 = (ma30 > ma200) & (ma30.shift(1) <= ma200.shift(1))
            cond2 = cross_30_200.iloc[-26:].any() or (curr_ma30 > curr_ma200)

            # ---------------------------------------------------------
            # 조건 3. 현재가 >= 지난 52주 최고가 (실질적 신고가 달성)
            # ---------------------------------------------------------
            cond3 = curr_price >= high_52w_prev

            if not (cond1 and cond2 and cond3):
                continue

            code_only = ticker.split(".")[0]
            kor_name = name_dict.get(code_only, ticker)
            raw_marcap = marcap_dict.get(code_only, 0)

            results.append({
                "종목코드": code_only,
                "종목명": kor_name,
                "현재가(원)": f"{int(curr_price):,}",
                "이전 52주 최고가": f"{int(high_52w_prev):,}",
                "조건 만족 여부": "✅ 조건 1,2,3 동시 만족",
                "5주 이평": f"{int(curr_ma5):,}",
                "30주 이평": f"{int(curr_ma30):,}",
                "200주 이평": f"{int(curr_ma200):,}",
                "시가총액(천억원)": (
                    round(raw_marcap / 1e11, 1) if raw_marcap else 0
                ),
            })
        except Exception:
            continue

    today_str = datetime.now().strftime("%Y-%m-%d")
    print(
        f"📊 [DEBUG] 필터링 조건 통과한 최종 종목 수: {len(results)}개"
    )

    if results:
        final_df = pd.DataFrame(results).sort_values(
            by="시가총액(천억원)", ascending=False
        )
        table_html = final_df.to_html(
            index=False, border=1, justify="center"
        ).replace(
            'border="1"',
            'style="border-collapse: collapse; width: 100%; text-align:'
            ' center; font-size: 14px;" border="1"',
        )

        html_content = f"""
        <h3 style="color: #0d47a1;">🇰🇷 주봉 트리플 AND (다중 이평선 수렴/돌파 + 52주 신고가) 보고서 ({today_str})</h3>
        <div style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
            <p style="margin: 0; font-size: 13px; color: #333;">
            <b>[적용 로직: 아래 3가지 조건 동시 만족 종목 선별]</b><br>
            <b>1.</b> 최근 8주 내 5주 이평선이 30주/200주를 상향 돌파했거나, 주가의 10% 이내로 초근접한 이력이 있음 <b>(AND)</b><br>
            <b>2.</b> 30주 이평선이 200주 이평선 위에 위치하거나 최근 26주 내 상향 돌파 <b>(AND)</b><br>
            <b>3. 현재가가 이전 52주 주간 종가 최고치 이상 (신고가 돌파)</b>
            </p>
        </div>
        {table_html}
        """
        send_email(html_content, is_html=True)
    else:
        html_content = f"""
        <h3 style="color: #b71c1c;">⚠️ 국장 스캐너 알림 ({today_str})</h3>
        <p>오늘 기준 <b>이평선 수렴/돌파 조건과 52주 신고가 조건</b>을 동시에 만족하는 강력한 모멘텀 종목이 포착되지 않았습니다.</p>
        """
        send_email(html_content, is_html=True)


if __name__ == "__main__":
    screen_krx_stocks()
