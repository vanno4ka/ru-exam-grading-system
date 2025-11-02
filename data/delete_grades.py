import pandas as pd

input_file = 'DataSet.csv'

try:
    df = pd.read_csv(input_file, encoding='utf-8', on_bad_lines='skip')
except:
    try:
        df = pd.read_csv(input_file, encoding='cp1251', on_bad_lines='skip')
    except:
        df = pd.read_csv(input_file, encoding='utf-8', sep=';', on_bad_lines='skip')

print(f"Количество столбцов: {len(df.columns)}")
print(f"Названия столбцов: {list(df.columns)}")
print(f"\nПервые 3 строки:\n{df.head(3)}")

if len(df.columns) < 7:
    print("\n\nПопытка прочитать с разделителем ';'...")
    try:
        df = pd.read_csv(input_file, sep=';', encoding='utf-8', on_bad_lines='skip')
    except:
        df = pd.read_csv(input_file, sep=';', encoding='cp1251', on_bad_lines='skip')

    print(f"Количество столбцов: {len(df.columns)}")
    print(f"Названия столбцов: {list(df.columns)}")
    print(f"\nПервые 3 строки:\n{df.head(3)}")

if len(df.columns) >= 7:
    question_ids = {
        1: 31053500,
        2: 30987676,
        3: 31175639,
        4: 31471997
    }

    column_id = df.columns[1]
    column_c = df.columns[2]
    column_f = df.columns[5]

    selected_rows = []
    for question_num, question_id in question_ids.items():
        df_question = df[df[column_id] == question_id]
        if not df_question.empty:
            selected_rows.append(df_question.iloc[0])
            print(f'Вопрос {question_num} (ID {question_id}): найден')
        else:
            print(f'Вопрос {question_num} (ID {question_id}): НЕ НАЙДЕН')

    result_df = pd.DataFrame(selected_rows)

    if column_f in result_df.columns:
        result_df[column_f] = ''
        print(f'\nЗначения в столбце "{column_f}" очищены')

    output_file = 'TestDataSetNoGrades.csv'
    result_df.to_csv(output_file, index=False, encoding='utf-8', sep=';')

    print(f'\nФайл "{output_file}" успешно создан!')
    print(f'Всего строк в файле: {len(result_df)}')
    print(f'\nСтолбцы: {list(result_df.columns)}')
    print(f'\nСодержимое файла:\n{result_df}')

else:
    print("\nОшибка: недостаточно столбцов в файле!")