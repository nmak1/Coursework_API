
import sys
import requests
import json
from tqdm import tqdm
import os
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Попытка импортировать dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()  # Загружаем переменные окружения из .env
except ImportError:
    print("Библиотека 'python-dotenv' не установлена. Установите её с помощью 'pip install python-dotenv'.")
    sys.exit(1)

# Константы
VK_API_URL = 'https://api.vk.com/method'
YANDEX_DISK_API_URL = 'https://cloud-api.yandex.net/v1/disk/resources'
PHOTOS_COUNT = 5
SCOPES = ['https://www.googleapis.com/auth/drive']  # Права для Google Drive

def get_vk_photos(user_id, token, album_id='profile', count=5):
    """Получает фотографии из указанного альбома пользователя ВКонтакте."""
    params = {
        'access_token': token,
        'v': '5.131',
        'owner_id': user_id,
        'album_id': album_id,
        'extended': 1,
        'photo_sizes': 1,
        'count': count
    }
    response = requests.get(f'{VK_API_URL}/photos.get', params=params)
    if response.status_code == 200:
        return response.json()['response']['items']
    else:
        raise Exception(f"Ошибка при получении фотографий: {response.status_code}")

def get_largest_photo(photo):
    """Возвращает URL и размер самой большой версии фотографии."""
    sizes = photo['sizes']
    largest = max(sizes, key=lambda x: x['width'] * x['height'])
    return largest['url'], largest['type']

def upload_to_yandex_disk(file_path, yandex_token):
    """Загружает файл на Яндекс.Диск."""
    headers = {
        'Authorization': f'OAuth {yandex_token}'
    }
    params = {
        'path': file_path,
        'overwrite': True
    }
    response = requests.get(f'{YANDEX_DISK_API_URL}/upload', headers=headers, params=params)
    if response.status_code == 200:
        upload_url = response.json()['href']
        with open(file_path, 'rb') as file:
            requests.put(upload_url, files={'file': file})
    else:
        raise Exception(f"Ошибка при загрузке на Яндекс.Диск: {response.status_code}")

def upload_to_google_drive(file_path, creds):
    """Загружает файл на Google Drive."""
    service = build('drive', 'v3', credentials=creds)
    file_metadata = {'name': os.path.basename(file_path)}
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Файл {file_path} загружен на Google Drive с ID: {file.get('id')}")

def authenticate_google_drive():
    """Аутентификация в Google Drive."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def main():
    try:
        # Ввод данных
        USER_ID = input("Введите id VK: ")
        if not USER_ID.isdigit():
            raise ValueError("ID пользователя должен быть числом.")
        USER_ID = int(USER_ID)

        ALBUM_ID = input("Введите ID альбома (например, 'profile', 'wall', 'saved'): ")
        if not ALBUM_ID:
            ALBUM_ID = 'profile'  # По умолчанию

        # Загрузка токенов из переменных окружения
        VK_TOKEN = os.getenv('VK_TOKEN')
        YANDEX_TOKEN = os.getenv('YANDEX_TOKEN')

        if not VK_TOKEN or not YANDEX_TOKEN:
            raise ValueError("Токены не найдены в переменных окружения. Убедитесь, что файл .env настроен правильно.")

        # Аутентификация в Google Drive
        creds = authenticate_google_drive()

        # Получение фотографий
        photos = get_vk_photos(USER_ID, VK_TOKEN, ALBUM_ID, PHOTOS_COUNT)
        photos_info = []

        for photo in tqdm(photos, desc="Обработка фотографий"):
            try:
                url, size = get_largest_photo(photo)
                likes = photo['likes']['count']
                # Добавляем дату для уникальности имени файла
                date = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"{likes}_{date}.jpg"

                # Скачивание фотографии
                with open(file_name, 'wb') as file:
                    file.write(requests.get(url).content)

                # Загрузка на Яндекс.Диск
                upload_to_yandex_disk(file_name, YANDEX_TOKEN)

                # Загрузка на Google Drive
                upload_to_google_drive(file_name, creds)

                photos_info.append({
                    'file_name': file_name,
                    'size': size
                })

            except Exception as e:
                print(f"Ошибка при обработке фотографии: {e}")
            finally:
                # Удаление временного файла
                if os.path.exists(file_name):
                    os.remove(file_name)

        # Сохранение информации в JSON
        with open('photos_info.json', 'w') as file:
            json.dump(photos_info, file, indent=4)

        print("Резервное копирование завершено успешно!")

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()