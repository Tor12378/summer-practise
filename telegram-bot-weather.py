import os
import json
import requests
import io

def post_message(message_json):
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if telegram_bot_token is None:
        return
    requests.post(url=f'https://api.telegram.org/bot{telegram_bot_token}/sendMessage', json=message_json)

def reply_to_message(text, message):
    chat_id = message['chat']['id']
    message_id = message['message_id']
    reply_parameters = {"message_id": message_id}
    reply_message = {'chat_id': chat_id, 'text': text, 'reply_parameters': reply_parameters}
    post_message(reply_message)

def send_message(text, message):
    chat_id = message['chat']['id']
    reply_message = {'chat_id': chat_id, 'text': text}
    post_message(reply_message)

def post_voice(data, voice_file):
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if telegram_bot_token is None:
        return
    requests.post(f"https://api.telegram.org/bot{telegram_bot_token}/sendVoice", data=data, files=voice_file)

def send_voice(voice, message):
    voice_file = io.BytesIO(voice)
    parameters = {"chat_id": message['chat']['id']}
    post_voice(data=parameters, voice_file={"voice": voice_file})

def send_help_message(message):
    HELP_TEXTS = ["Я расскажу о текущей погоде для населенного пункта.", "Я могу ответить на: - Текстовое сообщение с названием населенного пункта. - Голосовое сообщение с названием населенного пункта. - Сообщение с геопозицией."]
    for help_text in HELP_TEXTS:
        send_message(help_text, message)

def handle_command(message):
    match message['text']:
        case '/start' | '/help':
            send_help_message(message)
        case _:
            text = "Неизвестная команда!"
            send_message(text, message)

def get_wind_direction(degrees):
    directions = ["Северный", "Северо-северо-восточный", "Северо-восточный", "Востоко-северо-восточный", "Восточный", "Востоко-юго-восточный", "Юго-восточный", "Юго-юго-восточный", "Южный", "Юго-юго-западный", "Юго-западный", "Западо-юго-западный", "Западный", "Западо-северо-западный", "Северо-западный", "Северо-северо-западный"]
    num_directions = len(directions)
    degrees_per_direction = 360 / num_directions
    index = int((degrees + (degrees_per_direction / 2)) // degrees_per_direction) % num_directions
    return directions[index]

def format_current_weather(weather_info_json):
    city = weather_info_json['name']
    brief_description = weather_info_json['weather'][0]['description']
    temp = weather_info_json['main']['temp']
    feels_like = weather_info_json['main']['feels_like']
    temp_min = weather_info_json['main']['temp_min']
    temp_max = weather_info_json['main']['temp_max']
    pressure = weather_info_json['main']['pressure'] * 0.750064
    wind_speed = weather_info_json['wind']['speed']
    wind_deg = weather_info_json['wind']['deg']
    wind_direction = get_wind_direction(wind_deg)
    format_text = f"Погода в городе {city}: Сейчас {brief_description}, температура {temp}°C, но ощущается как {feels_like}°C. Максимальная температура {temp_max}°C, минимальная температура {temp_min}°C. Давление состовляет {int(pressure)} мм.рт.ст. Ветер {wind_direction.lower()} ({wind_deg}°) со скоростью {wind_speed} м/с."
    return format_text

def get_current_weather(place):
    token = os.environ.get("OPEN_WEATHER_TOKEN")
    url = "https://api.openweathermap.org/data/2.5/weather"
    parameters = {"q": place, "appid": token, "lang": "ru", "units": "metric"}
    response = requests.get(url=url, params=parameters).json()
    match str(response['cod']):
        case '404':
            raise ValueError(f"Я не нашел населенный пункт {place}")
        case '200':
            return format_current_weather(response)
        case '201', _:
            raise RuntimeError("Произошла непредвиденная ошибка! Попробуйте позже")

def download_file(file_id, token) -> bytes:
    url = f"https://api.telegram.org/bot{token}/getFile"
    parameters = {"file_id": file_id}
    response = requests.post(url=url, json=parameters).json()
    file = response["result"]
    file_path = file["file_path"]
    download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    download_response = requests.get(url=download_url)
    file_content = download_response.content
    return file_content

def stt(voice, token) -> str:
    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    auth = {"Authorization": f"Bearer {token}"}
    response = requests.post(url=url, headers=auth, data=voice).json()
    text = response["result"]
    return text

def tts(text, token) -> bytes:
    url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
    params = {"text": text, "voice": "ermil", "emotion": "good"}
    auth = {"Authorization": f"Bearer {token}"}
    yc_tts_response = requests.post(url=url, data=params, headers=auth)
    voice = yc_tts_response.content
    return voice

def format_current_weather_for_voice_message(current_weather: str):
    replacement_patterns = {"°C": "градусов по Цельсию", "мм.рт.ст": "миллиметров ртутного столба", "м/с": "метров в секунду"}
    for old, new in replacement_patterns.items():
        current_weather = current_weather.replace(old, new)
    return current_weather

def handle_text_message(message):
    if message['text'].startswith('/'):
        handle_command(message)
    else:
        city_name = message['text']
        try:
            current_weather = get_current_weather(city_name)
            send_message(current_weather, message)
        except (ValueError, RuntimeError) as e:
            send_message(text=e.args[0], message=message)

def handle_voice_message(message, yc_token):
    voice = message['voice']
    if voice['duration'] > 30:
        error_text = "Голосовое сообщение должно быть короче 30 секунд"
        send_message(error_text, message)
        return
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    voice_content = download_file(file_id=voice["file_id"], token=telegram_bot_token)
    city_name = stt(voice=voice_content, token=yc_token)
    try:
        current_weather = get_current_weather(city_name)
        formatted_current_weather = format_current_weather_for_voice_message(current_weather)
        voice_message = tts(formatted_current_weather, yc_token)
        send_voice(voice_message, message)
    except (ValueError, RuntimeError) as e:
        send_message(text=e.args[0], message=message)

def handler(event, context):
    func_reponse = {'statusCode': 200, 'body': ''}
    update = json.loads(event['body'])
    if 'message' not in update:
        return func_reponse
    message = update['message']
    if 'text' in message:
        handle_text_message(message)
    elif 'voice' in message:
        yc_token = context.token["access_token"]
        handle_voice_message(message, yc_token)
    else:
        error_text = "Могу ответить только на текстовое или голосовое сообщение"
        send_message(error_text, message)
    return func_repons