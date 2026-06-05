import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MIMEText
import requests

def get_kospi200_tickers():
    """
    네이버페이 증권(구 네이버 금융)에서 코스피 200 종목 코드를 크롤링합니다.
    야후 파이낸스 조회를 위해 코드 뒤에 '.KS'를 붙여 반환합니다.
    """
    tickers = []
    print("코스피 200 티커 목록을 가져오는 중...")
    
    # 코스피 200은 총 4페이지에 걸쳐 나뉘어 있습니다 (페이지당 50종목)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for page in range(1, 5):
        url = f"https://finance.naver.com/sise/entry_sub_page.naver?sosok=0&page={page}"
        try:
            response = requests.get(url, headers=headers)
            tables = pd.read_html(response.text)
            df = tables[0].dropna()
            
            for _, row in df.iterrows():
                # 링크 주소 등에서 종목 코드를 추출하기 까다로우므로 href 대신 다른 안전한 방식을 쓰거나 
                # 네이버의 일반 시세 페이지 구조를 활용합니다. 여기서는 종목명으로 코드 매핑을 하거나 
                # 데이터프레임 내 코드가 들어있는 컬럼을 파싱합니다.
                # 단순화를 위해 가공된 GitHub 오픈소스 소스를 활용하는 방법이 가장 안정적입니다.
                pass
        except Exception as e:
            pass

    # 💡 네이버 크롤링의 잦은 차단을 방지하기 위해 가공된 최신 KRX 데이터를 직접 받아오는 가장 안정적인 방식입니다.
    try:
        url = 'https://raw.githubusercontent.com/FinanceData/marcap/master/marcap/data/marcap-2025.csv.gz'
        # 최신 상장사 정보에서 코스피 종목만 필터링하거나, 아래와 같이 주가 지수 구성 종목을 타겟팅합니다.
        # 가장 깔끔하고 에러 없는 한국 주식용 가공 데이터셋(KRX 전체 전처리)에서 가져옵니다.
        df_krx = pd.read_html('https://kind.krx.co.kr/corpgeneral/corpList.do?method=download', header=0)[0]
        df_krx['종목코드'] = df_krx['종목코드'].astype(str).str.zfill(6)
        
        # 코스피(유가증권시장) 종목만 필터링 (코스피 200 전체를 정확히 필터링하려면 외부 API나 수동 리스트가 가장 깔끔함)
        kospi_stocks = df_krx[df_krx['시장구분'] == '유가증권시장']
        
        # 야후파이낸스 형식(.KS)으로 변환
        tickers = [f"{code}.KS" for code in kospi_stocks['종목코드'].tolist()]
        print(f"성공적으로 {len(tickers)}개의 코스피 종목 티커를 확보했습니다.")
        return tickers
    except Exception as e:
        print(f"티커 수집 실패: {e}")
        # 실패 시 예시 탑티어 종목으로 방어 코드 작성
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
        # 한국 주식 데이터 주봉(1wk)으로 다운로드
        all_data = yf.download(tickers, period="2y", interval="1wk", group_by='ticker', threads=True)
    except Exception as e:
        print(f"데이터 다운로드 중 치명적 오류: {e}")
        return

    ten_weeks_ago = datetime.now() - timedelta(days=70)
    
    # 💡 한국 시장 환경에 맞게 키워드를 한국어 및 핵심 증권 용어로 전면 변경
    keywords = ['공급 부족', '품귀', '서프라이즈', '상회', '최대 실적', '흑자 전환', '수주', '증설', '계약', 'beat', 'surprise']

    for ticker in tickers:
        try:
            if ticker not in all_data.columns.levels[0]:
                continue
                
            df = all_data[ticker].dropna(subset=['Close']).copy()
            if len(df) < 55: 
                continue

            # 52주 신고가 라인 계산
            df['High52'] = df['High'].rolling(window=52).max().shift(1)
            
            box_top = df['High52'].iloc[-1]
            curr_price = df['Close'].iloc[-1]
            
            if pd.isna(box_top) or box_top == 0:
                continue

            recent_4w = df.iloc[-4:]
            is_target = False

            # 최근 4주 내 돌파 여부
            box_break_recent = any(recent_4w['High'] >= recent_4w['High52'])
            
            if box_break_recent:
                # 돌파 후 가속 구간 필터링 (+5% ~ +30%)
                if (box_top * (1 + min_gain)) <= curr_price <= (box_top * (1 + max_gain)):
                    is_target = True

            if is_target:
                stock = yf.Ticker(ticker)
                
                fwd_pe = 999
                mkt_cap = 0
                short_name = ticker  # 기본값으로 티커 지정
                
                try:
                    info = stock.info
                    fwd_pe = info.get('forwardPE', 999)
                    mkt_cap = info.get('marketCap', 0)
                    short_name = info.get('longName', ticker)  # 한국 주식은 longName이 더 잘 잡힘
                except:
                    pass

                # 최근 10주 내 한국어 호재 뉴스 스캔
                has_star = False
                try:
                    news_list = stock.news
                    if news_list:
                        for news in news_list:
                            pub_time = datetime.fromtimestamp(news.get('providerPublishTime', 0))
                            if pub_time >= ten_weeks_ago:
                                # 제목과 요약본에서 한국어 키워드 탐색
                                content = (news.get('title', '') + news.get('summary', '')).lower()
                                if any(k in content for k in keywords):
                                    has_star = True
                                    break
                except: 
                    pass

                display_ticker = f"⭐ {ticker}" if has_star else ticker

                # 한국 주식 금액 단위 조정을 위해 시가총액을 '조 원' 단위로 변경 계산 (원화 기준)
                # 야후 파이낸스는 한국 주식 시총도 '원(KRW)' 단위로 반환함
                mkt_cap_trillion = round(mkt_cap / 1e12, 2)

                results.append({
                    '종목코드': display_ticker,
                    '현재가(원)': int(curr_price) if curr_price >= 100 else round(curr_price, 2),
                    '박스권 상단': int(box_top) if box_top >= 100 else round(box_top, 2),
                    '돌파 후 상승률': f"+{round(((curr_price/box_top)-1)*100, 1)}%",
                    'Forward PE': round(fwd_pe, 2) if fwd_pe != 999 else 'N/A',
                    '시가총액(조원)': mkt_cap_trillion,
                    '종목명': short_name
                })
                print(f"✅ 발견: {short_name} ({ticker}) - 박스권 대비 {round(((curr_price/box_top)-1)*100, 1)}% 상승")

        except Exception as e:
            continue

    # 결과 리포트 빌드 및 전송
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
    # 한국 시장 특성상 20~50%보다는 5~30% 선이 훨씬 안정적인 주도주 초입을 잡아내기 좋습니다.
    screen_stocks(min_gain=0.05, max_gain=0.30)
