import argparse
import json
import requests
import time
import sys

from datetime import datetime
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

NUMBER_OF_IRRIGATION_PROGRAM_STEPS = 6

VALVE_STEP_TRANSITION_DELAY = 30
VALVE_TRANSITION_DELAY = 30


class IrrigationProgram:
    def __init__(self, id, name, steps):
        self.id = id
        self.name = name

        if len(steps) != NUMBER_OF_IRRIGATION_PROGRAM_STEPS:
            raise Exception(
                f"Invalid number of steps. Expected {NUMBER_OF_IRRIGATION_PROGRAM_STEPS}"
            )

        self.steps = steps


def load_irrigation_programs(irrigation_programs_file):
    with open(irrigation_programs_file, "r") as f:
        return list(map(lambda p: IrrigationProgram(**p), json.load(f)))


def list_irrigation_programs(file):
    irrigation_programs = load_irrigation_programs(file)

    for irrigation_program in irrigation_programs:
        print(
            f"🔹 id: {irrigation_program.id}, name: {irrigation_program.name}, steps: {irrigation_program.steps}"
        )


@retry(stop=stop_after_attempt(12), wait=wait_fixed(10))
def open_valve(ipv4, step):
    try:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}    -> Opening valve for {step} seconds...")
        res = requests.post(f"http://{ipv4}/valve/open")

        if res.status_code != 200:
            raise Exception("Failed to open valve")
    except requests.exceptions.ConnectionError:
        raise Exception("Failed to open valve")


@retry(stop=stop_after_attempt(12), wait=wait_fixed(10))
def close_valve(ipv4):
    try:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}    -> Closing valve...")
        res = requests.post(f"http://{ipv4}/valve/close")

        if res.status_code != 200:
            raise Exception("Failed to close valve")
    except requests.exceptions.ConnectionError:
        raise Exception("Failed to close valve")


def run_irrigation_program(file, id, ipv4):
    irrigation_programs = load_irrigation_programs(file)

    irrigation_program = next(filter(lambda p: p.id == int(id), irrigation_programs))

    print(f"Running irrigation program {irrigation_program.name}...")

    try:
        for idx, step in enumerate(irrigation_program.steps):
            if step is None:
                break

            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Running step {idx + 1}/{NUMBER_OF_IRRIGATION_PROGRAM_STEPS}...")
            open_valve(ipv4, step)
            time.sleep(VALVE_TRANSITION_DELAY + step)
            close_valve(ipv4)
            time.sleep(VALVE_TRANSITION_DELAY + VALVE_STEP_TRANSITION_DELAY)

        print("Irrigation program finished.")
    except RetryError:
        print(
            "❌ Failed to complete the irrigation program. Please check the irrigation distributor and try again",
            file=sys.stderr,
        )


def main():
    parser = argparse.ArgumentParser(description="Irrigation controller.")

    parser.add_argument("--file", help="irrigation programs file", required=True)

    parser.add_argument(
        "--ipv4",
        help="ipv4 address",
    )

    parser.add_argument("--list", help="list irrigation programs", action="store_true")

    parser.add_argument("--run", help="run irrigation program", metavar="ID")

    args = parser.parse_args()

    if not args.list and not args.run:
        parser.error("No action requested, add --list or --run")

    if args.list:
        list_irrigation_programs(args.file)
    if args.run:
        run_irrigation_program(args.file, args.run, args.ipv4)


if __name__ == "__main__":
    main()
