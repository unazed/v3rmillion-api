import sys
import time
import pprint

from functools import wraps

try:

    from selenium import webdriver
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.expected_conditions import presence_of_element_located
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import NoSuchElementException
except ImportError:
    sys.exit("[1] Make sure to install Selenium for your Python version.")


class API(object):
    """
    Provides an interface to the https://www.v3rmillion.net/ website.
    """

    driver = "Chrome"
    url = "https://v3rmillion.net/index.php"
    alerts_url = "https://v3rmillion.net/alerts.php"
    pm_url = "https://v3rmillion.net/private.php"
    pm_send_url = "https://v3rmillion.net/private.php?action=send"
    max_alert_listing = 10

    try:
        driver = getattr(webdriver, driver)()
    except Exception:  # selenium throws Exception for some reason
        sys.exit("[1] Make sure you have the %r webdriver" % driver)

    def __init__(self, login=None, timeout=6, interactive=False):
        self.iprint("Initializer loaded.", interactive)
        self.timeout = timeout
        self.interactive = interactive
        self._login = False
        self._webdriver_closed = False

        if login is None:
            return
        
        self.username = login[0]
        # we want to discard the password as soon as possible so we don't store it.

        if interactive:
            self.driver.close()
            try:
                self.driver = webdriver.Chrome()
            except Exception:
                sys.exit("[1] No Chrome driver found for interactive mode.")

        if login[1:]:
            self.iprint("Logging in.")
            self.login(login[0], login[1])
        else:
            raise IndexError("Pass a full login tuple in the form (\"username\", \"password\")")
    
    def iprint(self, msg, interactive=None, use_input=False):
        if interactive is None:
            interactive = self.interactive
        
        if interactive:
            if not use_input:
                return print("INTERACTIVE: " + msg)
            input("INTERACTIVE (input): " + msg)

    def requires_login(func):
        def wrapper(*args, **kwargs):
            if not args[0]._login:
                raise PermissionError("Login first using the API.login(...) method")
            return func(*args, **kwargs)
        return wrapper

    def _recaptcha_login(self, username, password):
        username_textbox = self.driver.find_element_by_name("username")
        username_textbox.send_keys(username + Keys.TAB)

        password_textbox = self.driver.find_element_by_name("password")
        password_textbox.send_keys(password + Keys.ENTER)

        divs = self.driver.find_elements_by_xpath("//div[@class]")
        anchors = self.driver.find_elements_by_xpath("//a[@href]")

        for div, anchor in zip(divs, anchors):
            if anchor.get_attribute("href") == "member.php?action=lostpw":
                self.driver.close()
                raise LookupError("Invalid credentials.")
            elif div.get_attribute("class") == "error":
                if not self.interactive:
                    self.driver.close()
                    raise LookupError("reCAPTCHA required to be solved due to too many incorrect logins")
                else:
                    self.iprint("reCAPTCHA found, solve it please.", use_input=True)
                    self._recaptcha_login(username, password)

    def login(self, username, password):
        if self._login:
            self.iprint("Already logged in")
            return

        self.driver.get(self.url)
        WebDriverWait(self.driver, self.timeout).until(presence_of_element_located((By.ID, 'content')))
        
        # at this point, the website has loaded to the login page

        username_textbox = self.driver.find_element_by_name("username")
        username_textbox.send_keys(username + Keys.TAB)

        password_textbox = self.driver.find_element_by_name("password")
        password_textbox.send_keys(password + Keys.ENTER)

        # we should be in!
        
        self.driver.implicitly_wait(1)

        # let's verify
        
        divs = self.driver.find_elements_by_xpath("//div[@class]")
        anchors = self.driver.find_elements_by_xpath("//a[@href]")
        for div, anchor in zip(divs, anchors):
            if anchor.get_attribute("href") == "member.php?action=lostpw":
                # is there an <a> tag which guides us where to recover our passwords?
                
                self.driver.close()
                raise LookupError("Invalid credentials.")
            elif div.get_attribute("class") == "error":
                # reCAPTCHA notice found?

                if not self.interactive:
                    self.driver.close()
                    raise LookupError("reCAPTCHA required to be solved due to too many incorrect logins")
                else:
                    self.iprint("reCAPTCHA found, solve it please.", use_input=True)
                    self._recaptcha_login(username, password)
        self._login = True
    
    @requires_login
    def get_alert_count(self):
        self.driver.refresh()
        try:
            alerts = int(self.driver.find_element_by_xpath("//span[contains(@class, 'alert_count alert_new')]").text)
        except (IndexError, NoSuchElementException):
            return 0
        return alerts

    @requires_login
    def get_pm_count(self):
        self.driver.refresh()
        try:
            pms = int(self.driver.find_element_by_xpath("//span[contains(@class, 'pm_count pm_new')]").text)
        except (IndexError, NoSuchElementException):
            return 0
        return pms
    
    @requires_login
    def get_pm_alert_count(self):
        self.driver.refresh()
        try:
            alerts = int(self.driver.find_element_by_xpath("//span[contains(@class, 'alert_count alert_new')]").text)
        except (IndexError, NoSuchElementException):
            alerts = 0
        try:
            pms = int(self.driver.find_element_by_xpath("//span[contains(@class, 'pm_count pm_new')]").text)
        except (IndexError, NoSuchElementException):
            pms = 0
        
        return {
            "alerts": alerts,
            "pms": pms
        }

    @requires_login
    def get_latest_n_alerts(self, n):
        if n > self.max_alert_listing:
            raise IndexError("Can't retrieve more than %d alerts." % self.max_alert_listing)

        self.driver.get(self.alerts_url)

        WebDriverWait(self.driver, self.timeout).until(presence_of_element_located((By.ID, 'latestAlertsListing')))

        alerts_table = self.driver.find_element_by_xpath("//tbody[contains(@id, 'latestAlertsListing')]")
        alert_rows = alerts_table.find_elements_by_xpath("//tr[contains(@class, 'alert-row')]")

        for alert, _ in zip(alert_rows, range(n)):
            try:
                user_data, alert_data, date = alert.find_elements_by_xpath(".//td[contains(@class, 'trow')]")
            except ValueError:
                yield alert.get_attribute("innerHTML")
            yield {
                "avatar_link": user_data.find_element_by_class_name("avatar").find_elements_by_xpath(".//img")[0].get_attribute("src"),
                "username": alert_data.find_element_by_xpath(".//a/span[@style]").text,
                "action": alert_data.find_element_by_xpath(".//a").text,
                "time": date.text,
            }

        self.driver.get(self.url)  # restore position

    @requires_login
    def pm_read(self, username, title, silent=False, debug=False):
        self.driver.get(self.pm_url)
        pms = self.driver.find_elements_by_xpath("/html/body/div[3]/div/div[2]/form/table/tbody/tr/td[2]/table/tbody/tr")[2:-1]

        if not pms:
            if not silent and not debug:
                raise LookupError("No PMs found in PM directory")
            return False
        
        _ = 0
        for pm in pms:
            pm_title, pm_sender = pm.find_elements_by_xpath(".//td")[2:4]

            if pm_title.text == title and pm_sender.text == username:
                _ += 1
                break
        
        if not _:
            if not silent and not debug:
                raise LookupError("No PMs found that match the parameters")
            return False

        pm.find_element_by_xpath(".//a[@href]").click()
        message = self.driver.find_element_by_xpath("//*[@id='pid_']").text
        self.driver.get(self.url)
        return message

    @requires_login
    def pm_send(self, username, title, content):
        if not username[2:]:
            raise NameError("The name must be longer than 2 characters.")
        elif not title or not content:
            raise ValueError("The title and content must be at least 1 character.")

        self.driver.get(self.pm_send_url)
        username_input = self.driver.find_element_by_id("s2id_autogen1")
        username_input.send_keys(username)
        time.sleep(2)
        username_input.send_keys(Keys.ENTER)

        title_input = self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/form/table/tbody/tr/td[2]/table/tbody/tr[4]/td[2]/input")
        title_input.send_keys(title)

        content_input = self.driver.find_element_by_xpath("//*[@id=\"content\"]/form/table/tbody/tr/td[2]/table/tbody/tr[6]/td[2]/div/iframe")
        content_input.click()
        content_input.send_keys(content)

        self.driver.find_element_by_xpath('//*[@id="content"]/form/table/tbody/tr/td[2]/div/input[1]').click()
        time.sleep(1)

        general_error = self.driver.find_elements_by_xpath("/html/body/div[3]/div/div[2]/form/table/tbody/tr/td[2]/div[1]")
        recently_pmed_error = self.driver.find_elements_by_xpath("//*[@id=\"content\"]/table/tbody/tr[2]/td") 

        if general_error:
            if general_error[0].text:
                raise Exception(general_error[0].text)
        elif recently_pmed_error:
            raise Exception(recently_pmed_error[0].text)
        
        self.driver.get(self.url)

    def close(self):
        # alias method for self.__del__()

        self.__del__()

    def __del__(self):
        # possibly unsafe, needs experimentation

        if not self._webdriver_closed:
            self.driver.close()
            self._webdriver_closed = True
         
