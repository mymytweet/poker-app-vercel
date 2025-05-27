# ベースイメージを、軽量版(-slim)ではない標準のPython環境に変更します。
# これにより、ライブラリのインストールが安定します。
FROM python:3.11

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係ファイルをコピー
COPY requirements.txt .

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコピー
COPY . .

# Gunicornでアプリを起動する設定
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app