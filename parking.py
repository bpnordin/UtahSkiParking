from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)
import logging
from logging.config import dictConfig
import json
import os
import re
from dotenv import load_dotenv
import time
import datetime
from pushbullet import API


class ParkingBrowser:

    def __init__(self, parkingURL):

        self.parkingURL = parkingURL
        if self.parkingURL[-1] == "/":
            self.parkingURL = self.parkingURL[:-1]

        self.userParkingCode = True  # this will get updated when we check for codes

        load_dotenv()
        self.api = API()
        self.api.set_token(os.getenv("PUSHAPI"))
        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")

        if self.email is None or self.password is None:
            logger.error(
                "issue loading environment variables password: %s email: %s",
                self.password,
                self.email,
            )
            exit(1)

        if self.email == "email" or self.password == "password":
            logger.error(
                "default value for email or password detected, password: %s email: %s",
                self.password,
                self.email,
            )
            exit(1)

        chrome_options = Options()
        chrome_options.add_argument("--enable-logging")
        chrome_options.add_argument("--log-level=0")
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        self.driver = webdriver.Chrome(options=chrome_options)

        self.driver.execute_cdp_cmd("Network.enable", {})

        self.wait = WebDriverWait(self.driver, 5)

    def login(self):
        """
        login to the HONK website
        """
        self.driver.get(self.parkingURL + "/login")
        buttonClass = "Login_submitButton__fMHAq"

        usernameField = self.wait.until(
            EC.presence_of_element_located((By.ID, "emailAddress"))
        )
        passwordField = self.wait.until(
            EC.presence_of_element_located((By.ID, "password"))
        )

        if self.email and self.password:
            usernameField.send_keys(self.email)
            passwordField.send_keys(self.password)
        else:
            logger.error("email or password is none type")

        try:
            loginButton = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, buttonClass))
            )
            logger.info("clicking login button")
            loginButton.click()
        except TimeoutException:
            logger.error(
                "could not find the login button with class name: %s", buttonClass
            )
            exit(1)

        # waiting for redirect before function ends
        try:
            self.wait.until(EC.url_to_be(self.parkingURL + "/"))
        except TimeoutException:
            logger.error(
                "log in failed, timeout on redirect after clicking login button"
            )
            exit(1)
        logger.info("login succeeded")

    def viewParkingCodes(self):
        """
        goes to the parking codes URL
        """
        url = self.parkingURL + "/parking-codes"
        self.driver.get(url)
        logger.info("going to %s", url)

    def checkActiveCodes(self):
        """
        makes sure that there is not 2 parking codes already in use
        """
        self.viewParkingCodes()
        noActiveCodePath = '//*[@id="root"]/div/div/div/div[2]/div[2]/div/h5'
        try:
            noActiveCode = self.wait.until(
                EC.presence_of_element_located((By.XPATH, noActiveCodePath))
            )
            if noActiveCode.text == "No Active Parking Codes":
                print("couldn't find promo code, gonna use your credit card bruv")
                self.userParkingCode = False
                return False
        except TimeoutException:
            logger.debug(
                "time out on finding activation code xpath: %s", noActiveCodePath
            )

        infoClass = "PromoCodeCard_info__-yFEo"
        try:
            reservation = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, infoClass))
            )
        except TimeoutException:
            logger.info(
                "couldn't find promo code, gonna use your credit card bruv, no longer checking"
            )
            self.userParkingCode = False
            return False

        text = reservation.text.strip().split("/")
        if text[0] != "2":
            logger.info("going to use free parking promo code, no longer checking")
            self.userParkingCode = True
            return True
        logger.info("no available promo codes, using credit card, no longer checking")
        self.userParkingCode = False
        return False

    def makeReservation(self):
        """
        clicks the make reservation button that is on the parking codes page
        """
        xpath = '//*[@id="root"]/div/div/div/div[2]/div[2]/div/div[2]/button'
        try:
            reserveButton = self.wait.until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            reserveButton.click()
        except TimeoutException:
            logger.error(
                "could not find the button to make reservation with promo code"
            )
            exit(1)

    def clickDay(self, year, month, day):
        """
        click on the day that is specified by year, month, day
        """
        labelClass = "mbsc-calendar-cell-text"
        xpath = "//*[normalize-space(@class) = 'mbsc-calendar-cell mbsc-flex-1-0-0 mbsc-calendar-day mbsc-ios mbsc-ltr mbsc-calendar-day-colors']"
        calendar = self.wait.until(
            EC.presence_of_all_elements_located((By.XPATH, xpath))
        )

        for c in calendar:
            # get the child element of c
            labelElement = c.find_element(By.CLASS_NAME, labelClass)
            dayString = labelElement.get_attribute("aria-label")
            dateFormat = "%A, %B %d, %Y"
            if dayString:
                if "Today" in dayString:
                    dayString = dayString.removeprefix("Today, ").strip()
                try:
                    dateObject = datetime.datetime.strptime(dayString, dateFormat)
                    dateObject2 = datetime.datetime.strptime(
                        f"{day} {month} {year}", "%d %m %Y"
                    )

                    if dateObject.date() == dateObject2.date():
                        logger.info("clicking the day on the calendar: %s", dateObject2)
                        c.click()
                        break
                except ValueError:
                    continue

    def checkout(self):
        """
        clicks the checkout button after clicking on the open day
        """
        buttonClass = "SelectRate_card__AT83w"
        try:
            buttonList = self.wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, buttonClass))
            )
        except TimeoutException:
            logger.debug("for some reason i cannot find checkout button")
            return False
        price = {}
        for button in buttonList:
            buttonText = button.text
            match = re.search(r"\$(\d+)", buttonText)
            if match:
                i = match.group(1)
                try:
                    i = int(i)
                    price[i] = button
                except ValueError:
                    logger.error(f"could not turn price to integer{i}")
                    exit(1)
            else:
                logger.debug("no match for $integers on string: %s", buttonText)
        minKey = min(price.keys())
        button = price[minKey]
        button.click()

        # click pay button
        payButtonClass = "CtaButton--container"
        try:
            payButton = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, payButtonClass))
            )
            payButton.click()
        except TimeoutException:
            logger.error(
                "could not find the pay button with class name: %s", payButtonClass
            )
            exit(1)

        # confirm pay button
        floatXPATH = "//*[normalize-space(@class) = 'ui modal transition visible active ui modal small PurchaseConfirm basic ModalWithClose']"
        try:
            floatElement = self.wait.until(
                EC.presence_of_element_located((By.XPATH, floatXPATH))
            )
            checkoutButton = floatElement.find_element(
                By.XPATH,
                "//button[contains(@class, 'ButtonComponent') and text()=\"Confirm\"]",
            )
            checkoutButton.click()
            logger.info("should be reserved now")
            return True
        except TimeoutException:
            logger.error(
                "could not find the float element for confirming the license plate"
            )
            exit(1)
        except NoSuchElementException:
            logger.error("could not find the confirm play button")
            exit(1)

    def getJSONData(self):
        """
        should get the json data after refreshing the page. This is the most prone to breaking
        """
        logs = self.driver.get_log("performance")
        data = {}
        for log in logs:
            message = json.loads(log["message"])
            network_event = message["message"]
            try:
                request_id = network_event["params"]["requestId"]
                try:
                    if network_event["method"] == "Network.loadingFinished":
                        response_body = self.driver.execute_cdp_cmd(
                            "Network.getResponseBody", {"requestId": request_id}
                        )
                        body = response_body["body"]
                        try:
                            data = json.loads(body.strip())
                            if "data" in data.keys():
                                if "publicParkingAvailability" in data["data"].keys():
                                    logger.debug(
                                        "got the publicParkingAvailability network json data"
                                    )
                                    data = data["data"]["publicParkingAvailability"]
                                    return data
                                elif (
                                    "privateParkingAvailability" in data["data"].keys()
                                ):
                                    logger.debug(
                                        "got the privateParkingAvailability network json data"
                                    )
                                    data = data["data"]["privateParkingAvailability"]
                                    return data

                        except json.decoder.JSONDecodeError:
                            pass
                except KeyError:
                    pass
                except WebDriverException:
                    pass
            except KeyError:
                pass
        return None

    def run(self, year, month, day):
        """
        runs the whole program, refresh every 30 seconds if it is not available, checkout if it is
        """

        if self.userParkingCode:
            if not self.checkActiveCodes():
                self.userParkingCode = False
                self.driver.get(self.parkingURL + "/select-parking")
                # gonna wait for the element to be loaded before moving on
            else:
                self.viewParkingCodes()
                self.makeReservation()

        calendarXPATH = "//*[normalize-space(@class) = 'mbsc-calendar-cell mbsc-flex-1-0-0 mbsc-calendar-day mbsc-ios mbsc-ltr mbsc-calendar-day-colors']"
        try:
            self.wait.until(EC.element_to_be_clickable((By.XPATH, calendarXPATH)))
        except TimeoutException:
            logger.error("could not find the calendar element on the page")
            exit(1)

        waitCount = 0
        while True:
            # TODO make sure this is always getting good data
            data = self.getJSONData()
            if data is not None:
                try:
                    soldOut = data[f"{year}-{month}-{day}T00:00:00-07:00"]["status"][
                        "sold_out"
                    ]
                    logger.info("sold out on %s-%s: %s", month, day, soldOut)
                except KeyError as e:
                    logger.error("the datetime could not be found as a key in the return object %s",e)
                    exit(1)

            else:
                time.sleep(0.1)  # rate limit out log checking a lill
                waitCount = waitCount + 1
                if waitCount >= 20:
                    logger.debug(
                        "issue with getting the network info, just gonna wait 20 seconds"
                    )
                    waitCount = 0
                    soldOut = True
                else:
                    continue
            if not soldOut:
                logger.info("going to try and click the day")
                self.clickDay(year, month, day)
                if self.checkout():
                    logger.info("sending push bullet notification")
                    self.api.send_note("open", f"{day}")
                    logger.info(
                        "sleeping so you can make sure that the web page is showing the reservation"
                    )
                    time.sleep(1000000)
                    break

            logger.info("sleeping for 20 seconds")
            time.sleep(20)
            if self.userParkingCode:
                logger.info("refreshing by clicking parking code again")
                self.viewParkingCodes()
                self.makeReservation()
                self.wait.until(EC.element_to_be_clickable((By.XPATH, calendarXPATH)))
            else:
                logger.info("refreshing the page")
                self.driver.refresh()
                self.wait.until(EC.element_to_be_clickable((By.XPATH, calendarXPATH)))
