import sys
import requests
import json
from tqdm import tqdm
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Загружаем переменные окружения
load_dotenv()

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
    response.raise_for_status()  # Проверка на ошибки
    return response.json()['response']['items']

def get_largest_photo(photo):
    """Возвращает URL и размер самой большой версии фотографии."""
    sizes = photo['sizes']
    largest = max(sizes, key=lambda x: x['width'] * x['height'])
    return largest['url'], largest['type']

def download_image(url, file_path):
    """Скачивает изображение с использованием stream=True."""
    try:
        with requests.get(url, stream=True) as response:
            response.raise_for_status()  # Проверка на ошибки
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при скачивании изображения: {e}")
        raise

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
    response.raise_for_status()  # Проверка на ошибки
    upload_url = response.json()['href']
    with open(file_path, 'rb') as file:
        requests.put(upload_url, files={'file': file})

def upload_to_google_drive(file_path, creds):
    """Загружает файл на Google Drive."""
    service = build('drive', 'v3', credentials=creds)
    file_metadata = {'name': file_path.name}
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Файл {file_path.name} загружен на Google Drive с ID: {file.get('id')}")

def refresh_token(creds):
    """Обновляет access token с использованием refresh token."""
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        print("Токен успешно обновлен.")
    return creds


def refresh_vk_token(client_id, client_secret, refresh_token):
    """Обновляет access token с использованием refresh token."""
    url = "https://oauth.vk.com/access_token"
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, params=params)

    # Проверка на ошибки
    if response.status_code != 200:
        raise Exception(f"Ошибка при обновлении токена: {response.text}")

    # Парсинг JSON
    try:
        data = response.json()
        return data["access_token"], data["refresh_token"]
    except KeyError:
        raise Exception("Ответ API не содержит access_token или refresh_token.")
    except json.JSONDecodeError:
        raise Exception("Ошибка при парсинге JSON.")

def authenticate_google_drive():
    """Аутентификация в Google Drive с проверкой валидности токена."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        creds = refresh_token(creds)  # Обновляем токен, если он истек
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def get_file_name(photo):
    """Генерирует уникальное имя файла на основе лайков и даты загрузки."""
    likes = photo['likes']['count']
    date = datetime.fromtimestamp(photo['date']).strftime("%Y%m%d_%H%M%S")  # Дата из VK
    return f"{likes}_{date}.jpg"

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
        VK_CLIENT_ID = os.getenv('VK_CLIENT_ID')
        VK_CLIENT_SECRET = os.getenv('VK_CLIENT_SECRET')
        VK_REFRESH_TOKEN = os.getenv('VK_REFRESH_TOKEN')
        YANDEX_TOKEN = os.getenv('YANDEX_TOKEN')

        if not VK_CLIENT_ID or not VK_CLIENT_SECRET or not VK_REFRESH_TOKEN or not YANDEX_TOKEN:
            raise ValueError("Необходимые токены не найдены в переменных окружения. Убедитесь, что файл .env настроен правильно.")

        # Обновление access token
        try:
            VK_TOKEN, new_refresh_token = refresh_vk_token(VK_CLIENT_ID, VK_CLIENT_SECRET, VK_REFRESH_TOKEN)
            print("Access token успешно обновлен.")
        except Exception as e:
            print(f"Ошибка при обновлении токена: {e}")
            sys.exit(1)

        # Аутентификация в Google Drive
        creds = authenticate_google_drive()

        # Получение фотографий
        photos = get_vk_photos(USER_ID, VK_TOKEN, ALBUM_ID, PHOTOS_COUNT)
        photos_info = []

        for photo in tqdm(photos, desc="Обработка фотографий"):
            try:
                url, size = get_largest_photo(photo)
                file_name = get_file_name(photo)
                file_path = Path("photos") / file_name
                file_path.parent.mkdir(parents=True, exist_ok=True)  # Создаем директорию, если её нет

                # Скачивание фотографии
                download_image(url, file_path)

                # Загрузка на Яндекс.Диск
                upload_to_yandex_disk(file_path, YANDEX_TOKEN)

                # Загрузка на Google Drive
                upload_to_google_drive(file_path, creds)

                photos_info.append({
                    'file_name': file_name,
                    'size': size
                })

            except Exception as e:
                print(f"Ошибка при обработке фотографии: {e}")
            finally:
                # Удаление временного файла
                if file_path.exists():
                    file_path.unlink()

        # Сохранение информации в JSON
        with open('photos_info.json', 'w') as file:
            json.dump(photos_info, file, indent=4)

        print("Резервное копирование завершено успешно!")

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
