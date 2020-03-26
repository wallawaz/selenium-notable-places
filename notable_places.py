import csv
import random
import re
import sys
import time

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from urllib.parse import urlencode

args = sys.argv
input_file = args[1]

TYPES = [
    "Street","Square/plaza","Canal","Park","Train/bus/transit station",
    "Trail/path","Building","Bridge","Highway","Roundabout","Other","Unsure",
]
TYPE_DICT = {
    i: value for i, value in enumerate(TYPES)
}
DELAY = 5
BLURB_CLASS = "kno-rdesc"

def rdx():
    return random.choice([.333, .334, .335, .336])

class Chrome:
    def __init__(self):
        self.driver = webdriver.Chrome()
        self.notable_places = []

    def get_input_file(self, input_file):
        self.output_file = open(input_file + ".out.csv", "a")

        with open(input_file, "r") as fp:
            csvf = csv.DictReader(fp)
            self.writer = csv.DictWriter(self.output_file,
                                         fieldnames=csvf.fieldnames)
            print(self.writer.fieldnames)

            for line in csvf:
                self.notable_places.append(line)
            return

    def get_type(self):
        for k in TYPE_DICT.keys():
            print(f"{k}: {TYPE_DICT[k]}")

        t = None
        while not t:
            try:
                i = int(input("Enter Type Number: "))
            except ValueError:
                i = int(input("Incorrect Type Number, please enter again."))
            if i not in TYPE_DICT:
                print("Type Number not found, please enter again.")
                continue
            t = TYPE_DICT[i]
        return t

    def google_search(self, name, destination):
        search = "https://www.google.com/search?"
        search_str = name + " " + destination
        q = {"q": search_str}
        return search + urlencode(q)

    def get_comments(self, line):
        comments = str(input("Comments (leave blank if none): "))
        if comments:
            line["comments"] = comments
        return line

    def get_blurb(self):
        w2 = self.driver.window_handles[1]
        self.driver.switch_to.window(w2)
        try:
            blurb = WebDriverWait(
                self.driver,
                DELAY
            ).until(EC.presence_of_element_located((By.CLASS_NAME,
                                                    BLURB_CLASS)))
            blurb = blurb.text.split("\n")[-1]
        except TimeoutException:
            blurb = None
        return blurb

    def regex_search(self, search):
        types = [
            t.replace("/","|").lower() for t in TYPES
        ]
        for i, t in enumerate(types):
            if re.search(t, search, re.IGNORECASE):
                return TYPES[i]
        return None

    def get_type_from_blurb(self, blurb):
        return self.regex_search(blurb)

    def get_type_from_search_results(self):
        self.driver.switch_to.window(
            self.driver.window_handles[1]
        )
        search_class = "rc"
        results = self.driver.find_elements_by_class_name(search_class)

        # top 3 results
        n = 0
        for res in results:
            match = self.regex_search(res.text)
            if match:
                return match
            n += 1
            if n == 3:
                return None

    def get_user_input(self, line):
        print(f"|| {line['name']} ||")
        self.driver.get(line["url"])
        time.sleep(rdx())
        search_string = self.google_search(line["name"], line["destination"])

        # Open another tab with a Google Search for the Place name.
        self.driver.execute_script(f"window.open('{search_string}','_blank');")
        time.sleep(rdx())
        blurb = self.get_blurb()
        _type = None
        correct = "N"
        if blurb:
            _type = self.get_type_from_blurb(blurb)
            if _type:
                print(f"matched blurb: {_type}")
                correct = str(input("Correct (Y/N): "))
        else:
            print("No blurb found. Trying search results")
            _type = self.get_type_from_search_results()
            if _type:
                print(f"matched search results: {_type}")
                correct = str(input("Correct (Y/N): "))

        if correct.upper() == "Y":
            line["type"] = _type
        else:
            user_defined_type = self.get_type()
            line["type"] = user_defined_type

        line = self.get_comments(line)

        # close the second window opened
        self.writer.writerow(line)

    def window_dance(self):
        saved_window = None
        for i, w in enumerate(self.driver.window_handles):
            if i == 0:
                saved_window = w
                continue
            self.driver.switch_to.window(w)
            self.driver.close()
        self.driver.switch_to.window(saved_window)

    def run(self):
        for line in self.notable_places:
            if line.get("type") is not None and line.get("type") != "":
                print(line["name"], "already defined")
                self.writer.writerow(line)
                continue
            self.get_user_input(line)
            self.window_dance()

        self.output_file.close()


if __name__ == "__main__":
    chrome = Chrome()
    chrome.get_input_file(input_file)
    chrome.run()
