import sys
import os
import time
import subprocess
import shutil
import concurrent.futures
import random
from stat_util import get_elo
from variantfishtest import EngineMatch


base_engine = "./fsf730-bmi2"
if os.name == 'nt':
    base_engine += ".exe"


def get_latest_baseline():
    weights = []
    for file in os.listdir("./baselines"):
        if file.endswith(".nnue"):
            weights.append(int(file.split('.')[0].split("-")[-1]))
    weights.sort(reverse=True)
    return f"xiangqi-{weights[0]}"


class Tester():
    def __init__(self, count):
        self.count = count
        self.win = 0
        self.lose = 0
        self.draw = 0
        self.working_workers = 0

    def test_single(self, weight, engine, depth=None, game_time=10000, inc_time=100, hash=128, worker_id=0):
        self.working_workers += 1
        print(f"Worker {worker_id} started.")
        baseline = get_latest_baseline()
        if not engine:
            engine = base_engine
        if not weight:
            weight = f"./baselines/{baseline}.nnue"
        if depth <= 0:
            depth = None
        if not os.path.exists(f"{weight}") or not os.path.exists(f"./baselines/{baseline}.nnue"):
            print("File Not Exist")
            return
        print(engine, weight, base_engine, baseline)
        if os.name != 'nt':
            os.system(f"chmod +x {engine}")
            os.system(f"chmod +x {base_engine}")
        match = EngineMatch(engine, base_engine,
                            {"EvalFile": f"{weight}", "Hash": hash},
                            {"EvalFile": f"./baselines/{baseline}.nnue", "Hash": hash},
                            50000, depth=depth, gtime=game_time, inctime=inc_time)
        name = weight.split("/")[-1].split(".")[0]
        match.init_engines()
        match.init_book()
        last_win = 0
        last_lose = 0
        last_draw = 0
        pos = "fen " + random.choice(match.fens) if match.fens else "startpos"
        match_count = 0
        while True:
            if self.win + self.lose + self.draw + self.working_workers - 1 >= self.count and match_count % 2 == 0:
                break
            match_count += 1
            if match_count % 2 == 1:
                pos = "fen " + random.choice(match.fens) if match.fens else "startpos"
            match.init_game()
            if match_count % 2 == 1:
                res = match.process_game(0, 1, pos)
            else:
                res = match.process_game(1, 0, pos)
            win, lose, draw = res
            self.win += win - last_win
            self.lose += lose - last_lose
            self.draw += draw - last_draw
            last_win = win
            last_lose = lose
            last_draw = draw
            try:
                elo, elo_range, los = get_elo((self.win, self.lose, self.draw))
                los = los * 100
                print(f"{worker_id}|{name} vs {baseline} Total:", (self.win + self.lose + self.draw), "Win:", self.win, "Lose:", self.lose, "Draw:",
                      self.draw, "Elo:", round(elo, 1), "Elo_range:", round(elo_range, 1), "Los:", round(los, 1),
                      flush=True)
            except:
                print(f"{worker_id}|{name} vs {baseline} Total:", (self.win + self.lose + self.draw), "Win:", self.win, "Lose:", self.lose, "Draw:",
                      self.draw, flush=True)
            if self.win + self.lose + self.draw + self.working_workers - 1 >= self.count and match_count % 2 == 0:
                break
        self.working_workers -= 1
        print(f"Worker {worker_id} exited.")

    def test_multi(self, weight, engine, depth=None, game_time=10000, inc_time=100, hash=256, thread_count=2):
        baseline = get_latest_baseline()
        print(f"Start testing {weight}@{engine} with baseline {baseline}@{base_engine} on {thread_count} threads")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.test_single, weight, engine, depth, game_time, inc_time, hash, i) for i in range(thread_count)]
            result_list = [f.result() for f in futures]
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
                "elo": elo,
                "elo_range": elo_range,
                "los": los
            }


if __name__ == "__main__":
    # print(get_elo((103,120,352)))
    baseline = get_latest_baseline()
    tester = Tester(3000)
    # result = tester.test_multi("./nnue/xiangqi-712.nnue", game_time=10000, inc_time=100, thread_count=6)
    result = tester.test_multi(f"./baselines/{baseline}.nnue", game_time=10000, inc_time=100, thread_count=6)
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