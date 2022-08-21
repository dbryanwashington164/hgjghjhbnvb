import sys
import os
import threading
import time
import subprocess
import shutil
import concurrent.futures
import random
from stat_util import get_elo
from variantfishtest import EngineMatch
import client


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
    def __init__(self, count):
        self.count = count
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

        book_file = os.path.abspath(
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "books", "xiangqi.epd"))
        if os.path.exists(book_file):
            f = open(book_file)
            for line in f:
                self.fens.append(line.rstrip(';\n'))
            f.close()

        for i in range(count // 2):
            fen = random.choice(self.fens)
            self.fens.remove(fen)
            fen = "fen " + fen
            self.task_queue.append((fen, 0, 1))
            self.task_queue.append((fen, 1, 0))
            self.task_results[fen] = {
                0: "",
                1: ""
            }

    def test_single(self, weight, engine, baseline_weight, baseline_engine, depth=None, nodes=None,
                    game_time=10000, inc_time=100, hash=128, worker_id=0, uci_ops=None, baseline_uci_ops=None,
                    draw_move_limit=-1, draw_score_limit=-1, win_move_limit=-1, win_score_limit=-1):
        if baseline_uci_ops is None:
            baseline_uci_ops = {}
        if uci_ops is None:
            uci_ops = {}
        self.working_workers += 1
        self.started = True
        print(f"Worker {worker_id} started.")
        try:
            if not engine and not weight and not baseline_engine and not baseline_weight:
                self.need_exit = True
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
            if not os.path.exists(weight) or not os.path.exists(baseline_weight):
                print("Weight File Not Exist")
                return
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
            if match.engines[0].process.dead or match.engines[1].process.dead:
                raise Exception("Engine died")
            while True:
                self.lock.acquire()
                if len(self.task_queue) == 0:
                    self.lock.release()
                    break
                task = self.task_queue.pop(0)
                self.lock.release()
                fen = task[0]
                match.init_game()
                res = match.process_game(task[1], task[2], fen)
                self.lock.acquire()
                self.task_results[fen][task[1]] = res
                self.lock.release()
                print(f"Worker {worker_id}|{weight}@{engine} vs {baseline_weight}@{baseline_engine} Finished {fen} {'Red' if task[1] == 0 else 'Black'}: {res}")
                print(f"{len(self.task_queue)} tasks left")
                client.last_output_time = time.time()
        except Exception as e:
            print(repr(e))
            if "terminated" in repr(e):
                self.dead_threads.append(worker_id)
        self.working_workers -= 1
        print(f"Worker {worker_id} exited.")

    def test_multi(self, weight, engine, baseline_weight, baseline_engine, depth=None, nodes=None,
                   game_time=10000, inc_time=100, hash=256, thread_count=2, uci_ops=None, baseline_uci_ops=None,
                   draw_move_limit=-1, draw_score_limit=-1, win_move_limit=-1, win_score_limit=-1):
        print(
            f"Start testing {weight}@{engine} with baseline {baseline_weight}@{baseline_engine} on {thread_count} threads")
        thread_list = []
        for i in range(thread_count):
            thread = threading.Thread(target=self.test_single, args=(weight, engine,
                                                                     baseline_weight, baseline_engine,
                                                                     depth, nodes, game_time, inc_time, hash, i,
                                                                     uci_ops, baseline_uci_ops,
                                                                     draw_move_limit, draw_score_limit,
                                                                     win_move_limit, win_score_limit))
            thread.setDaemon(True)
            thread.start()
            thread_list.append(thread)

        while not self.need_exit:
            if self.started and self.working_workers == 0:
                break
            for died in self.dead_threads.copy():
                thread = threading.Thread(target=self.test_single, args=(
                    weight, engine, baseline_weight, baseline_engine, depth, nodes, game_time, inc_time, hash,
                    died))
                thread.setDaemon(True)
                thread.start()
                thread_list.append(thread)
                self.dead_threads.remove(died)
            time.sleep(0.1)
        for task_id in self.task_results:
            result = self.task_results[task_id]
            for i in range(2):
                res = result[i]
                if res == "win":
                    self.win += 1
                elif res == "lose":
                    self.lose += 1
                elif res == "draw":
                    self.draw += 1
                if i == 0:
                    if res == "win":
                        self.first_stats[0] += 1
                    elif res == "lose":
                        self.first_stats[2] += 1
                    elif res == "draw":
                        self.first_stats[1] += 1
            res = result[1]
            first_result = result[0]
            if res == "lose" and first_result == "lose":
                self.ptnml[0] += 1
            elif res == "lose" and first_result == "draw" or \
                    res == "draw" and first_result == "lose":
                self.ptnml[1] += 1
            elif res == "draw" and first_result == "draw" or \
                    res == "win" and first_result == "lose" or \
                    res == "lose" and first_result == "win":
                self.ptnml[2] += 1
            elif res == "win" and first_result == "draw" or \
                    res == "draw" and first_result == "win":
                self.ptnml[3] += 1
            elif res == "win" and first_result == "win":
                self.ptnml[4] += 1
            else:
                print(f"Err res:{res} first_result:{first_result}")
        total = self.win + self.lose + self.draw
        elo, elo_range, los = 0, 0, 50
        if self.lose > 0 and self.draw > 0:
            elo, elo_range, los = get_elo((self.win, self.lose, self.draw))
            los = los * 100
        return {
            "total": total,
            "win": self.win,
            "lose": self.lose,
            "draw": self.draw,
            "wdl": (self.win, self.draw, self.lose),
            "fwdl": self.first_stats,
            "ptnml": self.ptnml,
            "elo": elo,
            "elo_range": elo_range,
            "los": los
        }


if __name__ == "__main__":
    # print(get_elo((103,120,352)))
    tester = Tester(8)
    # result = tester.test_multi("./nnue/xiangqi-712.nnue", game_time=10000, inc_time=100, thread_count=6)
    result = tester.test_multi("xiangqi-xy.nnue", "819.exe", "xiangqi-xy.nnue", "807.exe", game_time=10000,
                               inc_time=100, depth=9, thread_count=2)
    print(result)
    # with open("test_sep.txt", "r") as f:
    #     tested_log = f.read()
    # results = []
    # for file in os.listdir("./test_seq"):
    #     if file in tested_log:
    #         continue
    #     tester = Tester(2000)
    #     result = tester.test_multi("./test_seq/" + file, depth=9, game_time=10000, inc_time=1000, thread_count=8)
    #     results.append(result)
    #     with open("test_sep.txt", "a") as f:
    #         f.write(f"{file} Total: {result['total']} Win: {result['win']} Lose: {result['lose']} Draw: {result['draw']} ELO: {result['elo']} +-{result['elo_range']} LOS: {result['los']}\n")
    #     print(result)
    # print(results)
