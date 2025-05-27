import os
from datetime import datetime
import gspread
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Google Spreadsheetの設定 (Cloud Run / ローカル両対応のデバッグ強化版) ---

gc = None
sh = None
SPREADSHEET_NAME = 'ポーカートーナメント収支表'  # ご自身のスプレッドシート名

try:
    SECRET_FILE_PATH = "/gcp/secrets/poker-app-credentials/versions/latest"

    print("INFO: Initializing credentials...")
    if os.path.exists(SECRET_FILE_PATH):
        gc = gspread.service_account(filename=SECRET_FILE_PATH)
        print("INFO: Authenticated via mounted secret file (Cloud Run).")
    else:
        gc = gspread.service_account(filename='service-account.json')
        print("INFO: Authenticated via local json file (Local).")

    try:
        print(f"INFO: Trying to open spreadsheet: '{SPREADSHEET_NAME}'...")
        sh = gc.open(SPREADSHEET_NAME).sheet1
        print("INFO: Spreadsheet opened successfully.")
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"FATAL ERROR: Spreadsheet Not Found. The sheet named '{SPREADSHED_NAME}' was not found. Please CHECK:")
        print("1. The spreadsheet name in the code EXACTLY matches the real one.")
        print("2. The sheet has been SHARED with the service account as an 'Editor'.")
        sh = None  # Ensure sh is None on failure
    except gspread.exceptions.APIError as api_error:
        print(
            f"FATAL ERROR: Google API Error. This often means the 'Google Drive API' or 'Google Sheets API' is not enabled in your GCP project. Details: {api_error}")
        sh = None  # Ensure sh is None on failure

except Exception as e:
    print(f"FATAL ERROR: An unexpected error occurred during initialization: {e}")
    gc = None
    sh = None


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


if __name__ == '__main__':
    # This part is for local execution only
    # It won't be used in Cloud Run
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)