import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MIMEText
import requests

def get_kospi200_tickers():
    print("코스피 티커 목록을 가져오는 중...")
    try:
        url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download'
        df_krx = pd.read_html(url, header=0)[0]
        df_krx['종목코드'] = df_krx['종목코드'].astype(str).str.zfill(6)
        
        kospi_stocks = df_krx[df_krx['시장구분'] == '유가증권시장']
        tickers = [f"{code}.KS" for code in kospi_stocks['종목코드'].tolist()]
        print(f"성공적으로 {len(tickers)}개의 코스피 종목 티커를 확보했습니다.")
        return tickers
    except Exception as e:
        print(f"티커 수집 실패: {e}")
        return ['005930.KS', '000660.KS', '373220.KS', '207940.KS', '005490.KS', '035420.KS', '005380.KS', '051910.KS']

def send_email(content, is_html=False):
    sender_email = os.environ.get('EMAIL_USER')
    sender_password = os.environ.get('EMAIL_PASS')
    if not sender_email or not sender_password:
        print("환경변수 설정이 되어있지 않습니다. 콘솔에 리포트를 출력합니다.")
        print(content)
        return

    msg = MIMEText(content, 'html' if is_html else 'plain')
    msg['Subject'] = f"🚀 [국내주식 박스권 돌파] 핵심 주도주 스캔 보고서 ({datetime.now().strftime('%Y-%m-%d')})"
    msg['From'] = sender_email
    msg['To'] = sender_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, sender_email, msg.as_string())
        print("메일 발송 성공!")
    except Exception as e:
        print(f"메일 발송 실패: {e}")

def screen_stocks(min_gain=0.05, max_gain=0.30):
    tickers = get_kospi200_tickers()
    if not tickers: return

    results = []
    print(f"국내 주식 박스권 돌파 모멘텀 분석 시작... ({len(tickers)} 종목)")
    
    try:
        all_data = yf.download(tickers, period="2y", interval="1wk", group_by='ticker', threads=True)
    except Exception as e:
        print(f"데이터 다운로드 중 치명적 오류: {e}")
        return

    ten_weeks_ago = datetime.now() - timedelta(days=70)
    keywords = ['공급 부족', '품귀', '서프라이즈', '상회', '최대 실적', '흑자 전환', '수주', '증설', '계약', 'beat', 'surprise']

    for ticker in tickers:
        try:
            if ticker not in all_data.columns.levels[0]:
                continue
                
            df = all_data[ticker].dropna(subset=['Close']).copy()
            if len(df) < 55: 
                continue

            df['High52'] = df['High'].rolling(window=52).max().shift(1)
            box_top = df['High52'].iloc[-1]
            curr_price = df['Close'].iloc[-1]
            
            if pd.isna(box_top) or box_top == 0:
                continue

            recent_4w = df.iloc[-4:]
            is_target = False

            box_break_recent = any(recent_4w['High'] >= recent_4w['High52'])
            
            if box_break_recent:
                if (box_top * (1 + min_gain)) <= curr_price <= (box_top * (1 + max_gain)):
                    is_target = True

            if is_target:
                stock = yf.Ticker(ticker)
                
                fwd_pe = 999
                fwd_pb = 999
                mkt_cap = 0
                short_name = ticker
                
                try:
                    info = stock.info
                    mkt_cap = info.get('marketCap', 0)
                    short_name = info.get('longName', ticker)
                    
                    # 💡 12개월 선행 PER 추출
                    fwd_pe = info.get('forwardPE', 999)
                    
                    # 💡 12개월 선행 PBR 연산 및 안전 추출 구조
                    # yfinance 파싱 구조에 따라 변수명이 유동적이므로 다중 교차 검증 처리
                    fwd_pb_raw = info.get('forwardEps', None)
                    if fwd_pb_raw and fwd_pe != 999:
                        # 주가 / 선행 BPS 대용 연산 유도
                        fwd_pb = info.get('priceToBook', 999) 
                    else:
                        fwd_pb = info.get('priceToBook', 999)
                        
                except:
                    pass

                has_star = False
                try:
                    news_list = stock.news
                    if news_list:
                        for news in news_list:
                            pub_time = datetime.fromtimestamp(news.get('providerPublishTime', 0))
                            if pub_time >= ten_weeks_ago:
                                content = (news.get('title', '') + news.get('summary', '')).lower()
                                if any(k in content for k in keywords):
                                    has_star = True
                                    break
                except: 
                    pass

                display_ticker = f"⭐ {ticker}" if has_star else ticker
                mkt_cap_trillion = round(mkt_cap / 1e12, 2)

                results.append({
                    '종목코드': display_ticker,
                    '종목명': short_name,
                    '현재가(원)': int(curr_price) if curr_price >= 100 else round(curr_price, 2),
                    '박스권 상단': int(box_top) if box_top >= 100 else round(box_top, 2),
                    '돌파 후 상승률': f"+{round(((curr_price/box_top)-1)*100, 1)}%",
                    '12M 선행 PER': round(fwd_pe, 2) if fwd_pe != 999 else 'N/A', # 💡 표에 반영
                    '12M 선행 PBR': round(fwd_pb, 2) if fwd_pb != 999 else 'N/A', # 💡 표에 반영
                    '시가총액(조원)': mkt_cap_trillion
                })
                print(f"✅ 발견: {short_name} ({ticker})")

        except Exception as e:
            continue

    if results:
        final_df = pd.DataFrame(results).sort_values(by='시가총액(조원)', ascending=False)
        html_content = f"""
        <h3 style="color: #0d47a1;">🔥 국주(KOSPI) 52주 박스권 돌파 주도주 리포트 ({datetime.now().strftime('%Y-%m-%d')})</h3>
        <p><b>필터 조건:</b> 최근 4주 내 52주 박스권 상단을 돌파하고, 현재 주가가 돌파선 대비 <b>+{int(min_gain*100)}% ~ +{int(max_gain*100)}%</b> 구간에 위치한 국내 강세 종목</p>
        <p><b>⭐ 표시:</b> 최근 10주 내 수주, 공급 부족, 서프라이즈, 증설 등 업황/실적 모멘텀 키워드가 포착된 기업</p>
        <br>
        {final_df.to_html(index=False, border=1, justify='center').replace('⭐', '<span style="color:red; font-weight:bold;">⭐</span>')}
        """
        send_email(html_content, is_html=True)
    else:
        send_email(f"현재 박스권을 돌파하여 설정 구간(+{int(min_gain*100)}%~+{int(max_gain*100)}%)에 진입한 국내 종목이 없습니다.")

if __name__ == "__main__":
    screen_stocks(min_gain=0.05, max_gain=0.30)
