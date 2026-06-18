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
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(user, pw)
        server.sendmail(user, user, msg.as_string())
        server.quit()
        print("📧 [EMAIL] Report dispatched successfully!")
    except Exception as e:
        print(f"❌ [EMAIL] Dispatch failed: {e}")
        raise e

# 💡 여기서부터가 누락되었던 핵심 실행 코드입니다!
def screen_krx_stocks():
    tickers, krx_listing = get_filtered_krx_tickers(kosdaq_percentile=50)
    results = []
    print(f"📊 [SCAN] Analyzing {len(tickers)} assets under Moving Average Crossover criteria...")
    
    chunk_size = 80
    all_close_data = pd.DataFrame()
    
    print("⏳ [DATA] Downloading 5-year weekly chart history via yfinance...")
    for i in range(0, len(tickers), chunk_size):
        chunk_tickers = tickers[i:i+chunk_size]
        try:
            chunk_data = yf.download(chunk_tickers, period="5y", interval="1wk", group_by='column', progress=False, timeout=40)
            if not chunk_data.empty and 'Close' in chunk_data.columns:
                chunk_close = chunk_data['Close']
                if all_close_data.empty:
                    all_close_data = chunk_close
                else:
                    all_close_data = pd.concat([all_close_data, chunk_close], axis=1)
            print(f"  > ⏳ Progress: {min(i + chunk_size, len(tickers))} / {len(tickers)} completed...")
            time.sleep(1.5)
        except Exception as e:
            continue

    if all_close_data.empty:
        print("❌ [DATA] Terminated: No valid data aggregated.")
        return

    if all_close_data.index.tz is not None:
        all_close_data.index = all_close_data.index.tz_localize(None)

    name_dict = pd.Series(krx_listing.Name.values, index=krx_listing.Code.values).to_dict() if not krx_listing.empty else {}
    marcap_dict = pd.Series(krx_listing.MarCap.values, index=krx_listing.Code.values).to_dict() if not krx_listing.empty else {}

    for ticker in all_close_data.columns:
        try:
            series_close = all_close_data[ticker].dropna()
            if len(series_close) <= 200: continue 
            
            ma5 = series_close.rolling(window=5).mean()
            ma30 = series_close.rolling(window=30).mean()
            ma200 = series_close.rolling(window=200).mean()
            
            cross_30 = (ma5 > ma30) & (ma5.shift(1) <= ma30.shift(1))
            cross_200 = (ma5 > ma200) & (ma5.shift(1) <= ma200.shift(1))
            
            recent_cross_30 = cross_30.iloc[-4:].any()
            recent_cross_200 = cross_200.iloc[-4:].any()
            
            if not (recent_cross_30 or recent_cross_200): continue
                
            breakthrough_type = []
            if recent_cross_30: breakthrough_type.append("5주-30주")
            if recent_cross_200: breakthrough_type.append("5주-200주")
            
            curr_price = series_close.iloc[-1]
            code_only = ticker.split('.')[0]
            kor_name = name_dict.get(code_only, ticker)
            raw_marcap = marcap_dict.get(code_only, 0)
            
            results.append({
                '종목코드': code_only, '종목명': kor_name,
                '현재가(원)': f"{int(curr_price):,}",
                '돌파 유형 (최근 4주)': " / ".join(breakthrough_type),
                '5주 이평': f"{int(ma5.iloc[-1]):,}",
                '30주 이평': f"{int(ma30.iloc[-1]):,}" if not pd.isna(ma30.iloc[-1]) else "-",
                '200주 이평': f"{int(ma200.iloc[-1]):,}" if not pd.isna(ma200.iloc[-1]) else "-",
                '시가총액(천억원)': round(raw_marcap / 1e11, 1) if raw_marcap else 0
            })
        except Exception:
            continue

    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"📊 [DEBUG] 필터링 조건 통과한 최종 종목 수: {len(results)}개")

    if results:
        final_df = pd.DataFrame(results).sort_values(by='시가총액(천억원)', ascending=False)
        table_html = final_df.to_html(index=False, border=1, justify='center').replace('border="1"', 'style="border-collapse: collapse; width: 100%; text-align: center; font-size: 14px;" border="1"')
        
        html_content = f"<h3>🇰🇷 주봉 이평선 돌파 보고서 ({today_str})</h3><br>{table_html}"
        send_email(html_content, is_html=True)
    else:
        send_email(f"<h3>⚠️ 국장 스캐너 알림 ({today_str})</h3><p>최근 4주 내 돌파 종목이 없습니다.</p>", is_html=True)

if __name__ == "__main__":
    screen_krx_stocks()
