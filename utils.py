import os
import sys
import pandas as pd

from datetime import datetime
from fake_headers import Headers
from time import sleep
from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

from webdriver_manager.chrome import ChromeDriverManager


#Class for the progress of the scraper instance.

class Progress:
    def __init__(self, current, total) -> None:
        self.current = current
        self.total = total
        pass

    def print_progress(self, current) -> None:
        self.current = current
        progress = current / self.total
        bar_length = 40
        progress_bar = (
            "["
            + "=" * int(bar_length * progress)
            + "-" * (bar_length - int(bar_length * progress))
            + "]"
        )
        sys.stdout.write(
            "\rProgress: [{:<40}] {:.2%} {} of {}".format(
                progress_bar, progress, current, self.total
            )
        )
        sys.stdout.flush()



#Class for the scrollbar of the web page.

class Scroller:
    def __init__(self, driver) -> None:
        self.driver = driver
        self.current_position = 0
        self.last_position = driver.execute_script("return window.pageYOffset;")
        self.scrolling = True
        self.scroll_count = 0
        pass

    def reset(self) -> None:
        self.current_position = 0
        self.last_position = self.driver.execute_script("return window.pageYOffset;")
        self.scroll_count = 0
        pass

    def scroll_to_top(self) -> None:
        self.driver.execute_script("window.scrollTo(0, 0);")
        pass

    def scroll_to_bottom(self) -> None:
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        pass

    def update_scroll_position(self) -> None:
        self.current_position = self.driver.execute_script("return window.pageYOffset;")
        pass


