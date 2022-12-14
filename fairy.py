import builtins
import sys
import os
import threading
import time
import subprocess
import shutil
import concurrent.futures
import random
import traceback

from stat_util import get_elo
from variantfishtest import EngineMatch


NO_OUTPUT = True


def print(*args, **kwargs):
    if not NO_OUTPUT:
        builtins.print(*args, **kwargs)


def get_latest_baseline():
    weights = []
    for file in os.listdir("./baselines"):
        if file.endswith(".nnue"):
            weights.append(int(file.split('.')[0].split("-")[-1]))
    weights.sort(reverse=True)
    return f"xiangqi-{weights[0]}"


base_engine = "./baseline_engine"
if os.name == 'nt':
    base_engine += ".exe"
base_weight = f"xiangqi-baseline.nnue"


class Tester():
    def __init__(self):
        self.win = 0
        self.lose = 0
        self.draw = 0
        self.first_stats = [0, 0, 0]
        self.ptnml = [0, 0, 0, 0, 0]
        self.working_workers = 0
        self.need_exit = False
        self.started = False
        self.dead_threads = []
        self.task_queue = []
        self.task_results = {}
        self.lock = threading.Lock()
        self.fens = []
        self.thread_list = []
        self.enable = True
        self.abandon_list = []

        book_file = os.path.abspath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "books", "xiangqi.epd"))
        if os.path.exists(book_file):
            f = open(book_file)
            for line in f:
                self.fens.append(line.rstrip(';\n'))
            f.close()

    def add_task(self, task_id, weight, engine, baseline_weight, baseline_engine, depth=None, nodes=None,
                   game_time=10000, inc_time=100, hash=256, thread_count=2, uci_ops=None, baseline_uci_ops=None,
                   draw_move_limit=-1, draw_score_limit=-1, win_move_limit=-1, win_score_limit=-1, count=6):
        fens = random.sample(self.fens, count // 2)
        if task_id not in self.task_results:
            self.task_results[task_id] = {}
        for fen in fens:
            fen = "fen " + fen
            if fen in self.task_results[task_id]:
                continue
            for order in range(2):
                self.task_queue.append({
                    "task_id": task_id,
                    "fen": fen,
                    "order": order,
                    "options": {
                        "engine": engine,
                        "weight": weight,
                        "baseline_engine": baseline_engine,
                        "baseline_weight": baseline_weight,
                        "depth": depth,
                        "nodes": nodes,
                        "game_time": game_time,
                        "inc_time": inc_time,
                        "hash": hash,
                        "thread_count": thread_count,
                        "uci_ops": uci_ops,
                        "baseline_uci_ops": baseline_uci_ops,
                        "draw_move_limit": draw_move_limit,
                        "draw_score_limit": draw_score_limit,
                        "win_move_limit": win_move_limit,
                        "win_score_limit": win_score_limit
                    },
                    "error_count": 0
                })
            self.task_results[task_id][fen] = {
                0: "",
                1: ""
            }

    def test_single(self, worker_id):
        print(f"Worker {worker_id} started.")
        self.working_workers += 1
        self.started = True
        while self.enable:
            output_cnt = 0
            while len(self.task_queue) == 0:
                output_cnt = (output_cnt + 1) % 5
                if output_cnt == 1:
                    print(f"?????? {worker_id} ????????????...")
                time.sleep(1)
                if not self.enable:
                    return
            self.lock.acquire()
            if len(self.task_queue) > 0:
                task = self.task_queue.pop()
            else:
                self.lock.release()
                continue
            self.lock.release()
            ops = task["options"]
            baseline_uci_ops = ops["baseline_uci_ops"]
            uci_ops = ops["uci_ops"]
            engine = ops["engine"]
            weight = ops["weight"]
            baseline_engine = ops["baseline_engine"]
            baseline_weight = ops["baseline_weight"]
            depth = ops["depth"]
            nodes = ops["nodes"]
            game_time = ops["game_time"]
            inc_time = ops["inc_time"]
            hash = ops["hash"]
            draw_move_limit = ops["draw_move_limit"]
            draw_score_limit = ops["draw_score_limit"]
            win_move_limit = ops["win_move_limit"]
            win_score_limit = ops["win_score_limit"]
            if baseline_uci_ops is None:
                baseline_uci_ops = {}
            if uci_ops is None:
                uci_ops = {}
            print(f"?????? {worker_id} ???????????? {task['fen']} {'Red' if task['order'] == 0 else 'Black'}")
            try:
                if not engine and not weight and not baseline_engine and not baseline_weight:
                    raise Exception("No engine or weight specified")
                if not baseline_engine:
                    raise Exception("No baseline engine specified")
                if not baseline_weight:
                    raise Exception("No baseline weight specified")
                if not engine:
                    engine = baseline_engine
                if not weight:
                    weight = baseline_weight
                if depth is not None and depth <= 0:
                    depth = None
                if nodes is not None and nodes < 0:
                    nodes = None
                if not os.path.exists(weight):
                    raise Exception("Weight File Not Exist")
                if not os.path.exists(engine):
                    raise Exception("Engine File Not Exist")
                if not os.path.exists(baseline_weight):
                    raise Exception("Baseline Weight File Not Exist")
                if not os.path.exists(baseline_engine):
                    raise Exception("Baseline Engine File Not Exist")
                if os.path.exists(engine + "_upx"):
                    engine += "_upx"
                if os.path.exists(baseline_engine + "_upx"):
                    baseline_engine += "_upx"
                if os.name != 'nt':
                    os.system(f"chmod +x {engine}")
                    os.system(f"chmod +x {baseline_engine}")
                uci_options = {
                    "Hash": hash,
                    "Threads": 1,
                    "EvalFile": weight
                }
                uci_options.update(uci_ops)
                baseline_uci_options = {
                    "Hash": hash,
                    "Threads": 1,
                    "EvalFile": baseline_weight
                }
                baseline_uci_options.update(baseline_uci_ops)
                match = EngineMatch(engine, baseline_engine,
                                    uci_options,
                                    baseline_uci_options,
                                    50000, depth=depth, nodes=nodes, gtime=game_time, inctime=inc_time,
                                    draw_move_limit=draw_move_limit, draw_score_limit=draw_score_limit,
                                    win_move_limit=win_move_limit, win_score_limit=win_score_limit)
                match.init_engines()
                match.init_book()
                time.sleep(0.2)
                if match.engines[0].process.dead or match.engines[1].process.dead:
                    raise Exception("Engine died")
                fen = task["fen"]
                task_id = task["task_id"]
                order = task["order"]
                match.init_game()
                # print(f"Worker {worker_id} before process_game")
                res = match.process_game(order, 1 - order, fen)
                # print(f"Worker {worker_id} after process_game")
                self.lock.acquire()
                if task_id in self.task_results and fen in self.task_results[task_id]:
                    self.task_results[task_id][fen][order] = res
                self.lock.release()
                for i in range(2):
                    match.engines[i].process.kill()
                print(
                    f"Worker {worker_id}|{weight}@{engine} vs {baseline_weight}@{baseline_engine} Finished {fen} {'Red' if order == 0 else 'Black'}: {res}")
                print(f"{len(self.task_queue)} tasks left")
            except Exception as e:
                task["error_count"] += 1
                if task["error_count"] <= 5:
                    self.lock.acquire()
                    self.task_queue.insert(0, task)
                    self.lock.release()
                    print(f"Worker {worker_id}|{weight}@{engine} vs {baseline_weight}@{baseline_engine} Error: {repr(e)}")
                    print("Insert task to queue")
                else:
                    self.lock.acquire()
                    for t in self.task_queue.copy():
                        if t["task_id"] == task["task_id"] and t["fen"] == task["fen"]:
                            self.task_queue.remove(t)
                    self.abandon_list.append({
                        "task_id": task["task_id"],
                        "fen": task["fen"],
                    })
                    self.lock.release()
                    print(f"Worker {worker_id}|{weight}@{engine} vs {baseline_weight}@{baseline_engine} Failed: {repr(e)}")
                    print(f"{len(self.task_queue)} tasks left")

        self.working_workers -= 1
        print(f"Worker {worker_id} exited.")

    def start_worker(self, thread_count):
        self.thread_list = []
        for i in range(thread_count):
            thread = threading.Thread(target=self.test_single, args=(i,))
            thread.setDaemon(True)
            thread.start()
            self.thread_list.append(thread)

        # return {
        #     "total": total,
        #     "win": self.win,
        #     "lose": self.lose,
        #     "draw": self.draw,
        #     "wdl": (self.win, self.draw, self.lose),
        #     "fwdl": self.first_stats,
        #     "ptnml": self.ptnml,
        #     "elo": elo,
        #     "elo_range": elo_range,
        #     "los": los
        # }


if __name__ == "__main__":
    # print(get_elo((103,120,352)))
    tester = Tester()
    tester.start_worker(2)
    tester.add_task(
        "test",
        "./files/xiangqi-34ibow.nnue",
        "./files/pkf.exe",
        "./files/xiangqi-34ibow.nnue",
        "./files/pkf.exe",
        game_time=10000,
        inc_time=100,
        count=2
    )
    # tester.add_task(
    #     "test",
    #     "xiangqi-34ibow.nnue",
    #     "engine_fce2hi",
    #     "xiangqi-34ibow.nnue",
    #     "engine_fce2hi",
    #     game_time=30000,
    #     inc_time=300,
    #     count=4
    # )
    while True:
        result_list = {}
        print(tester.task_results)
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
                print("Result of fen", fen, result)
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
                print(task_result)
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
        time.sleep(1)
