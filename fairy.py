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

    def test_single(self, weight, engine, baseline_weight, baseline_engine, depth=None, nodes=None, game_time=10000, inc_time=100, hash=128, worker_id=0):
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
            match = EngineMatch(engine, baseline_engine,
                                {"EvalFile": f"{weight}", "Hash": hash},
                                {"EvalFile": f"{baseline_weight}", "Hash": hash},
                                50000, depth=depth, nodes=nodes, gtime=game_time, inctime=inc_time)
            name = weight.split("/")[-1].split(".")[0]
            match.init_engines()
            match.init_book()
            if match.engines[0].process.dead or match.engines[1].process.dead:
                raise Exception("Engine died")
            pos = "fen " + random.choice(match.fens) if match.fens else "startpos"
            match_count = 0
            first_result = ""
            while True:
                if self.win + self.lose + self.draw + self.working_workers - 1 >= self.count and match_count % 2 == 0:
                    break
                match_count += 1
                if match_count % 2 == 1:
                    pos = "fen " + random.choice(match.fens) if match.fens else "startpos"
                match.init_game()
                if match_count % 2 == 1:
                    res = match.process_game(0, 1, pos)
                    first_result = res
                    if res == "win":
                        self.first_stats[0] += 1
                    elif res == "lose":
                        self.first_stats[2] += 1
                    elif res == "draw":
                        self.first_stats[1] += 1
                else:
                    res = match.process_game(1, 0, pos)
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
                if res == "win":
                    self.win += 1
                elif res == "lose":
                    self.lose += 1
                elif res == "draw":
                    self.draw += 1
                try:
                    elo, elo_range, los = get_elo((self.win, self.lose, self.draw))
                    los = los * 100
                    print(f"{worker_id}|{match_count}|{weight}@{engine} vs {baseline_weight}@{baseline_engine} Total:", (self.win + self.lose + self.draw), "Win:",
                          self.win, "Lose:", self.lose, "Draw:",
                          self.draw, "Elo:", round(elo, 1), "Elo_range:", round(elo_range, 1), "Los:", round(los, 1),
                          flush=True)
                except:
                    print(f"{worker_id}|{match_count}|{weight}@{engine} vs {baseline_weight}@{baseline_engine} Total:", (self.win + self.lose + self.draw), "Win:",
                          self.win, "Lose:", self.lose, "Draw:",
                          self.draw, flush=True)
                if self.win + self.lose + self.draw >= self.count and match_count % 2 == 0:
                    break
        except Exception as e:
            print(repr(e))
        self.working_workers -= 1
        print(f"Worker {worker_id} exited.")

    def test_multi(self, weight, engine, baseline_weight, baseline_engine, depth=None, nodes=None, game_time=10000, inc_time=100, hash=256, thread_count=2):
        print(f"Start testing {weight}@{engine} with baseline {baseline_weight}@{baseline_engine} on {thread_count} threads")
        thread_list = []
        for i in range(thread_count):
            thread = threading.Thread(target=self.test_single, args=(weight, engine, baseline_weight, baseline_engine, depth, nodes, game_time, inc_time, hash, i))
            thread.setDaemon(True)
            thread.start()
            thread_list.append(thread)
        total = self.win + self.lose + self.draw
        while not self.need_exit:
            if self.started and self.working_workers == 0:
                break
            total = self.win + self.lose + self.draw
            time.sleep(0.1)
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
    result = tester.test_multi("xiangqi-xy.nnue", "807.exe", "xiangqi-xy.nnue", "807.exe", game_time=10000, inc_time=100, depth=9, thread_count=2)
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