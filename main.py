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
    """KOSPI 전 종목 및 KOSDAQ 시가총액 상위 50% 종목만 선별하여 수집"""
    print("⏳ [KRX] Fetching and filtering tickers...")
    try:
        # 1. 코스피/코스닥 기본 리스트 가져오기
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        
        # 2. 코스닥 상위 50% 컷오프 계산 (MarCap 기준)
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
    """구글 SMTP 서비스를 이용한 안정적인 이메일 발송 함수 (TLS 587 포트 방식)"""
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
            print(f"⚠️ [DATA] Chunk download issue encountered: {e}. Skipping...")
            continue

    # 💡 [에러 수정] 들여쓰기가 깨져있던 if문 블록과 이하 로직 전체의 인덴트를 정확히 맞췄습니다.
    if all_close_data.empty:
        print("❌ [DATA] Terminated: No valid data aggregated.")
        return

    if all_close_data.
