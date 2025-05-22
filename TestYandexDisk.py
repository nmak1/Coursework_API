import os
import unittest

import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()  # Загружаем переменные окружения из .env файла


class TestYandexDiskAPI(unittest.TestCase):
    BASE_URL = "https://cloud-api.yandex.net/v1/disk/resources"
    TOKEN = os.getenv("YANDEX_DISK_TOKEN")
    HEADERS = {"Authorization": f"OAuth {TOKEN}"}
    TEST_FOLDER = "test_folder"

    def setUp(self):
        """Удаляем тестовую папку перед каждым тестом, если она существует"""
        requests.delete(f"{self.BASE_URL}?path={self.TEST_FOLDER}", headers=self.HEADERS)

    def test_create_folder_success(self):
        """Тест успешного создания папки"""
        response = requests.put(
            f"{self.BASE_URL}?path={self.TEST_FOLDER}",
            headers=self.HEADERS
        )

        # Проверяем код ответа
        self.assertEqual(response.status_code, 201)

        # Проверяем, что папка действительно создалась
        check_response = requests.get(
            f"{self.BASE_URL}?path={self.TEST_FOLDER}",
            headers=self.HEADERS
        )
        self.assertEqual(check_response.status_code, 200)

    def test_create_folder_already_exists(self):
        """Тест попытки создания уже существующей папки"""
        # Сначала создаем папку
        requests.put(
            f"{self.BASE_URL}?path={self.TEST_FOLDER}",
            headers=self.HEADERS
        )

        # Пытаемся создать снова
        response = requests.put(
            f"{self.BASE_URL}?path={self.TEST_FOLDER}",
            headers=self.HEADERS
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("уже существует", response.json().get("message", ""))

    def test_create_folder_unauthorized(self):
        """Тест создания папки без авторизации"""
        response = requests.put(
            f"{self.BASE_URL}?path={self.TEST_FOLDER}",
            headers={"Authorization": "OAuth invalid_token"}
        )

        self.assertEqual(response.status_code, 401)

    def test_create_folder_invalid_name(self):
        """Тест создания папки с недопустимым именем"""
        invalid_folder_name = "test/folder"
        response = requests.put(
            f"{self.BASE_URL}?path={invalid_folder_name}",
            headers=self.HEADERS
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("недопустимое", response.json().get("message", "").lower())

    def test_create_folder_no_token(self):
        """Тест создания папки без токена"""
        response = requests.put(
            f"{self.BASE_URL}?path={self.TEST_FOLDER}"
        )

        self.assertEqual(response.status_code, 401)


class TestYandexAuth(unittest.TestCase):
    LOGIN_URL = "https://passport.yandex.ru/auth"
    HOME_URL = "https://mail.yandex.ru/"

    def setUp(self):
        self.driver = webdriver.Chrome()
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 10)

        # Получаем учетные данные из переменных окружения
        self.valid_login = os.getenv("YANDEX_LOGIN")
        self.valid_password = os.getenv("YANDEX_PASSWORD")
        self.invalid_password = "wrong_password"

    def tearDown(self):
        self.driver.quit()

    def test_successful_auth(self):
        """Тест успешной авторизации"""
        self.driver.get(self.LOGIN_URL)

        # Вводим логин
        login_input = self.wait.until(
            EC.presence_of_element_located((By.ID, "passp-field-login"))
        )
        login_input.send_keys(self.valid_login)

        # Нажимаем кнопку "Войти"
        submit_button = self.wait.until(
            EC.element_to_be_clickable((By.ID, "passp:sign-in")))
        submit_button.click()

        # Вводим пароль
        password_input = self.wait.until(
            EC.presence_of_element_located((By.ID, "passp-field-passwd"))
        )
        password_input.send_keys(self.valid_password)

        # Нажимаем кнопку "Войти"
        submit_button = self.wait.until(
            EC.element_to_be_clickable((By.ID, "passp:sign-in"))
        )
        submit_button.click()

        # Проверяем, что авторизация прошла успешно
        self.wait.until(
            EC.url_contains(self.HOME_URL)
        )

        # Проверяем наличие элемента почты (дополнительная проверка)
        self.assertTrue(
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "mail-User-Name"))
            ))

    def test_wrong_password(self):
        """Тест авторизации с неверным паролем"""
        self.driver.get(self.LOGIN_URL)

        # Вводим логин
        login_input = self.wait.until(
            EC.presence_of_element_located((By.ID, "passp-field-login"))
        )
        login_input.send_keys(self.valid_login)
        self.driver.find_element(By.ID, "passp:sign-in").click()

        # Вводим неверный пароль
        password_input = self.wait.until(
            EC.presence_of_element_located((By.ID, "passp-field-passwd"))
        )
        password_input.send_keys(self.invalid_password)
        self.driver.find_element(By.ID, "passp:sign-in").click()

        # Проверяем сообщение об ошибке
        error_message = self.wait.until(
            EC.presence_of_element_located((By.ID, "field:input-passwd:hint"))
        )
        self.assertIn("Неверный пароль", error_message.text)

    def test_empty_login(self):
        """Тест попытки входа без логина"""
        self.driver.get(self.LOGIN_URL)

        # Нажимаем кнопку "Войти" без ввода логина
        submit_button = self.wait.until(
            EC.element_to_be_clickable((By.ID, "passp:sign-in"))
        )
        submit_button.click()

        # Проверяем сообщение об ошибке
        error_message = self.wait.until(
            EC.presence_of_element_located((By.ID, "field:input-login:hint"))
        )
        self.assertIn("Логин не указан", error_message.text)

if __name__ == "__main__":
    unittest.main()

