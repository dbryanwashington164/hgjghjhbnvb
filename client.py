import sys
import time
import threading
import random
import fairy
import client_helper
import multiprocessing as mp


def rand_str(length=4):
    return ''.join(random.sample('abcdefghijklmnopqrstuvwxyz0123456789', length))


program_version = "1.0.4"
current_task = ""
downloaded_tasks = []
thread_test = None
client_id = rand_str(8)
need_update = False


def test(task_id, task):
    global thread_test, need_update
    engine, weight = "", ""
    baseline_engine, baseline_weight = "", ""
    print(f"开始测试: {task_id}")
    if task['engine_url']:
        file_id = task['engine_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        engine = "engine_" + file_id
        if engine not in downloaded_tasks:
            print(f"下载引擎: {task['engine_url']}")
            result = client_helper.download_file_with_trail(task['engine_url'], engine)
            print(f"下载结果: {result}")
            if not result:
                thread_test = None
                return False
            if engine not in downloaded_tasks:
                downloaded_tasks.append(engine)
    if task['weight_url']:
        file_id = task['weight_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        weight = "xiangqi-" + file_id + ".nnue"
        if weight not in downloaded_tasks:
            print(f"下载权重: {task['weight_url']}")
            result = client_helper.download_file_with_trail(task['weight_url'], weight)
            print(f"下载结果: {result}")
            if not result:
                thread_test = None
                return False
            if weight not in downloaded_tasks:
                downloaded_tasks.append(weight)
    if task['baseline_engine_url']:
        file_id = task['baseline_engine_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        baseline_engine = "engine_" + file_id
        if baseline_engine not in downloaded_tasks:
            print(f"下载基准引擎: {task['baseline_engine_url']}")
            result = client_helper.download_file_with_trail(task['baseline_engine_url'], baseline_engine)
            print(f"下载结果: {result}")
            if not result:
                thread_test = None
                return False
            if baseline_engine not in downloaded_tasks:
                downloaded_tasks.append(baseline_engine)
    if task['baseline_weight_url']:
        file_id = task['baseline_weight_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        baseline_weight = "xiangqi-" + file_id + ".nnue"
        if baseline_weight not in downloaded_tasks:
            print(f"下载基准权重: {task['baseline_weight_url']}")
            result = client_helper.download_file_with_trail(task['baseline_weight_url'], baseline_weight)
            print(f"下载结果: {result}")
            if not result:
                thread_test = None
                return False
            if baseline_weight not in downloaded_tasks:
                downloaded_tasks.append(baseline_weight)
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
        result = tester.test_multi(weight, engine, baseline_weight, baseline_engine,
                          int(task['time_control'][2]),
                          int(task['nodes']),
                          int(task['time_control'][0]*1000),
                          int(task['time_control'][1]*1000), thread_count=mp.cpu_count())
        result = client_helper.upload_result(task_id, program_version, result["wdl"], result["fwdl"], result["ptnml"])
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


def heartbeat_loop():
    count = 0
    while thread_test is not None:
        count += 1
        if count % 45 * 5 == 0:
            client_helper.get_task(client_id)
            count = 0
        time.sleep(0.2)


def start_testing(task_id, task):
    global thread_test
    thread_test = threading.Thread(target=test, args=(task_id, task))
    thread_test.setDaemon(True)
    thread_test.start()
    # thread_heartbeat = threading.Thread(target=heartbeat_loop)
    # thread_heartbeat.setDaemon(True)
    # thread_heartbeat.start()


if __name__ == "__main__":
    result = client_helper.upload_result("ty5pef", program_version, [0, 0, 0], [0, 0, 0], [0,0,0,0,0])
    print(result)
    exit(9)
    while True:
        if thread_test is None:
            time.sleep(12)
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
                    start_testing(task_id, task)
            else:
                start_testing(task_id, task)
                current_task = task_id
        except Exception as e:
            print(repr(e))