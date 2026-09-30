# 楽天市場から「買える物」の商品を集めて goods.json を作る（GitHub Actions で毎日1回動く）
# 必要な秘密の値（GitHub の Settings → Secrets に登録）：
#   RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY / RAKUTEN_AFFILIATE_ID
import json, os, sys, time, urllib.parse, urllib.request

# アプリの「買える物」の金額帯と、楽天で探すキーワード（金額は game.ts の GOODS と合わせる）
TIERS = [
    (10, '駄菓子'), (50, 'ガム'), (100, 'キーホルダー'), (150, '缶コーヒー'),
    (300, 'ボールペン'), (500, 'ハンドタオル'), (1000, '石鹸 ギフト'),
    (3000, 'モバイルバッテリー'), (5000, 'ワイヤレスイヤホン'), (10000, '財布'),
    (30000, '腕時計'), (50000, 'ロボット掃除機'), (100000, 'タブレット'), (300000, 'ノートパソコン'),
]
URL = 'https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601'
SITE = 'https://studio-akari.github.io'
PICK = 3  # 1つの金額帯につき何個残すか

def search(keyword, lo, hi):
    q = {
        'applicationId': os.environ['RAKUTEN_APP_ID'],
        'accessKey': os.environ['RAKUTEN_ACCESS_KEY'],
        'affiliateId': os.environ['RAKUTEN_AFFILIATE_ID'],
        'format': 'json', 'formatVersion': '2', 'keyword': keyword,
        'minPrice': str(lo), 'maxPrice': str(hi), 'sort': '-reviewCount',
        'availability': '1', 'imageFlag': '1', 'hits': '10',
    }
    req = urllib.request.Request(URL + '?' + urllib.parse.urlencode(q), headers={
        'Referer': SITE + '/kachimiru/', 'Origin': SITE, 'User-Agent': 'kachimiru-goods/1.0',
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def img(it):
    u = it.get('mediumImageUrls') or []
    if not u: return ''
    u = u[0] if isinstance(u[0], str) else u[0].get('imageUrl', '')
    return u.split('?')[0] + '?_ex=256x256'

def main():
    out, ok = {}, 0
    for price, kw in TIERS:
        lo = max(1, int(price * 0.8))
        try:
            data = search(kw, lo, price)
        except Exception as e:
            print(f'{price}円 {kw}: 失敗 {e}', file=sys.stderr)
            time.sleep(1.5); continue
        items = []
        for it in data.get('Items', []):
            it = it.get('Item', it)
            items.append({'name': it['itemName'][:60], 'price': it['itemPrice'], 'url': it.get('affiliateUrl') or it['itemUrl'], 'img': img(it)})
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
