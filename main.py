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
    print("⏳ [KRX] Fetching and filtering tickers...")
    try:
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        
        df_kospi.columns = [col.upper() for col in df_kospi.columns]
        df_kosdaq.columns = [col.upper() for col in df_kosdaq.columns]
        
        df_kosdaq = df_kosdaq.copy()
        df_kosdaq['MARCAP'] = pd.to_numeric(df_kosdaq['MARCAP'], errors='coerce')
        df_kosdaq = df_kosdaq.dropna(subset=['MARCAP'])
        
        cutoff_value = df_kosdaq['MARCAP'].quantile(1 - (kosdaq_percentile / 100))
        df_kosdaq_filtered = df_kosdaq[df_kosdaq['MARCAP'] >= cutoff_value].copy()
        
        df_kospi['CODE'] = df_kospi['CODE'].astype(str).str.strip()
        df_kosdaq_filtered['CODE'] = df_kosdaq_filtered['CODE'].astype(str).str.strip()
        
        kospi_tickers = [f"{code}.KS" for code in df_kospi['CODE'] if len(code) == 6]
        kosdaq_tickers = [f"{code}.KQ" for code in df_kosdaq_filtered['CODE'] if len(code) == 6]
        
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
        fallback_df = pd.DataFrame({
            'CODE': ['005930', '000660', '005380', '035420', '035720'],
            'NAME': ['삼성전자', 'SK하이닉스', '현대차', 'NAVER', '카카오'],
            'MARCAP': [400000000000000, 100000000000000, 50000000000 ]
