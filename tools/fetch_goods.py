# 楽天市場から「買える物」の商品を集めて goods.json を作る（GitHub Actions で毎日1回動く）
# 必要な秘密の値（GitHub の Settings → Secrets に登録）：
#   RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY / RAKUTEN_AFFILIATE_ID
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

# アプリの「買える物」の金額帯（game.ts の GOODS と合わせる）。300円未満は楽天の商品を出さない。
# まず楽天市場の総合ランキング（約1000位まで）から、その金額で買える売れ筋を選ぶ。
# ランキングに無い金額帯（高い物など）だけ、ここに書いた言葉で検索して、レビューの多い順に選ぶ
TIERS = [
    (300, 'ボールペン'), (500, 'ハンドタオル'), (1000, '石鹸'), (3000, 'モバイルバッテリー'),
    (5000, 'ワイヤレスイヤホン'), (10000, '財布'), (30000, '腕時計'), (50000, 'ロボット掃除機'),
    (100000, 'iPad'), (300000, 'ノートパソコン'),
]
# 子どもも使うアプリなので、成人向けの物だけは外す
NG_ALL = ['アダルト', '成人向け', '18禁', 'R18', 'R-18', '大人のおもちゃ', 'ラブグッズ']
RANK_URL = 'https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601'
RANK_PAGES = 34  # 1ページ30件 × 34 ＝ 約1000位まで
URL = 'https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701'
SITE = 'https://studio-akari.github.io'
PICK = 5  # 1つの金額帯につき何個残すか（アプリで日替わり表示）

def get(url, q):
    q = dict(q, applicationId=os.environ['RAKUTEN_APP_ID'], accessKey=os.environ['RAKUTEN_ACCESS_KEY'],
             affiliateId=os.environ['RAKUTEN_AFFILIATE_ID'], format='json', formatVersion='2')
    req = urllib.request.Request(url + '?' + urllib.parse.urlencode(q), headers={
        'Referer': SITE + '/kachimiru/', 'Origin': SITE, 'User-Agent': 'kachimiru-goods/1.0',
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def items_of(data):
    return [it.get('Item', it) for it in data.get('Items', [])]

def search(keyword, lo, hi):
    return get(URL, {'keyword': keyword, 'minPrice': str(lo), 'maxPrice': str(hi), 'sort': '-reviewCount',
                     'availability': '1', 'imageFlag': '1', 'hits': '30'})

def clean(name):
    # 【〜】や「楽天1位」、クーポン・セールなどの宣伝文句を外して短くする
    name = re.sub(r'[【\[［<＜《(（][^】\]］>＞》)）]{0,40}[】\]］>＞》)）]', ' ', name)
    name = re.sub(r'[★☆◆◇■□●○♪！!&＆]+', ' ', name)
    name = re.sub(r'「[^」]{0,20}(楽天|位|受賞|最安|クーポン|OFF|オフ)[^」]{0,20}」', ' ', name)
    name = re.sub(r'\S*(クーポン|最安|セール|限定|OFF|オフ|ポイント|P\d+倍|\d[\d,]*円|楽天\d*位|\d+冠|ランキング|受賞)\S*', ' ', name)
    return re.sub(r'\s+', ' ', name).strip(' /／・|｜')[:40]

def img(it):
    u = it.get('mediumImageUrls') or []
    if not u: return ''
    u = u[0] if isinstance(u[0], str) else u[0].get('imageUrl', '')
    return u.split('?')[0] + '?_ex=256x256'

def entry(it):
    return {'name': clean(it['itemName']) or it['itemName'][:40], 'price': it['itemPrice'],
            'url': it.get('affiliateUrl') or it['itemUrl'], 'img': img(it)}

def ok(it):
    return it.get('itemPrice') and it.get('mediumImageUrls') and not any(n in it['itemName'] for n in NG_ALL)

def main():
    for k in ('RAKUTEN_APP_ID', 'RAKUTEN_ACCESS_KEY', 'RAKUTEN_AFFILIATE_ID'):
        v = os.environ.get(k, '')
        print(f'{k}: {"未登録" if not v else f"登録済み（{len(v)}文字）"}')

    # 1) 総合ランキングを集める（順位の高い順）
    ranking = []
    for page in range(1, RANK_PAGES + 1):
        try:
            ranking += items_of(get(RANK_URL, {'page': str(page)}))
        except urllib.error.HTTPError as e:
            print(f'ランキング {page}ページ目: 失敗 {e.code} {e.read().decode("utf-8", "replace")[:200]}', file=sys.stderr)
            if page == 1: break
        except Exception as e:
            print(f'ランキング {page}ページ目: 失敗 {e}', file=sys.stderr)
        time.sleep(1.2)
    print(f'ランキング：{len(ranking)}件')

    out, filled = {}, 0
    for price, kw in TIERS:
        lo = int(price * 0.8)
        picks, seen = [], set()
        for it in ranking:
            if ok(it) and lo <= it['itemPrice'] <= price and it['itemName'] not in seen:
                seen.add(it['itemName']); picks.append(entry(it))
                if len(picks) >= PICK: break
        src = 'ランキング'
        # 2) ランキングに無ければ、言葉で検索（レビューの多い順）
        if len(picks) < PICK:
            try:
                for it in items_of(search(kw, lo, price)):
                    if ok(it) and it['itemName'] not in seen:
                        seen.add(it['itemName']); picks.append(entry(it))
                        if len(picks) >= PICK: break
                src += '＋検索' if picks else ''
            except urllib.error.HTTPError as e:
                print(f'{price}円 検索: 失敗 {e.code} {e.read().decode("utf-8", "replace")[:200]}', file=sys.stderr)
            except Exception as e:
                print(f'{price}円 検索: 失敗 {e}', file=sys.stderr)
            time.sleep(1.2)
        out[str(price)] = picks
        filled += 1 if picks else 0
        print(f'{price}円: {len(picks)}件（{src}） ' + ' / '.join(x['name'][:20] for x in picks))
    if filled == 0:
        sys.exit('1件も取れなかったので、前回の goods.json をそのまま残します')
    with open('goods.json', 'w', encoding='utf-8') as f:
        json.dump({'updated': int(time.time()), 'tiers': out}, f, ensure_ascii=False, separators=(',', ':'))

main()
