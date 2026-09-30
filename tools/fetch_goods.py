# 楽天市場から「買える物」の商品を集めて goods.json を作る（GitHub Actions で毎日1回動く）
# 必要な秘密の値（GitHub の Settings → Secrets に登録）：
#   RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY / RAKUTEN_AFFILIATE_ID
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

# アプリの「買える物」の金額帯（game.ts の GOODS と合わせる）、楽天で探す言葉、
# 商品名に必ず入っていてほしい言葉（どれか1つ）、入っていたら外す言葉
TIERS = [
    (10, '駄菓子', ['駄菓子'], []),
    (50, 'ガム', ['ガム'], ['ギンガム', 'チャーム', '生地']),
    (100, 'キーホルダー', ['キーホルダー'], []),
    (150, '缶コーヒー', ['缶コーヒー', 'コーヒー'], []),
    (300, 'ボールペン', ['ボールペン'], ['替芯', '替え芯', '互換', 'リフィル', '芯']),
    (500, 'ハンドタオル', ['ハンドタオル', 'タオルハンカチ'], []),
    (1000, '石鹸', ['石鹸', 'せっけん', 'ソープ'], []),
    (3000, 'モバイルバッテリー', ['モバイルバッテリー'], ['ファン', '扇風機']),
    (5000, 'ワイヤレスイヤホン', ['イヤホン'], ['ケース', 'イヤーピース']),
    (10000, '財布', ['財布'], ['ケース', 'カバー']),
    (30000, '腕時計', ['腕時計', 'ウォッチ', 'WATCH'], ['ベルト', 'バンド']),
    (50000, 'ロボット掃除機', ['ロボット掃除機'], ['部品', 'フィルター', 'ブラシ']),
    (100000, 'タブレット', ['タブレット', 'iPad'], ['ケース', 'フィルム', 'カバー', 'ペン']),
    (300000, 'ノートパソコン', ['ノートパソコン', 'ノートPC', 'MacBook'], ['整備済']),
]
NG_ALL = ['中古', '訳あり', '訳有り', 'ジャンク', 'アウトレット']
URL = 'https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701'
SITE = 'https://studio-akari.github.io'
PICK = 3  # 1つの金額帯につき何個残すか

def search(keyword, lo, hi):
    q = {
        'applicationId': os.environ['RAKUTEN_APP_ID'],
        'accessKey': os.environ['RAKUTEN_ACCESS_KEY'],
        'affiliateId': os.environ['RAKUTEN_AFFILIATE_ID'],
        'format': 'json', 'formatVersion': '2', 'keyword': keyword,
        'minPrice': str(lo), 'maxPrice': str(hi), 'sort': '-reviewCount',
        'availability': '1', 'imageFlag': '1', 'hits': '30',
    }
    req = urllib.request.Request(URL + '?' + urllib.parse.urlencode(q), headers={
        'Referer': SITE + '/kachimiru/', 'Origin': SITE, 'User-Agent': 'kachimiru-goods/1.0',
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def clean(name):
    # 【〜】や［〜］の宣伝文句を外して短くする
    name = re.sub(r'[【\[［<＜(（][^】\]］>＞)）]{0,40}[】\]］>＞)）]', ' ', name)
    name = re.sub(r'[★☆◆◇■□●○♪！!]+', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()[:40]

def img(it):
    u = it.get('mediumImageUrls') or []
    if not u: return ''
    u = u[0] if isinstance(u[0], str) else u[0].get('imageUrl', '')
    return u.split('?')[0] + '?_ex=256x256'

def main():
    for k in ('RAKUTEN_APP_ID', 'RAKUTEN_ACCESS_KEY', 'RAKUTEN_AFFILIATE_ID'):
        v = os.environ.get(k, '')
        print(f'{k}: {"未登録" if not v else f"登録済み（{len(v)}文字）"}')
    out, ok = {}, 0
    for price, kw, must, ng in TIERS:
        lo = max(1, int(price * 0.8))
        try:
            data = search(kw, lo, price)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:300]
            print(f'{price}円 {kw}: 失敗 {e.code} {body}', file=sys.stderr)
            time.sleep(1.5); continue
        except Exception as e:
            print(f'{price}円 {kw}: 失敗 {e}', file=sys.stderr)
            time.sleep(1.5); continue
        items = []
        for it in data.get('Items', []):
            it = it.get('Item', it)
            nm = it['itemName']
            if not any(m in nm for m in must) or any(n in nm for n in ng + NG_ALL):
                continue
            items.append({'name': clean(nm) or nm[:40], 'price': it['itemPrice'], 'url': it.get('affiliateUrl') or it['itemUrl'], 'img': img(it)})
            if len(items) >= PICK: break
        out[str(price)] = items
        ok += 1 if items else 0
        print(f'{price}円 {kw}: {len(items)}件')
        time.sleep(1.5)  # 1秒に1回まで
    if ok == 0:
        sys.exit('1件も取れなかったので、前回の goods.json をそのまま残します')
    with open('goods.json', 'w', encoding='utf-8') as f:
        json.dump({'updated': int(time.time()), 'tiers': out}, f, ensure_ascii=False, separators=(',', ':'))

main()
