import requests
from modules.helpers import *

import os
import json
from itertools import product
from itertools import chain
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool
from datetime import datetime
import logging
import inspect
import math
import time

logger = logging.getLogger(__name__)

# Open config.json and fill in OPTIONAL information
json_config = json.load(open('config.json'))
json_global_settings = json_config["settings"]
multithreading = json_global_settings["multithreading"]
json_settings = json_config["supported"]["onlyfans"]["settings"]
auto_choice = json_settings["auto_choice"]
j_directory = get_directory(json_settings['directory'])
format_path = json_settings['file_name_format']
overwrite_files = json_settings["overwrite_files"]
date_format = json_settings["date_format"]
ignored_keywords = json_settings["ignored_keywords"]
maximum_length = 240
text_length = int(json_settings["text_length"]
                  ) if json_settings["text_length"] else maximum_length
if text_length > maximum_length:
    text_length = maximum_length


def start_datascraper(session, username, site_name, app_token):
    print("Scrape Processing")
    print("Name: "+username)
    user_id = link_check(session, app_token, username)
    if not user_id[0]:
        print(user_id[1])
        print("First time? Did you forget to edit your config.json file?")
        return [False, []]

    post_counts = user_id[2]
    user_id = user_id[1]
    array = scrape_choice(user_id, app_token, post_counts)
    prep_download = []
    for item in array:
        print("Type: "+item[2])
        only_links = item[1][3]
        post_count = str(item[1][4])
        item[1].append(username)
        item[1].pop(3)
        api_type = item[2]
        results = media_scraper(
            session, site_name, only_links, *item[1], api_type)
        for result in results[0]:
            if not only_links:
                media_set = result
                if not media_set["valid"]:
                    continue
                directory = results[1]
                location = result["type"]
                prep_download.append(
                    [media_set["valid"], session, directory, username, post_count, location])
    # When profile is done scraping, this function will return True
    print("Scrape Completed"+"\n")
    return [True, prep_download]


def link_check(session, app_token, username):
    link = 'https://onlyfans.com/api2/v2/users/' + username + \
           '&app-token=' + app_token
    r = session.get(link)
    y = json.loads(r.text)
    temp_user_id2 = dict()
    if not y:
        temp_user_id2[0] = False
        temp_user_id2[1] = "No users found"
        return temp_user_id2
    if "error" in y:
        temp_user_id2[0] = False
        temp_user_id2[1] = y["error"]["message"]
        return temp_user_id2

    subbed = y["subscribedBy"]
    if not subbed:
        temp_user_id2[0] = False
        temp_user_id2[1] = "You're not subscribed to the user"
        return temp_user_id2
    else:
        temp_user_id2[0] = True
        temp_user_id2[1] = str(y["id"])
        temp_user_id2[2] = [y["postsCount"], [y["photosCount"],
                                              y["videosCount"], y["audiosCount"]]]
        return temp_user_id2


def scrape_choice(user_id, app_token, post_counts):
    post_count = post_counts[0]
    media_counts = post_counts[1]
    x = ["Images", "Videos", "Audios"]
    x = dict(zip(x, media_counts))
    x = [k for k, v in x.items() if v != 0]
    if auto_choice:
        input_choice = auto_choice
    else:
        print('Scrape: a = Everything | b = Images | c = Videos | d = Audios')
        input_choice = input().strip()
    message_api = "https://onlyfans.com/api2/v2/chats/"+user_id + \
        "/messages?limit=100&offset=0&order=desc&app-token="+app_token+""
    post_api = "https://onlyfans.com/api2/v2/users/"+user_id + \
        "/posts?limit=100&offset=0&order=publish_date_desc&app-token="+app_token+""
    # ARGUMENTS
    only_links = False
    if "-l" in input_choice:
        only_links = True
        input_choice = input_choice.replace(" -l", "")
    mandatory = [j_directory, only_links]
    y = ["photo", "video", "stream", "gif", "audio"]
    p_array = ["You have chosen to scrape {}", [
        post_api, x, *mandatory, post_count], "Posts"]
    m_array = ["You have chosen to scrape {}", [
        message_api, x, *mandatory, post_count], "Messages"]
    array = [p_array, m_array]
    valid_input = False
    if input_choice == "a":
        valid_input = True
        a = []
        for z in x:
            if z == "Images":
                a.append([z, [y[0]]])
            if z == "Videos":
                a.append([z, y[1:4]])
            if z == "Audios":
                a.append([z, [y[4]]])
        for item in array:
            item[0] = array[0][0].format("all")
            item[1][1] = a
    if input_choice == "b":
        name = "Images"
        for item in array:
            item[0] = item[0].format(name)
            item[1][1] = [[name, [y[0]]]]
        valid_input = True
    if input_choice == "c":
        name = "Videos"
        for item in array:
            item[0] = item[0].format(name)
            item[1][1] = [[name, y[1:4]]]
        valid_input = True
    if input_choice == "d":
        name = "Audios"
        for item in array:
            item[0] = item[0].format(name)
            item[1][1] = [[name, [y[4]]]]
        valid_input = True
    if valid_input:
        return array
    else:
        print("Invalid Choice")
    return []


