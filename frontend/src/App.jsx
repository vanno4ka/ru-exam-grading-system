import React, { useState } from 'react';
import { Upload, Download, FileText, AlertCircle, CheckCircle, Info, XCircle } from 'lucide-react';

const API_URL = 'https://ru-exam-grading-system.onrender.com';
const BATCH_SIZE = 10;

const ExamGradingApp = () => {
  const [file, setFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingStatus, setProcessingStatus] = useState('');

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        setError('Пожалуйста, загрузите CSV файл');
        setFile(null);
        return;
      }

      if (selectedFile.size > 50 * 1024 * 1024) {
        setError('Размер файла не должен превышать 50 МБ');
        setFile(null);
        return;
      }

      setFile(selectedFile);
      setError(null);
      setResult(null);
      setUploadProgress(0);
      setProcessingStatus('');
    }
  };

  const processFile = async () => {
    if (!file) {
      setError('Файл не выбран');
      return;
    }

    setProcessing(true);
    setError(null);
    setResult(null);
    setUploadProgress(0);
    setProcessingStatus('Загрузка файла...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const initResponse = await fetch(`${API_URL}/api/grade-init`, {
        method: 'POST',
        body: formData,
      });

      if (!initResponse.ok) {
        const errorData = await initResponse.json().catch(() => ({ error: 'Ошибка инициализации' }));
        throw new Error(errorData.error || `Ошибка HTTP: ${initResponse.status}`);
      }

      const initData = await initResponse.json();
      const { sessionId, totalRecords } = initData;

      setProcessingStatus(`Обработка ${totalRecords} записей...`);

      let currentBatch = 0;
      let totalProcessed = 0;
      let totalErrors = 0;

      while (currentBatch < totalRecords) {
        const batchResponse = await fetch(`${API_URL}/api/grade-batch`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            sessionId: sessionId,
            batchStart: currentBatch,
            batchSize: BATCH_SIZE
          }),
        });

        if (!batchResponse.ok) {
          const errorData = await batchResponse.json().catch(() => ({ error: 'Ошибка обработки батча' }));
          throw new Error(errorData.error || `Ошибка HTTP: ${batchResponse.status}`);
        }

        const batchData = await batchResponse.json();

        totalProcessed += batchData.processedInBatch;
        totalErrors += batchData.errorsInBatch;
        currentBatch = batchData.batchEnd;

        const progress = Math.round((currentBatch / totalRecords) * 100);
        setUploadProgress(progress);
        setProcessingStatus(`Обработано ${currentBatch} из ${totalRecords} записей...`);

        await new Promise(resolve => setTimeout(resolve, 100));
      }

      setProcessingStatus('Завершение обработки...');

      const finalizeResponse = await fetch(`${API_URL}/api/grade-finalize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sessionId }),
      });

      if (!finalizeResponse.ok) {
        const errorData = await finalizeResponse.json().catch(() => ({ error: 'Ошибка финализации' }));
        throw new Error(errorData.error || `Ошибка HTTP: ${finalizeResponse.status}`);
      }

      const finalData = await finalizeResponse.json();

      setUploadProgress(100);
      setResult(finalData);
      setProcessingStatus('');

      if (finalData.errorCount > 0) {
        setError(`Внимание: ${finalData.errorCount} записей обработано с ошибками. Проверьте результирующий файл.`);
      }

    } catch (err) {
      if (err.name === 'TypeError' && err.message === 'Failed to fetch') {
        setError('Не удалось подключиться к серверу. Проверьте, что backend запущен.');
      } else if (err.message.includes('timeout')) {
        setError('Превышено время ожидания. Попробуйте файл меньшего размера или повторите позже.');
      } else {
        setError(err.message || 'Произошла ошибка при обработке файла');
      }
      setResult(null);
      setProcessingStatus('');
    } finally {
      setProcessing(false);
    }
  };

  const downloadResult = async () => {
    if (!result || !result.filename) {
      setError('Нет доступного файла для скачивания');
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/download/${result.filename}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Файл не найден' }));
        throw new Error(errorData.error || 'Ошибка при скачивании файла');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = result.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

    } catch (err) {
      setError(err.message || 'Ошибка при скачивании файла');
    }
  };

  const resetForm = () => {
    setFile(null);
    setResult(null);
    setError(null);
    setUploadProgress(0);
    setProcessingStatus('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-6 sm:p-8 mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-800 mb-2">
            Автоматическая оценка экзамена по русскому языку
          </h1>
          <p className="text-gray-600">
            Загрузите CSV файл для автоматической оценки
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-6 sm:p-8 mb-6">
          <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-6 sm:p-8 text-center hover:border-indigo-500 transition-colors">
            <Upload className="mx-auto mb-4 text-gray-400" size={48}/>
            <label className="cursor-pointer">
              <span className="text-indigo-600 hover:text-indigo-700 font-semibold">
                Выберите CSV файл
              </span>
              <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="hidden"
                  disabled={processing}
              />
            </label>
            <p className="text-sm text-gray-500 mt-2">Максимальный размер: 50 МБ</p>
            {file && (
                <div className="mt-4 flex items-center justify-center text-sm text-gray-600">
                  <FileText size={20} className="mr-2"/>
                  <span className="truncate max-w-xs">{file.name}</span>
                  <button
                      onClick={resetForm}
                      disabled={processing}
                      className="ml-3 text-red-500 hover:text-red-700"
                  >
                    <XCircle size={20}/>
                  </button>
                </div>
            )}
          </div>

          {error && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start">
                <AlertCircle className="text-red-500 mr-3 flex-shrink-0 mt-0.5" size={20}/>
                <span className="text-red-700 text-sm">{error}</span>
              </div>
          )}

          {processing && (
              <div className="mt-4">
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <span>{processingStatus || 'Обработка...'}</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                      className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                      style={{width: `${uploadProgress}%`}}
                  />
                </div>
                <p className="text-xs text-gray-500 mt-2 text-center">
                  Файл обрабатывается по {BATCH_SIZE} строк за раз. Пожалуйста, подождите...
                </p>
              </div>
          )}

          <button
              onClick={processFile}
              disabled={!file || processing}
              className="mt-6 w-full bg-indigo-600 text-white py-3 rounded-lg font-semibold hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {processing ? 'Обработка файла...' : 'Обработать файл'}
          </button>
        </div>

        {result && (
            <div className="bg-white rounded-lg shadow-lg p-6 sm:p-8 mb-6">
              <div className="flex items-center mb-6">
                <CheckCircle className="text-green-500 mr-3 flex-shrink-0" size={32}/>
                <h2 className="text-xl sm:text-2xl font-bold text-gray-800">
                  Оценка завершена
                </h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600 mb-1">Обработано успешно</div>
                  <div className="text-2xl font-bold text-green-600">{result.recordsProcessed}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600 mb-1">Всего записей</div>
                  <div className="text-2xl font-bold text-gray-800">{result.totalRecords}</div>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="text-sm text-gray-600 mb-1">Ошибок</div>
                  <div className={`text-2xl font-bold ${result.errorCount > 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {result.errorCount}
                  </div>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg sm:col-span-2">
                  <div className="text-sm text-gray-600 mb-1">Файл результата</div>
                  <div className="text-sm font-semibold text-gray-800 truncate">{result.filename}</div>
                </div>
              </div>

              <button
                  onClick={downloadResult}
                  className="w-full bg-green-600 text-white py-3 rounded-lg font-semibold hover:bg-green-700 transition-colors flex items-center justify-center"
              >
                <Download className="mr-2" size={20}/>
                Скачать файл с оценками
              </button>
            </div>
        )}

        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center">
            <Info className="mr-2 text-indigo-600" size={20}/>
            О системе оценки
          </h3>
          <ul className="space-y-2 text-sm text-gray-600">
            <li>• Для оценки используются дообученные классификаторы на базе YandexGPT 5 Lite.</li>
            <li>• Внимание: убедительная просьба запускать приложение только для оценки. Каждое обращение к моделям
              является платным.
            </li>
            <li>• При возникновении ошибки "Таймаут при обращении к YandexGPT API" просьба связаться с командой. Мы
              пополним аккаунт и Вы сможете протестировать работу приложения.
            </li>
          </ul>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="font-semibold text-blue-900 mb-2">Требования к CSV файлу:</h4>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• Кодировка: UTF-8 или Windows-1251.</li>
            <li>• Колонка "Оценка экзаменатора" не должна содержать значений.</li>
          </ul>
        </div>

      </div>
    </div>
  );
};

export default ExamGradingApp;