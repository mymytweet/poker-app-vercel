import os
import json  # jsonライブラリをインポート
from datetime import datetime
import gspread
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__, template_folder='../templates')
app.secret_key = os.urandom(24)

# --- Google Spreadsheetの設定 (Vercel環境変数対応) ---

gc = None
sh = None
SPREADSHEET_NAME = 'ポーカートーナメント収支表'

try:
    # Vercelの環境変数から認証情報を読み込む
    creds_json_str = os.getenv('GOOGLE_CREDENTIALS_JSON')
    if creds_json_str:
        creds_dict = json.loads(creds_json_str)
        gc = gspread.service_account_from_dict(creds_dict)
        print("INFO: Authenticated via Vercel Environment Variable.")
    else:
        # ローカル環境用のフォールバック (もしあれば)
        gc = gspread.service_account(filename='service-account.json')
        print("INFO: Authenticated via local json file.")

    sh = gc.open(SPREADSHEET_NAME).sheet1
    print("INFO: Spreadsheet opened successfully.")

except Exception as e:
    print(f"FATAL ERROR during initialization: {e}")
    # sh = None のままになる


# ... これ以降の @app.route('/') などの関数は変更なし ...
# ただし、一番下の if __name__ == '__main__': ... のブロックは削除してください。

# -------------------------------------------------------------------------

@app.route('/')
def index():
    """収支一覧とサマリー（ROIなど）を表示する"""
    if not sh:
        return "スプレッドシートに接続できませんでした。起動時のログを確認してください。", 500

    all_records = sh.get_all_records()

    # --- サマリー計算 ---
    total_buy_in = sum(int(r.get('バイイン') or 0) for r in all_records)
    total_prize = sum(int(r.get('賞金') or 0) for r in all_records)
    total_profit = total_prize - total_buy_in

    if total_buy_in > 0:
        roi = (total_profit / total_buy_in) * 100
    else:
        roi = 0
    # -------------------

    records_with_rows = []
    for i, record in enumerate(all_records):
        record['row_num'] = i + 2
        records_with_rows.append(record)

    records_with_rows.reverse()

    summary = {
        "total_buy_in": total_buy_in,
        "total_prize": total_prize,
        "total_profit": total_profit,
        "roi": roi,
        "entry_count": len(all_records)
    }

    return render_template('index.html', records=records_with_rows, summary=summary)


@app.route('/add', methods=['POST'])
def add_record():
    """新しい収支を記録する"""
    if not sh: return "スプレッドシートに接続できません。", 500

    try:
        buy_in = int(request.form.get('buy_in', 0))
        prize = int(request.form.get('prize', 0))
        event_name = request.form.get('event_name', '')
        memo = request.form.get('memo', '')
        balance = prize - buy_in
        today = datetime.now().strftime('%Y-%m-%d')

        new_row = [today, event_name, buy_in, prize, balance, memo]
        sh.append_row(new_row)

        flash('新しい記録を追加しました。', 'success')
    except Exception as e:
        flash(f'記録の追加に失敗しました: {e}', 'danger')

    return redirect(url_for('index'))


@app.route('/edit/<int:row_id>')
def edit_page(row_id):
    """編集ページを表示する"""
    if not sh: return "スプレッドシートに接続できません。", 500

    try:
        values = sh.row_values(row_id)
        if len(values) < 6:
            # Handle rows that might not have all columns
            values.extend([''] * (6 - len(values)))

        record = {
            '日付': values[0],
            'イベント名': values[1],
            'バイイン': values[2],
            '賞金': values[3],
            'メモ': values[5]
        }
        return render_template('edit.html', record=record, row_num=row_id)
    except Exception as e:
        flash(f'データの取得に失敗しました: {e}', 'danger')
        return redirect(url_for('index'))


@app.route('/update/<int:row_id>', methods=['POST'])
def update_record(row_id):
    """記録を更新する"""
    if not sh: return "スプレッドシートに接続できません。", 500

    try:
        buy_in = int(request.form.get('buy_in', 0))
        prize = int(request.form.get('prize', 0))
        event_name = request.form.get('event_name', '')
        memo = request.form.get('memo', '')
        date = request.form.get('date', '')

        balance = prize - buy_in

        updated_row = [date, event_name, buy_in, prize, balance, memo]
        sh.update(f'A{row_id}:F{row_id}', [updated_row])

        flash(f'記録（{row_id}行目）を更新しました。', 'success')
    except Exception as e:
        flash(f'更新に失敗しました: {e}', 'danger')

    return redirect(url_for('index'))


@app.route('/delete/<int:row_id>', methods=['POST'])
def delete_record(row_id):
    """記録を削除する"""
    if not sh: return "スプレッドシートに接続できません。", 500

    try:
        sh.delete_rows(row_id)
        flash(f'記録（{row_id}行目）を削除しました。', 'warning')
    except Exception as e:
        flash(f'削除に失敗しました: {e}', 'danger')

    return redirect(url_for('index'))