def scrape_array(link, session, directory, username, api_type):
    media_set = [[], []]
    media_type = directory[1]
    count = 0
    found = False
    y = {}
    while count < 11:
        r = session.get(link)
        count += 1
        if r.status_code != 200:
            continue
        y = json.loads(r.text)
        if not y:
            continue
        found = True
        break
    if not found:
        return media_set
    x = 0
    if api_type == "Messages":
        y = y["list"]
    master_date = "01-01-0001 00:00:00"
    for media_api in y:
        for media in media_api["media"]:
            if media["type"] not in media_type:
                x += 1
                continue
            date = "-001-11-30T00:00:00+00:00"
            size = 0
            if "source" in media:
                source = media["source"]
                link = source["source"]
                size = source["size"]
                date = media_api["postedAt"]
            if "src" in media:
                link = media["src"]
                size = media["info"]["preview"]["size"]
                date = media_api["createdAt"]
            if not link:
                continue
            if "ca2.convert" in link:
                link = media["preview"]
            new_dict = dict()
            new_dict["post_id"] = media_api["id"]
            new_dict["link"] = link
            if date == "-001-11-30T00:00:00+00:00":
                date_string = master_date
                date_object = datetime.strptime(
                    master_date, "%d-%m-%Y %H:%M:%S")
            else:
                date_object = datetime.fromisoformat(date)
                date_string = date_object.replace(tzinfo=None).strftime(
                    "%d-%m-%Y %H:%M:%S")
                master_date = date_string
            new_dict["text"] = media_api["text"] if media_api["text"] else ""
            new_dict["postedAt"] = date_string
            file_name = link.rsplit('/', 1)[-1]
            file_name, ext = os.path.splitext(file_name)
            ext = ext.__str__().replace(".", "")
            file_path = reformat(directory[0][1], file_name,
                                 new_dict["text"], ext, date_object, username, format_path, date_format, text_length, maximum_length)
            new_dict["directory"] = directory[0][1]
            new_dict["filename"] = file_path.rsplit('/', 1)[-1]
            new_dict["size"] = size
            if size == 0:
                media_set[1].append(new_dict)
                continue
            media_set[0].append(new_dict)
    return media_set


def media_scraper(session, site_name, only_links, link, locations, directory, post_count, username, api_type):
    seperator = " | "
    media_set = []
    for location in locations:
        print("Scraping ["+str(seperator.join(location[1])) +
              "]. Should take less than a minute.")
        array = format_directory(
            j_directory, site_name, username, location[0], api_type)
        user_directory = array[0]
        location_directory = array[2][0][1]
        metadata_directory = array[1]
        directories = array[2]+[location[1]]

        pool = ThreadPool()
        ceil = math.ceil(post_count / 100)
        a = list(range(ceil))
        offset_array = []
        if api_type == "Posts":
            for b in a:
                b = b * 100
                offset_array.append(link.replace(
                    "offset=0", "offset=" + str(b)))
        if api_type == "Messages":
            offset_count = 0
            while True:
                r = session.get(link)
                y = json.loads(r.text)
                if "list" in y:
                    if y["list"]:
                        offset_array.append(link)
                        if y["hasMore"]:
                            offset_count2 = offset_count+100
                            offset_count = offset_count2-100
                            link = link.replace(
                                "offset=" + str(offset_count), "offset=" + str(offset_count2))
                            offset_count = offset_count2
                        else:
                            break
                    else:
                        break
                else:
                    break
        results = format_media_set(location[0], pool.starmap(scrape_array, product(
            offset_array, [session], [directories], [username], [api_type])))
        if results["valid"]:
            os.makedirs(directory, exist_ok=True)
            os.makedirs(location_directory, exist_ok=True)
            os.makedirs(metadata_directory, exist_ok=True)
            archive_directory = metadata_directory+location[0]
            export_archive(results, archive_directory)
        media_set.append(results)

    return [media_set, directory]


