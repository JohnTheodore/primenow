import io
import ipdb
import re
import requests
import sys
import time
from bs4 import BeautifulSoup
from pycookiecheat import chrome_cookies
from pygame import mixer


primenow_url = 'https://primenow.amazon.com'
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) \
    Chrome/80.0.3987.149 Safari/537.36',
}


def get_primenow_cookies():
  return chrome_cookies(primenow_url)


def query_primenow(url, cookies):
  response = requests.get(url, headers=headers, cookies=cookies)
  response.raise_for_status()
  if 'Sign in' in str(response.content):
    sys.exit('Invalid authentication.')
  return response


def exit_on_empty_shopping_cart(checkout_button_html):
  if len(checkout_button_html) < 1:
    sys.exit('Shopping cart is currently empty.')


def get_checkout_html():
  primenow_cookies = get_primenow_cookies()
  shopping_cart_response = query_primenow('https://primenow.amazon.com/cart', primenow_cookies)
  primenow_cookies.update(shopping_cart_response.cookies.get_dict())
  shopping_cart_html = BeautifulSoup(shopping_cart_response.content, features='html.parser')
  checkout_button_html = shopping_cart_html.findAll('span', {'class': 'cart-checkout-button'})
  exit_on_empty_shopping_cart(checkout_button_html)
  checkout_link = checkout_button_html[0].find('a')['href']
  checkout_url = '%s%s' % (primenow_url, checkout_link)
  checkout_response = query_primenow(checkout_url, primenow_cookies)
  return BeautifulSoup(checkout_response.content, features='html.parser')


def delivery_time_availible(checkout_html):
  no_delivery_time = checkout_html.findAll(text=re.compile('No delivery windows available.'))
  if len(no_delivery_time) > 0:
    return False
  return True


def play_victory_music():
  daft_punk = requests.get('https://download.mp3-here.icu/i/Daft-Punk-End-Of-Line.mp3')
  mixer.init()
  mixer.music.load(io.BytesIO(daft_punk.content))
  mixer.music.play()


while not delivery_time_availible(get_checkout_html()):
  print('Still no delivery times available. :(')
  time.sleep(60)

play_victory_music()
ipdb.set_trace()
