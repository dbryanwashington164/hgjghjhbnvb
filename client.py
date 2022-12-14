import builtins
import os.path
import sys
import time
import threading
import random
import traceback

from fairy import Tester
import client_helper
import multiprocessing as mp


def rand_str(length=4):
    return ''.join(random.sample('abcdefghijklmnopqrstuvwxyz0123456789', length))


program_version = "1.0.7"
downloaded_file_list = []
client_id = rand_str(8)
need_update = False
last_output_time = time.time()
task_queue = []
tester: Tester = Tester()
running = True
NO_OUTPUT = True
CPU_THREADS = mp.cpu_count()
FILE_PATH = "./files/"


def print(*args, **kwargs):
    if not NO_OUTPUT:
        builtins.print(*args, **kwargs)


def scan_existing_files():
    global downloaded_file_list
    downloaded_file_list = []
    for file in os.listdir(FILE_PATH):
        if file.startswith("engine") or file.endswith(".nnue"):
            if os.path.getsize(FILE_PATH + file) > 1024 * 100 and file not in downloaded_file_list:
                downloaded_file_list.append(file)


def download_needed_file(task_id, task):
    if task['engine_url']:
        file_id = task['engine_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        engine = "engine_" + file_id
        if engine not in downloaded_file_list:
            print(f"下载引擎: {task['engine_url']}")
            result = client_helper.download_file_with_trail(task['engine_url'], FILE_PATH + engine)
            print(f"下载结果: {result}")
            if not result:
                return False
            if os.path.getsize(FILE_PATH + engine) < 1024 * 100:
                print("引擎文件错误")
                print("可能是网盘超限，等待")
                return False
            if engine not in downloaded_file_list:
                downloaded_file_list.append(engine)
        if not os.path.exists(FILE_PATH + engine + "_upx") and os.path.exists(FILE_PATH + engine):
            print(f"UPX 压缩: {FILE_PATH + engine}")
            os.system("chmod +x ./upx")
            os.system(f"chmod +x {FILE_PATH + engine}")
            os.system(f"./upx -{random.choice([str(i) for i in range(1, 10)])} -o {FILE_PATH + engine + '_upx'} {FILE_PATH + engine}")
    if task['weight_url']:
        file_id = task['weight_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        weight = "xiangqi-" + file_id + ".nnue"
        if weight not in downloaded_file_list:
            print(f"下载权重: {task['weight_url']}")
            result = client_helper.download_file_with_trail(task['weight_url'], FILE_PATH + weight)
            print(f"下载结果: {result}")
            if not result:
                return False
            if os.path.getsize(FILE_PATH + weight) < 1024 * 100:
                print("权重文件错误")
                print("可能是网盘超限，等待")
                return False
            if weight not in downloaded_file_list:
                downloaded_file_list.append(weight)
    if task['baseline_engine_url']:
        file_id = task['baseline_engine_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        baseline_engine = "engine_" + file_id
        if baseline_engine not in downloaded_file_list:
            print(f"下载基准引擎: {task['baseline_engine_url']}")
            result = client_helper.download_file_with_trail(task['baseline_engine_url'], FILE_PATH + baseline_engine)
            print(f"下载结果: {result}")
            if not result:
                return False
            if os.path.getsize(FILE_PATH + baseline_engine) < 1024 * 100:
                print("基准引擎文件错误")
                print("可能是网盘超限，等待")
                return False
            if baseline_engine not in downloaded_file_list:
                downloaded_file_list.append(baseline_engine)
            if not os.path.exists(FILE_PATH + baseline_engine + "_upx") and os.path.exists(FILE_PATH + baseline_engine):
                print(f"UPX 压缩: {FILE_PATH + baseline_engine}")
                os.system("chmod +x ./upx")
                os.system(f"chmod +x {FILE_PATH + baseline_engine}")
                os.system(
                    f"./upx -{random.choice([str(i) for i in range(1, 10)])} -o {FILE_PATH + baseline_engine + '_upx'} {FILE_PATH + baseline_engine}")
    if task['baseline_weight_url']:
        file_id = task['baseline_weight_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        baseline_weight = "xiangqi-" + file_id + ".nnue"
        if baseline_weight not in downloaded_file_list:
            print(f"下载基准权重: {task['baseline_weight_url']}")
            result = client_helper.download_file_with_trail(task['baseline_weight_url'], FILE_PATH + baseline_weight)
            print(f"下载结果: {result}")
            if not result:
                return False
            if os.path.getsize(FILE_PATH + baseline_weight) < 1024 * 100:
                print("基准权重文件错误")
                print("可能是网盘超限，等待")
                return False
            if baseline_weight not in downloaded_file_list:
                downloaded_file_list.append(baseline_weight)
    return True


# def heartbeat_loop():
#     count = 0
#     while thread_test is not None:
#         count += 1
#         if count % 58 * 5 == 0:
#             client_helper.heartbeat(client_id)
#             count = 0
#         time.sleep(0.2)


def get_name(url):
    return url.split("/")[-1]


def select_task(task_list):
    downloaded_tasks = []
    spsa_tasks = []
    normal_tasks = []
    for item in task_list:
        task = item["task"]
        if (task["engine_url"] == "" or get_name(task["engine_url"]) in downloaded_file_list) and \
                (task["weight_url"] == "" or get_name(task["weight_url"]) in downloaded_file_list) and \
                get_name(task["baseline_engine_url"]) in downloaded_file_list and \
                get_name(task["baseline_weight_url"]) in downloaded_file_list:
            downloaded_tasks.append(item)
        if task["type"] == "spsa":
            spsa_tasks.append(item)
        else:
            normal_tasks.append(item)
    if len(spsa_tasks) > 0:
        if len(normal_tasks) > 0 and random.random() > 0.8:
            return random.choice(normal_tasks)
        return random.choice(spsa_tasks)
    elif len(downloaded_tasks) > 0:
        return random.choice(downloaded_tasks)
    elif len(task_list) > 0:
        return random.choice(task_list)
    else:
        return None


def add_to_task(task_id, task):
    if task['engine_url']:
        file_id = task['engine_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        engine = FILE_PATH + "engine_" + file_id
    else:
        engine = ""
    if task["weight_url"]:
        file_id = task['weight_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        weight = FILE_PATH + "xiangqi-" + file_id + ".nnue"
    else:
        weight = ""
    if task["baseline_engine_url"]:
        file_id = task['baseline_engine_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        baseline_engine = FILE_PATH + "engine_" + file_id
    else:
        baseline_engine = ""
    if task["baseline_weight_url"]:
        file_id = task['baseline_weight_url'].split("/")[-1].split(".")[0].split("_")[-1].strip("_")
        baseline_weight = FILE_PATH + "xiangqi-" + file_id + ".nnue"
    else:
        baseline_weight = ""

    # for debug
    # engine = "pikafish-avx2.exe"
    # weight = "pikafish.nnue"
    # baseline_engine = "pikafish-avx2.exe"
    # baseline_weight = "pikafish.nnue"

    num_games = 6
    depth = int(task['time_control'][2])
    game_time = task['time_control'][0]
    nodes = task['nodes']
    if game_time >= 60:
        num_games = CPU_THREADS
    elif game_time >= 30:
        num_games = 2 * CPU_THREADS
    elif game_time >= 10:
        num_games = 3 * CPU_THREADS
    elif game_time >= 5:
        num_games = 6 * CPU_THREADS
    elif game_time >= 2.5:
        num_games = 12 * CPU_THREADS
    elif game_time >= 1.25:
        num_games = 24 * CPU_THREADS
    if 0 < depth <= 10 or 0 < nodes <= 50000:
        num_games = 6 * CPU_THREADS
    if task["type"] == "spsa":
        num_games = task["num_games"]
    if num_games % 2 != 0:
        num_games += 1

    tester.add_task(task_id, weight, engine, baseline_weight, baseline_engine,
                    int(task['time_control'][2]),
                    int(task['nodes']),
                    int(task['time_control'][0] * 1000),
                    int(task['time_control'][1] * 1000),
                    count=num_games,
                    uci_ops=task['uci_options'], baseline_uci_ops=task['baseline_uci_options'],
                    draw_move_limit=task['draw_move_limit'], draw_score_limit=task['draw_score_limit'],
                    win_move_limit=task['win_move_limit'], win_score_limit=task['win_score_limit'])
    print(f"添加 来自 {task_id} 的 {num_games} 个 {task['type']} 测试局面到队列成功")


def task_manage_loop():
    global running, tester
    while running:
        if len(tester.task_queue) >= CPU_THREADS:
            time.sleep(0.2)
            continue
        print("队列中任务不足，开始获取任务")
        data = client_helper.get_tasks(client_id)
        if data is None:
            print("获取任务失败")
            time.sleep(1)
            continue
        if "program_version" in data and data["program_version"] != program_version:
            print("版本不一致，请更新版本")
            running = False
            exit(0)
            continue
        task_data = select_task(data["tasks"])
        if task_data is None:
            print("没有可用任务")
            time.sleep(30)
            continue
        task_id = task_data["task_id"]
        task = task_data["task"]
        if task["type"] == "spsa":
            print("注册 spsa 任务中")
            result = client_helper.register_task(client_id, task_id)
        else:
            result = {
                "code": 0
            }
        if result["code"] == 0:
            result = download_needed_file(task_id, task)
            if result:
                add_to_task(task_id, task)
            else:
                print("下载失败，等待 60s")
                time.sleep(60)


def result_waiting_loop():
    global running
    while running:
        try:
            result_list = {}
            tester.lock.acquire()
            if len(tester.abandon_list) > 0:
                for item in tester.abandon_list.copy():
                    if item["task_id"] in tester.task_results and item["fen"] in tester.task_results[item["task_id"]]:
                        del tester.task_results[item["task_id"]][item["fen"]]
                        if len(tester.task_results[item["task_id"]]) == 0:
                            del tester.task_results[item["task_id"]]
                tester.abandon_list = []
            tester.lock.release()
            for task_id in list(tester.task_results):
                task_result = {
                    "task_id": task_id,
                    "wdl": [0, 0, 0],
                    "ptnml": [0, 0, 0, 0, 0],
                    "fwdl": [0, 0, 0],
                }
                done_fens = []
                results = tester.task_results[task_id]
                for fen in results:
                    result = results[fen]
                    if not result[0] or not result[1]:
                        continue
                    done_fens.append(fen)
                    for i in range(2):
                        res = result[i]
                        if res == "win":
                            task_result["wdl"][0] += 1
                        elif res == "lose":
                            task_result["wdl"][2] += 1
                        elif res == "draw":
                            task_result["wdl"][1] += 1
                        if i == 0:
                            if res == "win":
                                task_result["fwdl"][0] += 1
                            elif res == "lose":
                                task_result["fwdl"][2] += 1
                            elif res == "draw":
                                task_result["fwdl"][1] += 1
                    res = result[1]
                    first_result = result[0]
                    if res == "lose" and first_result == "lose":
                        task_result["ptnml"][0] += 1
                    elif res == "lose" and first_result == "draw" or \
                            res == "draw" and first_result == "lose":
                        task_result["ptnml"][1] += 1
                    elif res == "draw" and first_result == "draw" or \
                            res == "win" and first_result == "lose" or \
                            res == "lose" and first_result == "win":
                        task_result["ptnml"][2] += 1
                    elif res == "win" and first_result == "draw" or \
                            res == "draw" and first_result == "win":
                        task_result["ptnml"][3] += 1
                    elif res == "win" and first_result == "win":
                        task_result["ptnml"][4] += 1
                    else:
                        print(f"Err res:{res} first_result:{first_result}")
                if sum(task_result["wdl"]) > 0:
                    if task_id not in result_list:
                        result_list[task_id] = task_result
                    else:
                        for i in range(3):
                            result_list[task_id]["wdl"][i] += task_result["wdl"][i]
                            result_list[task_id]["fwdl"][i] += task_result["fwdl"][i]
                        for i in range(5):
                            result_list[task_id]["ptnml"][i] += task_result["ptnml"][i]
                    tester.lock.acquire()
                    for fen in done_fens:
                        tester.task_results[task_id].pop(fen)
                    tester.lock.release()

            if len(result_list) > 0:
                for task_id in list(result_list):
                    result = result_list[task_id]
                    result = client_helper.upload_result(task_id, program_version, result["wdl"], result["fwdl"],
                                                         result["ptnml"])
                    if result == "ver":
                        print(f"版本不一致，请更新版本")
                        running = False
                    else:
                        print(f"上传 {task_id} 结果:", result)
                    time.sleep(1)
        except Exception as e:
            print("Error in result_waiting_loop:", repr(e))
            traceback.print_exc()
        time.sleep(10)


if __name__ == "__main__":
    scan_existing_files()
    start_time = time.time()
    test_count = 0
    no_waiting = False
    tester.start_worker(CPU_THREADS)
    thread_result_waiting = threading.Thread(target=result_waiting_loop)
    thread_result_waiting.setDaemon(True)
    thread_result_waiting.start()
    task_manage_loop()
