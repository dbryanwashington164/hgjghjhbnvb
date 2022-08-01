import sys
import time
import threading
import random
import fairy
import client_helper
import multiprocessing as mp


def rand_str(length=4):
    return ''.join(random.sample('abcdefghijklmnopqrstuvwxyz0123456789', length))


program_version = "1.0.1"
current_task = ""
downloaded_tasks = []
thread_test = None
client_id = rand_str(8)
need_update = False


def test(task_id, task):
    global thread_test, need_update
    engine, weight = "", ""
    print(f"开始测试: {task_id}")
    if task['engine_url']:
        engine = "engine_" + task_id
        if task_id not in downloaded_tasks:
            print(f"下载引擎: {task['engine_url']}")
            result = client_helper.download_file_with_trail(task['engine_url'], "engine_" + task_id)
            print(f"下载结果: {result}")
            if not result:
                thread_test = None
                return False
    if task['weight_url']:
        weight = "xiangqi-" + task_id + ".nnue"
        if task_id not in downloaded_tasks:
            print(f"下载权重: {task['weight_url']}")
            result = client_helper.download_file_with_trail(task['weight_url'], "xiangqi-" + task_id + ".nnue")
            print(f"下载结果: {result}")
            if not result:
                thread_test = None
                return False
    if task_id not in downloaded_tasks:
        downloaded_tasks.append(task_id)
    num_games = 6
    depth = int(task['time_control'][2])
    game_time = task['time_control'][0]
    if game_time >= 60:
        num_games = 2
    elif game_time >= 30:
        num_games = 4
    elif game_time >= 10:
        num_games = 6
    if 0 < depth <= 10:
        num_games = 12
    tester = fairy.Tester(num_games)
    try:
        result = tester.test_multi(weight, engine,
                          int(task['time_control'][2]),
                          int(task['time_control'][0]*1000),
                          int(task['time_control'][1]*1000), thread_count=mp.cpu_count())
        result = client_helper.upload_result(task_id, result['win'], result['draw'], result['lose'])
        if result == "ver":
            print(f"版本不一致，请更新版本")
            thread_test = None
            need_update = True
            return False
        print("测试完成: ", result)
    except Exception as e:
        print("测试失败: ", repr(e))
    thread_test = None
    return True


if __name__ == "__main__":
    while True:
        if thread_test is None:
            time.sleep(5)
        else:
            time.sleep(1)
        try:
            if thread_test is not None:
                continue
            if need_update:
                exit(0)
            task = client_helper.get_task(client_id)
            if task is None or task["task"] is None:
                continue
            if "program_version" in task and task["program_version"] != program_version:
                print("版本不一致，请更新版本")
                need_update = True
                exit(0)
                continue
            task_id = task["id"]
            task = task["task"]
            if current_task == task_id:
                if thread_test is None:
                    thread_test = threading.Thread(target=test, args=(task_id, task))
                    thread_test.setDaemon(True)
                    thread_test.start()
            else:
                thread_test = threading.Thread(target=test, args=(task_id, task))
                thread_test.setDaemon(True)
                thread_test.start()
                current_task = task_id
        except Exception as e:
            print(repr(e))