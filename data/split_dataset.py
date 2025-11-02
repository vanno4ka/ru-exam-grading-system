import pandas as pd
from sklearn.model_selection import train_test_split

input_file = 'DataSet.csv'

try:
    df = pd.read_csv(input_file, encoding='utf-8', on_bad_lines='skip')
except:
    try:
        df = pd.read_csv(input_file, encoding='cp1251', on_bad_lines='skip')
    except:
        df = pd.read_csv(input_file, encoding='utf-8', sep=';', on_bad_lines='skip')

if len(df.columns) < 7:
    print("\n\nПопытка прочитать с разделителем ';'...")
    try:
        df = pd.read_csv(input_file, sep=';', encoding='utf-8', on_bad_lines='skip')
    except:
        df = pd.read_csv(input_file, sep=';', encoding='cp1251', on_bad_lines='skip')

if len(df.columns) >= 7:
    column_c = df.columns[2]
    column_d = df.columns[6]
    column_f = df.columns[5]

    for i in range(1, 5):
        df_question = df[df[column_c] == i]

        result = []
        for _, row in df_question.iterrows():
            grade = row[column_f]

            if i in [1, 3]:
                item = {
                    "text": row[column_d],
                    "grade-0": 1 if grade == 0 else 0,
                    "grade-1": 1 if grade == 1 else 0
                }
            else:
                item = {
                    "text": row[column_d],
                    "grade-0": 1 if grade == 0 else 0,
                    "grade-1": 1 if grade == 1 else 0,
                    "grade-2": 1 if grade == 2 else 0
                }

            result.append(item)

        train_data, val_data = train_test_split(result, test_size=0.1, random_state=42)

        train_file = f'Q{i}_train.jsonl'
        with open(train_file, 'w', encoding='utf-8') as f:
            for item in train_data:
                f.write(pd.Series(item).to_json(force_ascii=False) + '\n')

        val_file = f'Q{i}_val.jsonl'
        with open(val_file, 'w', encoding='utf-8') as f:
            for item in val_data:
                f.write(pd.Series(item).to_json(force_ascii=False) + '\n')

        print(f'Вопрос {i}: train={len(train_data)} строк, val={len(val_data)} строк')

    print('\nРазделение завершено успешно!')
    print(f'Всего обработано строк: {len(df[df[column_c].isin([1, 2, 3, 4])])}')

    for i in range(1, 5):
        count = len(df[df[column_c] == i])
        print(f'Вопрос {i}: {count} строк')
else:
    print("\nОшибка: недостаточно столбцов в файле!")
