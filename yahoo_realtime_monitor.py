import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

# ==================== カスタマイズポイント ====================

# 1. 検索キーワード（複数設定可能）
SEARCH_KEYWORDS = ["偽マフティー"]

# 2. LINE Notify トークン（GitHub Secretsから取得）
LINE_NOTIFY_TOKEN = os.environ.get('LINE_NOTIFY_TOKEN', '')

# 3. 通知メッセージのフォーマット
def format_notification(keyword, new_posts_count, posts):
    """
    通知メッセージのフォーマットをカスタマイズ
    最新1件の内容を表示し、他の件数を表示
    """
    message = f"\n🔔 「{keyword}」の新しい投稿が{new_posts_count}件見つかりました！\n"
    message += f"時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    if posts:
        # 最新の1件のみ詳細を表示
        latest_post = posts[0]
        message += "\n--- 最新の投稿 ---\n"
        message += f"{latest_post['text']}\n"  # 全文表示（文字数制限したい場合は [:100] など追加）
        
        if latest_post.get('user'):
            message += f"投稿者: {latest_post['user']}\n"
        if latest_post.get('time'):
            message += f"時間: {latest_post['time']}\n"
        if latest_post.get('link'):
            message += f"リンク: {latest_post['link']}\n"
        
        # 2件以上ある場合、残りの件数を表示
        if new_posts_count > 1:
            message += f"\n他 {new_posts_count - 1} 件の新規投稿があります"
    
    return message

# 4. スクレイピングの設定
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# 5. 前回取得したデータの保存先
CACHE_FILE = 'last_posts.json'

# ==================== メイン処理 ====================

def get_yahoo_realtime_posts(keyword):
    """
    Yahoo!リアルタイム検索から投稿を取得
    """
    url = f"https://search.yahoo.co.jp/realtime/search?p={keyword}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        posts = []
        
        # Yahoo!リアルタイム検索のHTML構造に基づいて抽出
        # 注: Yahoo!がHTML構造を変更する可能性があるため、適宜調整が必要
        
        # 投稿アイテムを探す（セレクタは要調整）
        post_items = soup.select('.sw-Card')  # 実際の構造に応じて変更
        
        for item in post_items[:10]:  # 最新10件を取得（変更可能）
            try:
                # テキスト抽出
                text_elem = item.select_one('.sw-Card__title')
                text = text_elem.get_text(strip=True) if text_elem else ''
                
                # ユーザー名抽出
                user_elem = item.select_one('.sw-Card__author')
                user = user_elem.get_text(strip=True) if user_elem else ''
                
                # 時間抽出
                time_elem = item.select_one('.sw-Card__time')
                time = time_elem.get_text(strip=True) if time_elem else ''
                
                # リンク抽出
                link_elem = item.select_one('a[href]')
                link = link_elem['href'] if link_elem else ''
                
                if text:  # テキストがある場合のみ追加
                    posts.append({
                        'text': text,
                        'user': user,
                        'time': time,
                        'link': link,
                        'id': hash(text + user + time)  # 簡易的なID生成
                    })
            except Exception as e:
                print(f"投稿の解析エラー: {e}")
                continue
        
        return posts
    
    except Exception as e:
        print(f"スクレイピングエラー: {e}")
        return []


def load_cache():
    """
    前回取得したデータを読み込み
    """
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_cache(data):
    """
    今回取得したデータを保存
    """
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_line_notification(message):
    """
    LINE Notifyで通知を送信
    """
    if not LINE_NOTIFY_TOKEN:
        print("LINE_NOTIFY_TOKEN が設定されていません")
        return False
    
    url = 'https://notify-api.line.me/api/notify'
    headers = {'Authorization': f'Bearer {LINE_NOTIFY_TOKEN}'}
    data = {'message': message}
    
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        print("LINE通知送信成功")
        return True
    except Exception as e:
        print(f"LINE通知エラー: {e}")
        return False


def main():
    """
    メイン処理
    """
    print(f"監視開始: {datetime.now()}")
    
    cache = load_cache()
    new_cache = {}
    
    for keyword in SEARCH_KEYWORDS:
        print(f"\nキーワード「{keyword}」を検索中...")
        
        # 現在の投稿を取得
        current_posts = get_yahoo_realtime_posts(keyword)
        
        if not current_posts:
            print(f"「{keyword}」の投稿が取得できませんでした")
            continue
        
        # 前回のIDリストを取得
        previous_ids = set(cache.get(keyword, []))
        
        # 現在のIDリスト
        current_ids = {post['id'] for post in current_posts}
        
        # 新規投稿を検出
        new_ids = current_ids - previous_ids
        new_posts = [post for post in current_posts if post['id'] in new_ids]
        
        print(f"取得した投稿数: {len(current_posts)}")
        print(f"新規投稿数: {len(new_posts)}")
        
        # 新規投稿があれば通知
        if new_posts:
            message = format_notification(keyword, len(new_posts), new_posts)
            send_line_notification(message)
        else:
            print("新規投稿なし")
        
        # キャッシュを更新
        new_cache[keyword] = list(current_ids)
    
    # キャッシュを保存
    save_cache(new_cache)
    print(f"\n監視終了: {datetime.now()}")


if __name__ == "__main__":
    main()