#Object for the tweet. Including its data.
class Tweet:
    def __init__(
        self,
        card: WebDriver,
        driver: WebDriver,
        actions: ActionChains,
        scrape_poster_details=False
    ) -> None:
        self.card = card
        self.error = False
        self.tweet = None

        try:
            self.user = card.find_element(
                "xpath", './/div[@data-testid="User-Name"]//span'
            ).text
        except NoSuchElementException:
            self.error = True
            self.user = "skip"

        try:
            self.handle = card.find_element(
                "xpath", './/span[contains(text(), "@")]'
            ).text
        except NoSuchElementException:
            self.error = True
            self.handle = "skip"

        try:
            self.date_time = card.find_element("xpath", ".//time").get_attribute(
                "datetime"
            )

            if self.date_time is not None:
                self.is_ad = False
        except NoSuchElementException:
            self.is_ad = True
            self.error = True
            self.date_time = "skip"
        
        if self.error:
            return

        try:
            card.find_element(
                "xpath", './/*[local-name()="svg" and @data-testid="icon-verified"]'
            )

            self.verified = True
        except NoSuchElementException:
            self.verified = False

        self.content = ""
        contents = card.find_elements(
            "xpath",
            '(.//div[@data-testid="tweetText"])[1]/span | (.//div[@data-testid="tweetText"])[1]/a',
        )

        for index, content in enumerate(contents):
            self.content += content.text

        try:
            self.reply_cnt = card.find_element(
                "xpath", './/div[@data-testid="reply"]//span'
            ).text
            
            if self.reply_cnt == "":
                self.reply_cnt = "0"
        except NoSuchElementException:
            self.reply_cnt = "0"

        try:
            self.retweet_cnt = card.find_element(
                "xpath", './/div[@data-testid="retweet"]//span'
            ).text
            
            if self.retweet_cnt == "":
                self.retweet_cnt = "0"
        except NoSuchElementException:
            self.retweet_cnt = "0"

        try:
            self.like_cnt = card.find_element(
                "xpath", './/div[@data-testid="like"]//span'
            ).text
            
            if self.like_cnt == "":
                self.like_cnt = "0"
        except NoSuchElementException:
            self.like_cnt = "0"

        try:
            self.analytics_cnt = card.find_element(
                "xpath", './/a[contains(@href, "/analytics")]//span'
            ).text
            
            if self.analytics_cnt == "":
                self.analytics_cnt = "0"
        except NoSuchElementException:
            self.analytics_cnt = "0"

        try:
            self.tags = card.find_elements(
                "xpath",
                './/a[contains(@href, "src=hashtag_click")]',
            )

            self.tags = [tag.text for tag in self.tags]
        except NoSuchElementException:
            self.tags = []
        
        try:
            self.mentions = card.find_elements(
                "xpath",
                '(.//div[@data-testid="tweetText"])[1]//a[contains(text(), "@")]',
            )

            self.mentions = [mention.text for mention in self.mentions]
        except NoSuchElementException:
            self.mentions = []
        
        try:
            raw_emojis = card.find_elements(
                "xpath",
                '(.//div[@data-testid="tweetText"])[1]/img[contains(@src, "emoji")]',
            )
            
            self.emojis = [emoji.get_attribute("alt").encode("unicode-escape").decode("ASCII") for emoji in raw_emojis]
        except NoSuchElementException:
            self.emojis = []
        
        try:
            self.profile_img = card.find_element(
                "xpath", './/div[@data-testid="Tweet-User-Avatar"]//img'
            ).get_attribute("src")
        except NoSuchElementException:
            self.profile_img = ""
            
        try:
            self.tweet_link = self.card.find_element(
                "xpath",
                ".//a[contains(@href, '/status/')]",
            ).get_attribute("href")
            self.tweet_id = str(self.tweet_link.split("/")[-1])
        except NoSuchElementException:
            self.tweet_link = ""
            self.tweet_id = ""
        
        self.following_cnt = "0"
        self.followers_cnt = "0"
        self.user_id = None
        
        if scrape_poster_details:
            el_name = card.find_element(
                "xpath", './/div[@data-testid="User-Name"]//span'
            )
            
            ext_hover_card = False
            ext_user_id = False
            ext_following = False
            ext_followers = False
            hover_attempt = 0
            
            while not ext_hover_card or not ext_user_id or not ext_following or not ext_followers:
                try:
                    actions.move_to_element(el_name).perform()
                    
                    hover_card = driver.find_element(
                        "xpath",
                        '//div[@data-testid="hoverCardParent"]'
                    )
                    
                    ext_hover_card = True
                    
                    while not ext_user_id:
                        try:
                            raw_user_id = hover_card.find_element(
                                "xpath",
                                '(.//div[contains(@data-testid, "-follow")]) | (.//div[contains(@data-testid, "-unfollow")])'
                            ).get_attribute("data-testid")
                            
                            if raw_user_id == "":
                                self.user_id = None
                            else:
                                self.user_id = str(raw_user_id.split("-")[0])
                            
                            ext_user_id = True
                        except NoSuchElementException:
                            continue
                        except StaleElementReferenceException:
                            self.error = True
                            return
                    
                    while not ext_following:
                        try:
                            self.following_cnt = hover_card.find_element(
                                "xpath",
                                './/a[contains(@href, "/following")]//span'
                            ).text
                            
                            if self.following_cnt == "":
                                self.following_cnt = "0"
                                
                            ext_following = True
                        except NoSuchElementException:
                            continue
                        except StaleElementReferenceException:
                            self.error = True
                            return
                    
                    while not ext_followers:
                        try:
                            self.followers_cnt = hover_card.find_element(
                                "xpath",
                                './/a[contains(@href, "/verified_followers")]//span'
                            ).text
                            
                            if self.followers_cnt == "":
                                self.followers_cnt = "0"
                            
                            ext_followers = True
                        except NoSuchElementException:
                            continue
                        except StaleElementReferenceException:
                            self.error = True
                            return
                except NoSuchElementException:
                    if hover_attempt==3:
                        self.error
                        return
                    hover_attempt+=1
                    sleep(0.5)
                    continue
                except StaleElementReferenceException:
                    self.error = True
                    return
            
            if ext_hover_card and ext_following and ext_followers:
                actions.reset_actions()
        
        self.tweet = (
            self.user,
            self.handle,
            self.date_time,
            self.verified,
            self.content,
            self.reply_cnt,
            self.retweet_cnt,
            self.like_cnt,
            self.analytics_cnt,
            self.tags,
            self.mentions,
            self.emojis,
            self.profile_img,
            self.tweet_link,
            self.tweet_id,
            self.user_id,
            self.following_cnt,
            self.followers_cnt,
        )

        pass


#Class for the Twitter Scraper.

TWITTER_LOGIN_URL = "https://twitter.com/i/flow/login"

class Twitter_Scraper:
    def __init__(
        self,
        username,
        password,
        max_tweets=50,
        scrape_username=None,
        scrape_hashtag=None,
        scrape_query=None,
        scrape_poster_details=False,
        scrape_latest=True,
        scrape_top=False,
        headless=False,
    ):
        print("Initializing Twitter Scraper...")
        self.username = username
        self.password = password
        self.interrupted = False
        self.tweet_ids = set()
        self.data = []
        self.tweet_cards = []
        self.scraper_details = {
            "type": None,
            "username": None,
            "hashtag": None,
            "query": None,
            "tab": None,
            "poster_details": False,
        }
        self.max_tweets = max_tweets
        self.progress = Progress(0, max_tweets)
        self.router = self.go_to_home
        self.driver = self._get_driver(headless)
        self.actions = ActionChains(self.driver)
        self.scroller = Scroller(self.driver)
        self._config_scraper(
            max_tweets,
            scrape_username,
            scrape_hashtag,
            scrape_query,
            scrape_latest,
            scrape_top,
            scrape_poster_details,
        )

    def _config_scraper(
        self,
        max_tweets=50,
        scrape_username=None,
        scrape_hashtag=None,
        scrape_query=None,
        scrape_latest=True,
        scrape_top=False,
        scrape_poster_details=False,
    ):
        self.tweet_ids = set()
        self.data = []
        self.tweet_cards = []
        self.max_tweets = max_tweets
        self.progress = Progress(0, max_tweets)
        self.scraper_details = {
            "type": None,
            "username": scrape_username,
            "hashtag": str(scrape_hashtag).replace("#", "")
            if scrape_hashtag is not None
            else None,
            "query": scrape_query,
            "tab": "Latest" if scrape_latest else "Top" if scrape_top else "Latest",
            "poster_details": scrape_poster_details,
        }
        self.router = self.go_to_home
        self.scroller = Scroller(self.driver)

        if scrape_username is not None:
            self.scraper_details["type"] = "Username"
            self.router = self.go_to_profile
        elif scrape_hashtag is not None:
            self.scraper_details["type"] = "Hashtag"
            self.router = self.go_to_hashtag
        elif scrape_query is not None:
            self.scraper_details["type"] = "Query"
            self.router = self.go_to_search
        else:
            self.scraper_details["type"] = "Home"
            self.router = self.go_to_home
        pass

    def _get_driver(self,headless=False):
        print("Setup WebDriver...")
        header = Headers().generate()["User-Agent"]

        browser_option = ChromeOptions()
        browser_option.add_argument("--no-sandbox")
        browser_option.add_argument("--disable-dev-shm-usage")
        browser_option.add_argument("--ignore-certificate-errors")
        browser_option.add_argument("--disable-gpu")
        browser_option.add_argument("--log-level=3")
        browser_option.add_argument("--disable-notifications")
        browser_option.add_argument("--disable-popup-blocking")
        browser_option.add_argument("--user-agent={}".format(header))


        #For Hiding Browser
        if headless:
           browser_option.add_argument("--headless")

        try:
            print("Initializing ChromeDriver...")
            driver = webdriver.Chrome(
                options=browser_option,
            )

            print("WebDriver Setup Complete")
            return driver
        except WebDriverException:
            try:
                print("Downloading ChromeDriver...")
                chromedriver_path = ChromeDriverManager().install()
                chrome_service = ChromeService(executable_path=chromedriver_path)

                print("Initializing ChromeDriver...")
                driver = webdriver.Chrome(
                    service=chrome_service,
                    options=browser_option,
                )

                print("WebDriver Setup Complete")
                return driver
            except Exception as e:
                print(f"Error setting up WebDriver: {e}")
                sys.exit(1)
        pass

    def login(self):
        print()
        print("Logging in to Twitter...")

        try:
            self.driver.maximize_window()
            self.driver.get(TWITTER_LOGIN_URL)
            sleep(3)

            self._input_username()
            self._input_unusual_activity()
            self._input_password()

            cookies = self.driver.get_cookies()

            auth_token = None

            for cookie in cookies:
                if cookie["name"] == "auth_token":
                    auth_token = cookie["value"]
                    break

            if auth_token is None:
                raise ValueError(
                    """This may be due to the following:

- Internet connection is unstable
- Username is incorrect
- Password is incorrect
"""
                )

            print()
            print("Login Successful")
            print()
        except Exception as e:
            print()
            print(f"Login Failed: {e}")
            sys.exit(1)

        pass

    def _input_username(self):
        input_attempt = 0

        while True:
            try:
                username = self.driver.find_element(
                    "xpath", "//input[@autocomplete='username']"
                )

                username.send_keys(self.username)
                username.send_keys(Keys.RETURN)
                sleep(3)
                break
            except NoSuchElementException:
                input_attempt += 1
                if input_attempt >= 3:
                    print()
                    print(
                        """There was an error inputting the username.

It may be due to the following:
- Internet connection is unstable
- Username is incorrect
- Twitter is experiencing unusual activity"""
                    )
                    self.driver.quit()
                    sys.exit(1)
                else:
                    print("Re-attempting to input username...")
                    sleep(2)

    def _input_unusual_activity(self):
        input_attempt = 0

        while True:
            try:
                unusual_activity = self.driver.find_element(
                    "xpath", "//input[@data-testid='ocfEnterTextTextInput']"
                )
                unusual_activity.send_keys(self.username)
                unusual_activity.send_keys(Keys.RETURN)
                sleep(3)
                break
            except NoSuchElementException:
                input_attempt += 1
                if input_attempt >= 3:
                    break

    def _input_password(self):
        input_attempt = 0

        while True:
            try:
                password = self.driver.find_element(
                    "xpath", "//input[@autocomplete='current-password']"
                )

                password.send_keys(self.password)
                password.send_keys(Keys.RETURN)
                sleep(3)
                break
            except NoSuchElementException:
                input_attempt += 1
                if input_attempt >= 3:
                    print()
                    print(
                        """There was an error inputting the password.

It may be due to the following:
- Internet connection is unstable
- Password is incorrect
- Twitter is experiencing unusual activity"""
                    )
                    self.driver.quit()
                    sys.exit(1)
                else:
                    print("Re-attempting to input password...")
                    sleep(2)

    def go_to_home(self):
        self.driver.get("https://twitter.com/home")
        sleep(3)
        pass

    def go_to_profile(self):
        if (
            self.scraper_details["username"] is None
            or self.scraper_details["username"] == ""
        ):
            print("Username is not set.")
            sys.exit(1)
        else:
            self.driver.get(f"https://twitter.com/{self.scraper_details['username']}")
            sleep(3)
        pass

    def go_to_hashtag(self):
        if (
            self.scraper_details["hashtag"] is None
            or self.scraper_details["hashtag"] == ""
        ):
            print("Hashtag is not set.")
            sys.exit(1)
        else:
            url = f"https://twitter.com/hashtag/{self.scraper_details['hashtag']}?src=hashtag_click"
            if self.scraper_details["tab"] == "Latest":
                url += "&f=live"

            self.driver.get(url)
            sleep(3)
        pass

    def go_to_search(self):
        if self.scraper_details["query"] is None or self.scraper_details["query"] == "":
            print("Query is not set.")
            sys.exit(1)
        else:
            url = f"https://twitter.com/search?q={self.scraper_details['query']}&src=typed_query"
            if self.scraper_details["tab"] == "Latest":
                url += "&f=live"

            self.driver.get(url)
            sleep(3)
        pass

    def get_tweet_cards(self):
        self.tweet_cards = self.driver.find_elements(
            "xpath", '//article[@data-testid="tweet" and not(@disabled)]'
        )
        pass

    def remove_hidden_cards(self):
        try:
            hidden_cards = self.driver.find_elements(
                "xpath", '//article[@data-testid="tweet" and @disabled]'
            )

            for card in hidden_cards[1:-2]:
                self.driver.execute_script(
                    "arguments[0].parentNode.parentNode.parentNode.remove();", card
                )
        except Exception as e:
            return
        pass

    def scrape_tweets(
        self,
        max_tweets=50,
        scrape_username=None,
        scrape_hashtag=None,
        scrape_query=None,
        scrape_latest=True,
        scrape_top=False,
        scrape_poster_details=False,
        router=None,
    ):
        self._config_scraper(
            max_tweets,
            scrape_username,
            scrape_hashtag,
            scrape_query,
            scrape_latest,
            scrape_top,
            scrape_poster_details,
        )

        if router is None:
            router = self.router

        router()

        if self.scraper_details["type"] == "Username":
            print(
                "Scraping Tweets from @{}...".format(self.scraper_details["username"])
            )
        elif self.scraper_details["type"] == "Hashtag":
            print(
                "Scraping {} Tweets from #{}...".format(
                    self.scraper_details["tab"], self.scraper_details["hashtag"]
                )
            )
        elif self.scraper_details["type"] == "Query":
            print(
                "Scraping {} Tweets from {} search...".format(
                    self.scraper_details["tab"], self.scraper_details["query"]
                )
            )
        elif self.scraper_details["type"] == "Home":
            print("Scraping Tweets from Home...")

        self.progress.print_progress(0)

        refresh_count = 0
        added_tweets = 0
        empty_count = 0

        while self.scroller.scrolling:
            try:
                self.get_tweet_cards()
                added_tweets = 0

                for card in self.tweet_cards[-15:]:
                    try:
                        tweet_id = str(card)

                        if tweet_id not in self.tweet_ids:
                            self.tweet_ids.add(tweet_id)

                            if not self.scraper_details["poster_details"]:
                                self.driver.execute_script(
                                    "arguments[0].scrollIntoView();", card
                                )

                            tweet = Tweet(
                                card=card,
                                driver=self.driver,
                                actions=self.actions,
                                scrape_poster_details=self.scraper_details[
                                    "poster_details"
                                ],
                            )

                            if tweet:
                                if not tweet.error and tweet.tweet is not None:
                                    if not tweet.is_ad:
                                        self.data.append(tweet.tweet)
                                        added_tweets += 1
                                        self.progress.print_progress(len(self.data))

                                        if len(self.data) >= self.max_tweets:
                                            self.scroller.scrolling = False
                                            break
                                    else:
                                        continue
                                else:
                                    continue
                            else:
                                continue
                        else:
                            continue
                    except NoSuchElementException:
                        continue

                if len(self.data) >= self.max_tweets:
                    break

                if added_tweets == 0:
                    if empty_count >= 5:
                        if refresh_count >= 3:
                            print()
                            print("No more tweets to scrape")
                            break
                        refresh_count += 1
                    empty_count += 1
                    sleep(1)
                else:
                    empty_count = 0
                    refresh_count = 0
            except StaleElementReferenceException:
                sleep(2)
                continue
            except KeyboardInterrupt:
                print("\n")
                print("Keyboard Interrupt")
                self.interrupted = True
                break
            except Exception as e:
                print("\n")
                print(f"Error scraping tweets: {e}")
                break

        print("")

        if len(self.data) >= self.max_tweets:
            print("Scraping Complete")
        else:
            print("Scraping Incomplete")

        print("Tweets: {} out of {}\n".format(len(self.data), self.max_tweets))

        pass

    def save_to_csv(self):
        print("Saving Tweets to CSV...")
        now = datetime.now()
        folder_path = "./tweets/"

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print("Created Folder: {}".format(folder_path))

        data = {
            "Name": [tweet[0] for tweet in self.data],
            "Handle": [tweet[1] for tweet in self.data],
            "Timestamp": [tweet[2] for tweet in self.data],
            "Verified": [tweet[3] for tweet in self.data],
            "Content": [tweet[4] for tweet in self.data],
            "Comments": [tweet[5] for tweet in self.data],
            "Retweets": [tweet[6] for tweet in self.data],
            "Likes": [tweet[7] for tweet in self.data],
            "Analytics": [tweet[8] for tweet in self.data],
            "Tags": [tweet[9] for tweet in self.data],
            "Mentions": [tweet[10] for tweet in self.data],
            "Emojis": [tweet[11] for tweet in self.data],
            "Profile Image": [tweet[12] for tweet in self.data],
            "Tweet Link": [tweet[13] for tweet in self.data],
            "Tweet ID": [f'tweet_id:{tweet[14]}' for tweet in self.data],
        }

        if self.scraper_details["poster_details"]:
            data["Tweeter ID"] = [f'user_id:{tweet[15]}' for tweet in self.data]
            data["Following"] = [tweet[16] for tweet in self.data]
            data["Followers"] = [tweet[17] for tweet in self.data]

        df = pd.DataFrame(data)

        current_time = now.strftime("%Y-%m-%d_%H-%M-%S")
        file_path = f"{folder_path}{current_time}_tweets_1-{len(self.data)}.csv"
        pd.set_option("display.max_colwidth", None)
        df.to_csv(file_path, index=False, encoding="utf-8")

        print("CSV Saved: {}".format(file_path))

        pass

    def get_tweets(self):
        return self.data