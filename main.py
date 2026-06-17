import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MIMEText
import time

def get_all_krx_tickers():
    """FinanceDataReader를 이용해 코스피(KOSPI)와 코스닥(KOSDAQ) 전 종목 수집"""
    print("⏳ [KRX] Fetching tickers...")
    try:
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        
        # yfinance 형식(.KS, .KQ)으로 매핑
        kospi_tickers = [f"{row['Code']}.KS" for _, row in df_kospi.iterrows() if len(str(row['Code'])) == 6]
        kosdaq_tickers = [f"{row['Code']}.KQ" for _, row in df_kosdaq.iterrows() if len(str(row['Code'])) == 6]
        
        tickers = kospi_tickers + kosdaq_tickers
        print(f"✅ [KRX] Done. (KOSPI: {len(kospi_tickers)}, KOSDAQ: {len(kosdaq_tickers)}, Total: {len(tickers)})")
        return tickers
    except Exception as e:
        print(f"⚠️ [KRX] Failed: {e}. Using fallback assets.")
        return ['005930.KS', '000660.KS', '005380.KS', '035420.KS', '035720.KS']

def send_email(content, is_html=False):
    sender_email = os.environ.get('EMAIL_USER')
    sender_password = os.environ.get('EMAIL_PASS')
    if not sender_email or not sender_password:
        print("\n⚠️ [ENV] Secrets missing. Outputting directly to console:\n")
        print(content)
        return

    msg = MIMEText(content, 'html' if is_html else 'plain')
    msg['Subject'] = f"📈 [국내주식 전수조사] 3년 신고가 달성 및 바닥 다지기 완만 상승주 리포트 ({datetime.now().strftime('%Y-%m-%d')})"
    msg['From'] = sender_email
    msg['To'] = sender_email

    try:
        # 안전한 587 포트 및 암호화 방식 유지
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, sender_email, msg.as_string())
        server.quit()
        print("📧 [EMAIL] Report
