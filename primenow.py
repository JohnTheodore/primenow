import datetime
import io
import json
import re
import requests
import sys
import time
from bs4 import BeautifulSoup
from pycookiecheat import chrome_cookies
from pygame import mixer

headers = {
  'User-Agent':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) \
    Chrome/80.0.3987.149 Safari/537.36',
}
primenow_url = 'https://primenow.amazon.com'
refresh_cadence = 30
tip_amount = '5'
chrome_cookie_file = '~/Library/Application Support/Google/Chrome/Profile 3/Cookies'


# automatically loads the primenow.com cookies from the Chrome defaults sqlite file.
# note, this is unlikely to work when you first run the program. Some people use brave,
# some use chrome. There are different "profiles" in chrome. Easiest thing is to find your
# Cookies files, and just set a symbolic link from ~/Library/Application\ Support/Google/Chrome/Default/Cookies
def get_primenow_cookies(primenow_url, chrome_cookie_file):
  return chrome_cookies(primenow_url, chrome_cookie_file)


def query_primenow(url, cookies, method='get', data=None, params=None):
  if method == 'get':
    response = requests.get(url, headers=headers, cookies=cookies)
  elif method == 'post':
    response = requests.post(url,
                             headers=headers,
                             cookies=cookies,
                             params=params,
                             data=data)
  response.raise_for_status()
  if 'Sign in' in str(response.content):
    sys.exit('Invalid authentication.')
  return response


def exit_on_empty_shopping_cart(checkout_button_html):
  if len(checkout_button_html) < 1:
    sys.exit('Shopping cart is currently empty.')


def get_checkout_html(primenow_url, primenow_cookies):
  shopping_cart_response = query_primenow('https://primenow.amazon.com/cart',
                                          primenow_cookies)
  primenow_cookies.update(shopping_cart_response.cookies.get_dict())
  shopping_cart_html = BeautifulSoup(shopping_cart_response.content,
                                     features='html.parser')
  checkout_button_html = shopping_cart_html.findAll(
    'span', {'class': 'cart-checkout-button'})
  exit_on_empty_shopping_cart(checkout_button_html)
  checkout_link = checkout_button_html[0].find('a')['href']
  checkout_url = '%s%s' % (primenow_url, checkout_link)
  checkout_response = query_primenow(checkout_url, primenow_cookies)
  primenow_cookies.update(checkout_response.cookies.get_dict())
  return (BeautifulSoup(checkout_response.content,
                        features='html.parser'), primenow_cookies)


# pull all the delivery window json values from the html, and return the earliest
def get_earliest_delivery_window(checkout_html):
  two_hour_soup_block = checkout_html.findAll('div', {'id': 'two-hour-window'})
  if len(two_hour_soup_block) < 1:
    print('empty delivery box div again?')
    buy_primenow_groceries()
  two_hour_soup_block = two_hour_soup_block[0]
  delivery_times = two_hour_soup_block.findAll(
    'div', {'class': 'a-section a-spacing-none'})
  available_delivery_windows = []
  for delivery_time in delivery_times:
    time_slot = delivery_time.findAll(text=re.compile(' - '))[0].strip()
    delivery_key_html = delivery_time.find(
      attrs={'data-action': 'selectdeliverywindow'
            })['data-selectdeliverywindow']
    delivery_json = json.loads(delivery_key_html)
    available_delivery_windows.append({
      'time_slot': time_slot,
      'delivery_json': delivery_json
    })
  print(available_delivery_windows)
  return available_delivery_windows[0]


def set_tip_amount(checkout_html, primenow_cookies, tip_amount):
  tip_form = checkout_html.findAll('form', {'id': 'checkout-edit-tip-form'})[0]
  purchase_id = tip_form.findAll('input', {'name': 'purchase-id'})[0]['value']
  token_value = tip_form.findAll('input', {'name': 'tokenValue'})[0]['value']
  data = {
    'purchase-id': purchase_id,
    'tokenValue': token_value,
    'tokenName': 'edit-tip-checkout',
    'tip': tip_amount
  }
  params = (('purchaseId', purchase_id),)
  checkout_tip_continue_url = 'https://primenow.amazon.com/checkout/tip/continue'
  response = query_primenow(checkout_tip_continue_url,
                            primenow_cookies,
                            method='post',
                            params=params,
                            data=data)
  return response


