import httpx
import logging
import time

logger = logging.getLogger(__name__)

# CiNii Research API の基本設定
# all/projectsAndProducts/articles/data/books/dissertations/projects/researchers
BASE_URL = "https://cir.nii.ac.jp/opensearch/v2/articles"


def search_cinii_research(
        keyword,
        count=20,
        start=1,
        start_year=None,
        max_retries=3,
        appid=None
):
    """
    CiNii Researchを検索し、結果をJSONで返す関数。

    :param keyword: 検索キーワード
    :param count: 取得する件数 (最大200)
    :param start: 検索結果の開始位置 (ページ番号)
    :param start_year: 検索対象の開始年 (例: 2020)
    :param max_retries: 403エラー時の最大再試行回数
    :return: 検索結果のJSONデータ (辞書型)
    """

    # クエリパラメータを設定
    params = {
        'q': keyword,              # 検索キーワード
        'format': 'json',          # レスポンス形式をJSONに指定
        'count': count,            # 取得件数
        'sortorder': 0,
        'start': start,           # ページ番号 (デフォルト1)
    }

    if appid:
        params['appid'] = appid
    if start_year:
        params['from'] = start_year

    logger.debug(f"Searching: {keyword}")

    for attempt in range(max_retries):
        response = httpx.get(
            BASE_URL,
            params=params,
            timeout=10.0,
            follow_redirects=True
        )

        if response.status_code == 403:
            logger.warning(
                f"Got 403 Forbidden. Retrying in 10 seconds... "
                f"({attempt + 1}/{max_retries})"
            )
            time.sleep(10)
            continue

        # 403以外のエラーまたは成功した場合はループを抜ける
        break

    # HTTPステータスコードをチェック
    response.raise_for_status()

    return response.json()


def process_results(data):
    """
    CiNii ResearchのJSON結果から必要な情報を抽出して表示する関数。
    """
    if not data or 'items' not in data:
        print("検索結果が見つかりませんでした。")
        return

    print("\n--- 検索結果 ---")

    title = data.get('title', '')
    print(f'Title: {title}')
    total = data.get('opensearch:totalResults', '')
    print(f'Total: {total}')
    sindex = data.get('opensearch:startIndex', '')
    print(f'Start Index: {sindex}')
    nitems = data.get('opensearch:itemsPerPage', '')
    print(f'Items/Page: {nitems}')

    items = data.get('items', [])
    for i, item in enumerate(items):
        # pprint.pprint(item)
        try:
            title = item.get('title', '')
            url = item.get('link', dict()).get('@id', '')
            date = item.get('prism:publicationDate', '')

            x = item.get('prism:publicationName', '')
            if x:
                title = title + f', {x}'

            x = item.get('dc:publisher', '')
            if x:
                title = title + f', {x}'

            print(f"[{i+1}]")
            print(f"  Title: {title}")
            print(f"  Link:  {url}")
            print(f"  Date:  {date}")

        except (KeyError, IndexError) as e:
            logger.error(f'parse error: {e}')
            continue


if __name__ == "__main__":
    search_keyword = "CMOS"  # 検索したいキーワードを設定

    # 検索を実行
    search_data = search_cinii_research(search_keyword, 10)

    # 結果の処理と表示
    process_results(search_data)
