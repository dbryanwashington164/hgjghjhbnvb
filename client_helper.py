import time
import multiprocessing as mp
import requests

DEBUG = False
HOST = "http://test.stockfishxq.com/api"
if DEBUG:
    HOST = "http://127.0.0.1:5003"


def get_task(client_id):
    try:
        rep = requests.get(HOST + "/get_task?client_id=" + client_id + "&core_count=" + str(mp.cpu_count()))
        info = rep.json()
        return info
    except Exception as e:
        print("获取任务失败:", repr(e))
        return None


def upload_result(task_id, program_version, wdl, fwdl, ptnml):
    try:
        rep = requests.post(HOST + "/upload_result", json={"task_id": task_id, "program_version": program_version,
                                                           "wdl": wdl, "fwdl": fwdl, "ptnml": ptnml})
        info = rep.text
        return info
    except Exception as e:
        print("上传结果失败:", repr(e))
        return None


def download_file(url, save_path):
    try:
        data = requests.get(url).content
        with open(save_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print("下载文件失败:", repr(e))
        return False


def download_file_with_trail(url, save_path, retry_count=3):
    for i in range(retry_count):
        if download_file(url, save_path):
            return True
        print("下载失败，重试中")
        time.sleep(1)
    return False