# set the delivery window to the next available shipping time
def set_earliest_delivery_window(checkout_html, delivery_window,
                                 primenow_cookies):
  next_url = checkout_html.findAll(
    'form', {'action': re.compile('/checkout/deliveryslot/')
            })[0]['action'].split('&')[0]
  delivery_slot_form = checkout_html.findAll('form',
                                             {'name': 'deliverySlotForm'})[0]
  token_value = delivery_slot_form.findAll('input',
                                           {'name': 'tokenValue'})[0]['value']
  params = (
    ('nexturl', next_url),
    ('ref_', 'pn_co_ds_c'),
    ('fromPanel', 'delivery-slot'),
  )
  data = delivery_window['delivery_json']
  data.update({
    'tokenName': 'delivery-slot',
    'shipOptionType': 'scheduled_two_hour_delivery',
    'sameDay': '',
    'deliveryType': 'UNATTENDED'
  })
  data['tokenValue'] = token_value
  checkout_prefetch_url = 'https://primenow.amazon.com/checkout/prefetch'
  response = query_primenow(checkout_prefetch_url,
                            primenow_cookies,
                            method='post',
                            params=params,
                            data=data)
  return response


# this is the final method that basically pays primenow and ships
def purchase_and_ship_cart(set_delivery_window_response, primenow_cookies):
  params = (('ref_', 'pn_co_ot_po'),)
  data = {}
  continue_html_string = json.loads(
    set_delivery_window_response.content)['htmlResponse']
  continue_html_soup = BeautifulSoup(continue_html_string,
                                     features='html.parser')
  continue_data_html = continue_html_soup.findAll(
    'form', {'action': '/checkout/spc/continue?ref_=pn_co_ot_po'})[0]
  data_inputs = continue_data_html.findAll('input')
  for data_input in data_inputs:
    name = data_input.get('name')
    if name:
      data[name] = data_input['value']

  checkout_spc_continue_url = 'https://primenow.amazon.com/checkout/spc/continue'
  response = query_primenow(checkout_spc_continue_url,
                            primenow_cookies,
                            method='post',
                            params=params,
                            data=data)
  return response


# this runs when there is a delivery window available
# it sets the earliest delivery window, then hits continue.
# Then it runs the final purchase_and_ship_cart method.
def checkout(checkout_html, primenow_cookies):
  delivery_window = get_earliest_delivery_window(checkout_html)
  set_delivery_window_response = set_earliest_delivery_window(
    checkout_html, delivery_window, primenow_cookies)
  set_tip_amount(checkout_html, primenow_cookies, tip_amount)
  # this response returned below is a javascript payload.
  # would need to hit order status endpoint to verify order
  purchase_and_ship_cart(set_delivery_window_response, primenow_cookies)


# returns True or False, let's me know if there are delivery windows available
def is_delivery_time_available(checkout_html):
  no_delivery_time = checkout_html.findAll(
    text=re.compile('No delivery windows available.'))
  # if there are no delivery times, return False and try again
  if len(no_delivery_time) > 0:
    return False
  wants_address_selected = checkout_html.findAll(
    text=re.compile('Select Delivery Address'))
  # randomly ~1/100 times it will ask me what address to ship to.
  # ~99/100, it will use my default address. primenow.com is so inconsistent.
  if len(wants_address_selected) > 0:
    print('dumb address bug')
    return False
  return True


# good music to alert me that my order went through
def play_victory_music(mp3_url):
  song_response = requests.get(mp3_url)
  mixer.init()
  mixer.music.load(io.BytesIO(song_response.content))
  mixer.music.play()


# the main loop
def buy_primenow_groceries(primenow_url, refresh_cadence):
  while True:
    primenow_cookies = get_primenow_cookies(primenow_url, chrome_cookie_file)
    checkout_html = get_checkout_html(primenow_url, primenow_cookies)
    delivery_time_available = is_delivery_time_available(checkout_html[0])
    if delivery_time_available:
      checkout(checkout_html[0], checkout_html[1])
      play_victory_music(
        'https://download.mp3-here.icu/i/Daft-Punk-End-Of-Line.mp3')
      # sleep to let the full song play
      time.sleep(180)
      sys.exit('Finished checkout out.')
    print('%s Still no delivery times available. :(' % datetime.datetime.now())
    time.sleep(refresh_cadence)


buy_primenow_groceries(primenow_url, refresh_cadence)
