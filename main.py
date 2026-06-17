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
    """FinanceDataReader를 이용해 코스피(KOSPI)와 코스닥(KOSDAQ) 전 종목의 티커를 수집합니다."""
    print("⏳ 대한민국 전 시장(KOSPI/KOSDAQ) 종목 주식 정보 수집 중...")
    try:
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        
        # 보통주 위주로 필터링하여 yfinance 형식(.KS, .KQ)으로 변환
        kospi_tickers = [f"{row['Code']}.KS" for _, row in df_kospi.iterrows() if len(str(row['Code'])) == 6]
        kosdaq_tickers = [f"{row['Code']}.KQ" for _, row in df_kosdaq.iterrows() if len(str(row['Code'])) == 6]
        
        tickers = kospi_tickers + kosdaq_tickers
        print(f"✅ 국장 종목 수집 완료 (코스피: {len(kospi_tickers)}개, 코스닥: {len(kosdaq_tickers)}개, 총 {len(tickers)}개)")
        return tickers
    except Exception as e:
        print(f"⚠️ KRX 종목 수집 실패: {e}. 기본 대형주로 대체합니다.")
        return ['005930.KS', '000660.KS', '005380.KS', '035420.KS', '035720.KS']

def send_email(content, is_html=False):
    sender_email = os.environ.get('EMAIL_USER')
    sender_password = os.environ.get('EMAIL_PASS')
    if not sender_email or not sender_password:
        print("\n⚠️ 환경변수(EMAIL_USER, EMAIL_PASS) 설정이 되어있지 않습니다. 콘솔에 리포트를 출력합니다.\n")
        print(content)
        return

    msg = MIMEText(content, 'html' if is_html else 'plain')
    msg['Subject'] = f"📈 [국내주식 전수조사] 3년 신고가 달성 및 바닥 다지기 완만 상승주 리포트 ({datetime.now().strftime('%Y-%m-%d')})"
    msg['From'] = sender_email
    msg['To'] = sender_email

    try:
        # 깃허브 액션 환경에서 가장 안정적인 587 포트 STARTTLS 방식으로 설정
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender
