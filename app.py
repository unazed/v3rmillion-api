import sys
import time
import re

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
    usersearch_url = "https://v3rmillion.net/memberlist.php?sort=username&order=ascending&perpage=500&username=%s&page=%d"
    profile_url = "https://v3rmillion.net/member.php?action=profile&uid=%s"

    uid_from_url = re.compile(r".+\?.+uid=(\d+)")

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

    def _get_profile(self, username=None, uid=None, page_depth=10):
        if username is None and uid is None:
            raise Exception("Either provide a username or a UID")

        if uid is not None:
            self.driver.get(self.profile_url % uid)

            error = self.driver.find_elements_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr[2]/td")

            if error and "The member you specified is either invalid or doesn't exist." in error[0].text:
                raise LookupError("Couldn't find user by UID.")
            thread_count = self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[5]/td[2]").text
            thread_count = thread_count.split('(')[0]

            post_count = self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[4]/td[2]").text
            post_count = post_count.split('(')[0]

            data = {
                "username": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/fieldset/table/tbody/tr/td[1]/span[1]/strong/span/strong").text,
                "status": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/fieldset/table/tbody/tr/td[1]/span[2]/span").text,
                "last_visit": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[3]/td[2]").text,
                "joined": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[2]/td[2]").text,
                "time_spent_online": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[6]/td[2]").text,
                "signature": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[3]/table[1]/tbody/tr[2]/td").text,
                "members_referred": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[7]/td[2]").text,
                "thread_count": int(thread_count),
                "post_count": int(post_count),
                "reputation": int(self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[8]/td[2]/strong").text)
            }

            self.driver.get(self.url)

            return data

        found = False
        
        for page in range(1, page_depth+1):
            if found:
                break

            self.driver.get(self.usersearch_url % (username, page))           
            error = self.driver.find_elements_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr[3]/td")

            if error and "There were no members found with the search criteria you entered." in error[0].text:
                raise LookupError("Couldn't find user by username.")

            for user in self.driver.find_elements_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr"):
                name = user.find_element_by_xpath(".//a")
                if name.text == username:
                    name.click()
                    found = True
                    break

        thread_count = self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[5]/td[2]").text
        thread_count = thread_count.split('(')[0]

        post_count = self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[4]/td[2]").text
        post_count = post_count.split('(')[0]

        status = self.driver.find_elements_by_xpath("/html/body/div[3]/div/div[2]/fieldset/table/tbody/tr/td[1]/span[2]/a[1]/span")

        if status:
            status = "Online"
        else:
            status = "Offline"

        data = {
            "username": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/fieldset/table/tbody/tr/td[1]/span[1]/strong/span/strong").text,
            "status": status,
            "last_visit": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[3]/td[2]").text,
            "joined": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[2]/td[2]").text,
            "time_spent_online": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[6]/td[2]").text,
            "signature": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[3]/table[1]/tbody/tr[2]/td").text,
            "members_referred": self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[7]/td[2]").text,
            "thread_count": int(thread_count),
            "post_count": int(post_count),
            "reputation": int(self.driver.find_element_by_xpath("/html/body/div[3]/div/div[2]/table/tbody/tr/td[1]/table[1]/tbody/tr[8]/td[2]/strong").text),
            "uid": self.uid_from_url.match(self.driver.current_url).groups()[0]
        }

        self.driver.get(self.url)

        return data

    @requires_login
    def reputation_read(self, username=None, uid=None):
        return self._get_profile(username, uid)['reputation']           

    @requires_login
    def post_count_read(self, username=None, uid=None):
        return self._get_profile(username, uid)['post_count']

    @requires_login
    def thread_count_read(self, username=None, uid=None):
        return self._get_profile(username, uid)['thread_count']

    @requires_login
    def referral_count_read(self, username=None, uid=None):
        return self._get_profile(username, uid)['members_referred']

    @requires_login
    def signature_read(self, username=None, uid=None):
        return self._get_profile(username, uid)['signature']

    @requires_login
    def time_spent_online_read(self, username=None, uid=None):
        return self._get_profile(username, uid)['time_spent_online']

    @requires_login
    def join_date_read(self, username=None, uid=None):
        return self._get_profile(username, uid)['joined']

    @requires_login
    def last_visit_read(self, username=None, uid=None):
        return self._get_profile(username, uid)['last_visit']

    @requires_login
    def status_read(self, username=None, uid=None):
        return self._get_profile(username, uid)['status']

    @requires_login
    def username_to_uid(self, username):
        return self._get_profile(username)['uid']

    def close(self):
        # alias method for self.__del__()

        self.__del__()

    def __del__(self):
        # possibly unsafe, needs experimentation

        if not self._webdriver_closed:
            self.driver.close()
            self._webdriver_closed = True
