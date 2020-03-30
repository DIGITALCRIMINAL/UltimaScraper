import re
from bs4 import BeautifulSoup
import platform
import csv
import json
import os
from os.path import dirname as up
import requests
import logging

path = up(up(os.path.realpath(__file__)))
os.chdir(path)

# Open config.json and fill in OPTIONAL information
path = os.path.join('settings', 'config.json')
json_config = json.load(open(path))
json_global_settings = json_config["settings"]
export_type = json_global_settings["export_type"]
os_name = platform.system()


def parse_links(site_name, input_link):
    if site_name in {"onlyfans", "justforfans"}:
        username = input_link.rsplit('/', 1)[-1]
        return username

    if site_name in {"4chan", "bbwchan"}:
        if "catalog" in input_link:
            input_link = input_link.split("/")[1]
            print(input_link)
            return input_link
        if input_link[-1:] == "/":
            input_link = input_link.split("/")[3]
            return input_link
        if "4chan.org" not in input_link:
            return input_link


def reformat(directory, media_id, file_name, text, ext, date, username, format_path, date_format, text_length, maximum_length):
    media_id = "" if media_id is None else str(media_id)
    path = format_path.replace("{username}", username)
    text = BeautifulSoup(text, 'lxml').get_text().replace(
        "\n", " ").strip()
    SAFE_PTN = '[^0-9a-zA-Z-_.()]+'
    # filtered_text = re.sub(r'[\\/*?:"<>|]', '', text)
    filtered_text = re.sub(SAFE_PTN, ' ',  text.strip()
                           ).strip().replace(' ', '_')[:text_length]
    path = path.replace("{text}", filtered_text)
    date = date.strftime(date_format)
    path = path.replace("{date}", date)
    path = path.replace("{id}", media_id)
    path = path.replace("{file_name}", file_name)
    path = path.replace("{ext}", ext)
    directory2 = directory + path

    lp = are_long_paths_enabled()
    if not lp:
        count_string = len(directory2)
        if count_string > maximum_length:
            num_sum = count_string - maximum_length
            directory2 = directory2.replace(
                filtered_text, filtered_text[:text_length])
        count_string = len(directory2)
        if count_string > maximum_length:
            num_sum = count_string - maximum_length
            directory2 = directory2.replace(
                filtered_text, filtered_text[:-num_sum])
            count_string = len(directory2)
            if count_string > maximum_length:
                directory2 = directory
        count_string = len(directory2)
        if count_string > maximum_length:
            num_sum = count_string - maximum_length
            directory2 = directory2.replace(
                filtered_text, filtered_text[:50])
            count_string = len(directory2)
            if count_string > maximum_length:
                directory2 = directory
    filename = os.path.basename(directory2)
    if len(filename) > 240:
        directory2 = directory2.replace(filename, filename[:240]+"."+ext)
    return directory2


def format_media_set(location, media_set):
    x = {}
    x["type"] = location
    x["valid"] = []
    x["invalid"] = []
    for y in media_set:
        x["valid"].extend(y[0])
        x["invalid"].extend(y[1])
    return x


def format_image(directory, timestamp):
    os_name = platform.system()
    if os_name == "Windows":
        from win32_setctime import setctime
        setctime(directory, timestamp)


def export_archive(data, archive_directory):
    # Not Finished
    if export_type == "json":
        with open(archive_directory+".json", 'w') as outfile:
            json.dump(data, outfile)
    if export_type == "csv":
        with open(archive_directory+'.csv', mode='w', encoding='utf-8', newline='') as csv_file:
            fieldnames = []
            if data["valid"]:
                fieldnames.extend(data["valid"][0].keys())
            elif data["invalid"]:
                fieldnames.extend(data["invalid"][0].keys())
            header = [""]+fieldnames
            if len(fieldnames) > 1:
                writer = csv.DictWriter(csv_file, fieldnames=header)
                writer.writeheader()
                for item in data["valid"]:
                    writer.writerow({**{"": "valid"}, **item})
                for item in data["invalid"]:
                    writer.writerow({**{"": "invalid"}, **item})


def get_directory(directory):
    if directory:
        os.makedirs(directory, exist_ok=True)
        return directory
    else:
        return os.path.abspath("sites")


def format_directory(j_directory, site_name, username, location, api_type):
    directory = j_directory

    user_directory = directory+"/"+site_name + "/"+username+"/"
    metadata_directory = user_directory+api_type+"/Metadata/"
    directories = []
    count = 0
    if "/sites/" == j_directory:
        user_directory = os.path.dirname(os.path.dirname(
            os.path.realpath(__file__))) + user_directory
        metadata_directory = os.path.dirname(os.path.dirname(
            os.path.realpath(__file__))) + metadata_directory
        directories.append(
            [location, user_directory+api_type + "/" + location+"/"])
    else:
        directories.append(
            [location, user_directory+api_type + "/" + location+"/"])
        count += 1
    return [user_directory, metadata_directory, directories]


def are_long_paths_enabled():
    if os_name == "Windows":
        from ctypes import WinDLL, c_ubyte
        ntdll = WinDLL('ntdll')

        if hasattr(ntdll, 'RtlAreLongPathsEnabled'):

            ntdll.RtlAreLongPathsEnabled.restype = c_ubyte
            ntdll.RtlAreLongPathsEnabled.argtypes = ()
            return bool(ntdll.RtlAreLongPathsEnabled())

        else:
            return False


def check_for_dupe_file(download_path, content_length):
    found = False
    if os.path.isfile(download_path):
        local_size = os.path.getsize(download_path)
        if local_size == content_length:
            found = True
    return found


def download_to_file(request, download_path):
    partial_path = download_path + ".part"

    try:
        os.unlink(partial_path)
    except FileNotFoundError:
        pass

    delete = False
    try:
        with open(partial_path, 'xb') as f:
            delete = True
            for chunk in request.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
    except:
        if delete:
            os.unlink(partial_path)
        raise
    else:
        os.replace(partial_path, download_path)


def json_request(session, link, method="GET", stream=False, json_format=True):
    count = 0
    while count < 11:
        try:
            headers = session.headers
            if json_format:
                headers["accept"] = "application/json, text/plain, */*"
            r = session.request(method, link, stream=stream)
            content_type = r.headers['Content-Type']
            if json_format:
                if "application/json;" not in content_type:
                    count += 1
                    continue
                return json.loads(r.text)
            else:
                return r
        except (ConnectionResetError) as e:
            log_error.exception(e)
            count += 1
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            log_error.exception(e)
            count += 1
        except Exception as e:
            log_error.exception(e)
            input("Enter to continue")


def update_config(json_config):
    path = os.path.join('settings', 'config.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(json_config, f, ensure_ascii=False, indent=2)


def choose_auth(array):
    string = ""
    names = []
    array = [{"auth_count": -1, "username": "All"}]+array
    name_count = len(array)
    if name_count > 1:

        count = 0
        for x in array:
            name = x["username"]
            string += str(count)+" = "+name
            names.append(x)
            if count+1 != name_count:
                string += " | "

            count += 1

    print("Auth Usernames: "+string)
    value = int(input().strip())
    if value:
        names = [names[value]]
    else:
        names.pop(0)
    return names


def is_me(user_api):
    if "email" in user_api:
        return True
    else:
        return False


def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""
    log_filename = "logs/"+log_file
    os.makedirs(os.path.dirname(log_filename), exist_ok=True)
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s')

    handler = logging.FileHandler(log_filename)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


log_error = setup_logger('errors', 'errors.log')
