from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import requests
import os
import time
from datetime import datetime
import traceback
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/textClassification"
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY', '')

MODEL_URIS = {
    1: os.getenv('MODEL_URI_Q1', ''),
    2: os.getenv('MODEL_URI_Q2', ''),
    3: os.getenv('MODEL_URI_Q3', ''),
    4: os.getenv('MODEL_URI_Q4', '')
}


def call_yandex_gpt(model_uri, text):
    if not YANDEX_API_KEY:
        raise ValueError("YANDEX_API_KEY не настроен")

    if not model_uri:
        raise ValueError("Model URI не настроен для данного вопроса")

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "modelUri": model_uri,
        "text": text
    }

    try:
        response = requests.post(YANDEX_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()

        if 'predictions' in result and len(result['predictions']) > 0:
            max_prediction = max(result['predictions'], key=lambda x: x.get('confidence', 0))
            label = max_prediction.get('label', 'ERROR')

            if label == 'grade-0':
                return '0'
            elif label == 'grade-1':
                return '1'
            elif label == 'grade-2':
                return '2'
            else:
                return label
        else:
            return 'ERROR'

    except requests.exceptions.Timeout:
        raise Exception("Таймаут при обращении к YandexGPT API")
    except requests.exceptions.ConnectionError:
        raise Exception("Ошибка подключения к YandexGPT API")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP ошибка {e.response.status_code}: {e.response.text}")
    except Exception as e:
        raise Exception(f"Ошибка при вызове YandexGPT: {str(e)}")


@app.route('/api/grade', methods=['POST'])
def grade_exam():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Файл не предоставлен'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400

        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Файл должен быть в формате CSV'}), 400

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_filename = file.filename
        upload_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{original_filename}")
        file.save(upload_path)

        encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'latin1']
        delimiters = [',', ';', '\t']
        df = None

        for encoding in encodings:
            for delimiter in delimiters:
                try:
                    df = pd.read_csv(upload_path, encoding=encoding, delimiter=delimiter, on_bad_lines='skip')
                    if df.shape[1] >= 7:
                        break
                except:
                    continue
            if df is not None and df.shape[1] >= 7:
                break

        if df is None:
            return jsonify({'error': 'Не удалось прочитать CSV файл. Проверьте формат и кодировку.'}), 400

        if df.empty:
            return jsonify({'error': 'CSV файл пустой'}), 400

        if df.shape[1] < 7:
            return jsonify({'error': f'CSV должен содержать минимум 7 колонок (A-G), найдено: {df.shape[1]}'}), 400

        question_col = df.columns[2]
        text_col = df.columns[6]
        grade_col = df.columns[5]

        if question_col not in df.columns:
            return jsonify({'error': f'Колонка C (вопрос) не найдена'}), 400
        if text_col not in df.columns:
            return jsonify({'error': f'Колонка G (текст) не найдена'}), 400

        df[grade_col] = None

        total_records = len(df)
        processed_count = 0
        error_count = 0
        scores = []
        start_time = time.time()

        for idx, row in df.iterrows():
            try:
                question_num = row[question_col]

                if pd.isna(question_num):
                    df.at[idx, grade_col] = 'ERROR: Номер вопроса отсутствует'
                    error_count += 1
                    continue

                try:
                    question_num = int(question_num)
                except (ValueError, TypeError):
                    df.at[idx, grade_col] = f'ERROR: Некорректный номер вопроса ({question_num})'
                    error_count += 1
                    continue

                if question_num not in [1, 2, 3, 4]:
                    df.at[idx, grade_col] = f'ERROR: Номер вопроса должен быть 1-4 (получено: {question_num})'
                    error_count += 1
                    continue

                text = row[text_col]

                if pd.isna(text) or str(text).strip() == '':
                    df.at[idx, grade_col] = 'ERROR: Текст ответа отсутствует'
                    error_count += 1
                    continue

                text = str(text).strip()

                model_uri = MODEL_URIS.get(question_num)
                if not model_uri:
                    df.at[idx, grade_col] = f'ERROR: Model URI не настроен для вопроса {question_num}'
                    error_count += 1
                    continue

                grade = call_yandex_gpt(model_uri, text)
                df.at[idx, grade_col] = grade

                try:
                    scores.append(float(grade))
                except (ValueError, TypeError):
                    pass

                processed_count += 1

            except Exception as e:
                df.at[idx, grade_col] = f'ERROR: {str(e)}'
                error_count += 1

        processing_time = round(time.time() - start_time, 2)

        output_filename = f"graded_{timestamp}_{original_filename}"
        output_path = os.path.join(PROCESSED_FOLDER, output_filename)

        df.to_csv(output_path, index=False, encoding='utf-8-sig', sep=';')

        avg_score = round(sum(scores) / len(scores), 2) if scores else 0

        result = {
            'filename': output_filename,
            'recordsProcessed': processed_count,
            'totalRecords': total_records,
            'errorCount': error_count,
            'avgScore': avg_score,
            'processingTime': f'{processing_time}s'
        }

        return jsonify(result), 200

    except Exception as e:
        app.logger.error(f"Критическая ошибка: {traceback.format_exc()}")
        return jsonify({'error': f'Критическая ошибка сервера: {str(e)}'}), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        file_path = os.path.join(PROCESSED_FOLDER, filename)

        if not os.path.exists(file_path):
            return jsonify({'error': 'Файл не найден'}), 404

        if not filename.startswith('graded_'):
            return jsonify({'error': 'Недопустимое имя файла'}), 403

        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        app.logger.error(f"Ошибка скачивания: {traceback.format_exc()}")
        return jsonify({'error': f'Ошибка при скачивании: {str(e)}'}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    config_status = {
        'api_key_configured': bool(YANDEX_API_KEY),
        'models_configured': {
            f'question_{i}': bool(MODEL_URIS[i]) for i in range(1, 5)
        }
    }
    return jsonify({'status': 'ok', 'config': config_status}), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)