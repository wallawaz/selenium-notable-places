from collections import defaultdict
import os
import string
import sys
import time

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

from pyperclip import paste as clipboard_paste
import yaml

# ignore DeprecationWarnings
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

MOVE_DELAY = 0.5
DELAY = 5
CONF = sys.argv[1]


class NotablePlaces:
    def __init__(self, config):
        self.config = config
        self.driver = webdriver.Chrome()
        self.tracker_sections = dict()
        self._parse_config()
        self.right = 0

    def _parse_config(self):
        with open(self.config) as f:
            conf = yaml.load(f)
            self.pages = {
                "app": {"url": conf["urls"]["app"]},
                "tracker": {"url": conf["urls"]["tracker"]},
                "maps_poi": {"url": None},
            }
            self.__user = conf["credentials"]["user"]
            self.__password = conf["credentials"]["password"]
            self._parse_tracker_sections(conf)

    def _parse_tracker_sections(self, conf):
        self.tracker_sections["metadata"] = conf["metadata"]
        self.tracker_sections["poi"] = conf["poi"]
        self.tracker_sections["experiences"] = conf["experiences"]

    def switch2active(self):
        return self.driver.switch_to_active_element()

    def copy_cell(self, cell, sleep=MOVE_DELAY):
        cell.send_keys(Keys.CONTROL, 'c')
        time.sleep(sleep)

    def deactivate_cell(self, cell, sleep=MOVE_DELAY):
        cell.send_keys(Keys.ESCAPE)
        time.sleep(sleep)

    def move_cell_right(self, sleep=.5):
        cell = self.switch2active()
        cell.send_keys(Keys.ARROW_RIGHT)
        time.sleep(sleep)
        self.right += 1

    def window_dance(self):
        saved_window = None
        for i, w in enumerate(self.driver.window_handles):
            if i == 0:
                saved_window = w
                continue
            self.driver.switch_to.window(w)
            self.driver.close()
        self.driver.switch_to.window(saved_window)

    def get_new_window(self, url):
        self.driver.execute_script(f"window.open('{url}','_blank');")

    def open_pages(self):
        for page in self.pages:
            if len(self.driver.window_handles) > 0:
                self.get_new_window(self.pages[page]["url"])
                self.driver.switch_to.window(self.driver.window_handles[-1])
            else:
                self.driver.get(pages[page]["url"])
            self.pages[page]["window"] = self.driver.current_window_handle

    def _wait_and_find_on_page(self, delay, selector_type, value):
        return WebDriverWait(
            self.driver,
            delay
        ).until(EC.presence_of_element_located((selector_type, value)))

    def _wait_and_clickable_on_page(self, delay, selector_type, value):
        return WebDriverWait(
            self.driver,
            delay
        ).until(EC.element_to_be_clickable((selector_type, value)))

    def _click_next(self):
        button = self._wait_and_find_on_page(DELAY, By.XPATH, "//span[@class='CwaK9']")
        button.click()
        WebDriverWait(self.driver, DELAY).until(EC.url_changes)
        time.sleep(5)

    def _enter_user(self):
        email_input = self._wait_and_find_on_page(DELAY, By.CSS_SELECTOR, "input")
        email_input.send_keys(self.__user)
        self._click_next()

    def _enter_password(self):
        pass_input = self._wait_and_find_on_page(DELAY,By.XPATH,
                                                 "//input[@type='password']")
        pass_input.send_keys(self.__password))
        self._click_next()

    def login(self):
        if self.__user is None or self.__password is None:
            sys.exit("Credentials missing in yaml config")
        logged_in = False

        # switch back to app 
        self.driver.switch_to.window(self.pages["app"]["window"])
        while not logged_in:
            self._enter_user()
            self.driver.implicitly_wait(5)
            self._enter_password()

            print("Touch input registration for browser.. waiting 12 seconds.")
            try:
                _app= self._wait_and_find_on_page(12, By.CLASS_NAME,
                                                  "pk-header-title")
                logged_in = True
            except TimeoutException:
                print("You did not login to app in time!")

    def _run(self):

        inserted = False
        run = True
        msg = "Press [Enter] to start a new topic item or any other key to quit."

        while run:
            topic, copy_data = (None, None)
            while topic is None and copy_data is None:
                topic = self._open_topic()
                copy_data = self._copy_and_paste()

            inserted = self.insert(copy_data)
            # Run again?
            run = str(input(msg)) == ""
            self.reset()
        return inserted

    def _open_topic(self):
        self.driver.switch_to.window(self.pages["app"]["window"])
        print("Please create/edit a topic list item.")
        try:
            topic_form = self._wait_and_find_on_page(12, By.CLASS_NAME,
                                                     "mat-dialog-title")
            return topic_form
        except TimeoutException:
            print("You did open a topic!")
            return

    def _copy_and_paste(self):
        self.driver.switch_to.window(self.pages["tracker"]["window"])
        ret = False
        in_correct_position = False

        msg = (
            'Please move to a new Topic row and start on Column B.\n'
            'To insert all values (Metadata, POIs, and Experiences) - enter "A"\n'
            'Only Metadata - enter "M"\n'
            'Only POIs - enter "P"\n'
            'Only Experiences enter "E"\n'
            'Choice: '
        )
        choices = ("A","M","P","E")
        while not in_correct_position:
            choice = input(msg).upper()
            in_correct_position = choice in choices
            if not in_correct_position:
                print("Invalid choice. Please try again")

        metadata = self.create_metadata_payload(choice)
        pois = self.create_poi_payload(choice)
        experiences = self.create_experiences_payload(choice)
        return {
            "metadata": metadata,
            "pois": pois,
            "experiences": experiences,
        }

    @property
    def _metadata_payload(self):
        payload = dict()
        for k, val in self.tracker_sections["metadata"].items():
            payload[val] = {"field": k}
        return payload

    def create_metadata_payload(self, choice):
        if choice not in ("A", "M"):
            for _ in range(7):
                self.move_cell_right()
            return None

        payload = self._metadata_payload

        while self.right <= max(payload.keys()):
            cell = self.switch2active()
            if self.right in payload:
                self.copy_cell(cell)
                print(
                    f"right: {self.right}, {payload[self.right]['field']}: "
                    f"{str(clipboard_paste())[:10] + '...'}"
                )
                payload[self.right]["vals"] = [clipboard_paste()]
                # De-activate the hightlighted cell.
                cell = self.switch2active()
                self.deactivate_cell(cell)

            time.sleep(.3)
            # move next
            self.move_cell_right()

        return payload

    def blank_cell(self, val):
        return val is None or str(val)[0] not in string.printable or str(val)[0] == "\n"

    def create_poi_payload(self, choice):
        if choice in ("A", "P"):
            pass
        elif choice == "E":
            return None
        else:
            return

        poi_1_position = self.tracker_sections["poi"]["start"]

        while self.right < poi_1_position:
            self.move_cell_right()

        pois = []
        poi_name = ""
        map_url = ""
        poi_number = 1
        for i in range(16):
            cell = self.switch2active()
            self.copy_cell(cell)

            val = clipboard_paste()
            if self.blank_cell(val):
                break

            if self.right % 2 == 1:
                poi_name = val
            else:
                map_url = val
                #print(f"poi: {poi_name} url: {map_url}")
                pois.append({
                    "field": f"POI#{poi_number}",
                    "vals": [poi_name, map_url],
                })
                poi_number += 1

            cell = self.switch2active()
            self.deactivate_cell(cell)

            self.move_cell_right()
        return pois

    def create_experiences_payload(self, choice):
        if choice not in ("A", "E"):
            return None

        exp_1_position = self.tracker_sections["experiences"]["start"]
        while self.right < exp_1_position:
            self.move_cell_right()

        experiences = []

        # series of 3: [mid, title, tagline]
        # only want `title`
        exp_counter = 0
        for i in range(33):
            if exp_counter > 2:
                exp_counter = 0

            cell = self.switch2active()
            self.copy_cell(cell)
            val = clipboard_paste()

            # Reached a blank cell - end.
            if self.blank_cell(val):
                break
            print(f"exp: {val}")

            if exp_counter == 1:
                experiences.append(val)

            cell = self.switch2active()
            try:
                self.deactivate_cell(cell)
            except Exception as ex:
                print(str(ex))
                continue

            self.move_cell_right()
            exp_counter += 1


        return experiences

    def insert(self, copy_data):
        if copy_data["metadata"] is not None:
            self.insert_metadata(copy_data["metadata"])
        if copy_data["pois"] is not None:
            self.insert_pois(copy_data["pois"])
        if copy_data["experiences"] is not None:
            self.insert_experiences(copy_data["experiences"])
        return True

    def insert_metadata(self, metadata):
        # switch back to app 
        self.driver.switch_to.window(self.pages["app"]["window"])


        for k in metadata.keys():

            field_dict = metadata[k]
            placeholder = field_dict["field"]
            val = field_dict["vals"][0]

            elem_type = "input"
            if placeholder.startswith("Description"):
                elem_type = "textarea"

            xpath = f"//{elem_type}[@placeholder='{placeholder}']"
            print(f"xpath: {xpath}")
            try:
                field = self._wait_and_find_on_page(DELAY, By.XPATH, xpath)
                field.send_keys(val)
                time.sleep(1)
            except TimeoutException:
                print(f"failed to find: {xpath}")
            time.sleep(MOVE_DELAY)

    def _open_poi_layer(self, add_location_xpath):
        try:
            loc_button = self._wait_and_clickable_on_page(DELAY, By.XPATH,
                                                          add_location_xpath)
            loc_button.click()
        except Exception as ex:
            print(str(ex.__class__))
            return False
        return True

    def _input_poi_name(self, poi_name, location_input_xpath):
        try:
            place_input = self._wait_and_find_on_page(DELAY, By.XPATH, location_input_xpath)
            place_input.send_keys(poi_name)
        except Exception as ex:
            print(str(ex.__cls__))
            return False
        return True

    def _submit_poi(self, select_xpath):
        try:
            select_button = self._wait_and_clickable_on_page(DELAY, By.XPATH,
                                                             select_xpath)
            select_button.click()
        except Exception as ex:
            print(str(ex))
            print("Could not submit the POI. Please click `Select`.")
            return False
        return True

    def _insert_poi_error_message(self, xpath, poi_name, closed):
        added_poi = False
        # extract the xpath search 
        error_type = xpath.split("=")[-1]
        error_type = error_type.translate(error_type.maketrans('', '', string.punctuation))

        error_messages = {
            "Add a place": [
                f"Could not Click the `Add a Place` Button.",
                f"Please Click and add {poi_name} manually.",
            ],
            "Enter a location": [
                f"Could not enter POI name.",
                f"Please enter {poi_name} manually.",
            ],
            "gmatbutton matfocusindicator matbutton matbuttonbase matprimary": [
                f"Could not submit Selected POI and PIN.",
            ],
        }
        message = error_messages.get(error_type, ["Unknown Error"])
        message.append("Press [Enter] when done")
        message = "\n".join(message)

        print(message)
        while not added_poi:
            # We were able to open the `Add a place` layer.
            # Check if it has been submitted by user now.
            if error_type != "Add a place":
                try:
                    WebDriverWait(self.driver, DELAY).until(
                        EC.invisibility_of_element_located((By.XPATH, closed))
                    )
                    added_poi = True
                except TimeoutException:
                    continue
            else:
                added_poi = input(str(message)) == ""

    def insert_pois(self, pois):
        add_location_xpath = f"//button[@mattooltip='Add a place']"
        location_input_xpath = f"//input[@placeholder='Enter a location']"
        select_button_css = "gmat-button mat-focus-indicator mat-button mat-button-base mat-primary"
        select_xpath = f"//button[@class='{select_button_css}']"

        for poi in pois:
            poi_name, poi_url = poi["vals"]
            print(f"{poi['field']}: '{poi_name}'")
            print(f"Opening POI URL")
            self._open_poi_url(poi_name, poi_url)
            time.sleep(1)
            self.driver.switch_to.window(self.pages["app"]["window"])

            if not self._open_poi_layer(add_location_xpath):
                self._insert_poi_error_message(add_location_xpath, poi_name, closed=location_input_xpath)

            if not self._input_poi_name(poi_name, location_input_xpath):
                self._insert_poi_error_message(location_input_xpath, poi_name, closed=location_input_xpath)

            self.driver.implicitly_wait(2)
            self._find_poi_address_match()

            if not self._submit_poi(select_xpath):
                self._insert_poi_error_message(select_xpath, poi_name, closed=location_input_xpath)
            #self._close_poi_url()


    def _open_poi_url(self, poi_name, poi_url):
        print(poi_name)
        print("Please search yourself.")
        self.pages["maps_poi"]["url"] = poi_url

        if self.pages["maps_poi"].get("window") is None:
            self.get_new_window(poi_url)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            self.pages["maps_poi"]["window"] = self.driver.current_window_handle
        else:
            self.driver.switch_to.window(self.pages["maps_poi"]["window"])
            self.driver.get(poi_url)
        self._get_poi_address()

    def _get_poi_address(self):
        self.pages["maps_poi"]["address"] = None
        xpath_address = "//span[@jsan='7.widget-pane-link' and not(@style='display:none')]"
        poi_address = self._wait_and_clickable_on_page(DELAY, By.XPATH,
                                                       xpath_address)
        if poi_address is not None:
            self.pages["maps_poi"]["address"] = poi_address.text

    def _close_poi_url(self):
        pass

    def insert_experiences(self, experiences):
        self.driver.switch_to.window(self.pages["app"]["window"])
        select_experiences = self._wait_and_clickable_on_page(DELAY, By.XPATH, "//mat-select")
        select_experiences.click()
        time.sleep(1)

        # List of all options after clicking experience drop-down.
        options_map = {
            option.text: option for option in self.driver.find_elements_by_xpath("//mat-option")
        }
        clicked = 0
        for exp in experiences:
            option = options_map.get(exp, None)
            if option is None:
                print(f"Could not find Experience: {exp} !")
                continue
            option.click()
            clicked += 1
            print(f"Clicked Experience: {exp}")
            time.sleep(1)
        print(f"Added {clicked} experiences")
        return

    def reset(self):
        self.right = 0

    def run(self):
        self.open_pages()
        self.login()
        ret = self._run()
        self.Killall()

    def Killall(self):
        import subprocess
        killall = subprocess.run(["killall", "chromedriver"],
                                 capture_output=True,
                                 text=True)
        if str(killall.returncode) != "0":
            print("Error killing chromedriver")
            print(killall.stdout)
            print(killall.stderr)

if __name__ == "__main__":
    notable_pl = NotablePlaces(CONF)
    notable_pl.run()
