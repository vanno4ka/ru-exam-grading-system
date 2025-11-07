from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import csv
import requests
import os
import time
from datetime import datetime
import traceback
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

CORS(app, origins=[
    'http://localhost:3000',
    'https://ru-exam-grading.onrender.com'
])

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


@app.route('/api/grade-init', methods=['POST'])
def grade_init():
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
        data = None
        headers = None

        for encoding in encodings:
            for delimiter in delimiters:
                try:
                    with open(upload_path, 'r', encoding=encoding) as f:
                        reader = csv.reader(f, delimiter=delimiter)
                        rows = list(reader)
                        if len(rows) > 0 and len(rows[0]) >= 7:
                            headers = rows[0]
                            data = rows[1:]
                            break
                except:
                    continue
            if data is not None:
                break

        if data is None or headers is None:
            return jsonify({'error': 'Не удалось прочитать CSV файл. Проверьте формат и кодировку.'}), 400

        if len(data) == 0:
            return jsonify({'error': 'CSV файл пустой'}), 400

        if len(headers) < 7:
            return jsonify({'error': f'CSV должен содержать минимум 7 колонок (A-G), найдено: {len(headers)}'}), 400

        session_id = f"{timestamp}_{original_filename}"
        session_path = os.path.join(UPLOAD_FOLDER, f"session_{session_id}.csv")

        with open(session_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(headers)
            writer.writerows(data)

        return jsonify({
            'sessionId': session_id,
            'totalRecords': len(data),
            'filename': original_filename
        }), 200

    except Exception as e:
        app.logger.error(f"Ошибка инициализации: {traceback.format_exc()}")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500


@app.route('/api/grade-batch', methods=['POST'])
def grade_batch():
    try:
        data = request.json
        session_id = data.get('sessionId')
        batch_start = data.get('batchStart', 0)
        batch_size = data.get('batchSize', 10)

        if not session_id:
            return jsonify({'error': 'Session ID не предоставлен'}), 400

        session_path = os.path.join(UPLOAD_FOLDER, f"session_{session_id}.csv")

        if not os.path.exists(session_path):
            return jsonify({'error': 'Сессия не найдена'}), 404

        # Читаем данные
        with open(session_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')
            headers = next(reader)
            all_rows = list(reader)

        total_records = len(all_rows)
        batch_end = min(batch_start + batch_size, total_records)
        batch_rows = all_rows[batch_start:batch_end]

        question_col_idx = 2
        text_col_idx = 6
        grade_col_idx = 5

        processed_count = 0
        error_count = 0
        scores = []

        for row in batch_rows:
            while len(row) < 7:
                row.append('')

            try:
                question_num = row[question_col_idx].strip()

                if not question_num:
                    row[grade_col_idx] = 'ERROR: Номер вопроса отсутствует'
                    error_count += 1
                    continue

                try:
                    question_num = int(question_num)
                except (ValueError, TypeError):
                    row[grade_col_idx] = f'ERROR: Некорректный номер вопроса ({question_num})'
                    error_count += 1
                    continue

                if question_num not in [1, 2, 3, 4]:
                    row[grade_col_idx] = f'ERROR: Номер вопроса должен быть 1-4 (получено: {question_num})'
                    error_count += 1
                    continue

                text = row[text_col_idx].strip()

                if not text:
                    row[grade_col_idx] = 'ERROR: Текст ответа отсутствует'
                    error_count += 1
                    continue

                model_uri = MODEL_URIS.get(question_num)
                if not model_uri:
                    row[grade_col_idx] = f'ERROR: Model URI не настроен для вопроса {question_num}'
                    error_count += 1
                    continue

                grade = call_yandex_gpt(model_uri, text)
                row[grade_col_idx] = grade

                try:
                    scores.append(float(grade))
                except (ValueError, TypeError):
                    pass

                processed_count += 1

            except Exception as e:
                row[grade_col_idx] = f'ERROR: {str(e)}'
                error_count += 1

        # Обновляем обработанные строки в файле
        all_rows[batch_start:batch_end] = batch_rows

        with open(session_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(headers)
            writer.writerows(all_rows)

        return jsonify({
            'processedInBatch': processed_count,
            'errorsInBatch': error_count,
            'batchStart': batch_start,
            'batchEnd': batch_end,
            'totalRecords': total_records,
            'completed': batch_end >= total_records
        }), 200

    except Exception as e:
        app.logger.error(f"Ошибка обработки батча: {traceback.format_exc()}")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500


@app.route('/api/grade-finalize', methods=['POST'])
def grade_finalize():
    try:
        data = request.json
        session_id = data.get('sessionId')

        if not session_id:
            return jsonify({'error': 'Session ID не предоставлен'}), 400

        session_path = os.path.join(UPLOAD_FOLDER, f"session_{session_id}.csv")

        if not os.path.exists(session_path):
            return jsonify({'error': 'Сессия не найдена'}), 404

        with open(session_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')
            headers = next(reader)
            all_rows = list(reader)

        grade_col_idx = 5

        total_records = len(all_rows)
        processed_count = 0
        error_count = 0
        scores = []

        for row in all_rows:
            if len(row) > grade_col_idx:
                grade_value = row[grade_col_idx]
                if grade_value and not grade_value.startswith('ERROR'):
                    processed_count += 1
                    try:
                        scores.append(float(grade_value))
                    except:
                        pass
                elif grade_value.startswith('ERROR'):
                    error_count += 1

        output_filename = f"graded_{session_id}"
        output_path = os.path.join(PROCESSED_FOLDER, output_filename)

        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(headers)
            writer.writerows(all_rows)

        try:
            os.remove(session_path)
            upload_path = os.path.join(UPLOAD_FOLDER, session_id)
            if os.path.exists(upload_path):
                os.remove(upload_path)
        except:
            pass

        avg_score = round(sum(scores) / len(scores), 2) if scores else 0

        return jsonify({
            'filename': output_filename,
            'recordsProcessed': processed_count,
            'totalRecords': total_records,
            'errorCount': error_count,
            'avgScore': avg_score
        }), 200

    except Exception as e:
        app.logger.error(f"Ошибка финализации: {traceback.format_exc()}")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500


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