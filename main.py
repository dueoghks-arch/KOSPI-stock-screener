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
    """FinanceDataReader를 이용해 코스피(KOSPI)와 코스닥(KOSDAQ) 전 종목의 티ker를 수집합니다."""
    print("⏳ 대한민국 전 시장(KOSPI/KOSDAQ) 종목 주식 정보 수집 중...")
    try:
        # 코스피, 코스닥 시장 데이터 가져오기
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        
        # 주식 및 주식예탁증서(DR) 형태의 일반 보통주 위주로 필터링 (우선주, ETF 등 제외하기 위함)
        # yfinance 형식에 맞게 코스피는 .KS, 코스닥은 .KQ를 붙여줍니다.
        kospi_tickers = [f"{row['Code']}.KS" for _, row in df_kospi.iterrows() if len(str(row['Code'])) == 6]
        kosdaq_tickers = [f"{row['Code']}.KQ" for _, row in df_kosdaq.iterrows() if len(str(row['Code'])) == 6]
        
        tickers = kospi_tickers + kosdaq_tickers
        print(f"✅ 국장 종목 수집 완료 (코스피: {len(kospi_tickers)}개, 코스닥: {len(kosdaq_tickers)}개, 총 {len(tickers)}개)")
        return tickers
    except Exception as e:
        print(f"⚠️ KRX 종목 수집 실패: {e}. 기본 대형주로 대체합니다.")
        # 실패 시 비상용 샘플 (삼성전자, SK하이닉스, 현대차, 네이버, 카카오 등)
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
        # 기존 SSL 465 통신 오류 문제를 예방하기 위해 구글 권장 STARTTLS(587) 방식으로 세팅
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, sender_email, msg.as_string())
        server.quit()
        print("📧 메일 발송 성공!")
    except Exception as e:
        print(f"❌ 메일 발송 실패: {e}")

def screen_krx_stocks():
    tickers = get_all_krx_tickers()
    results = []
    print(f"📊 총 {len(tickers)}개 종목 대상 국장 패턴 분석 시작...")
    
    # 한국 주식 시장 전 종목은 약 2500+개 이므로 청크 단위를 80개 정도로 조절하여 안정성 확보
    chunk_size = 80
    all_close_data = pd.DataFrame()
    
    print("⏳ yfinance로부터 3년 치 주봉 데이터 다운로드 중...")
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
            print(f"  > ⏳ {min(i + chunk_size, len(tickers))} / {len(tickers)} 종목 완료...")
            time.sleep(2.0) # 국장은 종목수가 많아 Rate Limit 방지를 위해 슬립 시간을 살짝 늘림
        except Exception as e:
            print(f"⚠️ 청크 데이터
