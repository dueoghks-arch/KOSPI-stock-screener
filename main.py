import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MIMEText
import time

def get_filtered_krx_tickers(kosdaq_percentile=50):
    """
    [수정] KOSPI 전 종목 및 KOSDAQ 시가총액 상위 50% 종목만 선별하여 수집
    """
    print("⏳ [KRX] Fetching and filtering tickers...")
    try:
        # 1. 코스피/코스닥 기본 리스트 가져오기
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        
        # 2. 코스닥 상위 50% 컷오프 계산 (MarCap 기준)
        # 문자열이나 결측치가 있을 수 있으므로 숫자형 변환 및 정렬
        df_kosdaq['MarCap'] = pd.to_numeric(df_kosdaq['MarCap'], errors='coerce')
        df_kosdaq = df_kosdaq.dropna(subset=['MarCap'])
        
        cutoff_value = df_kosdaq['MarCap'].quantile(1 - (kosdaq_percentile / 100))
        df_kosdaq_filtered = df_kosdaq[df_kosdaq['MarCap'] >= cutoff_value]
        
        # 3. 안전하게 종목코드(Code)의 공백을 제거하고 문자열 고정 후 매핑
        df_kospi['Code'] = df_kospi['Code'].astype(str).str.strip()
        df_kosdaq_filtered['Code'] = df_kosdaq_filtered['Code'].astype(str).str.strip()
        
        kospi_tickers = [f"{code}.KS" for code in df_kospi['Code'] if len(code) == 6]
        kosdaq_tickers = [f"{code}.KQ" for code in df_kosdaq_filtered['Code'] if len(code) == 6]
        
        tickers = kospi_tickers + kosdaq_tickers
        
        cutoff_in_eok = round(cutoff_value / 1e8, 1)
        print("✅ [KRX] 필터링 완료.")
        print(f"   > KOSPI: {len(kospi_tickers)}개 (전체)")
        print(f"   > KOSDAQ: {len(kosdaq_tickers)}개 (시총 상위 {kosdaq_percentile}%, 기준점: 약 {cutoff_in_eok:,}억 원 이상)")
        print(f"   > 총 대상 종목: {len(tickers)}개")
        return tickers
        
    except Exception as e:
        print(f"⚠️ [KRX] Failed: {e}. Using fallback assets.")
        return ['005930.KS', '000660.KS', '005380.KS', '035420.KS', '035720.KS']

def send_email(content, is_html=False):
    """구글 SMTP 서비스를 이용한 안정적인 이메일 발송 함수"""
    user = os.environ.get('EMAIL_USER')
    pw = os.environ.get('EMAIL_PASS')
    
    if not user or not pw:
        print("\n⚠️ [ENV] Secrets missing. Outputting directly to console:\n")
        print(content)
        return

    msg = MIMEText(content, 'html' if is_html else 'plain')
    msg['Subject'] = f"📈 [국내주식 전수조사] 3년 박스권 돌파형 장기 신고가 종목 리포트 ({datetime.now().strftime('%Y-%m-%d')})"
    msg['From'] = user
    msg['To'] = user

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(user, pw)
        server.sendmail(user, user, msg.as_string())
        server.quit()
        print("📧 [EMAIL] Report dispatched successfully!")
    except Exception as e:
        print(f"❌ [EMAIL] Dispatch failed: {e}")
        raise e