def resortPicker():
    """
    get the resort the user wants to get parking for
    """
    altaURL = "https://reserve.altaparking.com"
    brightonURL = "https://reservenski.parkbrightonresort.com"
    solitudeURL = "https://reservenski.parksolitude.com/"
    resortOptions = {"Alta": altaURL, "Brighton": brightonURL, "Solitude": solitudeURL}
    options = {}

    for i, resort in enumerate(resortOptions):
        print(f"{i+1}). {resort} -- {resortOptions[resort]}")
        options[i + 1] = resortOptions[resort]
    selectionInt = input("Enter number: ")

    try:
        if 1 <= int(selectionInt) <= len(resortOptions):
            selectionInt = int(selectionInt)
        else:
            logger.error(f"please input a number between 1 and {len(resortOptions)}")
            exit(0)
    except Exception as e:
        logger.error(e)
        logger.error(f"please input a number between 1 and {len(resortOptions)}")
        exit(0)

    return options[selectionInt]

def dayPicker():
    today = datetime.datetime.now()
    modifyDefaultDay = 0
    if today.weekday() < 4:
        #it is the weekday
        modifyDefaultDay = ((12 - today.weekday()) % 7) - 1
    elif today.weekday == 4 and today.hour >= 8:
        #no parking today, must be parking tmro or more
        modifyDefaultDay = 1

    defaultDay = today + datetime.timedelta(days=modifyDefaultDay)
    
    print("enter year, month, day, you can just press enter on any day to keep the default (parenthesis)")
    year = input("year (2025):")
    if year == "":
        year = "2025"
    month = input(f"month ({defaultDay.month}):")
    if month == "":
        month = defaultDay.month
    day = input(f"day ({defaultDay.day}):")
    if day == "":
        day = defaultDay.day

    if len(str(month)) == 1:
        month = "0"+str(month)
    if len(str(day)) == 1:
        day = "0"+str(day)

    return (str(year),str(month),str(day))



if __name__ == "__main__":
    LOGGING_CONFIG = {
        "version": 1,
        "formatters": {
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
        },
        "handlers": {
            "default": {
                "level": "INFO",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "level": "DEBUG",
                "formatter": "standard",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "log/log.log",
                "mode": "a",
                "backupCount": 5,
                "maxBytes": 100000,
            },
        },
        "loggers": {
            "__main__": {
                "handlers": ["default", "file"],
                "level": "DEBUG",
            },
        },
    }


    logger = logging.getLogger(__name__)
    dictConfig(LOGGING_CONFIG)


    url = resortPicker()
    #year, month, day = ("2025", "01", "12")
    year, month, day = dayPicker()
    browser = ParkingBrowser(url)
    browser.login()
    try:
        browser.run(year, month, day)
    except Exception as e:
        logger.error(e)