def download_media(media_set, session, directory, username, post_count, location):
    def download(media, session, directory, username):
        while True:
            link = media["link"]
            r = session.head(link)

            date_object = datetime.strptime(
                media["postedAt"], "%d-%m-%Y %H:%M:%S")
            og_filename = media["filename"]
            media["ext"] = os.path.splitext(og_filename)[1]
            media["ext"] = media["ext"].replace(".", "")
            download_path = media["directory"]+media["filename"]
            timestamp = date_object.timestamp()
            if not overwrite_files:
                if os.path.isfile(download_path):
                    return
            r = json_request(session, link)
            if not r:
                break
            with open(download_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
            format_image(download_path, timestamp)
            logger.info("Link: {}".format(link))
            logger.info("Path: {}".format(download_path))
            return True
    print("Download Processing")
    print("Name: "+username+" | Directory: " + directory)
    print("Downloading "+str(len(media_set))+" "+location+"\n")
    if multithreading:
        pool = ThreadPool()
    else:
        pool = ThreadPool(1)
    pool.starmap(download, product(
        media_set, [session], [directory], [username]))


def create_session(user_agent, auth_id, auth_hash, app_token, sess, fp):
    response = []
    count = 1
    while count < 11:
        print("Auth (V1) Attempt "+str(count)+"/"+"10")
        max_threads = multiprocessing.cpu_count()
        session = requests.Session()
        session.mount(
            'https://', requests.adapters.HTTPAdapter(pool_connections=max_threads, pool_maxsize=max_threads))
        session.headers = {
            'User-Agent': user_agent, 'Referer': 'https://onlyfans.com/'}
        auth_cookies = [
            {'name': 'auth_id', 'value': auth_id},
            {'name': 'auth_hash', 'value': auth_hash},
            {'name': 'sess', 'value': sess},
            {'name': 'fp', 'value': fp}
        ]
        for auth_cookie in auth_cookies:
            session.cookies.set(**auth_cookie)
        session.head("https://onlyfans.com")
        r = session.get(
            "https://onlyfans.com/api2/v2/users/me?app-token="+app_token)
        count += 1
        if r.status_code != 200:
            continue
        response = json.loads(r.text)
        if 'error' in response:
            error_message = response["error"]["message"]
            print(error_message)
            if "token" in error_message:
                count = 10
            continue
        else:
            print("Welcome "+response["name"])
        option_string = "username or profile link"
        return [session, option_string, response["subscribesCount"]]

    return [False, response]


def get_subscriptions(session, app_token, subscriber_count):
    link = "https://onlyfans.com/api2/v2/subscriptions/subscribes?limit=10&offset=0&type=active&app-token="+app_token
    pool = ThreadPool()
    ceil = math.ceil(subscriber_count / 10)
    a = list(range(ceil))
    offset_array = []
    for b in a:
        b = b * 10
        offset_array.append(link.replace("offset=0", "offset=" + str(b)))

    def multi(link, session):
        return json.loads(session.get(link).text)
    results = pool.starmap(multi, product(
        offset_array, [session]))
    results = list(chain(*results))
    results = list(reversed(results))
    if any("error" in result for result in results):
        print("Invalid App Token")
        return []
    else:
        return results


def format_options(array):
    string = ""
    names = []
    array = [{"user": {"username": "All"}}]+array
    name_count = len(array)
    if name_count > 1:

        count = 0
        for x in array:
            name = x["user"]["username"]
            string += str(count)+" = "+name
            names.append(name)
            if count+1 != name_count:
                string += " | "

            count += 1
    return [names, string]