def screen_krx_stocks():
    # 필터링된 티커 파싱 함수 호출
    tickers = get_filtered_krx_tickers(kosdaq_percentile=50)
    results = []
    print(f"📊 [SCAN] Analyzing {len(tickers)} assets under multi-layer criteria...")
    
    chunk_size = 80
    all_close_data = pd.DataFrame()
    
    print("⏳ [DATA] Downloading 3-year weekly chart history via yfinance...")
    for i in range(0, len(tickers), chunk_size):
        chunk_tickers = tickers[i:i+chunk_size]
        try:
            chunk_data = yf.download(chunk_tickers, period="3y", interval="1wk", progress=False, timeout=40)
            if not chunk_data.empty and 'Close' in chunk_data.columns:
                chunk_close = chunk_data['Close']
                if all_close_data.empty:
                    all_close_data = chunk_close
                else:
                    all_close_data = pd.concat([all_close_data, chunk_close], axis=1)
            print(f"  > ⏳ Progress: {min(i + chunk_size, len(tickers))} / {len(tickers)} completed...")
            time.sleep(2.0)
        except Exception as e:
            print("⚠️ [DATA] Chunk download issue encountered. Skipping...")
            continue

    if all_close_data.empty:
        print("❌ [DATA] Terminated: No valid data aggregated.")
        return

    if all_close_data.index.tz is not None:
        all_close_data.index = all_close_data.index.tz_localize(None)

    now = datetime.now()
    one_year_ago = now - timedelta(days=365)

    print("📋 [MAP] Structuring ticker name & market cap data...")
    try:
        krx_listing = pd.concat([fdr.StockListing('KOSPI'), fdr.StockListing('KOSDAQ')], axis=0)
        name_dict = pd.Series(krx_listing.Name.values, index=krx_listing.Code.values).to_dict()
        marcap_dict = pd.Series(krx_listing.MarCap.values, index=krx_listing.Code.values).to_dict()
    except Exception as e:
        print(f"⚠️ [MAP] Reference indexing failed: {e}")
        name_dict, marcap_dict = {}, {}

    print("🔍 [SCAN] Parsing signals...")
    
    # 단일 종목 다운로드 시 Series 변환 방지 구조화
    if isinstance(all_close_data, pd.Series):
        all_close_data = all_close_data.to_frame()

    for ticker in all_close_data.columns:
        try:
            series_close = all_close_data[ticker].dropna()
            if len(series_close) < 100: 
                continue 
            
            curr_price = series_close.iloc[-1]
            if pd.isna(curr_price) or curr_price <= 0: 
                continue
            
            # [조건 1] 3년 전체 최고가(신고가) 검증
            three_year_max = series_close.max()
            if curr_price < (three_year_max - 1e-5): 
                continue 

            # [조건 2] 최저가 부근 바닥 다지기 비율 검증 (10%로 완화)
            absolute_min = series_close.min()
            floor_limit = absolute_min * 1.50
            weeks_in_floor = series_close[(series_close >= absolute_min) & (series_close <= floor_limit)].count()
            floor_ratio = weeks_in_floor / len(series_close)
            
            if floor_ratio < 0.10: 
                continue 

            # [조건 3] 박스권 상단 탈출 마진 검증 (+0% ~ +30% 이내)
            box_period_series = series_close[series_close.index <= one_year_ago]
            if box_period_series.empty: 
                continue
            
            past_max = box_period_series.max() 
            if pd.isna(past_max) or past_max == 0: 
                continue
            
            if not (past_max <= curr_price <= past_max * 1.30): 
                continue

            # [조건 4] 완만한 장기 성장을 뜻하는 추세 기울기 평탄도 검증 (제한 조건 해제, 값만 기록)
            start_price = series_close.iloc[0]
            start_date = series_close.index[0]
            end_date = series_close.index[-1]
            
            total_days = (end_date - start_date).days
            
            angle_deg = 0.0
            if total_days > 0 and not pd.isna(start_price) and start_price > 0:
                total_gain_ratio = (curr_price - start_price) / start_price
                slope = (total_gain_ratio) / (total_days / 1095.0)
                angle_deg = np.degrees(np.arctan(slope))

            code_only = ticker.split('.')[0]
            kor_name = name_dict.get(code_only, ticker)
            raw_marcap = marcap_dict.get(code_only, 0)
            marcap_in_gwan = round(raw_marcap / 1e11, 1) if raw_marcap else 0 

            results.append({
                '종목코드': code_only,
                '종목명': kor_name,
                '현재가(원)': f"{int(curr_price):,}",
                '3년 최고가': f"{int(three_year_max):,}",
                '바닥밀집도': f"{round(floor_ratio * 100, 1)}%",
                '장기 추세각': f"{round(angle_deg, 1)}°",
                '시가총액(천억원)': marcap_in_gwan
            })
            print(f"🎯 [MATCHED] Found: {kor_name}({code_only})")

        except Exception:
            continue

    today_str = datetime.now().strftime('%Y-%m-%d')
    if results:
        final_df = pd.DataFrame(results).sort_values(by='시가총액(천억원)', ascending=False)
        table_html = final_df.to_html(index=False, border=1, justify='center')
        styled_table = table_html.replace('border="1"', 'style="border-collapse: collapse; width: 100%; text-align: center; font-size: 14px;" border="1"')
        
        html_content = f"""
        <h3 style="color: #0d47a1;">🇰🇷 국장 3년 박스권 상단 돌파형 종목 전수조사 보고서 ({today_str})</h3>
        <p><b>시장 범위:</b> KOSPI 전체 및 KOSDAQ 상위 50% 선별</p>
        <ul>
            <li style="color: #d32f2f;"><b>이번 주 주봉 종가가 최근 3년 최고가(신고가)를 기록 중인 종목</b></li>
            <li><b>바닥밀집도 허들 완화:</b> 10% 이상 (3년 중 최소 1년 이상 바닥 다지기)</li>
            <li><b>기울기 각도 무제한:</b> 오버슈팅 구간에 진입한 강력한 장대양봉 돌파주 포함</li>
        </ul><br>
        {styled_table}
        """
        print("🚀 [REPORT] Match found. Routing to mailbox...")
        send_email(html_content, is_html=True)
    else:
        no_result_html = f"""
        <h3 style="color: #b71c1c;">⚠️ 국장 스캐너 알림 ({today_str})</h3>
        <p><b>시장 범위:</b> KOSPI 전체 및 KOSDAQ 상위 50% 선별</p>
        <hr>
        <p>현재 조건 완화 기준(매집 10% 이상, 최저가~최저가*1.5 사이 가격을 매집 박스권)을 만족하는 국장 장기 박스권 돌파형 종목이 없습니다.</p>
        """
        print("ℹ : [REPORT] No assets matched criteria. Routing notification...")
        send_email(no_result_html, is_html=True)

if __name__ == "__main__":
    screen_krx_stocks()
