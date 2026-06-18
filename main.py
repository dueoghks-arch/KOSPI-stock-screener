import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
import time

def get_filtered_krx_tickers(kosdaq_percentile=50):
    """
    KOSPI 전 종목 및 KOSDAQ 시가총액 상위 50% 종목 선별 및 메타데이터 반환
    """
    print("⏳ [KRX] Fetching and filtering tickers...")
    try:
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        
        df_kosdaq = df_kosdaq.copy()
        df_kosdaq['MarCap'] = pd.to_numeric(df_kosdaq['MarCap'], errors='coerce')
        df_kosdaq = df_kosdaq.dropna(subset=['MarCap'])
        
        cutoff_value = df_kosdaq['MarCap'].quantile(1 - (kosdaq_percentile / 100))
        df_kosdaq_filtered = df_kosdaq[df_kosdaq['MarCap'] >= cutoff_value].copy()
        
        df_kospi['Code'] = df_kospi['Code'].astype(str).str.strip()
        df_kosdaq_filtered['Code'] = df_kosdaq_filtered['Code'].astype(str).str.strip()
        
        kospi_tickers = [f"{code}.KS" for code in df_kospi['Code'] if len(code) == 6]
        kosdaq_tickers = [f"{code}.KQ" for code in df_kosdaq_filtered['Code'] if len(code) == 6]
        
        tickers = kospi_tickers + kosdaq_tickers
        total_listing = pd.concat([df_kospi, df_kosdaq_filtered], axis=0)
        
        cutoff_in_eok = round(cutoff_value / 1e8, 1)
        print("✅ [KRX] 필터링 완료.")
        print(f"   > KOSPI: {len(kospi_tickers)}개 (전체)")
        print(f"   > KOSDAQ: {len(kosdaq_tickers)}개 (시총 상위 {kosdaq_percentile}%, 기준점: 약 {cutoff_in_eok:,}억 원 이상)")
        print(f"   > 총 대상 종목: {len(tickers)}개")
        
        return tickers, total_listing
        
    except Exception as e:
        print(f"⚠️ [KRX] Failed: {e}. Using fallback assets.")
        fallback_tickers = ['005930.KS', '000660.KS', '005380.KS', '035420.KS', '035720.KS']
        return fallback_tickers, pd.DataFrame()

def send_email(content, is_html=False):
    """구글 SMTP 서비스를 이용한 안정적인 이메일 발송 함수"""
    user = os.environ.get('EMAIL_USER')
    pw = os.environ.get('EMAIL_PASS')
    
    if not user or not pw:
        print("\n⚠️ [ENV] Secrets missing. Outputting directly to console:\n")
        print(content)
        return

    msg = MIMEText(content, 'html' if is_html else 'plain')
    msg['Subject'] = f"📈 [국내주식 전수조사] 주봉 이평선 돌파 종목 리포트 ({datetime.now().strftime('%Y-%m-%d')})"
    msg['From'] = user
    msg['To'] = user

    try:
        # 정상적으로 587 포트와 함께 괄호가 닫히고, try 블록 내부에 들어와야 합니다.
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(user, pw)
        server.sendmail(user, user, msg.as_string())
        server.quit()
        print("📧 [EMAIL] Report dispatched successfully!")
    except Exception as e:
        # try 문과 일치하는 레벨로 except 블록이 존재해야 문법 에러가 나지 않습니다.
        print(f"❌ [EMAIL] Dispatch failed: {e}")
        raise e
