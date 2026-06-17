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
    KOSPI 전 종목 및 KOSDAQ 시가총액 상위 50% 종목만 선별하여 수집
    """
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
        print(f"   > KOSDAQ: {len(kosdaq_tickers)}개 (시총 상위 {kosdaq_percentile}%, 기준점: 약 {cutoff_in
